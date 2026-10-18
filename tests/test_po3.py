"""PO3 Model [CantoLab] C2 + CISD yeniden yapımı.

Gerçek veri fixture'ları kullanıcının TradingView ekran görüntüleriyle karşılaştırıldı:
- BINANCE:BTCUSDT 5m, 17.10.2026: c2 20:00 mumu, +CISD çizgisi 81258.80
- BINANCE:QUSDT.P 5m, 18.10.2026: xc2 10:20 mumu, xCISD çizgisi 0.128737
"""

import json
from datetime import UTC, datetime
from pathlib import Path
from zoneinfo import ZoneInfo

from conftest import make_df

from obbot import ob
from obbot.config import OBConfig, OBParams
from obbot.markets.ohlcv import to_closed_frame
from obbot.models import Market, OBSignal
from obbot.notify.base import format_signal
from obbot.ob.po3 import detect

IST = ZoneInfo("Europe/Istanbul")
FIX = Path(__file__).parent / "fixtures"
P = OBParams(htf="1h")


def load(name: str):
    return to_closed_frame(json.loads((FIX / name).read_text()), "5m",
                           now=datetime(2100, 1, 1, tzinfo=UTC))


def local(t: datetime) -> str:
    return t.astimezone(IST).strftime("%H:%M")


def bullish(events):
    return [e for e in events if e.direction == "bullish"]


def test_btc_matches_tradingview():
    events = bullish(detect(load("btc_5m_2026-10-17.json"), P))
    last = events[-1]
    # TradingView'deki (History=1) son kurulum
    assert local(last.ob_time) == "20:00"  # c2 etiketi
    assert last.zone_high == 81258.80  # +CISD çizgisi
    assert last.zone_low == 81190.71  # c2 dibi
    assert local(last.candle_time) == "20:10"  # 20:05 mumu seviyenin üstünde kapandı
    assert last.price == 81285.31


def test_q_matches_tradingview():
    events = bullish(detect(load("q_5m_2026-10-18.json"), P))
    assert len(events) == 1
    e = events[0]
    # dip mumu (10:20) yükseliş → seviye, ondan önceki düşüş dizisinin açılışı (10:15)
    assert local(e.ob_time) == "10:20"
    assert e.zone_high == 0.128737 and e.zone_low == 0.123111
    assert local(e.candle_time) == "10:30"


# Sentetik senaryo: 5m, saat başına 12 mum. C1 = 13:00 UTC, C2 = 14:00 UTC.
def _scenario(c2_bars):
    c1 = [(100, 101, 99, 100)] * 12  # C1 dibi 99
    return make_df(c1 + c2_bars, datetime(2026, 1, 1, 13, 0, tzinfo=UTC), tf="5m")


def test_single_signal_per_setup_and_reset_on_new_low():
    c2 = [
        (100, 100.5, 99.5, 100),
        (100, 100, 98.5, 98.6),   # 1: düşüş, C1 dibini süpürür → seviye 100
        (98.6, 100.4, 98.6, 100.3),  # 2: 100 üstünde kapanış → +CISD
        (100.3, 100.8, 100, 100.6),  # 3: tekrar sinyal yok
        (100.6, 100.6, 97.0, 97.2),  # 4: yeni dip → kurulum geçersiz, seviye 100.6
        (97.2, 100.9, 97.2, 100.8),  # 5: 100.6 üstünde → ikinci +CISD
    ] + [(100.8, 101, 100.5, 100.9)] * 6
    events = bullish(detect(_scenario(c2), P))
    assert [(e.bar, e.zone_high, e.zone_low) for e in events] == [
        (14, 100.0, 98.5),
        (17, 100.6, 97.0),
    ]


def test_no_setup_without_sweep_or_incomplete_c1():
    c2 = [(100, 100.5, 99.2, 99.3), (99.3, 101, 99.3, 100.9)] + [(100.9, 101, 100.5, 100.9)] * 10
    assert bullish(detect(_scenario(c2), P)) == []  # C1 dibi (99) alınmadı
    # 13:30'dan başlayan veri: ilk saat tam değil → C1 sayılmaz
    df = make_df([(100, 101, 99, 100)] * 6 + [(100, 100, 98, 98.1), (98.1, 101, 98, 100.5)],
                 datetime(2026, 1, 1, 13, 30, tzinfo=UTC), tf="5m")
    assert detect(df, P) == []


def test_config_and_message_format():
    df = load("btc_5m_2026-10-17.json")
    cfg = OBConfig(engine="po3", direction="bullish", events=["cisd"], params=P)
    events = ob.detect(df, cfg)
    assert events and all(e.kind == "cisd" and e.direction == "bullish" for e in events)
    e = events[-1]
    s = OBSignal(Market("BTC", "USDT", "binance"), "5m", e.kind, e.direction, e.zone_low,
                 e.zone_high, e.candle_time, e.price)
    text = format_signal(s, IST)
    assert text.splitlines()[0] == "🟢 +CISD — BTC/USDT (5m)"
    assert "CISD seviyesi: 81258.80" in text
    assert "C2 dibi: 81190.71" in text
    assert "Mum: 20:10 (İST)" in text
    assert text.endswith("symbol=BINANCE:BTCUSDT&interval=5")
