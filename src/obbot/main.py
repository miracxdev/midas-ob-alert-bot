from __future__ import annotations

import argparse
from pathlib import Path

from loguru import logger

from obbot import __version__
from obbot.config import Secrets, load_config
from obbot.db import DB
from obbot.log import setup_logging
from obbot.notify import build_hub
from obbot.notify.telegram import TelegramClient
from obbot.state import AppState


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        prog="obbot",
        description="Midas 'En Çok Artan' coinleri için Order Block bildirim botu.",
    )
    p.add_argument("--config", type=Path, help="config.yaml yolu (varsayılan: proje kökü)")
    p.add_argument("--log-level", default="INFO", help="Konsol log seviyesi (varsayılan: INFO)")
    p.add_argument(
        "--check", action="store_true", help="Konfigürasyonu ve veritabanını doğrula, sonra çık"
    )
    p.add_argument("--version", action="version", version=f"obbot {__version__}")
    return p


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    setup_logging(args.log_level)

    cfg = load_config(args.config)
    secrets = Secrets()
    db = DB()
    logger.info(
        "Konfig yüklendi: zaman dilimleri={}, pencere={}–{}, notifier={}",
        cfg.timeframes,
        cfg.scan_window.start.strftime("%H:%M"),
        cfg.scan_window.end.strftime("%H:%M"),
        cfg.notifiers,
    )
    telegram = None
    if secrets.telegram_bot_token and secrets.telegram_chat_id:
        telegram = TelegramClient(secrets.telegram_bot_token, secrets.telegram_chat_id)
    elif "telegram" in cfg.notifiers:
        logger.warning("Telegram bilgileri .env'de eksik (TELEGRAM_BOT_TOKEN / TELEGRAM_CHAT_ID)")

    if args.check:
        logger.info("Kontrol tamam. Veritabanı: {}", db.conn.execute("PRAGMA database_list").fetchone()[2])
        return 0

    from obbot.bot.commands import CommandHandler, start_polling
    from obbot.scheduler import Bot, run_scheduler

    hub = build_hub(cfg, secrets, telegram)
    bot = Bot(cfg, db, hub, AppState())
    if telegram:
        start_polling(CommandHandler(bot, telegram))
    run_scheduler(bot)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
