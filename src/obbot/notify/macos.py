from __future__ import annotations

import shutil
import subprocess


def _quote(s: str) -> str:
    return '"' + s.replace("\\", "\\\\").replace('"', '\\"') + '"'


class MacOSNotifier:
    name = "macos"

    def __init__(self, sound: str = "Glass"):
        self.sound = sound

    def send_text(self, text: str, title: str = "OB Bot") -> None:
        lines = [ln for ln in text.splitlines() if ln and not ln.startswith("📈")]
        body = " · ".join(lines[1:4]) if len(lines) > 1 else text
        if shutil.which("terminal-notifier"):
            cmd = ["terminal-notifier", "-title", title, "-message", body, "-sound", self.sound]
            if "tradingview.com" in text:
                url = next(w for w in text.split() if "tradingview.com" in w)
                cmd += ["-open", url]
        else:
            script = (
                f"display notification {_quote(body)} with title {_quote(title)} "
                f"sound name {_quote(self.sound)}"
            )
            cmd = ["osascript", "-e", script]
        subprocess.run(cmd, check=True, capture_output=True, timeout=15)
