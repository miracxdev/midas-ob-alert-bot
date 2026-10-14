from __future__ import annotations

import sqlite3
import threading
from datetime import UTC, date, datetime
from pathlib import Path

from obbot import RUNTIME_DIR
from obbot.models import Market, OBSignal

DEFAULT_DB = RUNTIME_DIR / "bot.db"

SCHEMA = """
CREATE TABLE IF NOT EXISTS watchlist (
  date TEXT, base TEXT, source TEXT, exchange TEXT, tv_symbol TEXT,
  PRIMARY KEY (date, base)
);
CREATE TABLE IF NOT EXISTS signals (
  key TEXT PRIMARY KEY, tv_symbol TEXT, timeframe TEXT, kind TEXT,
  direction TEXT, zone_low REAL, zone_high REAL, candle_time TEXT, sent_at TEXT
);
CREATE TABLE IF NOT EXISTS runs (
  started_at TEXT, finished_at TEXT, symbols INTEGER, signals INTEGER, errors TEXT
);
"""


class DB:
    def __init__(self, path: Path | str = DEFAULT_DB):
        if str(path) != ":memory:":
            Path(path).parent.mkdir(parents=True, exist_ok=True)
        self.conn = sqlite3.connect(path, check_same_thread=False)
        self.conn.row_factory = sqlite3.Row
        self.conn.executescript(SCHEMA)
        # Zamanlayıcı ve Telegram thread'i aynı bağlantıyı paylaşır
        self.lock = threading.RLock()

    # --- watchlist ---
    def set_watchlist(
        self, day: date, bases: list[str], source: str, markets: dict[str, Market] | None = None
    ) -> None:
        markets = markets or {}
        with self.lock, self.conn:
            self.conn.execute("DELETE FROM watchlist WHERE date = ?", (day.isoformat(),))
            self.conn.executemany(
                "INSERT INTO watchlist VALUES (?, ?, ?, ?, ?)",
                [
                    (
                        day.isoformat(),
                        b,
                        source,
                        markets[b].exchange if b in markets else None,
                        markets[b].tv_symbol if b in markets else None,
                    )
                    for b in bases
                ],
            )

    def get_watchlist(self, day: date) -> list[sqlite3.Row]:
        with self.lock:
            return self.conn.execute(
                "SELECT * FROM watchlist WHERE date = ? ORDER BY rowid", (day.isoformat(),)
            ).fetchall()

    # --- signals (dedup) ---
    def is_sent(self, key: str) -> bool:
        with self.lock:
            row = self.conn.execute("SELECT 1 FROM signals WHERE key = ?", (key,)).fetchone()
        return row is not None

    def mark_sent(self, s: OBSignal) -> bool:
        """Sinyali kaydeder; daha önce kaydedilmişse False döner."""
        with self.lock, self.conn:
            cur = self.conn.execute(
                "INSERT OR IGNORE INTO signals VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
                (
                    s.key,
                    s.market.tv_symbol,
                    s.timeframe,
                    s.kind,
                    s.direction,
                    s.zone_low,
                    s.zone_high,
                    s.candle_time.isoformat(),
                    datetime.now(UTC).isoformat(),
                ),
            )
        return cur.rowcount == 1

    # --- runs ---
    def log_run(
        self, started_at: datetime, finished_at: datetime, symbols: int, signals: int, errors: str
    ) -> None:
        with self.lock, self.conn:
            self.conn.execute(
                "INSERT INTO runs VALUES (?, ?, ?, ?, ?)",
                (started_at.isoformat(), finished_at.isoformat(), symbols, signals, errors),
            )

    def last_runs(self, n: int = 3) -> list[sqlite3.Row]:
        with self.lock:
            return self.conn.execute(
                "SELECT * FROM runs ORDER BY started_at DESC LIMIT ?", (n,)
            ).fetchall()
