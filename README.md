# Threads 自動投稿ツール（かんたん版）

プログラミング知識がなくても使えるように、**投稿予約CSV**を読み込んで自動投稿するツールです。

## できること

- 指定日時になったら Threads に自動投稿
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

---

## 3) 実行する

```bash
source .venv/bin/activate
python threads_auto_post.py --csv posts.csv
```

実行後、ブラウザが開きます。  
Threads にログインしたら、ターミナルで Enter キーを押してください。  
その後は指定時刻になったら自動投稿されます。

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

---

## 注意

- Threads 側の画面仕様変更で動かなくなることがあります。
- 自動化の利用は、必ず Threads の利用規約とポリシーを確認して行ってください。