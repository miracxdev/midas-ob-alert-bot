from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime


@dataclass
class AppState:
    paused: bool = False
    last_scan_at: datetime | None = None
    last_scan_errors: int = 0
    consecutive_failures: int = 0
    failure_alert_sent: bool = False
    warned: set[str] = field(default_factory=set)  # günlük tek seferlik uyarılar
