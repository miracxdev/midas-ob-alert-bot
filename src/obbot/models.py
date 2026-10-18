from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Literal

from obbot.config import OBParams

__all__ = ["TV_PREFIX", "Market", "OBParams", "OBSignal"]

TV_PREFIX = {
    "binance": "BINANCE",
    "okx": "OKX",
    "bybit": "BYBIT",
    "gate": "GATEIO",
    "kucoin": "KUCOIN",
    "mexc": "MEXC",
}


@dataclass(frozen=True)
class Market:
    base: str  # "XYZ"
    quote: str  # "USDT" | "USD"
    exchange: str  # "binance"

    @property
    def ccxt_symbol(self) -> str:
        return f"{self.base}/{self.quote}"

    @property
    def tv_symbol(self) -> str:
        return f"{TV_PREFIX.get(self.exchange, self.exchange.upper())}:{self.base}{self.quote}"

    @property
    def tv_url(self) -> str:
        return f"https://www.tradingview.com/chart/?symbol={self.tv_symbol}"


@dataclass(frozen=True)
class OBSignal:
    market: Market
    timeframe: str
    kind: Literal["ob_formed", "ob_retest", "cisd"]
    direction: Literal["bullish", "bearish"]
    zone_low: float
    zone_high: float
    candle_time: datetime  # OB'yi doğuran mumun kapanışı (UTC)
    price: float  # son kapanış

    @property
    def key(self) -> str:
        return (
            f"{self.market.tv_symbol}|{self.timeframe}|{self.kind}|"
            f"{self.direction}|{self.candle_time.isoformat()}"
        )
