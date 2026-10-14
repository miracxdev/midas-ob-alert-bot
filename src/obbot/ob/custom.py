"""LuxAlgo "ICT Concepts" indikatörünün (indicator/ob.pine) Order Block kısmının Python portu.

Kaynak: ICT Concepts [LuxAlgo], © LuxAlgo, CC BY-NC-SA 4.0
(https://creativecommons.org/licenses/by-nc-sa/4.0/). Bu port da aynı lisansla paylaşılır.

Pine karşılıkları:
- `swings(length)`: `high[length]` son `length` barın en yükseğinden büyükse yön "tepe"ye döner
  ve o bar swing high olur (`low` için simetrik). Yön değişmeden yeni swing oluşmaz.
- Bullish OB: kapanış kırılmamış swing high'ın üstüne çıkınca, swing barı ile kırılım barı
  arasındaki (ikisi hariç) en düşük `min`'e sahip bar OB olur. Eşitlikte en eski bar seçilir.
  `useBody` açıksa `min/max` mum gövdesi, kapalıysa fitildir. Mum yönü şartı yoktur.
- Bearish OB: simetriği.
- Breaker: gövdenin altı (bullish) / üstü (bearish) bölgenin ötesine geçerse OB geçersiz olur.
  Pine bu bölgeyi "breaker" olarak çizmeye devam eder; bot için artık aktif OB değildir.
- Retest (Pine'da yok, botun eki): fiyat aktif bir OB bölgesine oluşumdan sonra ilk kez girerse.

Pine'daki `Present` modu (yalnızca son 500 bar) ve çizim kodu port edilmedi; sinyaller aynıdır.
Her bar yalnızca kendisine kadarki veriyi kullanır (repaint yok).
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np
import pandas as pd

from obbot.config import OBParams
from obbot.ob.default import Direction, OBEvent


@dataclass
class _Swing:
    y: float
    x: int
    crossed: bool = False


@dataclass
class _Zone:
    direction: Direction
    top: float
    btm: float
    ob_bar: int
    formed_bar: int
    retested: bool = False


def _pine_range(end: int) -> range:
    """Pine `for i = 1 to end`: end < 1 ise geriye doğru sayar."""
    return range(1, end + 1) if end >= 1 else range(1, end - 1, -1)


def detect(df: pd.DataFrame, params: OBParams) -> list[OBEvent]:
    """Tüm geçmiş için OB olaylarını (oluşum + retest) zaman sırasıyla döndürür."""
    n = len(df)
    L = params.swing_len
    if n < L + 2:
        return []

    o = df["open"].to_numpy(float)
    h = df["high"].to_numpy(float)
    lo = df["low"].to_numpy(float)
    c = df["close"].to_numpy(float)
    times = [t.to_pydatetime() for t in df["time"]]
    close_times = [t.to_pydatetime() for t in df["close_time"]]

    mx = np.maximum(o, c)
    mn = np.minimum(o, c)
    zmax = mx if params.use_body else h
    zmin = mn if params.use_body else lo

    events: list[OBEvent] = []
    bull: list[_Zone] = []
    bear: list[_Zone] = []
    top: _Swing | None = None
    btm: _Swing | None = None
    os = 0

    for t in range(n):
        # swings(length)
        prev_os = os
        if t >= L:
            upper = h[t - L + 1 : t + 1].max()
            lower = lo[t - L + 1 : t + 1].min()
            if h[t - L] > upper:
                os = 0
            elif lo[t - L] < lower:
                os = 1
        if os == 0 and prev_os != 0:
            top = _Swing(h[t - L], t - L)
        if os == 1 and prev_os != 1:
            btm = _Swing(lo[t - L], t - L)

        # Bullish OB
        if top is not None and c[t] > top.y and not top.crossed:
            top.crossed = True
            minima, maxima, loc = zmin[t - 1], zmax[t - 1], t - 1
            for i in _pine_range(t - top.x - 1):
                j = t - i
                minima = min(zmin[j], minima)
                if minima == zmin[j]:
                    maxima, loc = zmax[j], j
            bull.insert(0, _Zone("bullish", maxima, minima, loc, t))
            events.append(OBEvent("ob_formed", "bullish", minima, maxima, times[loc],
                                  close_times[t], c[t], t))

        alive = []
        for z in bull:
            if mn[t] < z.btm:
                continue  # breaker
            if z.formed_bar < t and not z.retested and lo[t] <= z.top:
                z.retested = True
                events.append(OBEvent("ob_retest", "bullish", z.btm, z.top, times[z.ob_bar],
                                      close_times[t], c[t], t))
            alive.append(z)
        bull = alive

        # Bearish OB
        if btm is not None and c[t] < btm.y and not btm.crossed:
            btm.crossed = True
            minima, maxima, loc = zmin[t - 1], zmax[t - 1], t - 1
            for i in _pine_range(t - btm.x - 1):
                j = t - i
                maxima = max(zmax[j], maxima)
                if maxima == zmax[j]:
                    minima, loc = zmin[j], j
            bear.insert(0, _Zone("bearish", maxima, minima, loc, t))
            events.append(OBEvent("ob_formed", "bearish", minima, maxima, times[loc],
                                  close_times[t], c[t], t))

        alive = []
        for z in bear:
            if mx[t] > z.top:
                continue  # breaker
            if z.formed_bar < t and not z.retested and h[t] >= z.btm:
                z.retested = True
                events.append(OBEvent("ob_retest", "bearish", z.btm, z.top, times[z.ob_bar],
                                      close_times[t], c[t], t))
            alive.append(z)
        bear = alive

    return events
