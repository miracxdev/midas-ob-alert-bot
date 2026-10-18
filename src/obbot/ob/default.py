"""Varsayılan Order Block mantığı (şartname Bölüm 7.2).

Swing + yapı kırılımı (BOS):
- Bullish OB: kapanış, son kırılmamış swing high'ın üstünde kapanırsa, swing high barı ile
  kırılım barı arasındaki en düşük low'a sahip düşüş mumu (close < open) OB olur.
- Bearish OB: simetriği.
- Mitigasyon: kapanış bölgenin tamamen ötesine geçerse OB geçersiz.
- Retest: fiyat aktif bir OB bölgesine (oluşumdan sonraki barlarda) ilk kez geri girerse.

Her bar yalnızca kendisine kadarki veriyi kullanır (repaint yok).
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Literal

import numpy as np
import pandas as pd

from obbot.config import OBParams
from obbot.ob.pivots import pivot_highs, pivot_lows

Direction = Literal["bullish", "bearish"]
Kind = Literal["ob_formed", "ob_retest", "cisd"]


@dataclass(frozen=True)
class OBEvent:
    kind: Kind
    direction: Direction
    zone_low: float
    zone_high: float
    ob_time: datetime  # OB mumunun açılışı (UTC)
    candle_time: datetime  # olayı doğuran mumun kapanışı (UTC)
    price: float  # olay mumunun kapanışı
    bar: int  # olay mumunun indeksi


@dataclass
class _Zone:
    direction: Direction
    low: float
    high: float
    ob_bar: int
    formed_bar: int
    retested: bool = False


def _pick_ob_bar(o, h, lo, c, start: int, end: int, bullish: bool) -> int:
    """[start, end) aralığında OB mumunu seçer; uygun yön mumu yoksa uç bar."""
    idx = np.arange(start, end)
    if bullish:
        cand = idx[c[idx] < o[idx]]
        pool = cand if len(cand) else idx
        vals = lo[pool]
        best = np.flatnonzero(vals == vals.min())[-1]  # eşitlikte en sonuncu
    else:
        cand = idx[c[idx] > o[idx]]
        pool = cand if len(cand) else idx
        vals = h[pool]
        best = np.flatnonzero(vals == vals.max())[-1]
    return int(pool[best])


def detect(df: pd.DataFrame, params: OBParams) -> list[OBEvent]:
    """Tüm geçmiş için OB olaylarını (oluşum + retest) zaman sırasıyla döndürür."""
    n = len(df)
    L = params.swing_len
    if n < 2 * L + 2:
        return []

    o = df["open"].to_numpy(float)
    h = df["high"].to_numpy(float)
    lo = df["low"].to_numpy(float)
    c = df["close"].to_numpy(float)
    times = [t.to_pydatetime() for t in df["time"]]
    close_times = [t.to_pydatetime() for t in df["close_time"]]

    ph = pivot_highs(h, L)
    pl = pivot_lows(lo, L)

    events: list[OBEvent] = []
    zones: list[_Zone] = []
    swing_high: int | None = None  # son onaylanmış, kırılmamış swing high bar indeksi
    swing_low: int | None = None

    def zone_of(bar: int) -> tuple[float, float]:
        if params.use_body:
            return min(o[bar], c[bar]), max(o[bar], c[bar])
        return lo[bar], h[bar]

    for t in range(n):
        # t barında onaylanan pivotlar: t - L
        p = t - L
        if p >= L:
            if ph[p]:
                swing_high = p
            if pl[p]:
                swing_low = p

        # Mitigasyon ve retest (önceki barlarda oluşmuş bölgeler)
        alive = []
        for z in zones:
            if z.formed_bar < t:
                if z.direction == "bullish" and c[t] < z.low:
                    continue
                if z.direction == "bearish" and c[t] > z.high:
                    continue
                if not z.retested:
                    touched = lo[t] <= z.high if z.direction == "bullish" else h[t] >= z.low
                    if touched:
                        z.retested = True
                        events.append(
                            OBEvent("ob_retest", z.direction, z.low, z.high, times[z.ob_bar],
                                    close_times[t], c[t], t)
                        )
            alive.append(z)
        zones = alive

        # Yukarı BOS → bullish OB
        if swing_high is not None and c[t] > h[swing_high]:
            ob = _pick_ob_bar(o, h, lo, c, swing_high, t, bullish=True)
            zl, zh = zone_of(ob)
            zones.append(_Zone("bullish", zl, zh, ob, t))
            events.append(OBEvent("ob_formed", "bullish", zl, zh, times[ob], close_times[t], c[t], t))
            swing_high = None

        # Aşağı BOS → bearish OB
        if swing_low is not None and c[t] < lo[swing_low]:
            ob = _pick_ob_bar(o, h, lo, c, swing_low, t, bullish=False)
            zl, zh = zone_of(ob)
            zones.append(_Zone("bearish", zl, zh, ob, t))
            events.append(OBEvent("ob_formed", "bearish", zl, zh, times[ob], close_times[t], c[t], t))
            swing_low = None

    return events
