from __future__ import annotations

from loguru import logger

from obbot.config import Config, Secrets
from obbot.notify.base import NotifyHub
from obbot.notify.telegram import TelegramClient


def build_hub(cfg: Config, secrets: Secrets, telegram: TelegramClient | None) -> NotifyHub:
    notifiers = []
    for name in cfg.notifiers:
        if name == "telegram":
            if telegram is None:
                logger.warning("Telegram notifier atlandı: .env'de token/chat_id yok")
                continue
            from obbot.notify.telegram import TelegramNotifier

            notifiers.append(TelegramNotifier(telegram))
        elif name == "ntfy":
            if not secrets.ntfy_topic:
                logger.warning("ntfy notifier atlandı: .env'de NTFY_TOPIC yok")
                continue
            from obbot.notify.ntfy import NtfyNotifier

            notifiers.append(NtfyNotifier(secrets.ntfy_topic))
        elif name == "macos":
            from obbot.notify.macos import MacOSNotifier

            notifiers.append(MacOSNotifier())
    if not notifiers:
        logger.warning("Hiç aktif bildirim kanalı yok; sinyaller yalnızca loglanacak")
    return NotifyHub(notifiers)
