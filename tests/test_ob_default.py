from datetime import UTC, datetime, timedelta

import numpy as np
from conftest import make_df

from obbot import ob
from obbot.config import OBConfig, OBParams
from obbot.ob.default import detect
from obbot.ob.pivots import pivot_highs, pivot_lows

P = OBParams(swing_len=2, use_body=False)


def test_pivots():
    h = np.array([11, 12, 15, 14.5, 13, 12, 16], float)
    assert np.flatnonzero(pivot_highs(h, 2)).tolist() == [2]
    lo = np.array([9, 10, 11, 12, 10.5, 10.8, 11.5], float)
    assert np.flatnonzero(pivot_lows(lo, 2)).tolist() == [4]


def test_bullish_ob_formed(scenario_df):
    events = [e for e in detect(scenario_df, P) if e.kind == "ob_formed" and e.direction == "bullish"]
    assert len(events) == 1
    e = events[0]
    assert (e.zone_low, e.zone_high) == (10.5, 13.0)
    assert e.bar == 6
    assert e.ob_time == scenario_df["time"][4].to_pydatetime()
    # sinyal zamanı = kırılım mumunun kapanışı
    assert e.candle_time == scenario_df["close_time"][6].to_pydatetime()
    assert e.price == 15.5


def test_use_body_zone(scenario_df):
    e = next(e for e in detect(scenario_df, OBParams(swing_len=2, use_body=True))
             if e.direction == "bullish" and e.kind == "ob_formed")
    assert (e.zone_low, e.zone_high) == (11.0, 12.5)


def test_retest_then_mitigation_and_bearish(scenario_df):
    events = detect(scenario_df, P)
    kinds = [(e.kind, e.direction, e.bar) for e in events]
    assert ("ob_retest", "bullish", 7) in kinds
    # mitigasyondan sonra o bölge için başka retest yok
    assert sum(1 for k in kinds if k[0] == "ob_retest" and k[1] == "bullish") == 1
    bear = next(e for e in events if e.kind == "ob_formed" and e.direction == "bearish")
    assert bear.bar == 8 and (bear.zone_low, bear.zone_high) == (11.5, 16.0)


def test_config_filters(scenario_df):
    cfg = OBConfig(direction="bullish", events=["ob_formed"], params=P)
    assert [(e.kind, e.direction) for e in ob.detect(scenario_df, cfg)] == [("ob_formed", "bullish")]
    cfg = OBConfig(direction="both", events=["ob_formed", "ob_retest"], params=P)
    assert len(ob.detect(scenario_df, cfg)) == 3


def test_too_short_returns_empty():
    df = make_df([(1, 2, 0.5, 1.5)] * 3, datetime(2026, 1, 1, tzinfo=UTC))
    assert detect(df, OBParams(swing_len=5)) == []


def test_no_repaint_random_walk():
    """Geçmiş barlarda bulunan olaylar, sonradan gelen veriyle değişmemeli."""
    rng = np.random.default_rng(42)
    closes = 100 + np.cumsum(rng.normal(0, 1, 400))
    bars = []
    prev = 100.0
    for c in closes:
        o = prev
        h = max(o, c) + abs(rng.normal(0, 0.5))
        lo = min(o, c) - abs(rng.normal(0, 0.5))
        bars.append((o, h, lo, c))
        prev = c
    full = make_df(bars, datetime(2026, 1, 1, tzinfo=UTC))
    params = OBParams(swing_len=5)
    all_events = detect(full, params)
    assert all_events, "rastgele veride en az bir OB beklenir"
    for k in (150, 250, 399):
        part = detect(full.iloc[:k].reset_index(drop=True), params)
        assert part == [e for e in all_events if e.bar < k]


def test_closed_frame_drops_open_candle():
    from obbot.markets.ohlcv import to_closed_frame

    t0 = datetime(2026, 1, 1, 12, 0, tzinfo=UTC)
    ms = int(t0.timestamp() * 1000)
    raw = [[ms + i * 900_000, 1, 2, 0.5, 1.5, 1] for i in range(4)]
    now = t0 + timedelta(minutes=50)  # 4. mum (12:45) henüz açık
    df = to_closed_frame(raw, "15m", now=now)
    assert len(df) == 3
    assert df["close_time"].iloc[-1].to_pydatetime() == t0 + timedelta(minutes=45)
