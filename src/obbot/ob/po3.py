"""PO3 Model [CantoLab] indikatörünün C2 + CISD kurulumunun yeniden yapımı.

Orijinal indikatör kapalı kaynaklıdır; bu modül yazarın açıklaması ve TradingView'deki
çizimlerle karşılaştırılarak yazılmıştır (BINANCE:BTCUSDT 17.10 20:00, Q/USDT 18.10 10:00
örnekleri birebir tutuyor). Alignment "Auto": 5m grafik ↔ 1h üst zaman dilimi.

Bullish (+CISD) kurulum:
1. C2: Üst zaman dilimi mumu (HTF), bir önceki tam HTF mumunun (C1) dibinin altına iner.
2. CISD seviyesi: C2'deki en düşük alt zaman dilimi (LTF) mumundan geriye doğru, dibe giden
   ardışık düşüş mumlarının (close < open) ilkinin açılışı. Dip mumu yükselişse ondan önceki
   düşüş dizisi alınır.
3. +CISD: C2 sürerken bir LTF mumu bu seviyenin üstünde kapanır → sinyal, o mumun kapanışında.
4. C2 içinde daha düşük bir dip oluşursa önceki kurulum geçersiz olur ve seviye yeniden
   hesaplanır (indikatördeki xc2 / xCISD). Bir kurulum en fazla bir kez sinyal verir.

Bearish (-CISD) simetriğidir. Sadece kapanmış mumlar kullanılır (repaint yok).
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np
import pandas as pd

from obbot.config import OBParams
from obbot.markets.ohlcv import TF_MINUTES
from obbot.ob.default import Direction, OBEvent


@dataclass
class _Setup:
    """Bir HTF mumu (C2) içindeki tek yönlü kurulumun durumu."""

    direction: Direction
    extreme: float = np.nan  # C2'nin şimdiye kadarki dibi (bullish) / tepesi (bearish)
    level: float | None = None  # CISD seviyesi; None → C1 süpürülmedi
    sweep_bar: int = -1
    fired: bool = False


def _series_open(o: np.ndarray, c: np.ndarray, end: int, bearish: bool) -> int:
    """`end`'den geriye, dibe/tepeye giden ardışık karşı yön mumlarının ilkini bulur."""
    against = (lambda i: c[i] < o[i]) if bearish else (lambda i: c[i] > o[i])
    j = end
    while j >= 0 and not against(j):
        j -= 1
    if j < 0:
        return end
    while j - 1 >= 0 and against(j - 1):
        j -= 1
    return j


def detect(df: pd.DataFrame, params: OBParams) -> list[OBEvent]:
    """Tüm geçmiş için CISD olaylarını (kind="cisd") zaman sırasıyla döndürür."""
    n = len(df)
    if n < 3:
        return []
    o = df["open"].to_numpy(float)
    h = df["high"].to_numpy(float)
    lo = df["low"].to_numpy(float)
    c = df["close"].to_numpy(float)
    times = [t.to_pydatetime() for t in df["time"]]
    close_times = [t.to_pydatetime() for t in df["close_time"]]

    ltf_min = int((df["time"].iloc[1] - df["time"].iloc[0]).total_seconds() // 60)
    htf_min = TF_MINUTES[params.htf]
    if htf_min <= ltf_min or htf_min % ltf_min:
        raise ValueError(f"HTF ({params.htf}) LTF'nin ({ltf_min}m) katı ve büyüğü olmalı")
    bars_per_htf = htf_min // ltf_min
    ts_min = ((df["time"] - pd.Timestamp(0, tz="UTC")) // pd.Timedelta(minutes=1)).to_numpy()
    bucket = ts_min // htf_min  # HTF mumları UTC'ye hizalı (TradingView ile aynı)

    events: list[OBEvent] = []
    cur_bucket = None
    cur_hi = cur_lo = np.nan
    cur_count = 0
    c1: tuple[float, float] | None = None  # (high, low) — yalnızca tam ve ardışık C1
    bull, bear = _Setup("bullish"), _Setup("bearish")

    for t in range(n):
        if bucket[t] != cur_bucket:
            complete = cur_bucket is not None and cur_count == bars_per_htf
            c1 = (cur_hi, cur_lo) if complete and bucket[t] == cur_bucket + 1 else None
            cur_bucket, cur_hi, cur_lo, cur_count = bucket[t], h[t], lo[t], 0
            bull, bear = _Setup("bullish", lo[t]), _Setup("bearish", h[t])
        cur_count += 1
        cur_hi, cur_lo = max(cur_hi, h[t]), min(cur_lo, lo[t])
        if c1 is None:
            continue
        c1_high, c1_low = c1

        # Bullish: C1 dibinin altında yeni dip → kurulumu (yeniden) kur
        if lo[t] <= bull.extreme and lo[t] < c1_low:
            if lo[t] < bull.extreme or bull.level is None:
                k = _series_open(o, c, t, bearish=True)
                bull = _Setup("bullish", lo[t], o[k], t)
        elif lo[t] < bull.extreme:
            bull.extreme = lo[t]
        if bull.level is not None and not bull.fired and c[t] > bull.level:
            bull.fired = True
            events.append(OBEvent("cisd", "bullish", bull.extreme, bull.level,
                                  times[bull.sweep_bar], close_times[t], c[t], t))

        # Bearish: C1 tepesinin üstünde yeni tepe
        if h[t] >= bear.extreme and h[t] > c1_high:
            if h[t] > bear.extreme or bear.level is None:
                k = _series_open(o, c, t, bearish=False)
                bear = _Setup("bearish", h[t], o[k], t)
        elif h[t] > bear.extreme:
            bear.extreme = h[t]
        if bear.level is not None and not bear.fired and c[t] < bear.level:
            bear.fired = True
            events.append(OBEvent("cisd", "bearish", bear.level, bear.extreme,
                                  times[bear.sweep_bar], close_times[t], c[t], t))

    return events
