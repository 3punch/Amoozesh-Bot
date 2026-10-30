"""
تست سریع یک سوال از خط فرمان — بدون تلگرام.

    python ask.py "استاد آذر ابوالقاسمی چطور استادی هستن"
    python ask.py --context "استاد ایزدیخواه چطوره؟"   # فقط زمینه‌ای که به مدل می‌رود
    python ask.py --json  "بهینه سازی خطی برای ورودی ۱۴۰۳ مجازه؟"

اگر Ollama در دسترس نباشد، فقط زمینه و بررسی قطعی چاپ می‌شود.
"""

import argparse
import json
import sys

import fallback
import llm
from prompts import build_messages
from retrieval import DataStore, estimate_tokens


def main() -> int:
    parser = argparse.ArgumentParser(description="پرسش مستقیم از ربات (بدون تلگرام)")
    parser.add_argument("question", nargs="+", help="متن سوال")
    parser.add_argument("--context", action="store_true", help="فقط زمینه را نشان بده")
    parser.add_argument("--json", action="store_true", help="خروجی JSON")
    args = parser.parse_args()

    question = " ".join(args.question).strip()
    store = DataStore(".")
    context, stats = store.build_context(question)
    messages = build_messages(question, context)

    result = {
        "question": question,
        "facts": fallback.answer(store, question),
        "stats": stats,
        "prompt_tokens_estimate": estimate_tokens(messages[0]["content"]) + estimate_tokens(question),
        "context": context,
        "answer": None,
        "error": None,
    }

    result["verified"] = None
    result["speed"] = None

    if not args.context:
        if not llm.wait_for_server(timeout=20):
            result["error"] = f"سرویس Ollama روی {llm.OLLAMA_HOST} بالا نیست."
        elif not llm.model_is_available():
            result["error"] = f"مدل «{llm.MODEL_NAME}» نصب نیست (ollama pull {llm.MODEL_NAME})."
        else:
            try:
                raw = llm.generate(messages)
                text = fallback.sanitize_model_text(
                    raw, allow_verdict=bool(stats.get("verdict"))
                )
                ok, why = fallback.verify_model_text(text, context)
                result["verified"] = ok
                result["verify_reason"] = why
                result["answer"] = text if ok else None
                result["speed"] = dict(llm.LAST_STATS)
                if not ok:
                    result["rejected_model_text"] = text
            except llm.LLMError as exc:
                result["error"] = str(exc)

    if args.json:
        print(json.dumps(result, ensure_ascii=False, indent=2))
        return 0 if result["answer"] or args.context else 1

    print(f"❓ سوال: {question}")
    print(f"📊 کلیدواژه‌ها: {'، '.join(stats['keywords']) or '—'}")
    print(f"👨‍🏫 استاد(های) پیدا‌شده: {stats['professors'] or '—'}")
    print(f"📚 ردیف‌های درس: {stats['courses']} | زمینه: {stats['chars']} کاراکتر "
          f"(~{stats['tokens']} توکن) | کل پرامپت: ~{result['prompt_tokens_estimate']} توکن")
    if stats.get("verdict"):
        print(f"⚖️ حکم قطعی: {stats['verdict']}")
    print("\n" + "=" * 60 + "\n📄 زمینه‌ی ارسالی به مدل:\n" + "=" * 60)
    print(context)
    if result["facts"]:
        print("\n" + "=" * 60 + "\n📋 پاسخ قطعی ربات (بدون مدل):\n" + "=" * 60)
        print(result["facts"])
    if result["speed"]:
        sp = result["speed"]
        print(f"\n⏱️ {sp.get('model')}: {sp.get('duration_s')}s | "
              f"{sp.get('eval_count')} توکن تولید | {sp.get('tok_per_s')} توکن/ثانیه | "
              f"زمینه {sp.get('prompt_eval_count')} توکن")
    if result["answer"]:
        print("\n" + "=" * 60 + f"\n🤖 جمع‌بندی {llm.MODEL_NAME} (تأییدشده):\n" + "=" * 60)
        print(result["answer"])
    elif result.get("rejected_model_text"):
        print("\n" + "=" * 60 + "\n🚫 جمع‌بندی مدل رد شد:\n" + "=" * 60)
        print(f"دلیل: {result.get('verify_reason')}")
        print(result["rejected_model_text"])
    elif result["error"]:
        print(f"\n⚠️ مدل اجرا نشد: {result['error']}")
    return 0 if result["answer"] or args.context else 1


if __name__ == "__main__":
    sys.exit(main())
