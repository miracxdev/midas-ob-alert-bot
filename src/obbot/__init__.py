import os
import sys
from pathlib import Path

__version__ = "0.1.0"

# src/obbot/__init__.py → proje kökü (config.yaml, data/symbol_aliases.yaml)
PROJECT_ROOT = Path(__file__).resolve().parents[2]


def _default_home() -> Path:
    if sys.platform == "darwin":
        return Path.home() / "Library" / "Application Support" / "obbot"
    return Path.home() / ".local" / "share" / "obbot"


# Çalışma verisi (SQLite, loglar, venv). Masaüstü iCloud ile senkronize olduğunda
# dosyalar buluta taşınıp okuma takılabildiği için proje klasörünün dışında tutulur.
RUNTIME_DIR = Path(os.environ.get("OBBOT_HOME") or _default_home())
