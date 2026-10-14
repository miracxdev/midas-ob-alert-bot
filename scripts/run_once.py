"""Tek seferlik tarama (pencere kontrolü olmadan) — hata ayıklama için.

Örnekler:
  .venv/bin/python scripts/run_once.py --symbols BTC,PEPE,XYZFAKE
  .venv/bin/python scripts/run_once.py --midas            # Midas En Çok Artan listesini kullan
  .venv/bin/python scripts/run_once.py --symbols SOL --hours 24 --tf 15m,1h
"""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

import argparse
from datetime import UTC, datetime, timedelta
from zoneinfo import ZoneInfo

from obbot import ob
from obbot.config import load_config
from obbot.log import setup_logging
from obbot.markets.ohlcv import fetch_closed_ohlcv
from obbot.markets.resolver import resolve
from obbot.models import OBSignal
from obbot.notify.base import format_signal
from obbot.sources.base import normalize
from obbot.sources.midas_web import MidasWebSource


def main() -> None:
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    g = p.add_mutually_exclusive_group(required=True)
    g.add_argument("--symbols", help="Virgülle ayrılmış base semboller (BTC,PEPE)")
    g.add_argument("--midas", action="store_true", help="Midas En Çok Artan listesini çek")
    p.add_argument("--tf", help="Zaman dilimleri (varsayılan: config)")
    p.add_argument("--hours", type=float, default=6, help="Son kaç saatin sinyalleri gösterilsin (varsayılan 6)")
    args = p.parse_args()

    setup_logging("WARNING")
    cfg = load_config()
    tz = ZoneInfo(cfg.timezone)
    tfs = args.tf.split(",") if args.tf else cfg.timeframes

    if args.midas:
        w = cfg.watchlist
        bases = normalize(MidasWebSource(w.midas_url, w.top_n, w.max_change_pct).fetch())
        print(f"Midas En Çok Artan (ilk {w.top_n}): {', '.join(bases)}\n")
    else:
        bases = normalize(args.symbols.split(","))

    res = resolve(bases, cfg)
    print("Parite eşleme:")
    for b in bases:
        m = res.markets.get(b)
        print(f"  {b:<10} → {m.tv_symbol:<24} {m.tv_url}" if m else f"  {b:<10} → ❌ USDT/USD paritesi bulunamadı")

    since = datetime.now(UTC) - timedelta(hours=args.hours)
    print(f"\nSon {args.hours:g} saatteki sinyaller ({cfg.ob.direction}, {', '.join(cfg.ob.events)}):")
    total = 0
    for b, m in res.markets.items():
        for tf in tfs:
            try:
                df = fetch_closed_ohlcv(m, tf, limit=max(cfg.min_bars + 50, 300))
            except Exception as e:
                print(f"  {m.tv_symbol} {tf}: veri alınamadı ({e})")
                continue
            if len(df) < cfg.min_bars:
                print(f"  {m.tv_symbol} {tf}: yeterli geçmiş yok ({len(df)} mum)")
                continue
            last = df["close_time"].iloc[-1].astimezone(tz)
            print(f"  {m.tv_symbol} {tf}: {len(df)} kapanmış mum, son kapanış {last:%d.%m %H:%M}")
            for e in ob.detect(df, cfg.ob):
                if e.candle_time >= since:
                    total += 1
                    s = OBSignal(m, tf, e.kind, e.direction, e.zone_low, e.zone_high, e.candle_time, e.price)
                    print("\n" + "\n".join("    " + ln for ln in format_signal(s, tz).splitlines()) + "\n")
    print(f"\nToplam {total} sinyal.")


if __name__ == "__main__":
    main()
