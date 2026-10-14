from __future__ import annotations

import re

import httpx


class NtfyNotifier:
    name = "ntfy"

    def __init__(self, topic: str, server: str = "https://ntfy.sh"):
        self.url = f"{server.rstrip('/')}/{topic}"

    def send_text(self, text: str, title: str = "OB Bot") -> None:
        headers = {"Title": title.encode("utf-8")}
        link = re.search(r"https://www\.tradingview\.com/\S+", text)
        if link:
            headers["Click"] = link.group(0)
        httpx.post(self.url, content=text.encode("utf-8"), headers=headers, timeout=15).raise_for_status()
