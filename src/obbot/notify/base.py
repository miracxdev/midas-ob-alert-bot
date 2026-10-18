from __future__ import annotations

import math
from collections import defaultdict
from typing import Protocol
from zoneinfo import ZoneInfo

from loguru import logger

from obbot.models import OBSignal

TV_INTERVAL = {"1m": "1", "3m": "3", "5m": "5", "15m": "15", "30m": "30",
               "1h": "60", "2h": "120", "4h": "240", "1d": "D"}


class Notifier(Protocol):
    name: str

    def send_text(self, text: str, title: str = "OB Bot") -> None: ...


def fmt_price(x: float) -> str:
    """Fiyatı büyüklüğüne göre anlamlı basamakla yazar (0.4123, 65012.50, 0.00001234)."""
    if x == 0 or not math.isfinite(x):
        return str(x)
    decimals = max(2, 3 - math.floor(math.log10(abs(x))))
    return f"{x:.{decimals}f}"


def signal_name(s: OBSignal) -> str:
    if s.kind == "cisd":
        return "+CISD" if s.direction == "bullish" else "-CISD"
    return f"{s.direction.upper()} {'OB' if s.kind == 'ob_formed' else 'OB RETEST'}"


def format_signal(s: OBSignal, tz: ZoneInfo) -> str:
    dot = "🟢" if s.direction == "bullish" else "🔴"
    local = s.candle_time.astimezone(tz)
    url = f"{s.market.tv_url}&interval={TV_INTERVAL.get(s.timeframe, s.timeframe)}"
    if s.kind == "cisd":
        bullish = s.direction == "bullish"
        return (
            f"{dot} {signal_name(s)} — {s.market.ccxt_symbol} ({s.timeframe})\n"
            f"CISD seviyesi: {fmt_price(s.zone_high if bullish else s.zone_low)}\n"
            f"C2 {'dibi' if bullish else 'tepesi'}: {fmt_price(s.zone_low if bullish else s.zone_high)}\n"
            f"Fiyat: {fmt_price(s.price)}\n"
            f"Mum: {local:%H:%M} (İST)\n"
            f"Borsa: {s.market.exchange.capitalize()}\n"
            f"📈 {url}"
        )
    return (
        f"{dot} {signal_name(s)} — {s.market.ccxt_symbol} ({s.timeframe})\n"
        f"Bölge: {fmt_price(s.zone_low)} – {fmt_price(s.zone_high)}\n"
        f"Fiyat: {fmt_price(s.price)}\n"
        f"Mum: {local:%H:%M} (İST)\n"
        f"Borsa: {s.market.exchange.capitalize()}\n"
        f"📈 {url}"
    )


def merge_signals(signals: list[OBSignal], tz: ZoneInfo) -> list[tuple[str, str]]:
    """Aynı coine ait sinyalleri tek mesajda birleştirir → [(başlık, metin)]."""
    groups: dict[str, list[OBSignal]] = defaultdict(list)
    for s in signals:
        groups[s.market.tv_symbol].append(s)
    out = []
    for group in groups.values():
        group.sort(key=lambda s: (s.candle_time, s.timeframe))
        first = group[0]
        title = f"{signal_name(first)} — {first.market.ccxt_symbol}"
        if len(group) > 1:
            title = f"{len(group)} sinyal — {first.market.ccxt_symbol}"
        out.append((title, "\n\n".join(format_signal(s, tz) for s in group)))
    return out


class NotifyHub:
    """Birden fazla notifier'a gönderir; başarısız gönderimleri kuyruğa alıp sonra tekrar dener."""

    def __init__(self, notifiers: list[Notifier]):
        self.notifiers = notifiers
        self.pending: dict[str, list[tuple[str, str]]] = {n.name: [] for n in notifiers}

    def _try(self, n: Notifier, title: str, text: str) -> bool:
        try:
            n.send_text(text, title)
            return True
        except Exception as e:
            logger.warning("{} bildirimi gönderilemedi: {}", n.name, e)
            return False

    def send_text(self, text: str, title: str = "OB Bot") -> None:
        for n in self.notifiers:
            if not self._try(n, title, text):
                self.pending[n.name].append((title, text))

    def flush(self) -> None:
        for n in self.notifiers:
            queue, self.pending[n.name] = self.pending[n.name], []
            for i, (title, text) in enumerate(queue):
                if not self._try(n, title, text):
                    self.pending[n.name].extend(queue[i:])
                    break
