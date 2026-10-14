from __future__ import annotations

from datetime import date, datetime
from pathlib import Path

from obbot import PROJECT_ROOT

DEFAULT_FILE = PROJECT_ROOT / "data" / "gainers_today.txt"


class FileSource:
    """data/gainers_today.txt (her satıra bir sembol). Sadece bugün düzenlenmişse kullanılır."""

    name = "file"

    def __init__(self, path: Path = DEFAULT_FILE, top_n: int = 10):
        self.path = path
        self.top_n = top_n

    def fetch(self) -> list[str]:
        if not self.path.exists():
            raise FileNotFoundError(f"{self.path} yok")
        if datetime.fromtimestamp(self.path.stat().st_mtime).date() != date.today():
            raise RuntimeError(f"{self.path.name} bugün güncellenmemiş")
        lines = [ln.split("#")[0].strip() for ln in self.path.read_text(encoding="utf-8").splitlines()]
        return [ln for ln in lines if ln][: self.top_n]
