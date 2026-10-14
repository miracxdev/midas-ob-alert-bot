from __future__ import annotations

from datetime import UTC, datetime

import pandas as pd
import pytest

from obbot.markets.ohlcv import to_closed_frame


def make_df(bars: list[tuple[float, float, float, float]], start: datetime, tf: str = "15m") -> pd.DataFrame:
    """(open, high, low, close) listesinden kapanmış mum DataFrame'i üretir."""
    step = {"15m": 15, "1h": 60}[tf] * 60_000
    t0 = int(start.timestamp() * 1000)
    raw = [[t0 + i * step, o, h, lo, c, 1.0] for i, (o, h, lo, c) in enumerate(bars)]
    return to_closed_frame(raw, tf, now=datetime(2100, 1, 1, tzinfo=UTC))


# Elle kurulmuş senaryo (swing_len=2):
#  bar 2 swing high (15) → bar 6 üstünde kapanış (BOS↑) → bullish OB = bar 4 [10.5, 13]
#  bar 7 bölgeye geri girer (retest), bar 8 bölgenin altında kapanır (mitigasyon)
#  bar 8 ayrıca bar 4 swing low'unu (10.5) kırar → bearish OB = bar 6 [11.5, 16]
SCENARIO = [
    (10.0, 11.0, 9.0, 10.5),
    (10.5, 12.0, 10.0, 11.5),
    (11.5, 15.0, 11.0, 14.0),
    (14.0, 14.5, 12.0, 12.5),
    (12.5, 13.0, 10.5, 11.0),
    (11.0, 12.0, 10.8, 11.8),
    (11.8, 16.0, 11.5, 15.5),
    (15.5, 15.6, 12.8, 13.5),
    (13.5, 13.6, 9.5, 10.0),
]


@pytest.fixture
def scenario_df() -> pd.DataFrame:
    return make_df(SCENARIO, datetime(2026, 1, 1, 13, 0, tzinfo=UTC))
