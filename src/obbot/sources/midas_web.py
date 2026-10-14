from __future__ import annotations

import html
import re
from dataclasses import dataclass

import httpx
from loguru import logger

USER_AGENT = (
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/129.0 Safari/537.36"
)

_ROW = re.compile(r'<tr class="table-row".*?</tr>', re.DOTALL)
_SYMBOL = re.compile(r'<span class="info">\s*([^<\s]+)')
_CHANGE = re.compile(r"dailyChangePercent[^>]*>\s*([-+]?[0-9.,]+)\s*%")


@dataclass(frozen=True)
class Gainer:
    symbol: str
    change_pct: float


def parse_tr_number(s: str) -> float:
    """'3.268,75' → 3268.75"""
    return float(s.replace(".", "").replace(",", "."))


def parse_gainers(page: str) -> list[Gainer]:
    out: list[Gainer] = []
    seen: set[str] = set()
    for row in _ROW.findall(page):
        sym, ch = _SYMBOL.search(row), _CHANGE.search(row)
        if not (sym and ch):
            continue
        symbol = html.unescape(sym.group(1)).strip().upper()
        if symbol in seen:
            continue
        seen.add(symbol)
        out.append(Gainer(symbol, parse_tr_number(ch.group(1))))
    return out


class MidasWebSource:
    """Midas 'En Çok Artan' herkese açık sayfası (giriş gerekmez)."""

    name = "midas_web"

    def __init__(self, url: str, top_n: int, max_change_pct: float | None = None):
        self.url = url
        self.top_n = top_n
        self.max_change_pct = max_change_pct

    def fetch(self) -> list[str]:
        r = httpx.get(self.url, headers={"User-Agent": USER_AGENT}, timeout=20, follow_redirects=True)
        r.raise_for_status()
        gainers = parse_gainers(r.text)
        if not gainers:
            raise RuntimeError("Midas sayfasında coin tablosu bulunamadı (sayfa yapısı değişmiş olabilir)")
        # Sayfa zaten sıralı geliyor; yine de garanti altına al
        gainers.sort(key=lambda g: g.change_pct, reverse=True)
        if self.max_change_pct is not None:
            skipped = [g for g in gainers if g.change_pct > self.max_change_pct]
            for g in skipped[: self.top_n]:
                logger.info("{} atlandı: %{:.2f} > max_change_pct", g.symbol, g.change_pct)
            gainers = [g for g in gainers if g.change_pct <= self.max_change_pct]
        top = gainers[: self.top_n]
        logger.info("Midas En Çok Artan: {}", ", ".join(f"{g.symbol} %{g.change_pct:.2f}" for g in top))
        return [g.symbol for g in top]
