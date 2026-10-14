from __future__ import annotations

from datetime import UTC, datetime, timedelta
from zoneinfo import ZoneInfo

from loguru import logger

from obbot import ob
from obbot.config import Config
from obbot.db import DB
from obbot.markets.ohlcv import TF_MINUTES, fetch_closed_ohlcv
from obbot.models import OBSignal
from obbot.notify.base import NotifyHub, merge_signals
from obbot.state import AppState
from obbot.watchlist import market_from_row

FAILURES_BEFORE_ALERT = 3


def scan(
    cfg: Config,
    db: DB,
    hub: NotifyHub,
    state: AppState,
    timeframes: list[str],
    session: datetime,
    now: datetime | None = None,
) -> list[OBSignal]:
    """İzleme listesindeki coinleri verilen zaman dilimlerinde tarar, yeni sinyalleri bildirir.

    `session`: aktif pencerenin başlangıcı (yerel). Bundan önce kapanmış mumlardaki OB'ler
    bildirilmez. `max_signal_age_bars` mumdan eski OB'ler de atlanır; böylece listeye gün
    içinde yeni giren bir coinin saatler önceki OB'si bildirilmez.
    """
    started = datetime.now(UTC)
    now = now or started
    tz = ZoneInfo(cfg.timezone)
    hub.flush()

    rows = db.get_watchlist(session.date())
    markets = [m for m in (market_from_row(r) for r in rows) if m]
    session_utc = session.astimezone(UTC)
    limit = max(cfg.min_bars + 50, 300)

    new: list[OBSignal] = []
    errors: list[str] = []
    for m in markets:
        for tf in timeframes:
            cutoff = session_utc
            if cfg.max_signal_age_bars:
                age = timedelta(minutes=TF_MINUTES[tf] * cfg.max_signal_age_bars)
                cutoff = max(cutoff, now.astimezone(UTC) - age)
            try:
                df = fetch_closed_ohlcv(m, tf, limit=limit, now=now)
                if len(df) < cfg.min_bars:
                    key = f"{session.date()}|minbars|{m.tv_symbol}|{tf}"
                    if key not in state.warned:
                        state.warned.add(key)
                        hub.send_text(f"ℹ️ {m.ccxt_symbol} ({tf}): yeterli geçmiş yok "
                                      f"({len(df)} < {cfg.min_bars} mum), atlandı.")
                    continue
                for e in ob.detect(df, cfg.ob):
                    if e.candle_time < cutoff:
                        continue
                    s = OBSignal(m, tf, e.kind, e.direction, e.zone_low, e.zone_high,
                                 e.candle_time, e.price)
                    if not db.is_sent(s.key):
                        new.append(s)
            except Exception as ex:  # bir coin diğerlerini durdurmaz
                logger.exception("{} {} taranamadı", m.tv_symbol, tf)
                errors.append(f"{m.tv_symbol} {tf}: {type(ex).__name__}: {ex}")

    for title, text in merge_signals(new, tz):
        logger.info("Sinyal: {}", text.splitlines()[0])
        hub.send_text(text, title)
    for s in new:
        db.mark_sent(s)

    finished = datetime.now(UTC)
    db.log_run(started, finished, len(markets), len(new), "\n".join(errors))
    state.last_scan_at = finished
    state.last_scan_errors = len(errors)

    if errors:
        state.consecutive_failures += 1
        if state.consecutive_failures >= FAILURES_BEFORE_ALERT and not state.failure_alert_sent:
            state.failure_alert_sent = True
            hub.send_text(f"⚠️ Art arda {state.consecutive_failures} taramada hata var. "
                          f"Son hata: {errors[-1]}", "Tarama hatası")
    else:
        state.consecutive_failures = 0
        state.failure_alert_sent = False

    logger.info("Tarama bitti: {} coin, {} TF, {} yeni sinyal, {} hata",
                len(markets), ",".join(timeframes), len(new), len(errors))
    return new
