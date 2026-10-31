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
    check("قاعده‌ی ضدتوهم در پرامپت هست", "از خودت نساز" in SYSTEM_PROMPT)
    check("محدودیت طول در پرامپت هست", "حداکثر ۳ خط" in SYSTEM_PROMPT)
    check("طول پرامپت پایه < ۱۵۰۰ کاراکتر", len(SYSTEM_PROMPT) < 1500)

    import llm as _llm
    old_model, old_think = _llm.MODEL_NAME, _llm.THINK
    try:
        _llm.MODEL_NAME, _llm.THINK = "qwen3:4b", False
        check("برای Qwen3، no_think تزریق می‌شود",
              build_messages("سوال", "زمینه")[1]["content"].endswith("/no_think"))
        _llm.MODEL_NAME = "qwen2.5:7b"
        check("برای Qwen2.5، no_think تزریق نمی‌شود",
              "/no_think" not in build_messages("سوال", "زمینه")[1]["content"])
    finally:
        _llm.MODEL_NAME, _llm.THINK = old_model, old_think

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
    check("امتیازهای فرم استخراج شد", "۹.۶ از ۱۰" in card, card[:200])
    check("نتیجه‌گیری ربات اول پاسخ است", card.startswith("👤") and "🎯 نتیجه:" in card)
    # هیچ پیام آرشیو نباید عیناً در پاسخ کپی شود (پاسخ باید «نتیجه» باشد)
    prof = next(x for x in store.professors if "ابوالقاسمی" in x.norm_name)
    copied = [c[:60] for c in prof.comments if len(c) > 60 and c[:60] in card]
    check("هیچ پیام آرشیو عیناً کپی نشده", not copied, str(copied[:1]))
    check("درس این ترم اضافه شد", "مبانی کارآفرینی" in card)

    course = fallback.answer(store, "ساختمان داده و الگوریتم ها")
    check("فهرست دروس بدون مدل", course and "ساختمان داده" in course)

    check("سوال بی‌ربط ⇒ None", fallback.answer(store, "سلام") is None)

    # --- استاد + درس: فقط ارائه‌های همان درس
    both = fallback.answer(store, "ساختمان داده و الگوریتم ها با همامی چه زمانی ارائه شده؟")
    check("پرسش استاد+درس فقط همان درس را می‌آورد",
          both and "ساختمان داده" in both and "اصول سیستم" not in both, str(both)[:120])
    check("سرتیتر به درس محدود شده", both and "ارائه‌های این استاد در" in both)

    # --- نام کوتاه/متفاوت درس در پرسش مجاز بودن
    alias = fallback.answer(store, "داده کاوی برای ورودی ۱۴۰۱")
    check("نام کوتاه درس با قوانین تطبیق خورد",
          alias and "مقدمه ای بر داده کاوی" in alias and "مجاز است" in alias, str(alias)[:120])

    # --- پرسش کاملاً بی‌ربط: پاسخ صریح، نه سکوت و نه درس اشتباه
    miss = fallback.answer(store, "تحقیق در عملیات ۱۴۰۴")
    check("درس ناموجود ⇒ پاسخ «پیدا نکردم»",
          miss and "پیدا نکردم" in miss and "روش تحقیق" not in miss, str(miss)[:120])
    check("ارقام پرسش در پاسخ فارسی شد", miss and "۱۴۰۴" in miss, str(miss)[:80])

    # --- مقایسه‌ی دو استاد (پرسش «فلانی یا فلانی؟»)
    cmp = fallback.answer(store, "غلامیان یا تهرانیان؟")
    check("پرسش مقایسه ⇒ پاسخ مقایسه‌ای", cmp and cmp.startswith("⚖️"), str(cmp)[:80])
    check("مقایسه به نتیجه می‌رسد", cmp and "🎯 نتیجه:" in cmp and "غلامیان" in cmp)
    check("ترتیب پرسش در مقایسه حفظ شد",
          cmp and cmp.index("محمد غلامیان") < cmp.index("ابوالفضل تهرانیان"), str(cmp)[:120])
    check("مقایسه رأی مستقیم آرشیو را نشان می‌دهد",
          cmp and "مقایسه‌های مستقیم" in cmp, str(cmp)[:200])
    # همان قاعده‌ی ضدکپی، برای پاسخ مقایسه‌ای هم برقرار است
    gholamian = next(x for x in store.professors if "غلامیان" in x.norm_name)
    leaked = [c[:60] for c in gholamian.comments if len(c) > 60 and c[:60] in (cmp or "")]
    check("مقایسه هم پیام آرشیو را کپی نمی‌کند", not leaked, str(leaked[:1]))

    # --- وقتی فقط یکی از دو استاد داده دارد، صریح گفته می‌شود
    uneven = fallback.answer(store, "همامی یا رحیم")
    check("مقایسه‌ی نامتوازن صادق است",
          uneven and "ارزیابی روشنی نیست" in uneven, str(uneven)[:160])

    # --- نسبت‌دادن هر بند پیام به استاد خودش (نه به صاحب شناسنامه)
    keys = fallback._name_keys(store)
    mixed = fallback._attributed(
        "غلامیان درست تر نمره میده ولی تهرانیان تاس میندازه",
        keys, "سهیلا دهقان چناری",
    )
    check("بند مثبت به غلامیان و بند منفی به تهرانیان رسید",
          mixed.get("محمد غلامیان", 0) > 0 and mixed.get("ابوالفضل تهرانیان", 0) < 0,
          str(mixed))

    # --- نگهبان ضدتوهم با خروجی واقعی gemma3:4b (تست رگرسیون)
    ctx_time, _ = store.build_context(
        "ساختمان داده و الگوریتم ها برای ورودی ۱۴۰۴ با همامی چه زمانی ارائه شده؟"
    )
    ok, why = fallback.verify_model_text("همامی: یکشنبه ۱۷:۴۰ تا ۱۹:۲۰", ctx_time)
    check("ساعت ساختگی گرفته شد", not ok and "17:40" in why, why)
    ok, why = fallback.verify_model_text("سه شنبه ۱۰:۳۰ تا ۱۲:۱۵", ctx_time)
    check("ساعت ناموجود گرفته شد", not ok and "12:15" in why, why)
    ok, _ = fallback.verify_model_text("یکشنبه از 14:20 تا 17:40", ctx_time)
    check("ساعت درست رد نشد", ok)

    ctx_prof, _ = store.build_context("استاد آذر ابوالقاسمی چطور استادی هستن")
    ok, why = fallback.verify_model_text("این مورد در اطلاعات موجود نیست.", ctx_prof)
    check("ادعای «اطلاعاتی نیست» رد شد", not ok, why)
    ok, why = fallback.verify_model_text("ظرفیت کلاس ۱۲۰ نفر است.", ctx_prof)
    check("عدد ساختگی گرفته شد", not ok and "120" in why, why)
    ok, _ = fallback.verify_model_text(
        "استاد خوبی است؛ نمره‌دهی با ارفاق و حضور و غیاب مهم است.", ctx_prof
    )
    check("خلاصه‌ی درست رد نشد", ok)

    # پاکسازی خروجی مدل
    check("حکم بی‌ربط مدل حذف شد",
          "نتیجه" not in fallback.sanitize_model_text("نتیجه: مجاز است"))
    check("حکم مرتبط مدل حفظ شد",
          "نتیجه" in fallback.sanitize_model_text("نتیجه: مجاز است", allow_verdict=True))


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

    async def edit_text(self, text, *a, **kw):
        self.text = text
        self.edited = True
        return self


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

    # --- حالت پیش‌فرض: بدون مدل، پاسخ فوری از داده
    bot.MODEL_SUMMARY = False
    called = {"n": 0}

    def spy(*a, **kw):
        called["n"] += 1
        return "نباید صدا زده شود"

    llm.generate = spy
    ctx_fast = types.SimpleNamespace(bot=types.SimpleNamespace(id=1, username="b"))

    msg_fast = FakeMessage("استاد آذر ابوالقاسمی چطور استادی هستن")
    asyncio.run(bot.handle_message(types.SimpleNamespace(message=msg_fast), ctx_fast))
    check("پیش‌فرض: مدل صدا زده نشد", called["n"] == 0, str(called))
    check("پیش‌فرض: پاسخ قطعی فوری رسید",
          "ارفاق" in msg_fast.answers[-1] and "جمع‌بندی مدل" not in msg_fast.answers[-1])

    msg_unknown = FakeMessage("سیب زمینی چند؟")
    asyncio.run(bot.handle_message(types.SimpleNamespace(message=msg_unknown), ctx_fast))
    check("پیش‌فرض: سوال بی‌ربط پاسخ صریح «پیدا نشد» گرفت (بدون معطلی مدل)",
          "پیدا نکردم" in msg_unknown.answers[-1], msg_unknown.answers[-1][:60])
    check("پیش‌فرض: مدل حتی برای سوال بی‌ربط صدا زده نشد", called["n"] == 0, str(called))

    # --- حالت با مدل
    bot.MODEL_SUMMARY = True

    def fake_generate(messages, **kw):
        fake_generate.last = messages
        assert messages[0]["role"] == "system"
        assert messages[-1]["content"] == "بهینه سازی خطی برای ورودی ۱۴۰۳ مجازه؟"
        assert "پاسخ قطعی" in messages[0]["content"]
        return "این درس ویژه‌ی ورودی ۱۴۰۳ است و برای بقیه‌ی ورودی‌ها بسته است."

    llm.generate = fake_generate

    msg = FakeMessage("بهینه سازی خطی برای ورودی ۱۴۰۳ مجازه؟")
    update = types.SimpleNamespace(message=msg)
    context = types.SimpleNamespace(bot=types.SimpleNamespace(id=1, username="amoozeshbot"))

    asyncio.run(bot.handle_message(update, context))
    reply = msg.answers[-1]
    check("پاسخ با نتیجه‌ی ربات شروع می‌شود", reply.startswith("🎯 نتیجه:"), reply[:60])
    check("حکم درست است", "مجاز است ✅" in reply, reply[:80])
    check("دلیل از داده آمده", "ویژه‌ی ورودی ۱۴۰۳" in reply, reply[:120])
    check("جمع‌بندی مدل ضمیمه شد", "جمع‌بندی مدل" in reply and "ویژه‌ی ورودی ۱۴۰۳" in reply)
    check("پیام «در حال بررسی…» پاک شد", msg.placeholders[0].deleted == 1)

    # مدلِ پرت‌وپلا ⇒ جمع‌بندی نمایش داده نمی‌شود، ولی داده‌ی قطعی می‌رسد
    llm.generate = lambda *a, **kw: "نتیجه: مجاز است"
    msg_junk = FakeMessage("استاد ایزدیخواه چطوره؟")
    asyncio.run(bot.handle_message(types.SimpleNamespace(message=msg_junk), context))
    junk_reply = msg_junk.answers[-1]
    check("جواب بی‌ارزش مدل دور ریخته شد", "جمع‌بندی مدل" not in junk_reply, junk_reply[:80])
    check("کارت قطعی استاد رسید", "ارائه‌ی این ترم" in junk_reply)

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
    check("سوال بی‌ربط بدون مدل پاسخ صریح گرفت",
          msg5.answers and "پیدا نکردم" in msg5.answers[-1], str(msg5.answers))

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



# ---------------------------------------------------------------- 3.7) حالت مدل

class FakeCallbackQuery:
    """همان چیزی که تلگرام هنگام کلیک دکمه می‌دهد."""

    def __init__(self, data, message=None):
        self.data = data
        self.message = message or FakeMessage("پاسخ قبلی")
        self.answered = 0
        self.edits = []

    async def answer(self, *a, **kw):
        self.answered += 1

    async def edit_message_text(self, text, *a, **kw):
        self.edits.append(text)
        return FakePlaceholder(text)


def test_deep_mode():
    print("\n[۳.۷] حالت تحلیل با مدل (deep)")
    import asyncio
    import time
    import types

    import deep
    import llm
    from retrieval import DataStore

    store = DataStore(".")

    # --- زمینه: متن کامل، نه زمینه‌ی بریده‌ی ۴۰۰۰ کاراکتری
    ctx, meta = deep.build_deep_context(store, "غلامیان یا تهرانیان؟")
    check("زمینه‌ی حالت مدل هر دو استاد را دارد",
          "محمد غلامیان" in ctx and "ابوالفضل تهرانیان" in ctx, str(meta))
    check("خلاصه‌ی عددی قابل استناد هست", "نظر مثبت:" in ctx and "نظر منفی:" in ctx)
    gholamian = next(x for x in store.professors if "غلامیان" in x.norm_name)
    longest = max(gholamian.comments, key=len)
    check("متن کامل نظرها (بدون بریدن ۹۰۰ کاراکتری) رسیده",
          longest[:80] in ctx, longest[:60])
    check("ردیف‌های درس این ترم هم هست", "مبانی آنالیز عددی" in ctx)

    # --- اعتبارسنجی تحلیل
    good = ("نتیجه: بین این دو، غلامیان انتخاب کم‌ریسک‌تری است.\n"
            "• چند نفر می‌گویند درست‌تر نمره می‌دهد.\n"
            "• تهرانیان به شانسی‌بودن سوال‌ها متهم شده.\n"
            "• هر دو نقد جدی گرفته‌اند؛ برای تصمیم نهایی ساعت کلاس را ببین.")
    ok, why = deep.verify_analysis_text(good, ctx)
    check("تحلیل معتبر پذیرفته شد", ok, why)

    bad_time, why = deep.verify_analysis_text("کلاس او شنبه ۲۱:۴۵ است.", ctx)
    check("ساعت ساختگی در تحلیل رد شد", not bad_time and "21:45" in why, why)

    bad_score, why = deep.verify_analysis_text("امتیاز او ۴.۴ از 10 است.", ctx)
    check("امتیاز ساختگی رد شد", not bad_score and "4.4" in why, why)

    bad_year, why = deep.verify_analysis_text("این درس برای ورودی ۱۳۹۹ است.", ctx)
    check("سال ساختگی رد شد", not bad_year and "1399" in why, why)

    check("تحلیل خالی رد شد", deep.verify_analysis_text("  ", ctx)[0] is False)

    # در اجرای واقعی مدل «آذرaboالقاسمی» تولید کرد ⇒ خروجی مخدوش پذیرفته نشود
    mixed_script, why = deep.verify_analysis_text(
        "استاد آذرaboالقاسمی خوب استادی هست و نمره‌دهی دست بازی دارد.", ctx)
    check("خروجی مخدوش (لاتین وسط فارسی) رد شد", not mixed_script and "abo" in why, why)

    # --- اجرا با مدل جعلی
    original = llm.generate
    try:
        llm.generate = lambda messages, **kw: good
        result = deep.analyze(store, "غلامیان یا تهرانیان؟")
        check("تحلیل مدل با موفقیت ساخته شد", result["ok"], result["reason"])
        check("زمینه‌ی کامل به مدل داده شد (num_ctx بزرگ‌تر)",
              result["meta"]["chars"] > 2000, str(result["meta"]))

        llm.generate = lambda messages, **kw: "کلاس او شنبه ۲۱:۴۵ است."
        result = deep.analyze(store, "استاد غلامیان")
        check("تحلیل ساختگی قبول نشد", not result["ok"], result["reason"])

        def boom(*a, **kw):
            raise llm.LLMError("Ollama قطع است")

        llm.generate = boom
        result = deep.analyze(store, "استاد غلامیان")
        check("خطای مدل در تحلیل مدیریت شد",
              not result["ok"] and result["model_failed"], str(result["reason"]))

        llm.generate = lambda messages, **kw: "نتیجه"
        result = deep.analyze(store, "سیب زمینی چند؟")
        check("پرسش بی‌داده بدون صدا زدن مدل رد شد",
              not result["ok"] and not result["model_failed"], result["reason"])
    finally:
        llm.generate = original

    # --- دفتر دکمه‌ها: یک‌بار مصرف + انقضا
    import EntekhabVahedBot as bot

    token = bot.remember_query("غلامیان یا تهرانیان؟", 7)
    check("توکن دکمه کوتاه است (سقف ۶۴ بایت تلگرام)", len(token) == 8)
    check("دکمه‌ی معتبر بازیابی شد", bot.recall_query(token)["query"].startswith("غلامیان"))
    check("دکمه یک‌بار مصرف است", bot.recall_query(token) is None)
    token2 = bot.remember_query("سوال قدیمی")
    bot.PENDING[token2]["ts"] = time.time() - bot.PENDING_TTL - 5
    check("دکمه‌ی منقضی بازیابی نمی‌شود", bot.recall_query(token2) is None)


# ---------------------------------------------------------------- 4) مسیر حالت مدل در تلگرام

def test_deep_end_to_end():
    print("\n[۴.۱] مسیر تلگرامِ حالت مدل (دکمه و /deep)")
    import asyncio
    import types

    import EntekhabVahedBot as bot
    import llm

    original = llm.generate

    class KeyedPlaceholder(FakePlaceholder):
        def __init__(self, text, kwargs=None):
            super().__init__(text)
            self.kwargs = kwargs or {}

    class KeyedMessage(FakeMessage):
        async def reply_text(self, text, *a, **kw):
            ph = KeyedPlaceholder(text, kw)
            self.placeholders.append(ph)
            self.sent.append(text)
            return ph

        async def edit_text(self, text, *a, **kw):
            self.edited = text
            return FakePlaceholder(text)

    analysis = ("نتیجه: غلامیان انتخاب کم‌ریسک‌تری است.\n"
                "• درست‌تر نمره می‌دهد.\n"
                "• تهرانیان بیشتر نقد شده است.")
    import tempfile

    import api_llm
    import quota

    old_api_key = api_llm.API_KEY
    old_quota = bot.QUOTA
    old_model_ready = bot.MODEL_READY
    # کلید واقعی و شمارنده‌ی واقعی را کنار می‌گذاریم تا نتیجه به محیط وابسته نباشد
    api_llm.API_KEY = ""
    bot.QUOTA = quota.QuotaStore(
        path=os.path.join(tempfile.mkdtemp(prefix="quota-flow-"), "quotas.json"),
        persist_remote=False,
    )
    try:
        llm.generate = lambda messages, **kw: analysis

        # ۱) پاسخ سریع + دکمه‌ی تحلیل
        bot.MODEL_SUMMARY = False
        bot.MODEL_READY = True
        ctx = types.SimpleNamespace(bot=types.SimpleNamespace(id=1, username="b"))
        msg = KeyedMessage("غلامیان یا تهرانیان؟")
        asyncio.run(bot.handle_message(types.SimpleNamespace(message=msg), ctx))
        last = msg.placeholders[-1]
        check("پاسخ سریع بدون معطلی مدل آمد", llm.generate is not None)
        markup = last.kwargs.get("reply_markup")
        check("دکمه‌ی تحلیل زیر پاسخ سریع هست", markup is not None)
        button = markup.inline_keyboard[0][0] if markup else None
        check("برچسب دکمه روشن است", button and "تحلیل" in button.text, str(button))
        check("callback_data کوتاه است", button and len(button.callback_data) < 64)
        check("پاسخ سریع همان مقایسه‌ی داده است", "⚖️" in last.text, last.text[:40])

        # ۲) کلیک روی دکمه
        cq = FakeCallbackQuery(button.callback_data)
        asyncio.run(bot.deep_callback(types.SimpleNamespace(callback_query=cq), ctx))
        check("به کلیک دکمه پاسخ داده شد", cq.answered == 1)
        check("پیام اول به «در حال تحلیل» تغییر کرد",
              len(cq.edits) == 2 and "در حال تحلیل" in cq.edits[0], str(cq.edits[:1]))
        check("تحلیل مدل جایگزین شد", "🧠 تحلیل مدل" in cq.edits[-1], cq.edits[-1][:60])
        check("خروجی، فهم مدل است نه فهرست داده", "کم‌ریسک‌تری" in cq.edits[-1])
        check("داده‌ی پایه برای شفافیت ضمیمه شد", "📊 داده‌ی پایه" in cq.edits[-1])
        check("حکم محاسبه‌شده از داده هم زیر تحلیل مدل می‌آید",
              "🎯 حکم داده (بدون مدل)" in cq.edits[-1], cq.edits[-1][-160:])

        # ۳) ضربه‌ی دوم روی همان دکمه ⇒ منقضی، نه تحلیل دوباره
        cq2 = FakeCallbackQuery(button.callback_data)
        asyncio.run(bot.deep_callback(types.SimpleNamespace(callback_query=cq2), ctx))
        check("ضربه‌ی دوم پیام منقضی گرفت", "منقضی" in cq2.edits[-1], cq2.edits[-1][:60])

        # ۴) دستور /deep
        msg_cmd = KeyedMessage("/deep غلامیان یا تهرانیان؟")
        asyncio.run(bot.deep_command(
            types.SimpleNamespace(message=msg_cmd),
            types.SimpleNamespace(args=["غلامیان", "یا", "تهرانیان؟"],
                                  bot=types.SimpleNamespace(id=1, username="b")),
        ))
        check("/deep مستقیم تحلیل می‌دهد",
              "🧠 تحلیل مدل" in msg_cmd.placeholders[-1].text,
              msg_cmd.placeholders[-1].text[:60])

        # ۵) مدل خطا داد ⇒ صادقانه + پاسخ معتبر داده
        def boom(*a, **kw):
            raise llm.LLMError("Ollama قطع است")

        llm.generate = boom
        token = bot.remember_query("غلامیان یا تهرانیان؟")
        cq3 = FakeCallbackQuery(f"deep:{token}")
        asyncio.run(bot.deep_callback(types.SimpleNamespace(callback_query=cq3), ctx))
        check("خطای مدل صادقانه گفته شد", "مدل در دسترس نبود" in cq3.edits[-1],
              cq3.edits[-1][:80])
        check("پاسخ معتبر داده در همان پیام ماند", "⚖️" in cq3.edits[-1])

        # ۶) حالت مدل خاموش ⇒ دکمه نباید بیاید
        llm.generate = lambda *a, **kw: analysis
        bot.MODEL_READY = False
        msg_nb = KeyedMessage("استاد ابوالقاسمی")
        asyncio.run(bot.handle_message(types.SimpleNamespace(message=msg_nb), ctx))
        check("بدون مدل، دکمه نمایش داده نمی‌شود",
              msg_nb.placeholders[-1].kwargs.get("reply_markup") is None)

        # ۷) /deep بدون مدل ⇒ پاسخ سریع با توضیح
        msg_off = KeyedMessage("/deep استاد ابوالقاسمی")
        asyncio.run(bot.deep_command(
            types.SimpleNamespace(message=msg_off),
            types.SimpleNamespace(args=["استاد", "ابوالقاسمی"],
                                  bot=types.SimpleNamespace(id=1, username="b")),
        ))
        off_text = msg_off.placeholders[-1].text
        check("‎/deep بدون مدل پاسخ سریع می‌دهد",
              "حالت مدل روی این اجرا فعال نیست" in off_text, off_text[:60])

        # ۸) مدل خاموش ولی API روشن ⇒ فقط دکمه‌ی ⚡ (بدون مدل هم API کار می‌کند)
        api_llm.API_KEY = "test-key"
        msg_api_only = KeyedMessage("استاد ابوالقاسمی")
        asyncio.run(bot.handle_message(types.SimpleNamespace(message=msg_api_only), ctx))
        only = msg_api_only.placeholders[-1].kwargs.get("reply_markup")
        rows = only.inline_keyboard if only else []
        check("مدل خاموش + API روشن ⇒ فقط دکمه‌ی API",
              len(rows) == 1 and rows[0][0].callback_data.startswith("api:"),
              str([[b.text for b in row] for row in rows]))
        api_llm.API_KEY = ""
        check("‎/deep بدون مدل داده را هم می‌آورد", "ابوالقاسمی" in off_text)
    finally:
        llm.generate = original
        api_llm.API_KEY = old_api_key
        bot.QUOTA = old_quota
        bot.MODEL_READY = old_model_ready



# ---------------------------------------------------------------- 5) گردش‌کارها

def test_workflows():
    print("\n[۵] گردش‌کارهای Actions (بدون دانلود تکراری مدل)")
    import pathlib

    yml = pathlib.Path(".github/workflows/bot.yml").read_text(encoding="utf-8")
    check("کش مدل با کلید ثابت تعریف شده", "steps.model_key.outputs.key" in yml)
    check("کش قدیمی هم بازیابی می‌شود (بدون دانلود دوباره)",
          "restore-keys" in yml and "ollama-" in yml)
    check("پیش از دانلود، وجود مدل بررسی می‌شود",
          'grep -qx "$MODEL_NAME"' in yml)
    check("شکست مدل، job را نمی‌کشد (ربات در حالت سریع بالا می‌آید)",
          yml.count("continue-on-error: true") >= 2)
    check("کش مدل از کلیدهای ساده‌ی تازه استفاده می‌کند", "-v3" in yml)
    check("نصب مدل فقط وقتی حالت مدل روشن است",
          "env.MODEL_SUMMARY == '1' || env.DEEP_MODE == '1'" in yml)

    for name in ("model-check.yml", "deep-check.yml"):
        text = pathlib.Path(f".github/workflows/{name}").read_text(encoding="utf-8")
        check(f"{name}: دانلود فقط در صورت نبودن مدل",
              'grep -qx "$MODEL_NAME"' in text)


# ---------------------------------------------------------------- 3.8) سهمیه و API

class FakeOpenAI(BaseHTTPRequestHandler):
    """سرور جعلی سازگار با OpenAI (همان چیزی که OpenRouter برمی‌گرداند)."""

    mode = "ok"
    last_body = None
    last_auth = None

    def log_message(self, *args):  # ساکت
        pass

    def _send(self, code, payload):
        body = json.dumps(payload).encode()
        self.send_response(code)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def do_POST(self):
        length = int(self.headers.get("Content-Length", 0))
        body = json.loads(self.rfile.read(length) or b"{}")
        FakeOpenAI.last_body = body
        FakeOpenAI.last_auth = self.headers.get("Authorization")
        if FakeOpenAI.mode == "401":
            return self._send(401, {"error": {"message": "invalid key"}})
        if FakeOpenAI.mode == "empty":
            return self._send(200, {"choices": []})
        return self._send(200, {
            "model": body.get("model"),
            "choices": [{"message": {
                "role": "assistant",
                "content": "نتیجه: غلامیان انتخاب کم‌ریسک‌تری است برای این درس.",
            }}],
            "usage": {"prompt_tokens": 120, "completion_tokens": 30},
        })


def test_api_provider():
    print("\n[۳.۸] ارائه‌دهنده‌ی API (سرور جعلی سازگار با OpenAI)")
    import api_llm

    server = HTTPServer(("127.0.0.1", 0), FakeOpenAI)
    port = server.server_address[1]
    threading.Thread(target=server.serve_forever, daemon=True).start()

    old = (api_llm.API_BASE_URL, api_llm.API_KEY, api_llm.API_MODEL)
    api_llm.API_BASE_URL = f"http://127.0.0.1:{port}"
    api_llm.API_KEY = "test-key"
    api_llm.API_MODEL = "test/model-1"
    try:
        check("با کلید، API فعال است", api_llm.enabled())

        text = api_llm.generate([{"role": "user", "content": "سلام"}])
        check("پاسخ API دریافت شد", "غلامیان" in text, text[:60])
        check("کلید در هدر Authorization رفت",
              FakeOpenAI.last_auth == "Bearer test-key", str(FakeOpenAI.last_auth))
        check("مدل در درخواست ارسال شد",
              (FakeOpenAI.last_body or {}).get("model") == "test/model-1")
        check("آمار مصرف ثبت شد",
              api_llm.LAST_STATS.get("provider") == "api"
              and api_llm.LAST_STATS.get("eval_count") == 30, str(api_llm.LAST_STATS))

        FakeOpenAI.mode = "401"
        try:
            api_llm.generate([{"role": "user", "content": "x"}])
            check("کلید نامعتبر خطا داد", False)
        except api_llm.APIError as exc:
            check("کلید نامعتبر خطا داد", "کلید" in str(exc), str(exc))

        FakeOpenAI.mode = "empty"
        try:
            api_llm.generate([{"role": "user", "content": "x"}])
            check("پاسخ خالی خطا داد", False)
        except api_llm.APIError as exc:
            check("پاسخ خالی خطا داد", "خالی" in str(exc), str(exc))
        FakeOpenAI.mode = "ok"

        api_llm.API_KEY = ""
        check("بدون کلید، API غیرفعال است", not api_llm.enabled())
        try:
            api_llm.generate([{"role": "user", "content": "x"}])
            check("بدون کلید درخواستی نمی‌رود", False)
        except api_llm.APIError as exc:
            check("بدون کلید درخواستی نمی‌رود", "تنظیم نشده" in str(exc), str(exc))

        # --- مسیر تحلیل با API در deep.py (اعتبارسنجی هم اجرا می‌شود)
        import deep
        from retrieval import DataStore

        api_llm.API_KEY = "test-key"
        store = DataStore(".")
        result = deep.analyze(store, "غلامیان یا تهرانیان؟", provider="api")
        check("تحلیل با API ساخته شد", result["ok"], result["reason"])
        check("برچسب مدل از API می‌آید", result["model"] == "test/model-1", result["model"])
        check("provider در خروجی ثبت شد", result["provider"] == "api")

        FakeOpenAI.mode = "401"
        failed = deep.analyze(store, "غلامیان یا تهرانیان؟", provider="api")
        check("خطای API به شکست مدل تبدیل شد",
              not failed["ok"] and failed["model_failed"], failed["reason"])
        FakeOpenAI.mode = "ok"
    finally:
        api_llm.API_BASE_URL, api_llm.API_KEY, api_llm.API_MODEL = old
        server.shutdown()


def test_quota():
    print("\n[۳.۹] سهمیه‌ی روزانه‌ی هر کاربر")
    import tempfile
    from datetime import datetime, timedelta, timezone

    import quota

    with tempfile.TemporaryDirectory() as tmp:
        path = os.path.join(tmp, "quotas.json")
        store = quota.QuotaStore(path=path, persist_remote=False)

        check("سقف پیش‌فرض: مدل ۳ بار", quota.LIMITS["deep"] == 3)
        check("سقف پیش‌فرض: API ۱ بار", quota.LIMITS["api"] == 1)
        check("کاربر تازه کل سهمیه را دارد",
              store.remaining(11, "deep") == 3 and store.remaining(11, "api") == 1)

        check("مصرف مدل ۱", store.consume(11, "deep"))
        check("مصرف مدل ۲", store.consume(11, "deep"))
        check("مصرف مدل ۳", store.consume(11, "deep"))
        check("مصرف چهارم رد شد", not store.consume(11, "deep"))
        check("سهمیه‌ی مدل صفر شد", store.remaining(11, "deep") == 0)

        check("مصرف API ۱", store.consume(11, "api"))
        check("مصرف API دوم رد شد", not store.consume(11, "api"))

        check("کاربر دیگر سهمیه‌ی خودش را دارد", store.remaining(22, "deep") == 3)

        store.refund(11, "deep")
        check("برگشت سهمیه بعد از خطا", store.remaining(11, "deep") == 1)

        reloaded = quota.QuotaStore(path=path, persist_remote=False)
        check("سهمیه روی دیسک ماند", reloaded.remaining(11, "deep") == 1
              and reloaded.remaining(11, "api") == 0)

        # گذشت روز ⇒ سهمیه‌ی تازه
        original_today = quota.today_key
        tomorrow = datetime.now(timezone.utc) + timedelta(days=1)
        quota.today_key = lambda now=None: original_today(tomorrow)
        try:
            check("روز بعد سهمیه ریست می‌شود", store.remaining(11, "deep") == 3)
        finally:
            quota.today_key = original_today

        store.reset(11)
        check("ریست دستی کار می‌کند", store.remaining(11, "api") == 1)

    # --- ادغام با پشتیبان گیت‌هاب (max برنده است)
    class FakeRemote:
        def __init__(self, data):
            self.data = data
            self.saved = None

        def load(self):
            return self.data

        def save(self, data):
            self.saved = data
            return True

    with tempfile.TemporaryDirectory() as tmp:
        path = os.path.join(tmp, "quotas.json")
        today = quota.today_key()
        # کلید خاموش‌کننده‌ی محیطی (QUOTA_PERSIST=0) را برای این دو بررسی
        # موقتاً روشن می‌کنیم تا رفتار «همگام با ریموت» واقعاً سنجیده شود.
        old_persist = quota.PERSIST
        quota.PERSIST = True
        try:
            remote = FakeRemote({today: {"33": {"deep": 2}}})
            store = quota.QuotaStore(path=path, remote=remote, persist_remote=True)
            store.sync()
            check("سهمیه‌ی گیت‌هاب خوانده شد", store.remaining(33, "deep") == 1,
                  str(store.remaining(33, "deep")))
            store.consume(33, "deep")
            check("شمارنده‌ی محلی جلوتر از ریموت نگه داشته می‌شود",
                  store.remaining(33, "deep") == 0)
        finally:
            quota.PERSIST = old_persist


# ---------------------------------------------------------------- 3.95) سهمیه در ربات

def test_rate_limits_in_bot():
    print("\n[۳.۹۵] دکمه‌ها و سهمیه در ربات")
    import asyncio
    import tempfile
    import types

    import EntekhabVahedBot as bot
    import api_llm
    import llm
    import quota

    with tempfile.TemporaryDirectory() as tmp:
        old_quota = bot.QUOTA
        old_api_key = api_llm.API_KEY
        old_model_ready = bot.MODEL_READY
        bot.QUOTA = quota.QuotaStore(
            path=os.path.join(tmp, "quotas.json"), persist_remote=False
        )
        api_llm.API_KEY = "test-key"
        bot.MODEL_READY = True
        try:
            markup = bot.deep_keyboard("غلامیان یا تهرانیان؟", 77)
            check("دو دکمه ساخته شد (مدل + API)", markup and len(markup.inline_keyboard) == 2,
                  str(markup))
            deep_label = markup.inline_keyboard[0][0].text
            api_label = markup.inline_keyboard[1][0].text
            check("دکمه‌ی مدل سهمیه را نشان می‌دهد", "۳ از ۳" in deep_label, deep_label)
            check("دکمه‌ی API سهمیه‌ی خودش را نشان می‌دهد", "۱ از ۱" in api_label, api_label)
            check("callback دکمه‌ها کوتاه و تفکیک‌شده‌اند",
                  markup.inline_keyboard[0][0].callback_data.startswith("deep:")
                  and markup.inline_keyboard[1][0].callback_data.startswith("api:")
                  and all(len(row[0].callback_data) < 64 for row in markup.inline_keyboard))

            # مصرف کامل مدل ⇒ برچسب صفر
            for _ in range(3):
                bot.QUOTA.consume(77, "deep")
            after = bot.deep_keyboard("غلامیان یا تهرانیان؟", 77)
            check("دکمه‌ی مدل بعد از اتمام ۰ از ۳ نشان می‌دهد",
                  "۰ از ۳" in after.inline_keyboard[0][0].text,
                  after.inline_keyboard[0][0].text)

            # کلیک روی دکمه‌ی بی‌سهمیه ⇒ پیام روشن
            token = bot.remember_query("غلامیان یا تهرانیان؟", 77)
            cq = FakeCallbackQuery(f"deep:{token}")
            cq.from_user = types.SimpleNamespace(id=77)
            asyncio.run(bot.deep_callback(types.SimpleNamespace(callback_query=cq),
                                          types.SimpleNamespace()))
            check("سهمیه‌ی تمام‌شده با پیام روشن گفته می‌شود",
                  "سهمیه‌ی امروزت" in cq.edits[-1], cq.edits[-1][:80])
            check("به گزینه‌ی دیگر ارجاع می‌دهد", "API" in cq.edits[-1])

            # سهمیه‌ی API مصرف‌شده ⇒ پیام آن هم پیام درست بدهد
            bot.QUOTA.consume(77, "api")
            token_api = bot.remember_query("غلامیان یا تهرانیان؟", 77)
            cq_api = FakeCallbackQuery(f"api:{token_api}")
            cq_api.from_user = types.SimpleNamespace(id=77)
            asyncio.run(bot.api_callback(types.SimpleNamespace(callback_query=cq_api),
                                         types.SimpleNamespace()))
            check("سهمیه‌ی API هم گارد دارد", "سهمیه‌ی امروزت" in cq_api.edits[-1])

            # خطای زیرساخت ⇒ سهمیه برمی‌گردد
            bot.QUOTA.reset(88)
            original_generate = llm.generate

            def boom(*a, **kw):
                raise llm.LLMError("Ollama قطع است")

            llm.generate = boom
            try:
                asyncio.run(bot.run_deep(bot.STORE, "غلامیان یا تهرانیان؟",
                                         provider="deep" if False else "local",
                                         user_id=88))
            finally:
                llm.generate = original_generate
            check("خطای مدل سهمیه را مصرف نمی‌کند",
                  bot.QUOTA.remaining(88, "deep") == 3,
                  str(bot.QUOTA.remaining(88, "deep")))

            # اجرای موفق سهمیه را کم می‌کند
            llm.generate = lambda *a, **kw: (
                "نتیجه: غلامیان انتخاب کم‌ریسک‌تری است.\n"
                "• چند نفر می‌گویند درست‌تر نمره می‌دهد.\n"
                "• تهرانیان نقد بیشتری گرفته است."
            )
            try:
                text = asyncio.run(bot.run_deep(bot.STORE, "غلامیان یا تهرانیان؟",
                                                provider="local", user_id=88))
            finally:
                llm.generate = original_generate
            check("اجرای موفق یک واحد از سهمیه کم کرد",
                  bot.QUOTA.remaining(88, "deep") == 2,
                  str(bot.QUOTA.remaining(88, "deep")))
            check("سهمیه‌ی باقی‌مانده در پاسخ دیده می‌شود", "سهمیه‌ی امروز" in text,
                  text[-120:])
        finally:
            bot.QUOTA = old_quota
            api_llm.API_KEY = old_api_key
            bot.MODEL_READY = old_model_ready



# ---------------------------------------------------------------- 3.96) مجموعه‌ی طلایی

def test_golden_eval():
    print("\n[۳.۹۶] سنجش کیفیت با مجموعه‌ی طلایی")
    import importlib.util
    import json

    with open("eval/golden.json", encoding="utf-8") as handle:
        cases = json.load(handle)["items"]
    check("مجموعه‌ی طلایی خوانده شد", len(cases) >= 8, str(len(cases)))
    check("هر مورد شناسه و پرسش دارد",
          all(c.get("id") and c.get("query") for c in cases))
    check("هم پرسش مقایسه‌ای دارد هم استادشناسی",
          any(c["kind"] == "compare" for c in cases)
          and any(c["kind"] == "prof" for c in cases))

    spec = importlib.util.spec_from_file_location("eval_deep", "scripts/eval_deep.py")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)

    ok_result = {"ok": True, "reason": "ok", "elapsed": 1.0,
                 "text": "نتیجه: غلامیان بهتر است.\n• دلیل"}
    bad_result = {"ok": True, "reason": "ok", "elapsed": 1.0,
                  "text": "غلامیان خوب است"}

    case = {"id": "x", "query": "غلامیان یا تهرانیان؟", "entities": ["غلامیان"]}
    check("پاسخ درست قبول می‌شود", mod.score_case(case, ok_result)["passed"])
    check("پاسخ بدون «نتیجه:» رد می‌شود", not mod.score_case(case, bad_result)["passed"])
    check("نبود موجودیت رد می‌شود",
          not mod.score_case({"id": "y", "entities": ["تهرانیان"]}, ok_result)["passed"])
    check("متن ممنوع رد می‌کند",
          not mod.score_case({"id": "z", "entities": ["غلامیان"],
                              "forbid": ["بهتر است"]}, ok_result)["passed"])

def isolate_environment() -> None:
    """تست‌ها نباید به کلید API واقعی یا سهمیه‌ی واقعی وابسته باشند.

    روی runner گیت‌هاب، secret ممکن است وجود داشته باشد و `.state/` هم بین
    اجراها بماند؛ آن وقت نتیجه‌ی تست به محیط بستگی پیدا می‌کند نه به کد.
    """
    import tempfile

    os.environ.pop("API_KEY", None)
    os.environ.pop("OPENROUTER_API_KEY", None)
    os.environ["QUOTA_PERSIST"] = "0"
    os.environ.pop("GITHUB_TOKEN", None)
    os.environ.pop("GITHUB_REPOSITORY", None)
    import quota

    quota.PERSIST = False
    quota.STATE_PATH = os.path.join(tempfile.mkdtemp(prefix="quota-test-"), "quotas.json")
    quota.STATE_FILE = quota.STATE_PATH


if __name__ == "__main__":
    isolate_environment()
    test_retrieval()
    test_llm_client()
    test_prompts()
    test_fallback()
    test_deep_mode()
    test_end_to_end()
    test_deep_end_to_end()
    test_api_provider()
    test_quota()
    test_rate_limits_in_bot()
    test_golden_eval()
    test_workflows()
    print("\n" + ("✅ همه تست‌ها پاس شد." if not FAILS else f"❌ {len(FAILS)} تست ناموفق: {FAILS}"))
    sys.exit(1 if FAILS else 0)
