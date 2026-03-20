#!/usr/bin/env bash
set -euo pipefail

REPO_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
AUTOSTART_DIR="${HOME}/.config/autostart"
DESKTOP_FILE="${AUTOSTART_DIR}/threads-auto-post.desktop"
RUN_SCRIPT="${REPO_DIR}/run_threads_daily.sh"

mkdir -p "${AUTOSTART_DIR}"
chmod +x "${RUN_SCRIPT}"

cat > "${DESKTOP_FILE}" <<EOF
[Desktop Entry]
Type=Application
Version=1.0
Name=Threads Daily Auto Post
Comment=Start Threads auto posting at login
Exec=${RUN_SCRIPT}
Path=${REPO_DIR}
Terminal=false
X-GNOME-Autostart-enabled=true
EOF

echo "自動起動を設定しました: ${DESKTOP_FILE}"
echo "ログを確認する場合: tail -f ~/.threads_auto_post.log"
