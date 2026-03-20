#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
LOG_FILE="${HOME}/.threads_auto_post.log"

cd "${SCRIPT_DIR}"

if [[ ! -f ".venv/bin/activate" ]]; then
  echo "[ERROR] .venv が見つかりません。READMEの準備手順を先に実行してください。" >> "${LOG_FILE}"
  exit 1
fi

if [[ ! -f "daily_posts.csv" ]]; then
  echo "[ERROR] daily_posts.csv が見つかりません。ファイルを作成してください。" >> "${LOG_FILE}"
  exit 1
fi

source ".venv/bin/activate"
python3 threads_auto_post.py --mode daily --csv daily_posts.csv --no-login-prompt >> "${LOG_FILE}" 2>&1
