"""
ارائه‌دهنده‌ی API ابری (سازگار با OpenAI / OpenRouter).

مدل محلی روی CPU رانر کند و متوسط است؛ این ماژول یک مسیر **انتخابی** اضافه
می‌کند که همان تحلیل را با یک مدل بزرگ‌تر و سریع‌تر انجام می‌دهد — بدون اینکه
هیچ پاسخی به آن وابسته باشد.

فعال‌سازی: فقط با گذاشتن یک توکن. بدون توکن، هیچ درخواستی به بیرون نمی‌رود و
دکمه‌ی API در ربات نمایش داده نمی‌شود.

متغیرهای محیطی:
    API_KEY        کلید سرویس (اگر خالی باشد، API غیرفعال است)
    API_MODEL      نام مدل                        (پیش‌فرض: qwen/qwen2.5-72b-instruct)
    API_BASE_URL   آدرس سازگار با OpenAI          (پیش‌فرض: https://openrouter.ai/api/v1)
    API_TIMEOUT    مهلت هر درخواست (ثانیه)        (پیش‌فرض: 120)
    API_MAX_TOKENS حداکثر توکن پاسخ               (پیش‌فرض: 700)

هر سرویس سازگار با OpenAI کار می‌کند؛ کافی است سه متغیر را عوض کنی
(مثلاً Together، Groq، DeepSeek، یا یک gateway داخلی).
"""

from __future__ import annotations

import os
import time

import requests

API_KEY = (
    os.getenv("API_KEY")
    or os.getenv("OPENROUTER_API_KEY")
    or os.getenv("OPENAI_API_KEY")
    or ""
).strip()
API_MODEL = os.getenv("API_MODEL", "qwen/qwen2.5-72b-instruct").strip()
API_BASE_URL = os.getenv("API_BASE_URL", "https://openrouter.ai/api/v1").rstrip("/")
API_TIMEOUT = int(os.getenv("API_TIMEOUT", "120"))
API_MAX_TOKENS = int(os.getenv("API_MAX_TOKENS", "700"))
APP_URL = os.getenv("APP_URL", "https://github.com")
APP_NAME = os.getenv("APP_NAME", "Amoozesh-Bot")

LAST_STATS: dict = {}
LAST_ERROR = ""


class APIError(RuntimeError):
    """خطای سرویس ابری (شبکه، کلید، سهمیه یا پاسخ نامعتبر)."""


def enabled() -> bool:
    """API فقط وقتی فعال است که کلید داشته باشیم."""
    return bool(API_KEY)


def model_label() -> str:
    return API_MODEL or "api"


def _headers() -> dict:
    headers = {
        "Authorization": f"Bearer {API_KEY}",
        "Content-Type": "application/json",
    }
    # OpenRouter برای رتبه‌بندی این دو هدر را می‌خواهد؛ برای بقیه سرویس‌ها بی‌ضرر است.
    headers["HTTP-Referer"] = APP_URL
    headers["X-Title"] = APP_NAME
    return headers


def generate(messages: list[dict], *, max_tokens: int | None = None,
             temperature: float = 0.2, timeout: int | None = None) -> str:
    """یک پاسخ متنی از سرویس ابری می‌گیرد.

    خطاها به APIError تبدیل می‌شوند تا مسیر ربات یکسان بماند.
    """
    global LAST_ERROR
    if not enabled():
        raise APIError("کلید API تنظیم نشده است.")

    payload = {
        "model": API_MODEL,
        "messages": messages,
        "max_tokens": API_MAX_TOKENS if max_tokens is None else max_tokens,
        "temperature": temperature,
    }
    url = f"{API_BASE_URL}/chat/completions"
    started = time.time()

    response = None
    for attempt in range(2):
        try:
            response = requests.post(
                url, json=payload, headers=_headers(), timeout=timeout or API_TIMEOUT
            )
        except requests.Timeout as exc:
            raise APIError("سرویس API در زمان مجاز پاسخ نداد.") from exc
        except requests.RequestException as exc:
            raise APIError(f"ارتباط با سرویس API برقرار نشد: {exc}") from exc

        if response.status_code in (429, 500, 502, 503, 504) and attempt == 0:
            time.sleep(2)
            continue
        break

    assert response is not None
    if response.status_code == 401:
        raise APIError("کلید API پذیرفته نشد (۴۰۱).")
    if response.status_code == 402:
        raise APIError("اعتبار حساب API تمام شده است (۴۰۲).")
    if response.status_code == 429:
        raise APIError("سهمیه‌ی سرویس API پر شده است (۴۲۹)؛ بعداً امتحان کن.")
    if response.status_code != 200:
        LAST_ERROR = f"HTTP {response.status_code}: {response.text[:160]}"
        raise APIError(f"سرویس API خطا داد (HTTP {response.status_code}).")

    try:
        data = response.json()
    except ValueError as exc:
        raise APIError("پاسخ سرویس API قابل خواندن نبود.") from exc

    choices = data.get("choices") or []
    message = (choices[0] if choices else {}).get("message") or {}
    content = (message.get("content") or "").strip()
    usage = data.get("usage") or {}

    LAST_STATS.clear()
    LAST_STATS.update(
        {
            "model": data.get("model", API_MODEL),
            "eval_count": usage.get("completion_tokens", 0),
            "prompt_eval_count": usage.get("prompt_tokens", 0),
            "duration_s": round(time.time() - started, 2),
            "provider": "api",
        }
    )
    if not content:
        raise APIError("سرویس API پاسخ خالی برگرداند.")
    return content
