from __future__ import annotations

import re
from pathlib import Path
from typing import Protocol

import yaml

from obbot import PROJECT_ROOT

ALIASES_FILE = PROJECT_ROOT / "data" / "symbol_aliases.yaml"
# "USD" bilerek yok: TUSD, FDUSD gibi coinleri bozar
_SUFFIXES = ("USDT", "TRY")


class GainersSource(Protocol):
    name: str

    def fetch(self) -> list[str]: ...  # ["XYZ", "ABC", ...] — yalnızca base sembol


def load_aliases(path: Path = ALIASES_FILE) -> dict[str, str]:
    if not path.exists():
        return {}
    data = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    return {str(k).upper(): str(v).upper() for k, v in data.items()}


def normalize(symbols: list[str], aliases: dict[str, str] | None = None) -> list[str]:
    """Büyük harf, TRY/USDT son eki ve '/' ayracı temizlenir, alias uygulanır, tekrarlar atılır."""
    aliases = aliases if aliases is not None else load_aliases()
    out: list[str] = []
    for raw in symbols:
        s = re.sub(r"[^A-Z0-9/]", "", raw.upper())
        s = s.split("/")[0]
        if s in aliases:
            s = aliases[s]
        else:
            for suf in _SUFFIXES:
                if s.endswith(suf) and len(s) > len(suf):
                    s = s[: -len(suf)]
                    break
            s = aliases.get(s, s)
        if s and s not in out:
            out.append(s)
    return out
