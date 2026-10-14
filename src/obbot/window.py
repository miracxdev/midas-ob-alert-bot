from __future__ import annotations

from datetime import datetime, timedelta

from obbot.config import Config

WEEKDAYS = ["mon", "tue", "wed", "thu", "fri", "sat", "sun"]


def session_start(now: datetime, cfg: Config) -> datetime | None:
    """`now` (yerel saat, tz'li) aktif bir tarama penceresindeyse pencerenin başlangıcını döner.

    Gece yarısını aşan pencereler (ör. 16:30–04:00) desteklenir; gün kontrolü pencerenin
    başladığı güne göre yapılır.
    """
    start, end = cfg.scan_window.start, cfg.scan_window.end
    t = now.timetz().replace(tzinfo=None)
    day = now.date()
    if start <= end:
        if not (start <= t <= end):
            return None
    elif t >= start:
        pass
    elif t <= end:
        day = day - timedelta(days=1)
    else:
        return None
    if WEEKDAYS[day.weekday()] not in cfg.days:
        return None
    return datetime.combine(day, start, tzinfo=now.tzinfo)
