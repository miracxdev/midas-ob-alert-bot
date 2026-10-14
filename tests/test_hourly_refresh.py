"""Saatlik liste yenileme ve eski sinyal filtresi."""

from datetime import UTC, date, datetime
from zoneinfo import ZoneInfo

from conftest import SCENARIO, make_df
from freezegun import freeze_time

from obbot import scanner, watchlist
from obbot.config import Config, OBConfig, OBParams
from obbot.db import DB
from obbot.markets.resolver import ResolveResult
from obbot.models import Market
from obbot.notify.base import NotifyHub
from obbot.scheduler import Bot
from obbot.state import AppState

IST = ZoneInfo("Europe/Istanbul")
DAY = date(2026, 10, 12)


class FakeNotifier:
    name = "fake"

    def __init__(self):
        self.sent: list[tuple[str, str]] = []

    def send_text(self, text, title="OB Bot"):
        self.sent.append((title, text))


class FakeSource:
    name = "midas_web"

    def __init__(self):
        self.bases: list[str] | Exception = []

    def fetch(self):
        if isinstance(self.bases, Exception):
            raise self.bases
        return self.bases


def make_bot(monkeypatch, cfg: Config | None = None):
    cfg = cfg or Config()
    src = FakeSource()
    monkeypatch.setattr(watchlist, "build_sources", lambda cfg: [src])
    monkeypatch.setattr(
        watchlist, "resolve",
        lambda bases, cfg: ResolveResult({b: Market(b, "USDT", "binance") for b in bases}, []),
    )
    notifier = FakeNotifier()
    bot = Bot(cfg, DB(":memory:"), NotifyHub([notifier]), AppState())
    return bot, src, notifier


def test_first_refresh_sends_full_list_then_only_changes(monkeypatch):
    bot, src, notifier = make_bot(monkeypatch)
    src.bases = ["AAA", "BBB", "CCC"]
    with freeze_time(datetime(2026, 10, 12, 16, 25, tzinfo=IST)):
        bot.refresh()
    assert [t for t, _ in notifier.sent] == ["İzleme listesi"]

    # aynı liste (sıra farklı) → mesaj yok
    src.bases = ["CCC", "AAA", "BBB"]
    with freeze_time(datetime(2026, 10, 12, 17, 25, tzinfo=IST)):
        bot.hourly_refresh()
    assert len(notifier.sent) == 1

    # değişti → eklenen/çıkan bildirilir, DB güncellenir
    src.bases = ["AAA", "DDD", "CCC"]
    with freeze_time(datetime(2026, 10, 12, 18, 25, tzinfo=IST)):
        bot.hourly_refresh()
    title, text = notifier.sent[-1]
    assert title == "Liste güncellendi"
    assert "➕ Eklenen: DDD (BINANCE:DDDUSDT)" in text
    assert "➖ Çıkan: BBB" in text
    assert [r["base"] for r in bot.db.get_watchlist(DAY)] == ["AAA", "DDD", "CCC"]


def test_hourly_refresh_failure_keeps_list_silently(monkeypatch):
    bot, src, notifier = make_bot(monkeypatch)
    src.bases = ["AAA"]
    with freeze_time(datetime(2026, 10, 12, 16, 25, tzinfo=IST)):
        bot.refresh()
    src.bases = ConnectionError("midas yok")
    with freeze_time(datetime(2026, 10, 12, 17, 25, tzinfo=IST)):
        bot.hourly_refresh()
    assert len(notifier.sent) == 1
    assert [r["base"] for r in bot.db.get_watchlist(DAY)] == ["AAA"]


def test_hourly_refresh_keeps_manual_list_and_skips_outside_window(monkeypatch):
    bot, src, notifier = make_bot(monkeypatch)
    src.bases = ["AAA"]
    with freeze_time(datetime(2026, 10, 12, 15, 25, tzinfo=IST)):  # pencere dışı
        bot.hourly_refresh()
    assert bot.db.get_watchlist(DAY) == []

    bot.db.set_watchlist(DAY, ["MAN"], watchlist.MANUAL)
    with freeze_time(datetime(2026, 10, 12, 17, 25, tzinfo=IST)):
        bot.hourly_refresh()
    assert [r["base"] for r in bot.db.get_watchlist(DAY)] == ["MAN"]
    assert notifier.sent == []


def test_old_ob_of_newly_added_coin_not_notified(monkeypatch):
    # BOS barı 19:15 İST'de kapanır; coin listeye 20:25'te girer → 1 saatlik OB bildirilmez
    cfg = Config(min_bars=5, ob=OBConfig(params=OBParams(swing_len=2)), timeframes=["15m"])
    bot, _, notifier = make_bot(monkeypatch, cfg)
    bot.db.set_watchlist(DAY, ["XYZ"], "midas_web", {"XYZ": Market("XYZ", "USDT", "binance")})
    df = make_df(SCENARIO, datetime(2026, 10, 12, 14, 30, tzinfo=UTC))
    monkeypatch.setattr(scanner, "fetch_closed_ohlcv", lambda m, tf, limit, now: df)
    with freeze_time(datetime(2026, 10, 12, 20, 30, 10, tzinfo=IST)):
        bot.tick()
    assert notifier.sent == []

    # aynı OB taze iken (3 mum içinde) bildirilir
    with freeze_time(datetime(2026, 10, 12, 19, 45, 10, tzinfo=IST)):
        bot.tick()
    assert len(notifier.sent) == 1
