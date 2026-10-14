from __future__ import annotations

import httpx

API = "https://api.telegram.org/bot{token}/{method}"


class TelegramClient:
    def __init__(self, token: str, chat_id: str, timeout: float = 15):
        self.token = token
        self.chat_id = str(chat_id)
        self.http = httpx.Client(timeout=timeout)

    def call(self, method: str, http_timeout: float | None = None, **params) -> dict:
        r = self.http.post(API.format(token=self.token, method=method), json=params,
                           timeout=http_timeout or self.http.timeout)
        data = r.json()
        if not data.get("ok"):
            raise RuntimeError(f"Telegram {method} hatası: {data.get('description', r.text)}")
        return data["result"]

    def send_message(self, text: str, chat_id: str | None = None) -> None:
        self.call("sendMessage", chat_id=chat_id or self.chat_id, text=text,
                  disable_web_page_preview=True)


class TelegramNotifier:
    name = "telegram"

    def __init__(self, client: TelegramClient):
        self.client = client

    def send_text(self, text: str, title: str = "OB Bot") -> None:
        self.client.send_message(text)
