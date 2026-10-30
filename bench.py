"""
بنچمارک مدل‌های Ollama روی سوال‌های واقعی پروژه.

برای هر مدل: هر سوال را از مسیر کامل (retrieval → prompt → مدل → اعتبارسنجی)
می‌گذراند و زمان، سرعت توکن و «تأیید/رد» جمع‌بندی را ثبت می‌کند.

    python bench.py --models qwen3:4b qwen3:8b qwen2.5:7b
    python bench.py --models qwen3:4b --report reports/model-bench.md

خروجی: جدول Markdown + فایل گزارش (برای کامیت در Actions).
"""

from __future__ import annotations

import argparse
import json
import os
import re
import subprocess
import sys
import time
from datetime import datetime, timezone

import fallback
import llm
from prompts import build_messages
from retrieval import DataStore

QUESTIONS = [
    "استاد آذر ابوالقاسمی چطور استادی هستن",
    "بهینه سازی خطی برای ورودی ۱۴۰۴ مجازه؟",
    "استاد ایزدیخواه چطوره؟",
    "ساختمان داده و الگوریتم ها برای ورودی ۱۴۰۴ با همامی چه زمانی ارائه شده؟",
]


def slug(name: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", name.lower()).strip("-")


def pull(model: str) -> bool:
    print(f"⬇️  دریافت {model} …", flush=True)
    started = time.time()
    proc = subprocess.run(["ollama", "pull", model], capture_output=True, text=True)
    if proc.returncode != 0:
        print(f"❌ دریافت {model} ناموفق: {proc.stderr[-300:]}", flush=True)
        return False
    print(f"✅ {model} آماده شد ({time.time() - started:.0f}s)", flush=True)
    return True


def set_model(model: str) -> None:
    llm.MODEL_NAME = model
    llm.LAST_STATS.clear()


def ask(store: DataStore, question: str) -> dict:
    context, stats = store.build_context(question)
    messages = build_messages(question, context)
    row = {"question": question}
    started = time.time()
    try:
        raw = llm.generate(messages)
    except llm.LLMError as exc:
        row.update(error=str(exc), seconds=round(time.time() - started, 1))
        return row
    row["seconds"] = round(time.time() - started, 1)
    row["speed"] = dict(llm.LAST_STATS)

    text = fallback.sanitize_model_text(raw, allow_verdict=bool(stats.get("verdict")))
    ok, why = fallback.verify_model_text(text, context)
    row.update(raw=raw.strip(), text=text, verified=ok, reason=why,
               facts=fallback.answer(store, question))
    return row


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--models", nargs="+", default=["qwen3:4b"])
    parser.add_argument("--report", default="")
    parser.add_argument("--questions", nargs="*", default=None)
    args = parser.parse_args()

    store = DataStore(".")
    questions = args.questions or QUESTIONS
    report_path = args.report or os.getenv("BENCH_REPORT", "")
    lines: list[str] = []
    results: dict[str, list[dict]] = {}

    def emit(text: str = "") -> None:
        print(text, flush=True)
        lines.append(text)

    emit("# بنچمارک مدل‌ها")
    emit()
    emit(f"- زمان: {datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M UTC')}")
    emit(f"- کامیت: `{os.getenv('GITHUB_SHA', 'local')[:7]}`")
    emit(f"- THINK: {llm.THINK} | NUM_CTX: {llm.NUM_CTX} | MAX_TOKENS: {llm.MAX_TOKENS}")
    emit()

    for model in args.models:
        if not pull(model):
            continue
        set_model(model)
        llm.preload()
        rows: list[dict] = []
        for question in questions:
            print(f"\n▶️  {model} ← {question}", flush=True)
            row = ask(store, question)
            rows.append(row)
            dur = row.get("seconds")
            speed = (row.get("speed") or {}).get("tok_per_s")
            status = ("✅ تأیید" if row.get("verified")
                      else f"🚫 {row.get('reason') or row.get('error')}")
            print(f"   {dur}s | {speed} tok/s | {status}", flush=True)
        results[model] = rows

    # --- جدول خلاصه
    emit("## خلاصه")
    emit()
    emit("| مدل | پاسخ معتبر | میانگین زمان | میانگین سرعت |")
    emit("|---|---|---|---|")
    for model, rows in results.items():
        ok = sum(1 for r in rows if r.get("verified"))
        secs = [r["seconds"] for r in rows if r.get("seconds")]
        speeds = [(r.get("speed") or {}).get("tok_per_s", 0) for r in rows]
        speeds = [s for s in speeds if s]
        emit(
            f"| `{model}` | {ok}/{len(rows)} | "
            f"{sum(secs) / len(secs):.1f}s | "
            f"{(sum(speeds) / len(speeds)) if speeds else 0:.1f} tok/s |"
        )
    emit()

    # --- جزئیات
    for model, rows in results.items():
        emit(f"## {model}")
        emit()
        for i, row in enumerate(rows, 1):
            emit(f"### {i}. {row['question']}")
            emit()
            speed = row.get("speed") or {}
            emit(f"`{row.get('seconds')}s` · `{speed.get('tok_per_s')} tok/s` · "
                 f"زمینه `{speed.get('prompt_eval_count')}` توکن")
            emit()
            if row.get("facts"):
                emit("**پاسخ قطعی ربات:**")
                emit()
                emit("```")
                emit(row["facts"][:700])
                emit("```")
                emit()
            if row.get("text"):
                tag = "تأییدشده" if row.get("verified") else f"رد شد — {row.get('reason')}"
                emit(f"**جمع‌بندی مدل ({tag}):**")
                emit()
                emit("```")
                emit(row["text"][:900])
                emit("```")
            elif row.get("raw"):
                emit("**خروجی خام مدل:**")
                emit()
                emit("```")
                emit(row["raw"][:900])
                emit("```")
            if row.get("error"):
                emit(f"⚠️ خطا: `{row['error']}`")
            emit()

    if report_path:
        os.makedirs(os.path.dirname(report_path) or ".", exist_ok=True)
        with open(report_path, "w", encoding="utf-8") as f:
            f.write("\n".join(lines) + "\n")
        print(f"\n📝 گزارش در {report_path} نوشته شد.")

    with open("bench-results.json", "w", encoding="utf-8") as f:
        json.dump(results, f, ensure_ascii=False, indent=2, default=str)
    return 0


if __name__ == "__main__":
    sys.exit(main())
