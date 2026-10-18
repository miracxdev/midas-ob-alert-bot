from __future__ import annotations

import pandas as pd

from obbot.config import OBConfig
from obbot.ob.default import OBEvent


def detect(df: pd.DataFrame, ob_cfg: OBConfig) -> list[OBEvent]:
    """Konfigürasyondaki motoru çalıştırır, yön ve olay türüne göre filtreler."""
    if ob_cfg.engine == "custom":
        from obbot.ob import custom as engine
    elif ob_cfg.engine == "po3":
        from obbot.ob import po3 as engine
    else:
        from obbot.ob import default as engine
    events = engine.detect(df, ob_cfg.params)
    return [
        e
        for e in events
        if e.kind in ob_cfg.events and ob_cfg.direction in ("both", e.direction)
    ]
