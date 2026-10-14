from __future__ import annotations

from datetime import UTC, datetime

import pandas as pd

from obbot.markets.exchanges import get_client, with_retry
from obbot.models import Market

TF_MINUTES = {"1m": 1, "3m": 3, "5m": 5, "15m": 15, "30m": 30, "1h": 60, "2h": 120, "4h": 240, "1d": 1440}


def tf_ms(timeframe: str) -> int:
    return TF_MINUTES[timeframe] * 60_000


def fetch_closed_ohlcv(
    market: Market, timeframe: str, limit: int = 500, now: datetime | None = None
) -> pd.DataFrame:
    """Kapanmış mumları döndürür.

    Kolonlar: time (mum açılışı, UTC), close_time (UTC), open, high, low, close, volume.
    """
    client = get_client(market.exchange)
    raw = with_retry(
        lambda: client.fetch_ohlcv(market.ccxt_symbol, timeframe, limit=limit),
        f"{market.exchange} {market.ccxt_symbol} {timeframe} OHLCV",
    )
    return to_closed_frame(raw, timeframe, now)


def to_closed_frame(raw: list[list], timeframe: str, now: datetime | None = None) -> pd.DataFrame:
    df = pd.DataFrame(raw, columns=["ts", "open", "high", "low", "close", "volume"])
    if df.empty:
        return df.assign(time=pd.Series(dtype="datetime64[ns, UTC]"))
    df = df.drop_duplicates("ts").sort_values("ts")
    now_ms = int((now or datetime.now(UTC)).timestamp() * 1000)
    # Açık (henüz kapanmamış) mumu at
    df = df[df["ts"] + tf_ms(timeframe) <= now_ms]
    df["time"] = pd.to_datetime(df["ts"], unit="ms", utc=True)
    df["close_time"] = pd.to_datetime(df["ts"] + tf_ms(timeframe), unit="ms", utc=True)
    return df[["time", "close_time", "open", "high", "low", "close", "volume"]].reset_index(drop=True)
