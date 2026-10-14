"""Aktif bildirim kanallarına örnek bir OB sinyali gönderir (Telegram, macOS, ntfy)."""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from datetime import UTC, datetime
from zoneinfo import ZoneInfo

from obbot.config import Secrets, load_config
from obbot.log import setup_logging
from obbot.models import Market, OBSignal
from obbot.notify import build_hub
from obbot.notify.base import merge_signals
from obbot.notify.telegram import TelegramClient


def main() -> None:
    setup_logging("INFO")
    cfg, secrets = load_config(), Secrets()
    tg = None
    if secrets.telegram_bot_token and secrets.telegram_chat_id:
        tg = TelegramClient(secrets.telegram_bot_token, secrets.telegram_chat_id)
    hub = build_hub(cfg, secrets, tg)
    s = OBSignal(Market("BTC", "USDT", "binance"), "15m", "ob_formed", "bullish",
                 64123.5, 64480.0, datetime.now(UTC).replace(second=0, microsecond=0), 64950.25)
    for title, text in merge_signals([s], ZoneInfo(cfg.timezone)):
        print(text)
        hub.send_text("🧪 TEST\n" + text, "TEST — " + title)
    failed = [n for n, q in hub.pending.items() if q]
    print("\nGönderildi:", [n.name for n in hub.notifiers if n.name not in failed], "Başarısız:", failed)


if __name__ == "__main__":
    main()
