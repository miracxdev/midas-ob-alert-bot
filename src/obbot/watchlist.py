"""Günlük izleme listesi: kaynaktan liste al → normalize et → pariteleri eşle → DB'ye yaz."""

from __future__ import annotations

from datetime import date

from loguru import logger

from obbot.config import Config
from obbot.db import DB
from obbot.markets.resolver import resolve
from obbot.models import Market
from obbot.notify.base import NotifyHub
from obbot.sources.base import GainersSource, normalize
from obbot.sources.file import FileSource
from obbot.sources.midas_web import MidasWebSource

MANUAL = "manual"


def build_sources(cfg: Config) -> list[GainersSource]:
    w = cfg.watchlist
    out: list[GainersSource] = []
    for name in w.sources:
        if name == "midas_web":
            out.append(MidasWebSource(w.midas_url, w.top_n, w.max_change_pct))
        elif name == "file":
            out.append(FileSource(top_n=w.top_n))
        # "manual" kaynağı Telegram /liste komutuyla DB'ye doğrudan yazılır
    return out


def market_from_row(row) -> Market | None:
    if not row["tv_symbol"]:
        return None
    pair = row["tv_symbol"].split(":", 1)[1]
    return Market(row["base"], pair[len(row["base"]):], row["exchange"])


def format_watchlist(day: date, rows) -> str:
    if not rows:
        return f"{day:%d.%m.%Y} için izleme listesi boş."
    lines = [f"📋 {day:%d.%m.%Y} izleme listesi ({rows[0]['source']}):"]
    for i, r in enumerate(rows, 1):
        lines.append(f"{i}. {r['base']} → {r['tv_symbol'] or '❌ parite bulunamadı'}")
    return "\n".join(lines)


def save_list(day: date, bases: list[str], source: str, cfg: Config, db: DB) -> list[str]:
    """Pariteleri eşler ve listeyi kaydeder; bulunamayan sembolleri döndürür."""
    res = resolve(bases, cfg)
    db.set_watchlist(day, bases, source, res.markets)
    return res.not_found


def format_changes(day: date, added: list[str], removed: list[str], rows) -> str:
    lines = ["🔄 Midas listesi güncellendi"]
    by_base = {r["base"]: r for r in rows}
    if added:
        lines.append("➕ Eklenen: " + ", ".join(
            f"{b} ({by_base[b]['tv_symbol'] or '❌ parite yok'})" for b in added))
    if removed:
        lines.append("➖ Çıkan: " + ", ".join(removed))
    return "\n".join(lines) + "\n\n" + format_watchlist(day, rows)


def refresh_watchlist(cfg: Config, db: DB, hub: NotifyHub, day: date, force: bool = False) -> bool:
    """Günün listesini yeniler. Elle girilmiş liste varsa (force değilse) korunur.

    Günün ilk alımında (veya force ile) tüm liste gönderilir. Saatlik yenilemelerde yalnızca
    liste değiştiyse eklenen/çıkan coinler bildirilir; kaynak geçici olarak alınamazsa mevcut
    liste sessizce korunur.
    """
    existing = db.get_watchlist(day)
    if existing and existing[0]["source"] == MANUAL and not force:
        logger.info("Bugün için elle girilmiş liste var, yenileme atlandı")
        return True
    old = [r["base"] for r in existing]

    for src in build_sources(cfg):
        try:
            bases = normalize(src.fetch())[: cfg.watchlist.top_n]
        except Exception as e:
            logger.warning("{} kaynağı başarısız: {}", src.name, e)
            continue
        if not bases:
            continue
        added = [b for b in bases if b not in old]
        removed = [b for b in old if b not in bases]
        if old and not force and not added and not removed:
            logger.info("Liste değişmedi ({} coin)", len(bases))
            return True
        save_list(day, bases, src.name, cfg, db)
        rows = db.get_watchlist(day)
        if old and not force:
            logger.info("Liste güncellendi: +{} -{}", added, removed)
            hub.send_text(format_changes(day, added, removed, rows), "Liste güncellendi")
        else:
            hub.send_text(format_watchlist(day, rows), "İzleme listesi")
        return True

    if old and not force:
        logger.warning("Liste yenilenemedi, mevcut liste korunuyor")
        return True
    logger.error("Hiçbir kaynaktan liste alınamadı")
    hub.send_text(
        "⚠️ Bugünün Midas listesi alınamadı. /liste XYZ ABC ... ile elle girebilirsin.",
        "Liste alınamadı",
    )
    return False
