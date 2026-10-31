"""
سنجش کیفیت «تحلیل با مدل» روی یک مجموعه‌ی طلایی.

بدون عدد، «بهتر شد» فقط حس است. این اسکریپت چند پرسش ثابت را از مدل محلی یا
API می‌پرسد و سه معیار عینی را می‌سنجد:

    format   خط اول پاسخ با «نتیجه:» شروع شده باشد (قرارداد خروجی)
    entity   اسم استاد/درسی که در پرسش آمده، در پاسخ آمده باشد
    verify   اعتبارسنجی اعداد و ساعت (verify_analysis_text) پاس شده باشد

اجرا:
    python scripts/eval_deep.py                     # مدل محلی، همه‌ی موارد
    python scripts/eval_deep.py --provider api      # سرویس ابری
    python scripts/eval_deep.py --limit 4           # فقط ۴ مورد (برای CI سریع)
    python scripts/eval_deep.py --json out.json

کد خروج ۰ = نرخ موفقیت ≥ آستانه (پیش‌فرض ۰٫۶)، وگرنه ۱.
"""

from __future__ import annotations

import argparse
import json
import os
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import deep  # noqa: E402
from retrieval import DataStore, normalize  # noqa: E402

GOLDEN = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                      "eval", "golden.json")


def load_cases() -> list[dict]:
    with open(GOLDEN, encoding="utf-8") as handle:
        return json.load(handle)["items"]


def score_case(case: dict, result: dict) -> dict:
    """سه معیار عینی + دلیل شکست."""
    text = (result.get("text") or "").strip()
    first = text.splitlines()[0].strip() if text else ""
    lowered = normalize(text)
    entity_ok = all(normalize(e) in lowered for e in case.get("entities", []))
    forbid_hit = [f for f in case.get("forbid", []) if normalize(f) in lowered]

    return {
        "id": case["id"],
        "ok": bool(result.get("ok")),
        "format": first.startswith("نتیجه"),
        "entity": entity_ok,
        "verify": bool(result.get("ok")),
        "forbid_hit": forbid_hit,
        "passed": bool(result.get("ok")) and first.startswith("نتیجه")
                  and entity_ok and not forbid_hit,
        "reason": result.get("reason", ""),
        "elapsed": result.get("elapsed", 0.0),
        "text": text,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="سنجش کیفیت تحلیل مدل")
    parser.add_argument("--provider", choices=["local", "api"], default="local")
    parser.add_argument("--limit", type=int, default=0, help="حداکثر تعداد مورد")
    parser.add_argument("--threshold", type=float, default=0.6)
    parser.add_argument("--json", dest="json_path", default="")
    parser.add_argument("--show", action="store_true", help="چاپ متن پاسخ‌ها")
    args = parser.parse_args()

    cases = load_cases()
    if args.limit:
        cases = cases[: args.limit]

    store = DataStore(".")
    rows = []
    started = time.time()
    print(f"🧪 سنجش {len(cases)} مورد با provider={args.provider} "
          f"({deep.provider_label(args.provider)})\n")

    for case in cases:
        result = deep.analyze(store, case["query"], provider=args.provider)
        row = score_case(case, result)
        rows.append(row)
        mark = "✅" if row["passed"] else "❌"
        detail = "" if row["passed"] else (
            f"ok={row['ok']} format={row['format']} entity={row['entity']} "
            f"reason={row['reason'][:40]}"
        )
        print(f"{mark} {row['id']:<28} {row['elapsed']:>6.1f}s  {detail}")
        if args.show and row["text"]:
            for line in row["text"].splitlines():
                print(f"      {line}")

    passed = sum(1 for row in rows if row["passed"])
    rate = passed / max(len(rows), 1)
    total_time = time.time() - started
    print(f"\n📊 {passed}/{len(rows)} قبول ({rate:.0%}) در {total_time:.1f} ثانیه")
    print(f"   format: {sum(r['format'] for r in rows)}/{len(rows)} · "
          f"entity: {sum(r['entity'] for r in rows)}/{len(rows)} · "
          f"verify: {sum(r['verify'] for r in rows)}/{len(rows)}")

    if args.json_path:
        with open(args.json_path, "w", encoding="utf-8") as handle:
            json.dump({"provider": args.provider, "model": deep.provider_label(args.provider),
                       "passed": passed, "total": len(rows), "rate": rate,
                       "seconds": round(total_time, 1), "rows": rows},
                      handle, ensure_ascii=False, indent=2)
        print(f"   گزارش JSON: {args.json_path}")

    return 0 if rate >= args.threshold else 1


if __name__ == "__main__":
    sys.exit(main())
