"""Saati taklit eden entegrasyon testi: aynı OB yalnızca bir kez bildirilir."""

from datetime import UTC, date, datetime
from zoneinfo import ZoneInfo

import pytest
from conftest import SCENARIO, make_df
from freezegun import freeze_time

from obbot import scanner
from obbot.config import Config, OBConfig, OBParams
from obbot.db import DB
from obbot.models import Market
from obbot.notify.base import NotifyHub, fmt_price, merge_signals
from obbot.scheduler import Bot
from obbot.state import AppState

IST = ZoneInfo("Europe/Istanbul")


class FakeNotifier:
    name = "fake"

    def __init__(self, fail_times: int = 0):
        self.sent: list[tuple[str, str]] = []
        self.fail_times = fail_times

    def send_text(self, text, title="OB Bot"):
        if self.fail_times:
            self.fail_times -= 1
            raise ConnectionError("ağ yok")
        self.sent.append((title, text))


def setup(monkeypatch, start_utc: datetime, fail_times: int = 0):
    cfg = Config(min_bars=5, ob=OBConfig(params=OBParams(swing_len=2)), timeframes=["15m"])
    db = DB(":memory:")
    db.set_watchlist(date(2026, 10, 12), ["XYZ"], "midas_web", {"XYZ": Market("XYZ", "USDT", "binance")})
    df = make_df(SCENARIO, start_utc)
    calls = []

    def fake_fetch(m, tf, limit, now):
        calls.append((m.tv_symbol, tf))
        return df

    monkeypatch.setattr(scanner, "fetch_closed_ohlcv", fake_fetch)
    notifier = FakeNotifier(fail_times)
    bot = Bot(cfg, db, NotifyHub([notifier]), AppState())
    return bot, notifier, df, calls


def test_single_notification_across_ticks(monkeypatch):
    # Senaryo 14:30 UTC'de başlar; BOS barının (6) kapanışı 16:15 UTC = 19:15 İST → pencere içinde
    bot, notifier, _, calls = setup(monkeypatch, datetime(2026, 10, 12, 14, 30, tzinfo=UTC))
    with freeze_time(datetime(2026, 10, 12, 19, 30, 10, tzinfo=IST)):
        bot.tick()
    with freeze_time(datetime(2026, 10, 12, 19, 45, 10, tzinfo=IST)):
        bot.tick()
    assert len(calls) == 2
    signals = [t for _, t in notifier.sent]
    assert len(signals) == 1
    assert "🟢 BULLISH OB — XYZ/USDT (15m)" in signals[0]
    assert "Mum: 19:15 (İST)" in signals[0]
    assert "BINANCE:XYZUSDT&interval=15" in signals[0]


def test_no_scan_outside_window_or_off_tick(monkeypatch):
    bot, notifier, _, calls = setup(monkeypatch, datetime(2026, 10, 12, 14, 30, tzinfo=UTC))
    with freeze_time(datetime(2026, 10, 12, 16, 15, 10, tzinfo=IST)):  # pencere öncesi
        bot.tick()
    with freeze_time(datetime(2026, 10, 12, 19, 31, 10, tzinfo=IST)):  # mum kapanışı değil
        bot.tick()
    bot.state.paused = True
    with freeze_time(datetime(2026, 10, 12, 19, 45, 10, tzinfo=IST)):
        bot.tick()
    assert calls == [] and notifier.sent == []


def test_ob_before_window_not_notified(monkeypatch):
    # BOS barı 13:15 İST'de kapanır (pencereden önce) → bildirilmez
    bot, notifier, _, calls = setup(monkeypatch, datetime(2026, 10, 12, 8, 30, tzinfo=UTC))
    with freeze_time(datetime(2026, 10, 12, 16, 30, 10, tzinfo=IST)):
        bot.tick()
    assert len(calls) == 1 and notifier.sent == []


def test_failed_send_is_retried(monkeypatch):
    bot, notifier, _, _ = setup(monkeypatch, datetime(2026, 10, 12, 14, 30, tzinfo=UTC), fail_times=1)
    with freeze_time(datetime(2026, 10, 12, 19, 30, 10, tzinfo=IST)):
        bot.tick()
    assert notifier.sent == []
    with freeze_time(datetime(2026, 10, 12, 19, 45, 10, tzinfo=IST)):
        bot.tick()
    assert len(notifier.sent) == 1  # kuyruktan gönderildi, tekrar üretilmedi


def test_merge_and_price_format():
    from obbot.models import OBSignal

    m = Market("PEPE", "USDT", "binance")
    t = datetime(2026, 10, 12, 15, 0, tzinfo=UTC)
    a = OBSignal(m, "15m", "ob_formed", "bullish", 0.00000419, 0.00000423, t, 0.00000427)
    b = OBSignal(m, "1h", "ob_formed", "bullish", 0.0000041, 0.0000043, t, 0.00000427)
    out = merge_signals([a, b], IST)
    assert len(out) == 1 and out[0][0] == "2 sinyal — PEPE/USDT"
    assert fmt_price(0.4123) == "0.4123"
    assert fmt_price(65012.5) == "65012.50"
    assert fmt_price(0.00001234) == "0.00001234"


@pytest.mark.parametrize("n", [3])
def test_failure_alert_after_consecutive_errors(monkeypatch, n):
    bot, notifier, _, _ = setup(monkeypatch, datetime(2026, 10, 12, 14, 30, tzinfo=UTC))

    def boom(*a, **k):
        raise ConnectionError("borsa yok")

    monkeypatch.setattr(scanner, "fetch_closed_ohlcv", boom)
    for i in range(n + 1):
        with freeze_time(datetime(2026, 10, 12, 17, 0 + 15 * i, 10, tzinfo=IST)):
            bot.tick()
    alerts = [t for title, t in notifier.sent if title == "Tarama hatası"]
    assert len(alerts) == 1
