from datetime import UTC, date, datetime

from obbot.config import load_config
from obbot.db import DB
from obbot.models import Market, OBSignal


def test_config_loads():
    cfg = load_config()
    assert cfg.timezone == "Europe/Istanbul"
    assert cfg.scan_window.start.strftime("%H:%M") == "16:30"
    assert cfg.watchlist.top_n == 20


def test_market_tv_symbol():
    m = Market("PEPE", "USDT", "gate")
    assert m.ccxt_symbol == "PEPE/USDT"
    assert m.tv_symbol == "GATEIO:PEPEUSDT"
    assert m.tv_url.endswith("symbol=GATEIO:PEPEUSDT")


def test_db_dedup_and_watchlist():
    db = DB(":memory:")
    m = Market("BTC", "USDT", "binance")
    s = OBSignal(m, "15m", "ob_formed", "bullish", 1.0, 2.0, datetime(2026, 1, 1, tzinfo=UTC), 2.5)
    assert db.mark_sent(s) is True
    assert db.mark_sent(s) is False
    assert db.is_sent(s.key)

    db.set_watchlist(date(2026, 1, 1), ["BTC", "XYZ"], "midas_web", {"BTC": m})
    rows = db.get_watchlist(date(2026, 1, 1))
    assert [r["base"] for r in rows] == ["BTC", "XYZ"]
    assert rows[0]["tv_symbol"] == "BINANCE:BTCUSDT" and rows[1]["tv_symbol"] is None
