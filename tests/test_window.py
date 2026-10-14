from datetime import UTC, datetime, time
from zoneinfo import ZoneInfo

from obbot.config import Config, ScanWindow
from obbot.scheduler import closed_timeframes
from obbot.window import session_start

IST = ZoneInfo("Europe/Istanbul")


def at(y, mo, d, h, mi, s=0):
    return datetime(y, mo, d, h, mi, s, tzinfo=IST)


def test_normal_window():
    cfg = Config()  # 16:30–23:59
    assert session_start(at(2026, 10, 12, 16, 29), cfg) is None
    assert session_start(at(2026, 10, 12, 16, 30), cfg) == at(2026, 10, 12, 16, 30)
    assert session_start(at(2026, 10, 12, 23, 59), cfg) == at(2026, 10, 12, 16, 30)
    assert session_start(at(2026, 10, 13, 0, 5), cfg) is None


def test_window_across_midnight():
    cfg = Config(scan_window=ScanWindow(start=time(16, 30), end=time(4, 0)))
    assert session_start(at(2026, 10, 12, 20, 0), cfg) == at(2026, 10, 12, 16, 30)
    # gece yarısından sonra hâlâ önceki günün oturumu
    assert session_start(at(2026, 10, 13, 3, 59), cfg) == at(2026, 10, 12, 16, 30)
    assert session_start(at(2026, 10, 13, 4, 1), cfg) is None
    assert session_start(at(2026, 10, 13, 12, 0), cfg) is None


def test_days_filter():
    cfg = Config(days=["mon", "tue", "wed", "thu", "fri"])
    assert session_start(at(2026, 10, 12, 17, 0), cfg) is not None  # Pazartesi
    assert session_start(at(2026, 10, 17, 17, 0), cfg) is None  # Cumartesi
    # Cuma gecesi başlayan oturum Cumartesi 02:00'de de geçerli
    cfg2 = cfg.model_copy(update={"scan_window": ScanWindow(start=time(16, 30), end=time(4, 0))})
    assert session_start(at(2026, 10, 17, 2, 0), cfg2) == at(2026, 10, 16, 16, 30)


def test_closed_timeframes_alignment():
    tfs = ["15m", "1h"]
    assert closed_timeframes(at(2026, 10, 12, 17, 0, 10), tfs) == ["15m", "1h"]
    assert closed_timeframes(at(2026, 10, 12, 17, 15, 10), tfs) == ["15m"]
    assert closed_timeframes(at(2026, 10, 12, 17, 16, 10), tfs) == []
    # 4h ve 1d mumları UTC'ye hizalı kapanır (İstanbul = UTC+3)
    assert closed_timeframes(datetime(2026, 10, 12, 0, 0, 10, tzinfo=UTC), ["4h", "1d"]) == ["4h", "1d"]
