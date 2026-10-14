from __future__ import annotations

import numpy as np


def pivot_highs(high: np.ndarray, length: int) -> np.ndarray:
    """ta.pivothigh(length, length) karşılığı.

    Dönen dizinin i. elemanı True ise i. bar bir swing high'dır: solundaki `length`
    barın hepsinden yüksek, sağındaki `length` barın hiçbirinden düşük değil.
    Pivot ancak i + length barında onaylanır (bunu kullanan kod dikkate almalı).
    """
    n = len(high)
    out = np.zeros(n, dtype=bool)
    for i in range(length, n - length):
        h = high[i]
        if h > high[i - length : i].max() and h >= high[i + 1 : i + length + 1].max():
            out[i] = True
    return out


def pivot_lows(low: np.ndarray, length: int) -> np.ndarray:
    """ta.pivotlow(length, length) karşılığı (simetrik)."""
    n = len(low)
    out = np.zeros(n, dtype=bool)
    for i in range(length, n - length):
        v = low[i]
        if v < low[i - length : i].min() and v <= low[i + 1 : i + length + 1].min():
            out[i] = True
    return out
