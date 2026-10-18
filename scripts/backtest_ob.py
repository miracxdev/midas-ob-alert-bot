"""Bir coin için son N mumdaki OB'leri listeler (TradingView ile karşılaştırma için).

Örnek:
  .venv/bin/python scripts/backtest_ob.py BINANCE:BTCUSDT 15m
  .venv/bin/python scripts/backtest_ob.py OKX:PEPEUSDT 1h --bars 500 --direction both
"""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

import argparse
from zoneinfo import ZoneInfo

from obbot import ob
from obbot.config import load_config
from obbot.log import setup_logging
from obbot.markets.ohlcv import fetch_closed_ohlcv
from obbot.models import TV_PREFIX, Market
from obbot.notify.base import fmt_price

TV_TO_CCXT = {v: k for k, v in TV_PREFIX.items()}


def parse_tv_symbol(s: str, quotes: list[str]) -> Market:
    prefix, pair = s.upper().split(":", 1)
    exchange = TV_TO_CCXT.get(prefix, prefix.lower())
    for q in quotes:
        if pair.endswith(q) and len(pair) > len(q):
            return Market(pair[: -len(q)], q, exchange)
    raise SystemExit(f"Parite çözülemedi: {s} (beklenen ör. BINANCE:BTCUSDT)")


def main() -> None:
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("symbol", help="TradingView sembolü, ör. BINANCE:BTCUSDT")
    p.add_argument("timeframe", help="ör. 15m, 1h")
    p.add_argument("--bars", type=int, default=300, help="Kaç mum (varsayılan 300)")
    p.add_argument("--direction", choices=["bullish", "bearish", "both"], help="Varsayılan: config")
    p.add_argument("--retest", action="store_true", help="Retest olaylarını da göster")
    args = p.parse_args()

    setup_logging("WARNING")
    cfg = load_config()
    tz = ZoneInfo(cfg.timezone)
    ob_cfg = cfg.ob.model_copy(deep=True)
    if args.direction:
        ob_cfg.direction = args.direction
    if ob_cfg.engine != "po3":
        ob_cfg.events = ["ob_formed", "ob_retest"] if args.retest else ["ob_formed"]

    m = parse_tv_symbol(args.symbol, cfg.quote_preference)
    df = fetch_closed_ohlcv(m, args.timeframe, limit=args.bars)
    print(f"{m.tv_symbol} {args.timeframe} — {len(df)} mum: "
          f"{df['time'].iloc[0].astimezone(tz):%d.%m %H:%M} → {df['close_time'].iloc[-1].astimezone(tz):%d.%m %H:%M} (İST)")
    print(f"Parametreler: {ob_cfg.params.model_dump()}  yön: {ob_cfg.direction}\n")
    ref = "c2 mumu (İST)" if ob_cfg.engine == "po3" else "OB mumu (İST)"
    print(f"{'Olay':<10} {'Yön':<8} {ref:<15} {'Sinyal (İST)':<15} {'Bölge':<28} Fiyat")
    events = ob.detect(df, ob_cfg)
    for e in events:
        kind = {"ob_formed": "OLUŞUM", "ob_retest": "RETEST", "cisd": "CISD"}[e.kind]
        zone = f"{fmt_price(e.zone_low)} – {fmt_price(e.zone_high)}"
        print(f"{kind:<10} {e.direction:<8} {e.ob_time.astimezone(tz):%d.%m %H:%M}    "
              f"{e.candle_time.astimezone(tz):%d.%m %H:%M}    {zone:<28} {fmt_price(e.price)}")
    print(f"\nToplam {len(events)} olay. Grafik: {m.tv_url}")


if __name__ == "__main__":
    main()
