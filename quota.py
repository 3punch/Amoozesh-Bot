"""
سهمیه‌ی روزانه‌ی هر کاربر.

هر کاربر در هر روز فقط تعداد محدودی درخواست «مدل» دارد:

    deep  ۳ بار در روز  →  تحلیل با مدل محلی (Ollama روی runner)
    api   ۱ بار در روز  →  تحلیل با API ابری (دقیق‌تر و سریع‌تر)

روز بر اساس نیمه‌شب **تهران** عوض می‌شود، نه UTC.

چالش اصلی: ربات در GitHub Actions اجرا می‌شود و هر اجرا یک ماشین تازه است؛ پس
شمارنده‌ها باید بیرون از فایل‌سیستم موقت نگه‌داری شوند. دو لایه داریم:

    ۱) فایل محلی  `.state/quotas.json`  (برای اجرای محلی و همین نمونه)
    ۲) نسخه‌ی مرجع روی شاخه‌ی `bot-state` در همان ریپو (با Contents API گیت‌هاب)

لایه‌ی دوم فقط وقتی فعال می‌شود که `GITHUB_TOKEN` و `GITHUB_REPOSITORY` موجود
باشند و `QUOTA_PERSIST` صفر نباشد. اگر شبکه یا توکن نبود، ربات به شمارنده‌ی
محلی تکیه می‌کند و هیچ‌وقت به‌خاطر سهمیه از کار نمی‌افتد.

چرا شاخه‌ی جدا؟ چون `bot.yml` با push روی `main` دوباره راه می‌افتد و هر بار
نوشتن سهمیه، ربات فعال را ری‌استارت می‌کرد.
"""

from __future__ import annotations

import base64
import json
import logging
import os
import threading
from datetime import date, datetime, timedelta, timezone

import requests

log = logging.getLogger("amoozeshbot.quota")

LIMITS = {"deep": 3, "api": 1}
KIND_LABEL = {"deep": "تحلیل با مدل محلی", "api": "تحلیل با API"}

STATE_PATH = os.getenv("QUOTA_STATE_PATH", ".state/quotas.json")
STATE_BRANCH = os.getenv("QUOTA_STATE_BRANCH", "bot-state")
STATE_FILE = os.getenv("QUOTA_STATE_FILE", ".state/quotas.json")
PERSIST = os.getenv("QUOTA_PERSIST", "1") != "0"
KEEP_DAYS = 3

try:  # دقیق‌ترین حالت
    from zoneinfo import ZoneInfo

    TEHRAN = ZoneInfo("Asia/Tehran")
except Exception:  # pragma: no cover - روی ایمیج‌های بدون tzdata
    TEHRAN = timezone(timedelta(hours=3, minutes=30), "Asia/Tehran")


def today_key(now: datetime | None = None) -> str:
    """کلید روز به وقت تهران (YYYY-MM-DD)."""
    moment = now or datetime.now(timezone.utc)
    if moment.tzinfo is None:
        moment = moment.replace(tzinfo=timezone.utc)
    return moment.astimezone(TEHRAN).strftime("%Y-%m-%d")


def reset_text() -> str:
    """متن انسانی برای زمان آزادشدن سهمیه."""
    return "نیمه‌شب به وقت تهران"


def _load_json(path: str) -> dict:
    try:
        with open(path, encoding="utf-8") as handle:
            data = json.load(handle)
        return data if isinstance(data, dict) else {}
    except (OSError, ValueError):
        return {}


def _save_json(path: str, data: dict) -> None:
    directory = os.path.dirname(path)
    if directory:
        os.makedirs(directory, exist_ok=True)
    temporary = f"{path}.tmp"
    with open(temporary, "w", encoding="utf-8") as handle:
        json.dump(data, handle, ensure_ascii=False, indent=2)
    os.replace(temporary, path)


# ---------------------------------------------------------------- پشتیبان گیت‌هاب


class GitHubState:
    """نگه‌داری شمارنده‌ها روی شاخه‌ی `bot-state` با Contents API.

    شاخه با اولین PUT خودکار ساخته می‌شود؛ اگر شاخه نبود، از `main` منشعب می‌شود.
    """

    def __init__(self, repository: str, token: str, branch: str = STATE_BRANCH,
                 path: str = STATE_FILE):
        self.repository = repository
        self.token = token
        self.branch = branch
        self.path = path.lstrip("./")
        self.sha: str | None = None
        self.api = f"https://api.github.com/repos/{repository}/contents/{self.path}"
        self.headers = {
            "Authorization": f"Bearer {token}",
            "Accept": "application/vnd.github+json",
            "X-GitHub-Api-Version": "2022-11-28",
        }

    def load(self) -> dict:
        try:
            response = requests.get(
                self.api, params={"ref": self.branch}, headers=self.headers, timeout=15
            )
            if response.status_code == 404:
                return {}
            response.raise_for_status()
            payload = response.json()
            self.sha = payload.get("sha")
            content = base64.b64decode(payload.get("content", "") or "").decode("utf-8")
            data = json.loads(content)
            return data if isinstance(data, dict) else {}
        except (requests.RequestException, ValueError, KeyError) as exc:
            log.warning("خواندن سهمیه از گیت‌هاب ناموفق بود: %s", exc)
            return {}

    def save(self, data: dict) -> bool:
        body = {
            "message": f"quota state {today_key()}",
            "content": base64.b64encode(
                json.dumps(data, ensure_ascii=False, indent=2).encode("utf-8")
            ).decode("ascii"),
            "branch": self.branch,
        }
        if self.sha:
            body["sha"] = self.sha
        try:
            response = requests.put(self.api, json=body, headers=self.headers, timeout=20)
            if response.status_code in (409, 422) and "sha" in body:
                # کسی دیگر زودتر نوشته؛ دوباره بخوان و یک‌بار دیگر تلاش کن
                fresh = self.load()
                merged = {**fresh, **{k: v for k, v in data.items() if k not in fresh}}
                return self._put(merged)
            response.raise_for_status()
            self.sha = (response.json().get("content") or {}).get("sha", self.sha)
            return True
        except (requests.RequestException, ValueError) as exc:
            log.warning("ذخیره‌ی سهمیه در گیت‌هاب ناموفق بود: %s", exc)
            return False

    def _put(self, data: dict) -> bool:
        body = {
            "message": f"quota state {today_key()}",
            "content": base64.b64encode(
                json.dumps(data, ensure_ascii=False, indent=2).encode("utf-8")
            ).decode("ascii"),
            "branch": self.branch,
            "sha": self.sha,
        }
        try:
            response = requests.put(self.api, json=body, headers=self.headers, timeout=20)
            response.raise_for_status()
            self.sha = (response.json().get("content") or {}).get("sha", self.sha)
            return True
        except (requests.RequestException, ValueError) as exc:
            log.warning("ذخیره‌ی دوم سهمیه هم ناموفق بود: %s", exc)
            return False


# ---------------------------------------------------------------- انبار سهمیه


class QuotaStore:
    """شمارنده‌ی روزانه برای هر کاربر و هر نوع درخواست."""

    def __init__(self, path: str = STATE_PATH, remote: GitHubState | None = None,
                 persist_remote: bool | None = None):
        self.path = path
        self.remote = remote
        self.persist_remote = (
            PERSIST if persist_remote is None else (persist_remote and PERSIST)
        )
        self._lock = threading.Lock()
        self._data: dict[str, dict[str, dict[str, int]]] = _load_json(path)

    # ---------- همگام‌سازی

    def sync(self) -> None:
        """شمارنده‌های گیت‌هاب را با محلی ادغام می‌کند (بیشترین مقدار برنده است)."""
        if not (self.remote and self.persist_remote):
            return
        remote = self.remote.load()
        if not remote:
            return
        with self._lock:
            for day, users in remote.items():
                if not isinstance(users, dict):
                    continue
                target = self._data.setdefault(day, {})
                for user, counts in users.items():
                    if not isinstance(counts, dict):
                        continue
                    current = target.setdefault(str(user), {})
                    for kind, value in counts.items():
                        try:
                            value = int(value)
                        except (TypeError, ValueError):
                            continue
                        current[kind] = max(current.get(kind, 0), value)
            self._save()

    def _save(self) -> None:
        """نوشتن محلی + ارسال به گیت‌هاب (بدون بلوکه‌کردن ربات)."""
        self._prune()
        try:
            _save_json(self.path, self._data)
        except OSError as exc:
            log.warning("نوشتن فایل سهمیه ناموفق بود: %s", exc)
        if self.remote and self.persist_remote:
            snapshot = json.loads(json.dumps(self._data))
            threading.Thread(target=self.remote.save, args=(snapshot,), daemon=True).start()

    def _prune(self) -> None:
        today = date.fromisoformat(today_key())
        for day in list(self._data):
            try:
                old = date.fromisoformat(day)
            except ValueError:
                self._data.pop(day, None)
                continue
            if (today - old).days > KEEP_DAYS:
                self._data.pop(day, None)

    # ---------- کار با سهمیه

    def used(self, user_id, kind: str) -> int:
        try:
            return int(self._data.get(today_key(), {}).get(str(user_id), {}).get(kind, 0))
        except (TypeError, ValueError):
            return 0

    def limit(self, kind: str) -> int:
        return LIMITS.get(kind, 0)

    def remaining(self, user_id, kind: str) -> int:
        return max(0, self.limit(kind) - self.used(user_id, kind))

    def consume(self, user_id, kind: str) -> bool:
        """اگر سهمیه مانده باشد یکی کم می‌کند و True برمی‌گرداند."""
        if kind not in LIMITS:
            return False
        with self._lock:
            if self.remaining(user_id, kind) <= 0:
                return False
            day = self._data.setdefault(today_key(), {})
            user = day.setdefault(str(user_id), {})
            user[kind] = user.get(kind, 0) + 1
            self._save()
            return True

    def refund(self, user_id, kind: str) -> None:
        """اگر درخواست به خطای زیرساخت خورد، سهمیه برمی‌گردد."""
        with self._lock:
            user = self._data.get(today_key(), {}).get(str(user_id))
            if not user or user.get(kind, 0) <= 0:
                return
            user[kind] -= 1
            if user[kind] == 0:
                user.pop(kind, None)
            self._save()

    def reset(self, user_id=None) -> None:
        """پاک‌کردن شمارنده (برای تست یا ریست دستی)."""
        with self._lock:
            if user_id is None:
                self._data.pop(today_key(), None)
            else:
                self._data.get(today_key(), {}).pop(str(user_id), None)
            self._save()

    def summary(self, user_id) -> str:
        """«۲ از ۳» برای دکمه‌ها."""
        return f"{self.remaining(user_id, 'deep')} از {self.limit('deep')}"


def build_remote() -> GitHubState | None:
    token = os.getenv("GITHUB_TOKEN") or os.getenv("GH_TOKEN")
    repository = os.getenv("GITHUB_REPOSITORY")
    if not (token and repository and PERSIST):
        return None
    return GitHubState(repository, token)


def create_store(path: str = STATE_PATH) -> QuotaStore:
    """انبار سهمیه با پشتیبان گیت‌هاب (اگر در Actions باشیم)."""
    store = QuotaStore(path=path, remote=build_remote())
    try:
        store.sync()
    except Exception as exc:  # noqa: BLE001 - سهمیه نباید ربات را بخواباند
        log.warning("همگام‌سازی سهمیه ناموفق بود: %s", exc)
    return store
