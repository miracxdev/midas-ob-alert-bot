"""Telegram komutları (long polling). Yalnızca .env'deki TELEGRAM_CHAT_ID'ye cevap verir."""

from __future__ import annotations

import threading
import time

from loguru import logger

from obbot.notify.telegram import TelegramClient
from obbot.scheduler import Bot
from obbot.sources.base import normalize
from obbot.watchlist import MANUAL, format_watchlist, save_list
from obbot.window import session_start

HELP = """Komutlar:
/liste XYZ ABC ... — bugünün listesini elle ayarla
/yenile — listeyi Midas'tan yeniden çek
/bugun — bugünün izleme listesi ve pariteler
/durum — son tarama, hata sayısı, pencere
/test — deneme bildirimi
/durdur, /baslat — taramayı duraklat / devam ettir"""


class CommandHandler:
    def __init__(self, bot: Bot, client: TelegramClient):
        self.bot = bot
        self.client = client

    def reply(self, text: str) -> None:
        self.client.send_message(text)

    def handle(self, msg: dict) -> None:
        if str(msg.get("chat", {}).get("id")) != self.client.chat_id:
            logger.warning("Yetkisiz chat'ten mesaj yok sayıldı: {}", msg.get("chat", {}).get("id"))
            return
        if "photo" in msg:
            self.reply("Ekran görüntüsünden liste okuma etkin değil. "
                       "Liste otomatik olarak Midas sitesinden alınıyor; elle girmek için /liste XYZ ABC ...")
            return
        text = (msg.get("text") or "").strip()
        if not text.startswith("/"):
            return
        cmd, *args = text.split()
        cmd = cmd.split("@")[0].lower()
        fn = {
            "/liste": self.cmd_liste,
            "/yenile": self.cmd_yenile,
            "/bugun": self.cmd_bugun,
            "/durum": self.cmd_durum,
            "/test": self.cmd_test,
            "/durdur": self.cmd_durdur,
            "/baslat": self.cmd_baslat,
            "/start": self.cmd_help,
            "/yardim": self.cmd_help,
            "/help": self.cmd_help,
        }.get(cmd)
        if fn is None:
            self.reply("Bilinmeyen komut.\n\n" + HELP)
            return
        fn(args)

    def cmd_help(self, args: list[str]) -> None:
        self.reply(HELP)

    def cmd_liste(self, args: list[str]) -> None:
        bases = normalize(" ".join(args).replace(",", " ").split())
        if not bases:
            self.reply("Kullanım: /liste XYZ ABC DEF")
            return
        day = self.bot.list_day()
        not_found = save_list(day, bases, MANUAL, self.bot.cfg, self.bot.db)
        self.bot.state.warned.clear()
        msg = format_watchlist(day, self.bot.db.get_watchlist(day))
        if not_found:
            msg += f"\n\n⚠️ Parite bulunamadı: {', '.join(not_found)}"
        self.reply(msg)

    def cmd_yenile(self, args: list[str]) -> None:
        self.reply("Midas listesi yeniden alınıyor…")
        if not self.bot.refresh(force=True):
            self.reply("Liste alınamadı, logları kontrol et.")

    def cmd_bugun(self, args: list[str]) -> None:
        day = self.bot.list_day()
        self.reply(format_watchlist(day, self.bot.db.get_watchlist(day)))

    def cmd_durum(self, args: list[str]) -> None:
        st, cfg = self.bot.state, self.bot.cfg
        now = self.bot.now()
        last = st.last_scan_at.astimezone(self.bot.tz).strftime("%d.%m %H:%M:%S") if st.last_scan_at else "henüz yok"
        active = "aktif ✅" if session_start(now, cfg) else "dışında ⏸"
        self.reply(
            f"Durum: {'⏸ DURAKLATILDI' if st.paused else '▶️ çalışıyor'}\n"
            f"Pencere: {cfg.scan_window.start:%H:%M}–{cfg.scan_window.end:%H:%M} ({active})\n"
            f"Zaman dilimleri: {', '.join(cfg.timeframes)} · Yön: {cfg.ob.direction}\n"
            f"Son tarama: {last} · hata: {st.last_scan_errors}\n"
            f"Art arda hatalı tarama: {st.consecutive_failures}"
        )

    def cmd_test(self, args: list[str]) -> None:
        self.bot.hub.send_text("✅ Test bildirimi — bot çalışıyor.", "OB Bot test")

    def cmd_durdur(self, args: list[str]) -> None:
        self.bot.state.paused = True
        self.reply("⏸ Tarama duraklatıldı. Devam için /baslat")

    def cmd_baslat(self, args: list[str]) -> None:
        self.bot.state.paused = False
        self.reply("▶️ Tarama devam ediyor.")


def start_polling(handler: CommandHandler) -> threading.Thread:
    def loop() -> None:
        offset = None
        while True:
            try:
                params = {"timeout": 30, "allowed_updates": ["message"]}
                if offset is not None:
                    params["offset"] = offset
                updates = handler.client.call("getUpdates", http_timeout=40, **params)
                for u in updates:
                    offset = u["update_id"] + 1
                    if "message" in u:
                        try:
                            handler.handle(u["message"])
                        except Exception:
                            logger.exception("Komut işlenemedi")
            except Exception as e:
                logger.warning("Telegram polling hatası: {}", e)
                time.sleep(5)

    t = threading.Thread(target=loop, name="telegram-polling", daemon=True)
    t.start()
    logger.info("Telegram komutları dinleniyor")
    return t
