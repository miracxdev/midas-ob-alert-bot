from datetime import UTC, datetime

from conftest import make_df

from obbot import ob
from obbot.config import OBConfig, OBParams
from obbot.ob.custom import detect

# Elle kurulmuş senaryo (swing_len=3):
#  bar 5'te bar 2 swing low (9) onaylanır, bar 9'da bar 6 swing high (14) onaylanır
#  bar 11 14'ün üstünde kapanır → bullish OB (bar 7–10 arası en düşük min)
#  bar 12 bölgeye girer (retest), bar 13 gövdesi bölgenin altına iner (breaker)
#  bar 12'de bar 9 swing low (11) onaylanır, bar 14 altında kapanır → bearish OB
SCENARIO = [
    (12.0, 12.5, 11.0, 11.5),
    (11.5, 12.0, 10.0, 10.5),
    (10.5, 11.0, 9.0, 9.5),
    (9.5, 11.0, 9.4, 10.8),
    (10.8, 12.0, 10.5, 11.8),
    (11.8, 13.0, 11.5, 12.8),
    (12.8, 14.0, 12.5, 13.5),
    (13.5, 13.8, 12.0, 12.2),
    (12.2, 12.5, 11.2, 11.6),
    (11.6, 12.0, 11.0, 11.8),
    (11.8, 13.0, 11.7, 12.9),
    (12.9, 14.6, 12.8, 14.5),
    (14.5, 14.8, 12.1, 12.6),
    (12.6, 12.7, 11.0, 11.2),
    (11.2, 11.3, 10.5, 10.6),
]

BODY = OBParams(swing_len=3, use_body=True)
WICK = OBParams(swing_len=3, use_body=False)


def _df():
    return make_df(SCENARIO, datetime(2026, 1, 1, 13, 0, tzinfo=UTC))


def test_bullish_ob_body_tie_picks_oldest_bar():
    df = _df()
    e = next(e for e in detect(df, BODY) if e.kind == "ob_formed" and e.direction == "bullish")
    # bar 8 ve bar 9'un gövde altı eşit (11.6) → Pine en eskisini (bar 8) seçer
    assert e.bar == 11
    assert (e.zone_low, e.zone_high) == (11.6, 12.2)
    assert e.ob_time == df["time"][8].to_pydatetime()
    assert e.candle_time == df["close_time"][11].to_pydatetime()
    assert e.price == 14.5


def test_bullish_ob_wick_mode():
    df = _df()
    e = next(e for e in detect(df, WICK) if e.kind == "ob_formed" and e.direction == "bullish")
    assert (e.zone_low, e.zone_high) == (11.0, 12.0)
    assert e.ob_time == df["time"][9].to_pydatetime()


def test_retest_then_breaker_then_bearish():
    events = detect(_df(), BODY)
    kinds = [(e.kind, e.direction, e.bar) for e in events]
    assert kinds == [
        ("ob_formed", "bullish", 11),
        ("ob_retest", "bullish", 12),
        ("ob_formed", "bearish", 14),
    ]
    bear = events[-1]
    # bar 11 ve 12'nin gövde üstü eşit (14.5) → en eski (bar 11)
    assert (bear.zone_low, bear.zone_high) == (12.9, 14.5)


def test_engine_selection_from_config():
    cfg = OBConfig(engine="custom", direction="both", events=["ob_formed"], params=BODY)
    assert [(e.kind, e.direction) for e in ob.detect(_df(), cfg)] == [
        ("ob_formed", "bullish"), ("ob_formed", "bearish")]


def test_too_short_returns_empty():
    df = make_df([(1, 2, 0.5, 1.5)] * 3, datetime(2026, 1, 1, tzinfo=UTC))
    assert detect(df, OBParams(swing_len=10)) == []
