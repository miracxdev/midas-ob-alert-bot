from __future__ import annotations

from datetime import date, datetime
from zoneinfo import ZoneInfo

from apscheduler.executors.pool import ThreadPoolExecutor
from apscheduler.schedulers.blocking import BlockingScheduler
from apscheduler.triggers.cron import CronTrigger
from loguru import logger

from obbot.config import Config
from obbot.db import DB
from obbot.markets.ohlcv import TF_MINUTES
from obbot.notify.base import NotifyHub
from obbot.scanner import scan
from obbot.state import AppState
from obbot.watchlist import refresh_watchlist
from obbot.window import session_start


def closed_timeframes(now: datetime, timeframes: list[str]) -> list[str]:
    """`now` anında (UTC dakikası) mumu yeni kapanan zaman dilimleri."""
    minute = int(now.timestamp() // 60)
    return [tf for tf in timeframes if minute % TF_MINUTES[tf] == 0]


class Bot:
    def __init__(self, cfg: Config, db: DB, hub: NotifyHub, state: AppState):
        self.cfg, self.db, self.hub, self.state = cfg, db, hub, state
        self.tz = ZoneInfo(cfg.timezone)

    def now(self) -> datetime:
        return datetime.now(self.tz)

    def list_day(self) -> date:
        """İzleme listesinin ait olduğu gün (gece yarısını aşan pencerede başlangıç günü)."""
        now = self.now()
        return (session_start(now, self.cfg) or now).date()

    def refresh(self, force: bool = False) -> bool:
        self.state.warned.clear()
        return refresh_watchlist(self.cfg, self.db, self.hub, self.list_day(), force=force)

    def hourly_refresh(self) -> None:
        """Tarama penceresi içinde listeyi yeniden çeker (değişiklik varsa bildirir)."""
        if self.state.paused or session_start(self.now(), self.cfg) is None:
            return
        # warned temizlenmez: aynı coin için "yeterli geçmiş yok" uyarısı her saat tekrarlanmasın
        refresh_watchlist(self.cfg, self.db, self.hub, self.list_day())

    def remind_if_empty(self) -> None:
        if not self.db.get_watchlist(self.list_day()):
            self.hub.send_text("⏰ Tarama başladı ama bugünün listesi yok. "
                               "/liste XYZ ABC ... ile gönder ya da /yenile dene.", "Liste yok")

    def tick(self) -> None:
        if self.state.paused:
            return
        now = self.now()
        tfs = closed_timeframes(now, self.cfg.timeframes)
        if not tfs:
            return
        session = session_start(now, self.cfg)
        if session is None:
            return
        scan(self.cfg, self.db, self.hub, self.state, tfs, session)

    def startup(self) -> None:
        """Yeniden başlatmada bugünün listesi yoksa ve yenileme saati geçtiyse hemen al."""
        now = self.now()
        due = now.time() >= self.cfg.watchlist.refresh_at or session_start(now, self.cfg)
        if due and not self.db.get_watchlist(self.list_day()):
            logger.info("Bugünün listesi yok, şimdi alınıyor")
            self.refresh()


def run_scheduler(bot: Bot) -> None:
    cfg = bot.cfg
    sched = BlockingScheduler(
        timezone=bot.tz,
        executors={"default": ThreadPoolExecutor(1)},
        job_defaults={"coalesce": True, "max_instances": 1, "misfire_grace_time": 120},
    )
    r = cfg.watchlist.refresh_at
    sched.add_job(bot.refresh, CronTrigger(hour=r.hour, minute=r.minute, timezone=bot.tz),
                  id="refresh")
    if cfg.watchlist.hourly_refresh:
        sched.add_job(bot.hourly_refresh, CronTrigger(minute=r.minute, timezone=bot.tz),
                      id="hourly_refresh")
    s = cfg.scan_window.start
    sched.add_job(bot.remind_if_empty, CronTrigger(hour=s.hour, minute=s.minute, second=30,
                                                   timezone=bot.tz), id="remind")
    sched.add_job(bot.tick, CronTrigger(second=cfg.candle_close_delay_sec % 60, timezone=bot.tz),
                  id="tick")
    logger.info("Zamanlayıcı başladı: liste {:%H:%M}, pencere {:%H:%M}–{:%H:%M}, TF {}",
                r, s, cfg.scan_window.end, cfg.timeframes)
    sched.add_job(bot.startup, id="startup")
    try:
        sched.start()
    except (KeyboardInterrupt, SystemExit):
        logger.info("Kapatılıyor")
