"""
تست آفلاین: بدون نیاز به مدل و بدون تلگرام.

1) اندازه‌ی زمینه و انتخاب بخش‌های مرتبط را بررسی می‌کند.
2) با یک سرور جعلی Ollama، مسیر کامل «درخواست → پاسخ» و مدیریت خطا را تست می‌کند.

اجرا:
    python tests/test_offline.py
"""

import json
import os
import sys
import threading
from http.server import BaseHTTPRequestHandler, HTTPServer

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

FAILS = []


def check(name, cond, detail=""):
    print(("  ✅ " if cond else "  ❌ ") + name + (f" — {detail}" if detail and not cond else ""))
    if not cond:
        FAILS.append(name)


# ---------------------------------------------------------------- 1) retrieval

def test_retrieval():
    print("\n[۱] لایه‌ی بازیابی (retrieval)")
    from retrieval import DataStore, estimate_tokens, keywords, normalize, prioritize_comments

    store = DataStore(".")
    check("جدول دروس بارگذاری شد", store.courses is not None and len(store.courses) > 50)
    check("شناسنامه‌های استاد جدا شدند (۳۵ مورد)", len(store.professors) == 35,
          f"شد {len(store.professors)}")
    check("نرمال‌سازی ی/ك", normalize("علي كريمي") == "علی کریمی")
    check("اعداد فارسی", "1403" in normalize("ورودی ۱۴۰۳"))
    check("حذف کلمات پوچ", "استاد" not in keywords("استاد ایزدیخواه چطوره"))

    cases = [
        ("بهینه سازی خطی برای ورودی ۱۴۰۳ مجازه؟", "بهینه سازی خطی", False),
        ("استاد ایزدیخواه چطوره؟", "ایزدیخواه", True),
        ("ساختمان داده و الگوریتم ها با همامی", "همامی", True),
        ("سلام", "", False),
    ]
    for query, expect, want_prof in cases:
        ctx, st = store.build_context(query)
        short_q = query[:38]
        check(f"زمینه زیر بودجه ({short_q})", st["chars"] <= 9000, f"{st['chars']} کاراکتر")
        check(f"زمینه معنادار است ({short_q})", st["tokens"] > 200, f"~{st['tokens']} توکن")
        check(f"توکن برآوردی منطقی ({short_q})", estimate_tokens(ctx) == st["tokens"])
        if expect:
            check(f"بخش مرتبط پیدا شد: {expect}", expect in ctx)
        if want_prof:
            check(f"شناسنامه‌ی {expect} آورده شد", expect in ctx and "نظرات دانشجویان" in ctx)
        else:
            check(f"شناسنامه‌ی بی‌ربط حذف شد ({short_q})", "نظرات دانشجویان" not in ctx)
    print("\n  [تمیزکاری نظرات (رگرسیون: استاد آذر ابوالقاسمی)]")
    prof = next((p for p in store.professors if "ابوالقاسمی" in p.norm_name), None)
    check("شناسنامه‌ی آذر ابوالقاسمی پیدا شد", prof is not None)
    if prof:
        check("پیام‌های لینکی حذف شدند", prof.dropped_comments >= 1, f"{prof.dropped_comments}")
        check("نظر مفید ثبت شده", len(prof.comments) >= 5, f"{len(prof.comments)}")
        joined = " ".join(prof.comments)
        check("تبلیغ ربات/کانال حذف شد", "tahqiqat_bot" not in joined and "@unni_news" not in joined)
        check("لینک‌های t.me حذف شدند", "t.me/" not in joined)
        top = " ".join(prioritize_comments(prof.comments)[:3])
        check("ارزیابی واقعی در صدر نظرات است",
              any(w in top for w in ("نمره", "ارفاق", "استاد خوبی", "اره", "اکی", "حضور")), top[:80])

    q_prof = "استاد آذر ابوالقاسمی چطور استادی هستن"
    ctx, st = store.build_context(q_prof)
    check("برای سوال استادشناسی، قوانین ورودی‌ها حذف شد", "قوانین ورودی‌ها" not in ctx)
    check("دروس خود استاد آورده شد", "مبانی کارآفرینی" in ctx)
    check("ارزیابی واقعی به مدل می‌رسد", "ارفاق" in ctx or "استاد خوبی" in ctx)
    check("پرامپت کل کوچک است", st["tokens"] < 900, f"~{st['tokens']} توکن")
    check("کلیدواژه‌های پوچ حذف شدند", "استادی" not in st["keywords"] and "هستن" not in st["keywords"])

    q_course = "بهینه سازی خطی برای ورودی ۱۴۰۳ مجازه؟"
    ctx2, st2 = store.build_context(q_course)
    check("برای سوال مجاز بودن، قوانین ورودی‌ها حاضر است", "قوانین ورودی‌ها" in ctx2)

    print("\n  [بررسی قطعی مجاز بودن درس]")
    truth = [
        ("آیا بهینه سازی خطی برای ورودی ۱۴۰۲ مجازه؟", "مجاز نیست"),
        ("بهینه سازی خطی برای ورودی ۱۴۰۳ مجازه؟", "مجاز است"),
        ("بهینه سازی خطی برای ورودی ۱۴۰۴ مجازه؟", "مجاز نیست"),
        ("ساختمان داده و الگوریتم ها برای ورودی ۱۴۰۴ مجازه؟", "مجاز است"),
        ("ساختمان داده و الگوریتم ها برای ورودی ۱۴۰۳ مجازه؟", "مجاز نیست"),
        ("مقدمه ای بر داده کاوی برای ورودی ۱۴۰۱ مجازه؟", "مجاز است"),
        ("استاد ایزدیخواه چطوره؟", ""),
    ]
    for q, want in truth:
        got = store.check_eligibility(q)
        check(f"{q[:45]} → {want or 'بدون حکم'}", (want in got) if want else got == "",
              got or "خالی")
        if want:
            ctx, st = store.build_context(q)
            check("حکم قطعی اول زمینه است", ctx.startswith("### پاسخ قطعی") and st["verdict"] == got)

    print("  ℹ️  میانگین اندازه‌ی زمینه:", end=" ")
    sizes = [store.build_context(q)[1]["tokens"] for q, _, _ in cases]
    print(f"~{sum(sizes) // len(sizes)} توکن (سقف پنجره ۸۱۹۲)")


# ---------------------------------------------------------------- 2) ollama

class FakeOllama(BaseHTTPRequestHandler):
    mode = "ok"

    def log_message(self, *args):  # ساکت
        pass

    def _send(self, code, payload):
        body = json.dumps(payload).encode()
        self.send_response(code)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self):
        if self.path == "/api/tags":
            self._send(200, {"models": [{"name": "gemma3:4b"}]})
        else:
            self._send(404, {"error": "not found"})

    def do_POST(self):
        length = int(self.headers.get("Content-Length", 0))
        body = json.loads(self.rfile.read(length) or b"{}")
        if self.path == "/api/generate":
            return self._send(200, {"response": "ok", "done_reason": "stop"})
        if FakeOllama.mode == "500":
            return self._send(500, {"error": "boom"})
        assert body.get("model"), "مدل در payload نیست"
        return self._send(200, {
            "message": {"role": "assistant", "content": "نتیجه: مجاز است."},
            "done_reason": "stop",
        })


def test_llm_client():
    print("\n[۲] کلاینت مدل (با سرور جعلی Ollama)")
    server = HTTPServer(("127.0.0.1", 0), FakeOllama)
    port = server.server_thread_port = server.server_address[1]
    threading.Thread(target=server.serve_forever, daemon=True).start()

    os.environ["OLLAMA_HOST"] = f"http://127.0.0.1:{port}"
    os.environ["MODEL_NAME"] = "gemma3:4b"
    import importlib
    import llm
    importlib.reload(llm)

    check("wait_for_server", llm.wait_for_server(timeout=5))
    check("model_is_available", llm.model_is_available())
    check("preload", llm.preload())

    out = llm.generate([{"role": "user", "content": "سلام"}])
    check("پاسخ مدل دریافت شد", out == "نتیجه: مجاز است.", out)

    FakeOllama.mode = "500"
    try:
        llm.generate([{"role": "user", "content": "سلام"}])
        check("خطای HTTP به LLMError تبدیل شد", False)
    except llm.LLMError as exc:
        check("خطای HTTP به LLMError تبدیل شد", "500" in str(exc), str(exc))
    FakeOllama.mode = "ok"

    os.environ["MODEL_NAME"] = "gemma3:1b-missing"
    importlib.reload(llm)
    check("مدل نصب‌نشده تشخیص داده شد", not llm.model_is_available())
    server.shutdown()


# ---------------------------------------------------------------- 3) prompts

def test_prompts():
    print("\n[۳] پرامپت و شکستن پیام")
    from prompts import SYSTEM_PROMPT, build_messages

    msgs = build_messages("سوال تست", "زمینه تست")
    check("نقش system و user درست است",
          [m["role"] for m in msgs] == ["system", "user"])
    check("زمینه در system جای‌گذاری شد", "زمینه تست" in msgs[0]["content"])
    check("قواعد در پرامپت هست", "نتیجه: مجاز است" in SYSTEM_PROMPT)
    check("طول پرامپت پایه < ۱۵۰۰ کاراکتر", len(SYSTEM_PROMPT) < 1500)

    sys.argv = ["x"]
    import EntekhabVahedBot as bot

    parts = bot.split_message("خط\n" * 3000)
    check("متن بلند شکسته شد", len(parts) > 1, str(len(parts)))
    check("هر تکه ≤ ۴۰۰۰", all(len(p) <= 4000 for p in parts))
    check("بازسازی متن", "".join(parts).replace("\n", "") == ("خط" * 3000))
    check("متن کوتاه دست‌نخورده", bot.split_message("سلام") == ["سلام"])
    check("متن خالی", bot.split_message("") == [])


# ---------------------------------------------------------------- 3.5) fallback

def test_fallback():
    print("\n[۳.۵] پاسخ قطعی بدون مدل (fallback)")
    import fallback
    from retrieval import DataStore

    store = DataStore(".")

    verdict = fallback.answer(store, "بهینه سازی خطی برای ورودی ۱۴۰۴ مجازه؟")
    check("حکم مجاز بودن بدون مدل", verdict and "مجاز نیست" in verdict, str(verdict))

    card = fallback.answer(store, "استاد آذر ابوالقاسمی چطور استادی هستن")
    check("کارت استاد ساخته شد", card and "آذر ابوالقاسمی" in card)
    check("نمره‌دهی از فرم استخراج شد", "ارفاق" in card, card[:80])
    check("امتیازهای فرم استخراج شد", "۱۰/۱۰" in card)
    check("درس این ترم اضافه شد", "مبانی کارآفرینی" in card)

    course = fallback.answer(store, "ساختمان داده و الگوریتم ها")
    check("فهرست دروس بدون مدل", course and "ساختمان داده" in course)

    check("سوال بی‌ربط ⇒ None", fallback.answer(store, "سلام") is None)


# ---------------------------------------------------------------- 4) end-to-end

class FakeChat:
    type = "private"

    def __init__(self):
        self.actions = []

    async def send_action(self, action):
        self.actions.append(action)


class FakePlaceholder:
    """همان چیزی که تلگرام از reply_text برمی‌گرداند (پیام جدا و قابل حذف)."""

    def __init__(self, text):
        self.text = text
        self.deleted = 0

    async def delete(self):
        self.deleted += 1


class FakeMessage:
    def __init__(self, text, chat=None):
        self.text = text
        self.chat = chat or FakeChat()
        self.reply_to_message = None
        self.sent = []
        self.placeholders = []

    async def reply_text(self, text, *a, **kw):
        ph = FakePlaceholder(text)
        self.placeholders.append(ph)
        self.sent.append(text)
        return ph

    @property
    def answers(self):
        return [p.text for p in self.placeholders[1:]]

    async def delete(self):
        self.deleted += 1


def test_end_to_end():
    print("\n[۴] مسیر کامل هندلر تلگرام (مدل جعلی)")
    import asyncio
    import types

    import EntekhabVahedBot as bot
    import llm

    def fake_generate(messages, **kw):
        fake_generate.last = messages
        assert messages[0]["role"] == "system"
        assert messages[-1]["content"] == "بهینه سازی خطی برای ورودی ۱۴۰۳ مجازه؟"
        assert "پاسخ قطعی" in messages[0]["content"]
        return "نتیجه: مجاز است ✅"

    llm.generate = fake_generate

    msg = FakeMessage("بهینه سازی خطی برای ورودی ۱۴۰۳ مجازه؟")
    update = types.SimpleNamespace(message=msg)
    context = types.SimpleNamespace(bot=types.SimpleNamespace(id=1, username="amoozeshbot"))

    asyncio.run(bot.handle_message(update, context))
    check("پاسخ ارسال شد", msg.answers == ["نتیجه: مجاز است ✅"], str(msg.sent))
    check("پیام «در حال بررسی…» پاک شد", msg.placeholders[0].deleted == 1)

    # خطای مدل ⇒ پاسخ قطعی از خود دیتا (بدون تولید آزاد)
    msg2 = FakeMessage("استاد ایزدیخواه چطوره؟")
    llm.generate = lambda *a, **kw: (_ for _ in ()).throw(llm.LLMError("Ollama قطع است"))
    asyncio.run(bot.handle_message(types.SimpleNamespace(message=msg2), context))
    off = msg2.answers[-1]
    check("بدون مدل، پاسخ از داده‌های پروژه ساخته شد", "ایزدیخواه" in off and "ارائه‌ی این ترم" in off, off[:80])
    check("به کاربر گفته شد که مدل نبود", "مدل محلی در دسترس نبود" in off)
    check("پاسخ کوتاه و قابل ارسال است", len(off) < 4000, str(len(off)))

    # خطای مدل و سوال بی‌ربط ⇒ پیام راهنما (نه سکوت)
    msg5 = FakeMessage("سیب زمینی چند؟")
    asyncio.run(bot.handle_message(types.SimpleNamespace(message=msg5), context))
    check("سوال بی‌ربط بدون مدل پیام راهنما گرفت", msg5.answers and "نتوانستم" in msg5.answers[-1],
          str(msg5.answers))

    # در گروه، بدون منشن و بدون ریپلای، جواب نمی‌دهد
    msg3 = FakeMessage("سلام بچه‌ها")
    msg3.chat.type = "group"
    asyncio.run(bot.handle_message(types.SimpleNamespace(message=msg3), context))
    check("در گروه بدون منشن ساکت است", msg3.sent == [] and msg3.placeholders == [])

    # با منشن جواب می‌دهد
    llm.generate = lambda *a, **kw: "سلام 👋"
    msg4 = FakeMessage("@amoozeshbot سلام")
    msg4.chat.type = "supergroup"
    asyncio.run(bot.handle_message(types.SimpleNamespace(message=msg4), context))
    check("در گروه با منشن جواب می‌دهد", msg4.answers == ["سلام 👋"], str(msg4.sent))


if __name__ == "__main__":
    test_retrieval()
    test_llm_client()
    test_prompts()
    test_fallback()
    test_end_to_end()
    print("\n" + ("✅ همه تست‌ها پاس شد." if not FAILS else f"❌ {len(FAILS)} تست ناموفق: {FAILS}"))
    sys.exit(1 if FAILS else 0)
