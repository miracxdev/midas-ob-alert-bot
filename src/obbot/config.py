from __future__ import annotations

from datetime import time
from pathlib import Path
from typing import Literal

import yaml
from pydantic import BaseModel, Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

from obbot import PROJECT_ROOT

Weekday = Literal["mon", "tue", "wed", "thu", "fri", "sat", "sun"]


class Secrets(BaseSettings):
    """`.env` dosyasından okunan gizli değerler."""

    model_config = SettingsConfigDict(
        env_file=PROJECT_ROOT / ".env", env_file_encoding="utf-8", extra="ignore"
    )

    telegram_bot_token: str = ""
    telegram_chat_id: str = ""
    ntfy_topic: str = ""


class WatchlistConfig(BaseModel):
    refresh_at: time = time(16, 25)
    top_n: int = Field(10, ge=1)
    sources: list[str] = ["midas_web", "manual", "file"]
    midas_url: str = "https://www.getmidas.com/canli-kripto/en-cok-artan"
    max_change_pct: float | None = None
    # Tarama penceresi boyunca her saat (refresh_at dakikasında) listeyi yeniden çek
    hourly_refresh: bool = True


class ScanWindow(BaseModel):
    start: time = time(16, 30)
    end: time = time(23, 59)


class OBParams(BaseModel):
    swing_len: int = Field(5, ge=1)
    use_body: bool = False


class OBConfig(BaseModel):
    engine: Literal["default", "custom"] = "default"
    direction: Literal["bullish", "bearish", "both"] = "bullish"
    events: list[Literal["ob_formed", "ob_retest"]] = ["ob_formed"]
    params: OBParams = OBParams()


class Config(BaseModel):
    timezone: str = "Europe/Istanbul"
    watchlist: WatchlistConfig = WatchlistConfig()
    scan_window: ScanWindow = ScanWindow()
    days: list[Weekday] = ["mon", "tue", "wed", "thu", "fri", "sat", "sun"]
    timeframes: list[str] = ["15m"]
    candle_close_delay_sec: int = 10
    # Bundan eski mumlarda oluşmuş OB'ler bildirilmez (mum sayısı; null = sınır yok)
    max_signal_age_bars: int | None = Field(3, ge=1)
    exchanges: list[str] = ["binance", "okx", "bybit", "gate", "kucoin", "mexc"]
    quote_preference: list[str] = ["USDT", "USD"]
    min_bars: int = 200
    ob: OBConfig = OBConfig()
    notifiers: list[Literal["telegram", "ntfy", "macos"]] = ["telegram", "macos"]
    merge_window_min: int = 10

    @field_validator("timeframes")
    @classmethod
    def _check_timeframes(cls, v: list[str]) -> list[str]:
        allowed = {"1m", "3m", "5m", "15m", "30m", "1h", "2h", "4h", "1d"}
        bad = [tf for tf in v if tf not in allowed]
        if bad:
            raise ValueError(f"Desteklenmeyen zaman dilimi: {bad}")
        return v


def load_config(path: Path | None = None) -> Config:
    path = path or PROJECT_ROOT / "config.yaml"
    data = yaml.safe_load(path.read_text(encoding="utf-8")) if path.exists() else {}
    return Config.model_validate(data or {})
