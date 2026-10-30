"""
کلاینت مدل محلی (Ollama) — جایگزین کامل OpenRouter.

مدل روی همان ماشینی اجرا می‌شود که ربات روی آن است و از طریق HTTP محلی
(پیش‌فرض http://127.0.0.1:11434) صدا زده می‌شود. هیچ API key ای لازم نیست.

متغیرهای محیطی:
    MODEL_NAME     نام مدل در Ollama            (پیش‌فرض: qwen2.5:7b)
    THINK          حالت استدلال مدل‌های Qwen3    (۰ = خاموش، پیش‌فرض)
    OLLAMA_HOST    آدرس سرویس Ollama            (پیش‌فرض: http://127.0.0.1:11434)
    NUM_CTX        اندازه پنجره‌ی زمینه          (پیش‌فرض: 8192)
    MAX_TOKENS     حداکثر توکن پاسخ              (پیش‌فرض: 320)
    TEMPERATURE    دمای نمونه‌گیری                (پیش‌فرض: 0.2)
    LLM_TIMEOUT    مهلت هر درخواست به ثانیه      (پیش‌فرض: 300)
    OLLAMA_KEEP_ALIVE  مدت نگه‌داشتن مدل در RAM   (پیش‌فرض: 6h)
"""

from __future__ import annotations

import os
import time

import requests

MODEL_NAME = os.getenv("MODEL_NAME", "qwen2.5:7b")
# مدل‌های Qwen3 به‌طور پیش‌فرض «فکر کردن» طولانی دارند که برای پاسخ کوتاه
# فارسی فقط تأخیر تولید می‌کند؛ خاموشش می‌کنیم.
THINK = os.getenv("THINK", "0") == "1"


def is_thinking_model(name: str | None = None) -> bool:
    """مدل‌های Qwen3 در حالت خاموش هم نیاز به «/no_think» دارند."""
    return (name or MODEL_NAME).lower().startswith("qwen3")
OLLAMA_HOST = os.getenv("OLLAMA_HOST", "http://127.0.0.1:11434").rstrip("/")
NUM_CTX = int(os.getenv("NUM_CTX", "8192"))
MAX_TOKENS = int(os.getenv("MAX_TOKENS", "320"))
TEMPERATURE = float(os.getenv("TEMPERATURE", "0.2"))
LLM_TIMEOUT = int(os.getenv("LLM_TIMEOUT", "300"))
KEEP_ALIVE = os.getenv("OLLAMA_KEEP_ALIVE", "6h")

# آخرین آمار پاسخ (برای لاگ و اندازه‌گیری سرعت)
LAST_STATS: dict = {}


class LLMError(RuntimeError):
    """خطای ارتباط با مدل محلی."""


def _options(max_tokens: int | None = None, temperature: float | None = None) -> dict:
    return {
        "num_ctx": NUM_CTX,
        "num_predict": MAX_TOKENS if max_tokens is None else max_tokens,
        "temperature": TEMPERATURE if temperature is None else temperature,
        "top_p": 0.9,
        "repeat_penalty": 1.1,
    }


def wait_for_server(timeout: int = 180, interval: float = 2.0) -> bool:
    """منتظر بالا آمدن سرویس Ollama می‌ماند (مفید در GitHub Actions)."""
    deadline = time.time() + timeout
    while time.time() < deadline:
        try:
            r = requests.get(f"{OLLAMA_HOST}/api/tags", timeout=5)
            if r.status_code == 200:
                return True
        except requests.RequestException:
            pass
        time.sleep(interval)
    return False


def model_is_available() -> bool:
    try:
        r = requests.get(f"{OLLAMA_HOST}/api/tags", timeout=10)
        r.raise_for_status()
        names = {m.get("name", "") for m in r.json().get("models", [])}
    except (requests.RequestException, ValueError):
        return False
    def canon(name: str) -> str:
        return name[:-7] if name.endswith(":latest") else name

    target = canon(MODEL_NAME)
    for name in names:
        candidate = canon(name)
        if candidate == target:
            return True
        # نام‌های دارای namespace مثل library/gemma3:4b
        if "/" in candidate and candidate.split("/", 1)[1] == target:
            return True
    return False


def generate(
    messages: list[dict],
    *,
    max_tokens: int | None = None,
    temperature: float | None = None,
    timeout: int | None = None,
) -> str:
    """یک پاسخ متنی از مدل محلی می‌گیرد. در خطا LLMError می‌اندازد."""
    payload = {
        "model": MODEL_NAME,
        "messages": messages,
        "stream": False,
        "keep_alive": KEEP_ALIVE,
        "think": THINK,
        "options": _options(max_tokens, temperature),
    }
    url = f"{OLLAMA_HOST}/api/chat"

    try:
        resp = requests.post(url, json=payload, timeout=timeout or LLM_TIMEOUT)
    except requests.Timeout as exc:
        raise LLMError("مدل محلی در زمان مجاز پاسخ نداد.") from exc
    except requests.RequestException as exc:
        raise LLMError(f"ارتباط با سرویس Ollama برقرار نشد: {exc}") from exc

    if resp.status_code == 404:
        raise LLMError(
            f"مدل «{MODEL_NAME}» روی Ollama نصب نیست. دستور «ollama pull {MODEL_NAME}» را اجرا کنید."
        )
    if resp.status_code != 200:
        raise LLMError(f"Ollama خطا برگرداند (HTTP {resp.status_code}): {resp.text[:200]}")

    try:
        data = resp.json()
    except ValueError as exc:
        raise LLMError("پاسخ Ollama قابل خواندن نبود.") from exc

    content = (data.get("message") or {}).get("content", "").strip()
    LAST_STATS.clear()
    LAST_STATS.update(
        {
            "model": data.get("model", MODEL_NAME),
            "eval_count": data.get("eval_count", 0),
            "prompt_eval_count": data.get("prompt_eval_count", 0),
            "duration_s": round(data.get("total_duration", 0) / 1e9, 2),
            "tok_per_s": round(
                (data.get("eval_count", 0) or 0)
                / max(data.get("eval_duration", 1) / 1e9, 0.001),
                1,
            ),
            "thinking": bool((data.get("message") or {}).get("thinking")),
        }
    )
    if not content:
        raise LLMError("مدل پاسخ خالی برگرداند.")

    done_reason = data.get("done_reason")
    if done_reason == "length":
        # پاسخ به سقف توکن خورده؛ به کاربر بفهمانیم ناقص است.
        content += "\n\n(پاسخ به سقف طول رسید. لطفاً سوال را کوتاه‌تر بپرسید.)"

    return content


def preload() -> bool:
    """مدل را از قبل در حافظه بار می‌کند تا اولین پاسخ کاربر سریع باشد."""
    try:
        requests.post(
            f"{OLLAMA_HOST}/api/generate",
            json={"model": MODEL_NAME, "prompt": "سلام", "stream": False, "keep_alive": KEEP_ALIVE,
                  "options": {"num_predict": 8, "num_ctx": 512}},
            timeout=LLM_TIMEOUT,
        )
        return True
    except requests.RequestException:
        return False
