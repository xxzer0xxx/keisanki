#!/usr/bin/env bash
set -euo pipefail

DESKTOP_FILE="${HOME}/.config/autostart/threads-auto-post.desktop"

if [[ -f "${DESKTOP_FILE}" ]]; then
  rm -f "${DESKTOP_FILE}"
  echo "自動起動設定を削除しました: ${DESKTOP_FILE}"
else
  echo "自動起動設定は見つかりませんでした。"
fi
