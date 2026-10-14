#!/bin/zsh
# macOS: botu oturum açılışında başlatan ve çökerse yeniden başlatan LaunchAgent'ı kurar.
#   ./scripts/install_launchd.sh            → kur / güncelle
#   ./scripts/install_launchd.sh uninstall  → kaldır
set -euo pipefail

LABEL="com.obbot.midas"
PROJECT="$(cd "$(dirname "$0")/.." && pwd)"
OBBOT_HOME="${OBBOT_HOME:-$HOME/Library/Application Support/obbot}"
PLIST="$HOME/Library/LaunchAgents/$LABEL.plist"
UID_NUM="$(id -u)"

if [[ "${1:-}" == "uninstall" ]]; then
  launchctl bootout "gui/$UID_NUM/$LABEL" 2>/dev/null || true
  rm -f "$PLIST"
  echo "Kaldırıldı: $LABEL"
  exit 0
fi

if [[ ! -x "$OBBOT_HOME/venv/bin/python" ]]; then
  echo "Sanal ortam bulunamadı: $OBBOT_HOME/venv — önce README'deki kurulum adımlarını uygulayın." >&2
  exit 1
fi

mkdir -p "$OBBOT_HOME/logs" "$HOME/Library/LaunchAgents"
# XML için & karakterini kaçır
esc() { print -r -- "${1//&/&amp;}"; }
sed -e "s|__PROJECT__|$(esc "$PROJECT")|g" -e "s|__HOME__|$(esc "$OBBOT_HOME")|g" \
  "$PROJECT/deploy/$LABEL.plist" > "$PLIST"
plutil -lint "$PLIST" >/dev/null

launchctl bootout "gui/$UID_NUM/$LABEL" 2>/dev/null || true
launchctl bootstrap "gui/$UID_NUM" "$PLIST"
launchctl enable "gui/$UID_NUM/$LABEL"

echo "Kuruldu ve başlatıldı: $LABEL"
echo "Durum : launchctl print gui/$UID_NUM/$LABEL | grep -E 'state|pid'"
echo "Loglar: $OBBOT_HOME/logs/"
