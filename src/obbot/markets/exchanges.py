from __future__ import annotations

import time
from collections.abc import Callable
from datetime import date
from typing import Any, TypeVar

import ccxt
from loguru import logger

T = TypeVar("T")

_clients: dict[str, ccxt.Exchange] = {}
_markets_loaded_on: dict[str, date] = {}


def get_client(exchange_id: str) -> ccxt.Exchange:
    """Spot-only, public ccxt istemcisi (API key yok)."""
    if exchange_id not in _clients:
        cls = getattr(ccxt, exchange_id)
        _clients[exchange_id] = cls(
            {
                "enableRateLimit": True,
                "timeout": 20000,
                "options": {"defaultType": "spot", "fetchMarkets": {"types": ["spot"]}},
            }
        )
    return _clients[exchange_id]


def with_retry(fn: Callable[[], T], what: str, attempts: int = 3, base_delay: float = 1.0) -> T:
    """Ağ/borsa hatalarında üstel beklemeyle tekrar dener."""
    for i in range(attempts):
        try:
            return fn()
        except (ccxt.NetworkError, ccxt.ExchangeNotAvailable, ccxt.RequestTimeout) as e:
            if i == attempts - 1:
                raise
            delay = base_delay * 2**i
            logger.warning("{} başarısız ({}), {:.0f} sn sonra tekrar", what, type(e).__name__, delay)
            time.sleep(delay)
    raise AssertionError("unreachable")


def load_markets(exchange_id: str, today: date | None = None) -> dict[str, Any]:
    """Market listesini günde bir kez yükler."""
    today = today or date.today()
    client = get_client(exchange_id)
    if _markets_loaded_on.get(exchange_id) != today or not client.markets:
        with_retry(lambda: client.load_markets(reload=True), f"{exchange_id} load_markets")
        _markets_loaded_on[exchange_id] = today
    return client.markets
