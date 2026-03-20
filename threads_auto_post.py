import argparse
import csv
import hashlib
import json
import time
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path

from playwright.sync_api import Page, TimeoutError as PlaywrightTimeoutError, sync_playwright


DATE_FORMATS = ("%Y-%m-%d %H:%M", "%Y/%m/%d %H:%M")


@dataclass
class ScheduledPost:
    post_id: str
    run_at: datetime
    text: str


def parse_datetime(value: str) -> datetime:
    cleaned = value.strip()
    for date_format in DATE_FORMATS:
        try:
            return datetime.strptime(cleaned, date_format)
        except ValueError:
            continue
    raise ValueError(
        f"日時形式が不正です: {value} / 例: 2026-03-20 21:30"
    )


def build_post_id(run_at: datetime, text: str) -> str:
    raw = f"{run_at.isoformat()}|{text}".encode("utf-8")
    return hashlib.sha256(raw).hexdigest()[:16]


def load_posts(csv_path: Path) -> list[ScheduledPost]:
    if not csv_path.exists():
        raise FileNotFoundError(f"CSVファイルが見つかりません: {csv_path}")

    with csv_path.open("r", encoding="utf-8-sig", newline="") as file:
        reader = csv.DictReader(file)
        required = {"datetime", "text"}
        if not reader.fieldnames or not required.issubset(set(reader.fieldnames)):
            raise ValueError(
                "CSVのヘッダーは datetime,text が必要です。"
            )

        posts: list[ScheduledPost] = []
        for row_number, row in enumerate(reader, start=2):
            raw_dt = (row.get("datetime") or "").strip()
            raw_text = (row.get("text") or "").strip()
            if not raw_dt or not raw_text:
                print(f"[SKIP] {row_number}行目: 空行または必須値不足")
                continue

            run_at = parse_datetime(raw_dt)
            post_id = build_post_id(run_at, raw_text)
            posts.append(ScheduledPost(post_id=post_id, run_at=run_at, text=raw_text))

    posts.sort(key=lambda item: item.run_at)
    return posts


def load_posted_ids(state_path: Path) -> set[str]:
    if not state_path.exists():
        return set()
    with state_path.open("r", encoding="utf-8") as file:
        data = json.load(file)
    if not isinstance(data, list):
        return set()
    return {str(item) for item in data}


def save_posted_ids(state_path: Path, posted_ids: set[str]) -> None:
    state_path.parent.mkdir(parents=True, exist_ok=True)
    with state_path.open("w", encoding="utf-8") as file:
        json.dump(sorted(posted_ids), file, ensure_ascii=False, indent=2)


def first_visible(page: Page, selectors: list[str]):
    for selector in selectors:
        locator = page.locator(selector).first
        try:
            if locator.is_visible(timeout=1500):
                return locator
        except PlaywrightTimeoutError:
            continue
    return None


def create_post(page: Page, text: str, dry_run: bool) -> bool:
    page.goto("https://www.threads.net/", wait_until="domcontentloaded")

    compose = first_visible(
        page,
        [
            "button[aria-label*='新規']",
            "button[aria-label*='作成']",
            "button[aria-label*='thread' i]",
            "button[aria-label*='new' i]",
            "a[href*='/new']",
            "button:has-text('新規スレッド')",
            "button:has-text('New thread')",
        ],
    )
    if compose is None:
        print("[ERROR] 新規投稿ボタンが見つかりません。ログイン状態を確認してください。")
        return False
    compose.click()

    text_box = first_visible(
        page,
        [
            "div[role='textbox']",
            "textarea",
            "[contenteditable='true']",
        ],
    )
    if text_box is None:
        print("[ERROR] 投稿入力欄が見つかりません。画面UIが変更された可能性があります。")
        return False

    text_box.click()
    text_box.fill(text)

    if dry_run:
        print("[DRY-RUN] 投稿は送信せず入力だけ行いました。")
        return True

    post_button = first_visible(
        page,
        [
            "button:has-text('投稿')",
            "button:has-text('Post')",
            "div[role='dialog'] button[type='submit']",
        ],
    )
    if post_button is None:
        print("[ERROR] 投稿ボタンが見つかりませんでした。")
        return False

    post_button.click()
    time.sleep(2)
    return True


def monitor_and_post(
    posts: list[ScheduledPost],
    state_path: Path,
    profile_dir: Path,
    interval_seconds: int,
    dry_run: bool,
) -> None:
    posted_ids = load_posted_ids(state_path)
    pending = [p for p in posts if p.post_id not in posted_ids]

    if not pending:
        print("投稿予定はすべて完了済みです。")
        return

    print("ブラウザを開きます。Threadsにログインしてから、Enterキーを押してください。")

    with sync_playwright() as p:
        context = p.chromium.launch_persistent_context(
            user_data_dir=str(profile_dir),
            headless=False,
            locale="ja-JP",
            viewport={"width": 1280, "height": 800},
        )
        page = context.new_page()
        page.goto("https://www.threads.net/", wait_until="domcontentloaded")
        input("ログイン完了後、ここでEnterを押してください > ")

        print("監視を開始しました。Ctrl+C で終了できます。")
        try:
            while True:
                now = datetime.now()
                due = [post for post in pending if post.run_at <= now]
                for post in due:
                    print(f"[POST] {post.run_at:%Y-%m-%d %H:%M} / {post.text[:40]}")
                    success = create_post(page, post.text, dry_run=dry_run)
                    if success:
                        posted_ids.add(post.post_id)
                        save_posted_ids(state_path, posted_ids)
                        pending.remove(post)
                        print("[OK] 投稿処理が完了しました。")
                    else:
                        print("[WARN] 投稿に失敗。次のループで再試行します。")

                if not pending:
                    print("すべての投稿が完了しました。")
                    break
                time.sleep(interval_seconds)
        except KeyboardInterrupt:
            print("\n停止しました。次回起動時に未投稿分のみ再開されます。")
        finally:
            context.close()


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Threads予約投稿ツール（初回ログイン手動、以後自動）"
    )
    parser.add_argument("--csv", default="posts.csv", help="投稿予約CSV（default: posts.csv）")
    parser.add_argument(
        "--state",
        default=".threads_state/posted.json",
        help="投稿済み履歴JSON（default: .threads_state/posted.json）",
    )
    parser.add_argument(
        "--profile-dir",
        default=".threads_profile",
        help="ブラウザプロフィール保存先（default: .threads_profile）",
    )
    parser.add_argument(
        "--check-interval",
        type=int,
        default=20,
        help="投稿判定間隔（秒）",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="実投稿せず入力だけ行うテストモード",
    )
    args = parser.parse_args()

    if args.check_interval < 5:
        raise ValueError("--check-interval は5秒以上を指定してください。")

    csv_path = Path(args.csv)
    state_path = Path(args.state)
    profile_dir = Path(args.profile_dir)

    posts = load_posts(csv_path)
    print(f"{len(posts)}件の投稿予定を読み込みました。")
    monitor_and_post(
        posts=posts,
        state_path=state_path,
        profile_dir=profile_dir,
        interval_seconds=args.check_interval,
        dry_run=args.dry_run,
    )


if __name__ == "__main__":
    main()
