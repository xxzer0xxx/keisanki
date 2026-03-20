# Threads 自動投稿ツール（かんたん版）

プログラミング知識がなくても使えるように、**投稿予約CSV**を読み込んで自動投稿するツールです。

## できること

- 指定日時になったら Threads に自動投稿
- 毎日同じ時刻に自動投稿（dailyモード）
- Linuxでログイン時に自動起動（PC起動後）
- 一度投稿した内容は履歴に記録（重複投稿を防止）
- 初回ログインだけ手動、2回目以降はログイン状態を再利用
- `--dry-run` で投稿せずに動作確認可能

---

## 1) 最初の準備（1回だけ）

以下をそのまま実行してください。

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
python -m playwright install chromium
```

---

## 2) 予約投稿ファイルを作る

`posts.csv` という名前で、次の形式で保存します。

```csv
datetime,text
2026-03-21 09:00,おはようございます！
2026-03-21 20:00,今日も1日お疲れさまでした。
```

- `datetime` は `YYYY-MM-DD HH:MM`（または `YYYY/MM/DD HH:MM`）
- `text` は投稿本文

サンプルとして `posts_example.csv` も入っています。

### 毎日投稿したい場合（dailyモード）

`daily_posts.csv` を次の形式で作ってください。

```csv
time,text
09:00,おはようございます！
20:00,今日も1日お疲れさまでした。
```

- `time` は `HH:MM`（24時間表記）
- その日の時刻を過ぎていて未投稿なら、起動中に1回投稿します
- 1日1回だけ投稿され、同じ日に重複投稿しません

サンプルとして `daily_posts_example.csv` も入っています。

---

## 3) 実行する

### 通常（日時指定で1回投稿）

```bash
source .venv/bin/activate
python threads_auto_post.py --csv posts.csv
```

実行後、ブラウザが開きます。  
Threads にログインしたら、ターミナルで Enter キーを押してください。  
その後は指定時刻になったら自動投稿されます。

### 毎日同じ時刻に投稿（dailyモード）

```bash
source .venv/bin/activate
python threads_auto_post.py --mode daily --csv daily_posts.csv
```

これは終了するまで動き続け、毎日指定時刻に投稿します。  
止めるときは `Ctrl+C` を押してください。

### PC起動後に自動開始（Linux GUI）

> これは「電源ON直後」ではなく、**ログイン後に自動起動**です。

1) まず1回だけ手動ログインを保存

```bash
source .venv/bin/activate
python threads_auto_post.py --mode daily --csv daily_posts.csv
```

ログイン後、監視が始まったら `Ctrl+C` で止めてOKです。  
（この時点でログイン状態が保存されます）

2) 自動起動を設定

```bash
chmod +x run_threads_daily.sh install_autostart_linux.sh
bash install_autostart_linux.sh
```

3) PCを再起動して確認

ログ確認:

```bash
tail -f ~/.threads_auto_post.log
```

4) 自動起動を解除したいとき

```bash
chmod +x uninstall_autostart_linux.sh
bash uninstall_autostart_linux.sh
```

---

## よく使うオプション

- テスト投稿（実際には投稿しない）

```bash
python threads_auto_post.py --csv posts.csv --dry-run
```

- 投稿判定間隔を変更（秒）

```bash
python threads_auto_post.py --csv posts.csv --check-interval 30
```

- 毎日モードをテスト（実投稿しない）

```bash
python threads_auto_post.py --mode daily --csv daily_posts.csv --dry-run
```

- ログイン待ち入力をしない（自動起動向け）

```bash
python threads_auto_post.py --mode daily --csv daily_posts.csv --no-login-prompt
```

---

## 注意

- Threads 側の画面仕様変更で動かなくなることがあります。
- 自動化の利用は、必ず Threads の利用規約とポリシーを確認して行ってください。