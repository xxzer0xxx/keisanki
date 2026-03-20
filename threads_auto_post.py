import argparse
import csv
import hashlib
import json
import time
from dataclasses import dataclass
from datetime import datetime, time as dt_time
from pathlib import Path
from typing import Any

try:
    from playwright.sync_api import (
        Page,
        TimeoutError as PlaywrightTimeoutError,
        sync_playwright,
    )
except ModuleNotFoundError:
    Page = Any  # type: ignore[misc,assignment]
    PlaywrightTimeoutError = TimeoutError  # type: ignore[assignment]
    sync_playwright = None


DATE_FORMATS = ("%Y-%m-%d %H:%M", "%Y/%m/%d %H:%M")
TIME_FORMAT = "%H:%M"


@dataclass
class ScheduledPost:
    post_id: str
    run_at: datetime
    text: str


@dataclass
class DailyPost:
    post_id: str
    run_time: dt_time
    text: str


@dataclass
class PostedState:
    once_posted_ids: set[str]
    daily_last_posted: dict[str, str]


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


def parse_time(value: str) -> dt_time:
    cleaned = value.strip()
    try:
        return datetime.strptime(cleaned, TIME_FORMAT).time()
    except ValueError as error:
        raise ValueError(f"時刻形式が不正です: {value} / 例: 09:30") from error


def build_post_id(run_at: datetime, text: str) -> str:
    raw = f"{run_at.isoformat()}|{text}".encode("utf-8")
    return hashlib.sha256(raw).hexdigest()[:16]


def build_daily_post_id(run_time: dt_time, text: str) -> str:
    raw = f"{run_time.isoformat()}|{text}".encode("utf-8")
    return hashlib.sha256(raw).hexdigest()[:16]


def load_once_posts(csv_path: Path) -> list[ScheduledPost]:
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


def load_daily_posts(csv_path: Path) -> list[DailyPost]:
    if not csv_path.exists():
        raise FileNotFoundError(f"CSVファイルが見つかりません: {csv_path}")

    with csv_path.open("r", encoding="utf-8-sig", newline="") as file:
        reader = csv.DictReader(file)
        required = {"time", "text"}
        if not reader.fieldnames or not required.issubset(set(reader.fieldnames)):
            raise ValueError(
                "dailyモードではCSVヘッダー time,text が必要です。"
            )

        posts: list[DailyPost] = []
        for row_number, row in enumerate(reader, start=2):
            raw_time = (row.get("time") or "").strip()
            raw_text = (row.get("text") or "").strip()
            if not raw_time or not raw_text:
                print(f"[SKIP] {row_number}行目: 空行または必須値不足")
                continue

            run_time = parse_time(raw_time)
            post_id = build_daily_post_id(run_time, raw_text)
            posts.append(DailyPost(post_id=post_id, run_time=run_time, text=raw_text))

    posts.sort(key=lambda item: item.run_time)
    return posts


def load_posted_state(state_path: Path) -> PostedState:
    if not state_path.exists():
        return PostedState(once_posted_ids=set(), daily_last_posted={})

    with state_path.open("r", encoding="utf-8") as file:
        data = json.load(file)

    if isinstance(data, list):
        # 旧バージョン互換: 以前は投稿済みID配列のみ保存していた
        return PostedState(once_posted_ids={str(item) for item in data}, daily_last_posted={})

    if not isinstance(data, dict):
        return PostedState(once_posted_ids=set(), daily_last_posted={})

    once_raw = data.get("once_posted_ids", [])
    daily_raw = data.get("daily_last_posted", {})
    once_posted_ids = {str(item) for item in once_raw} if isinstance(once_raw, list) else set()
    daily_last_posted = (
        {str(key): str(value) for key, value in daily_raw.items()}
        if isinstance(daily_raw, dict)
        else {}
    )
    return PostedState(
        once_posted_ids=once_posted_ids,
        daily_last_posted=daily_last_posted,
    )


def save_posted_state(state_path: Path, state: PostedState) -> None:
    state_path.parent.mkdir(parents=True, exist_ok=True)
    with state_path.open("w", encoding="utf-8") as file:
        json.dump(
            {
                "once_posted_ids": sorted(state.once_posted_ids),
                "daily_last_posted": state.daily_last_posted,
            },
            file,
            ensure_ascii=False,
            indent=2,
        )


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


def monitor_once_posts(
    posts: list[ScheduledPost],
    state_path: Path,
    profile_dir: Path,
    interval_seconds: int,
    dry_run: bool,
) -> None:
    if sync_playwright is None:
        raise RuntimeError(
            "Playwrightが未インストールです。READMEの手順で準備してください。"
        )

    posted_state = load_posted_state(state_path)
    pending = [p for p in posts if p.post_id not in posted_state.once_posted_ids]

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
                        posted_state.once_posted_ids.add(post.post_id)
                        save_posted_state(state_path, posted_state)
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


def monitor_daily_posts(
    posts: list[DailyPost],
    state_path: Path,
    profile_dir: Path,
    interval_seconds: int,
    dry_run: bool,
) -> None:
    if sync_playwright is None:
        raise RuntimeError(
            "Playwrightが未インストールです。READMEの手順で準備してください。"
        )

    if not posts:
        print("dailyモードの投稿予定がありません。")
        return

    posted_state = load_posted_state(state_path)
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

        print("毎日モードで監視を開始しました。Ctrl+C で終了できます。")
        try:
            while True:
                now = datetime.now()
                today_key = now.date().isoformat()

                for post in posts:
                    run_at_today = now.replace(
                        hour=post.run_time.hour,
                        minute=post.run_time.minute,
                        second=0,
                        microsecond=0,
                    )
                    last_posted_day = posted_state.daily_last_posted.get(post.post_id)

                    if now < run_at_today:
                        continue
                    if last_posted_day == today_key:
                        continue

                    print(f"[POST-DAILY] {post.run_time:%H:%M} / {post.text[:40]}")
                    success = create_post(page, post.text, dry_run=dry_run)
                    if success:
                        posted_state.daily_last_posted[post.post_id] = today_key
                        save_posted_state(state_path, posted_state)
                        print("[OK] 本日の投稿処理が完了しました。")
                    else:
                        print("[WARN] 投稿に失敗。次のループで再試行します。")

                time.sleep(interval_seconds)
        except KeyboardInterrupt:
            print("\n停止しました。次回起動時に当日未投稿分のみ再開されます。")
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
    parser.add_argument(
        "--mode",
        choices=("once", "daily"),
        default="once",
        help="once: 日時指定で1回投稿 / daily: 毎日同じ時刻に投稿",
    )
    args = parser.parse_args()

    if args.check_interval < 5:
        raise ValueError("--check-interval は5秒以上を指定してください。")

    csv_path = Path(args.csv)
    state_path = Path(args.state)
    profile_dir = Path(args.profile_dir)

    if args.mode == "once":
        posts = load_once_posts(csv_path)
        print(f"{len(posts)}件の投稿予定を読み込みました（onceモード）。")
        monitor_once_posts(
            posts=posts,
            state_path=state_path,
            profile_dir=profile_dir,
            interval_seconds=args.check_interval,
            dry_run=args.dry_run,
        )
    else:
        posts = load_daily_posts(csv_path)
        print(f"{len(posts)}件の投稿予定を読み込みました（dailyモード）。")
        monitor_daily_posts(
            posts=posts,
            state_path=state_path,
            profile_dir=profile_dir,
            interval_seconds=args.check_interval,
            dry_run=args.dry_run,
        )


if __name__ == "__main__":
    main()
