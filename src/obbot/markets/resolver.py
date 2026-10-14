from __future__ import annotations

from dataclasses import dataclass, field

from loguru import logger

from obbot.config import Config
from obbot.markets.exchanges import load_markets
from obbot.models import Market


@dataclass
class ResolveResult:
    markets: dict[str, Market] = field(default_factory=dict)
    not_found: list[str] = field(default_factory=list)


def _is_tradable_spot(m: dict) -> bool:
    return bool(m.get("spot")) and m.get("active") is not False


def resolve(bases: list[str], cfg: Config, unavailable: set[str] | None = None) -> ResolveResult:
    """Her base sembol için config sırasına göre ilk uygun borsa paritesini bulur.

    Erişilemeyen borsalar `unavailable` kümesine eklenir ve atlanır.
    """
    unavailable = unavailable if unavailable is not None else set()
    result = ResolveResult()
    pending = list(dict.fromkeys(bases))

    for ex in cfg.exchanges:
        if not pending:
            break
        if ex in unavailable:
            continue
        try:
            markets = load_markets(ex)
        except Exception as e:  # borsa erişilemezse sıradakine düş
            logger.warning("{} market listesi alınamadı: {}", ex, e)
            unavailable.add(ex)
            continue
        still = []
        for base in pending:
            for quote in cfg.quote_preference:
                m = markets.get(f"{base}/{quote}")
                if m and _is_tradable_spot(m):
                    result.markets[base] = Market(base, quote, ex)
                    break
            else:
                still.append(base)
        pending = still

    result.not_found = pending
    for base in pending:
        logger.warning("{} için {} paritesi bulunamadı", base, "/".join(cfg.quote_preference))
    return result
