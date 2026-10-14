import pytest

from obbot.config import Config
from obbot.markets import resolver

FAKE = {
    "binance": {"BTC/USDT": {"spot": True, "active": True},
                "OLD/USDT": {"spot": True, "active": False}},
    "okx": {"PEPE/USDT": {"spot": True, "active": True},
            "OLD/USDT": {"spot": True, "active": True}},
    "bybit": {"USDONLY/USD": {"spot": True, "active": True}},
}


@pytest.fixture(autouse=True)
def fake_markets(monkeypatch):
    def load(ex, today=None):
        if ex == "gate":
            raise ConnectionError("erişilemiyor")
        return FAKE.get(ex, {})

    monkeypatch.setattr(resolver, "load_markets", load)


def test_priority_and_fallbacks():
    cfg = Config(exchanges=["binance", "gate", "okx", "bybit"])
    unavailable: set[str] = set()
    res = resolver.resolve(["BTC", "PEPE", "OLD", "USDONLY", "NOPE"], cfg, unavailable)
    assert res.markets["BTC"].tv_symbol == "BINANCE:BTCUSDT"
    assert res.markets["PEPE"].tv_symbol == "OKX:PEPEUSDT"
    # Binance'te pasif → OKX'e düşer
    assert res.markets["OLD"].exchange == "okx"
    assert res.markets["USDONLY"].tv_symbol == "BYBIT:USDONLYUSD"
    assert res.not_found == ["NOPE"]
    assert unavailable == {"gate"}


def test_normalize():
    from obbot.sources.base import normalize

    aliases = {"1000PEPE": "PEPE"}
    assert normalize(["btc", "ETHTRY", "sol/usdt", "1000PEPE", "BTC", "FDUSD", " w "], aliases) == [
        "BTC", "ETH", "SOL", "PEPE", "FDUSD", "W"
    ]
