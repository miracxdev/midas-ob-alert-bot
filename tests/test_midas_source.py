from pathlib import Path

import httpx
import pytest

from obbot.sources import midas_web
from obbot.sources.midas_web import MidasWebSource, parse_gainers, parse_tr_number

PAGE = (Path(__file__).parent / "fixtures" / "midas_en_cok_artan.html").read_text(encoding="utf-8")


def test_parse_tr_number():
    assert parse_tr_number("3.268,75") == 3268.75
    assert parse_tr_number("-0,85") == -0.85
    assert parse_tr_number("12,90") == 12.9


def test_parse_fixture():
    g = parse_gainers(PAGE)
    assert [x.symbol for x in g] == ["OM", "W", "ZRO", "API3", "CORE"]
    assert g[0].change_pct == 3268.75
    assert g[-1].change_pct == -0.85


@pytest.fixture
def fake_http(monkeypatch):
    monkeypatch.setattr(midas_web.httpx, "get",
                        lambda *a, **k: httpx.Response(200, text=PAGE, request=httpx.Request("GET", a[0])))


def test_fetch_top_n_and_filter(fake_http):
    assert MidasWebSource("https://x", top_n=3).fetch() == ["OM", "W", "ZRO"]
    assert MidasWebSource("https://x", top_n=3, max_change_pct=500).fetch() == ["W", "ZRO", "API3"]


def test_fetch_empty_page_raises(monkeypatch):
    monkeypatch.setattr(midas_web.httpx, "get",
                        lambda *a, **k: httpx.Response(200, text="<html></html>",
                                                       request=httpx.Request("GET", a[0])))
    with pytest.raises(RuntimeError):
        MidasWebSource("https://x", top_n=3).fetch()
