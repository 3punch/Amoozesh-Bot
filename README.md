# 🎓 Course Registration Assistant

[![Telegram Bot](https://github.com/3punch/Amoozesh-Bot/actions/workflows/bot.yml/badge.svg?branch=main)](https://github.com/3punch/Amoozesh-Bot/actions/workflows/bot.yml)
[![Model Quality](https://github.com/3punch/Amoozesh-Bot/actions/workflows/model-check.yml/badge.svg?branch=main)](https://github.com/3punch/Amoozesh-Bot/actions/workflows/model-check.yml)
[![Python 3.10+](https://img.shields.io/badge/Python-3.10%2B-3776AB?logo=python&logoColor=white)](https://www.python.org/)
[![MIT License](https://img.shields.io/badge/License-MIT-2ea44f.svg)](LICENSE)

**A Persian-language Telegram assistant that turns course schedules, enrollment rules, curriculum data, and student feedback into useful, evidence-backed answers.**

The project is more than a chatbot connected to an LLM. Course eligibility, schedules, and capacities come from structured data. Instructor feedback is supported by archived student comments and explicit statistics. Optional model-generated analysis is checked for unsupported dates, scores, and class times before it is shown.

## Highlights

| Capability | Description |
|---|---|
| 📚 Course information | Current-term offerings, instructors, schedules, capacities, prerequisites, and eligible cohorts |
| 👩‍🏫 Instructor feedback | Archived student comments, instructor profiles, and side-by-side comparisons |
| ⚡ Fast, model-free answers | Structured retrieval and deterministic rules; usually under a second |
| 🧠 Local model analysis | Optional Qwen analysis through Ollama on GitHub Actions; requested by the user |
| 🔐 Cloud API | Optional OpenAI-compatible endpoint; disabled unless an API key is configured |
| 🛡️ Grounding and validation | Data-backed answers remain available if a model is unavailable; fabricated dates, scores, and times are rejected |
| 🧪 Quality checks | Offline tests, a golden question set, model-evaluation workflows, and benchmarks |
| 🚀 Hosted operation | The bot runs on GitHub Actions; no personal computer needs to stay online |

> **Honest limitation:** the fast path is retrieval and rules, not a language model. It prioritizes speed and traceable evidence; it will not match the reasoning or flexibility of a strong API model on every ambiguous question.

## Example answers

The bot replies in Persian. These abbreviated examples show its actual response style.

### Instructor feedback

```text
👤 آذر ابوالقاسمی · بر پایه‌ی ۲۳ پیام آرشیو
💬 نظرهای واقعی دانشجوها (عین متن؛ تجربه‌ها ممکن است متفاوت باشد):
“استادش رو باهاش این اصول مدیریت داشتم اکی بود واقعا آذر ابوالقاسمی”
“اگه استادش آذر ابوالقاسمی باشه خیلی راحته و میشه خوب نمره گرفت”
🎯 جمع‌بندی آماری: استاد خوبی است؛ ارزیابی دانشجویان مثبت و یکدست است.
📊 ارزیابی دانشجویان: ۹.۶ از ۱۰
```

The fast answer shows selected, filtered archive comments before the statistical summary. Comments are presented as individual experiences, not as universal claims.

### Course eligibility

```text
🎯 نتیجه: «هوش مصنوعی» برای ورودی ۱۴۰۴ مجاز نیست ❌
این درس فقط برای ورودی ۱۴۰۳ مجاز است و برای این ورودی باز نیست.

⛔ ارائه‌هایی که برای این ورودی باز نیستند
• هوش مصنوعی — پویا درخشان برجویی · چهارشنبه ۱۳:۳۰–۱۷:۴۰ · ظرفیت ۵۵ · فقط ورودی ۱۴۰۳
```

### Instructor comparison

```text
⚖️ مقایسه‌ی محمد غلامیان، ابوالفضل تهرانیان
🎯 نتیجه: نظرهای آرشیو به «محمد غلامیان» متمایل‌تر است؛ ۲ مقایسه‌ی مستقیم ثبت شده و نتیجه به سود اوست.

👤 محمد غلامیان — ۲۵ پیام · ۲ نظر مثبت · ۶ نظر منفی
👤 ابوالفضل تهرانیان — ۲۴ پیام · ۳ نظر مثبت · ۷ نظر منفی
```

### Schedule lookup

A schedule question returns the relevant course offerings without unrelated instructor-review text:

```text
📚 کلاس‌های این ترم «محمد همامی»
• ساختمان داده ها و الگوریتم ها — یکشنبه ۱۴:۲۰–۱۷:۴۰ · ظرفیت ۵۵ · فقط ورودی ۱۴۰۴
• ساختمان داده ها و الگوریتم ها — سه شنبه ۱۰:۳۰–۱۲:۱۰ و ۱۲:۴۰–۱۴:۲۰ · ظرفیت ۵۵ · فقط ورودی ۱۴۰۴
```

## Answer modes

| | **Fast** | **🧠 Local model** | **⚡ API** |
|---|---|---|---|
| How to use | Automatic | Button below an answer or `/deep` | Button below an answer or `/api` |
| Daily per-user limit | Unlimited | **3 successful requests** | **1 successful request** |
| Typical latency | Usually under 1 second | Several minutes on a CPU runner | Depends on the provider; typically seconds |
| Evidence | Structured records and selected archived comments | Full relevant comments, extracted evidence, and structured data | Same analysis context, using the configured provider |
| API key required | No | No | **Yes** |
| Failure behavior | — | Data-backed answer remains available | Data-backed answer remains available; infrastructure failures refund quota |

Model analysis is opt-in. Send a question to get the fast answer, then use a button or a command such as:

```text
/deep غلامیان یا تهرانیان؟
/api غلامیان یا تهرانیان؟
```

The API option is only shown when an API key is configured. Callback buttons are single-use and expire after 30 minutes.

## How model analysis is kept grounded

- The analysis prompt asks for a direct Persian answer, not a raw dump of comments.
- Key evidence and numerical summaries are supplied alongside relevant full comments.
- Comments that mention multiple instructors are attributed by clause where possible.
- The result validator rejects unsupported class times, years, scores, and malformed/non-Persian output.
- If a model fails or its answer is rejected, the bot keeps the data-backed response instead of presenting the rejected answer.

These safeguards reduce avoidable errors; they do **not** guarantee that every qualitative interpretation is correct.

## Model quality and performance

A previous run of `qwen2.5:7b` on a GitHub Actions CPU runner took approximately 127–343 seconds for three sample questions. Results were mixed: it handled some instructor questions, but missed a direct winner in a comparison and made a weak interpretation on another question. The local model is therefore optional rather than part of the fast path.

Use the `Deep Mode Check` workflow to run fresh examples or evaluate the golden set. Treat those reports as measurements for the specific run/model—not as a general accuracy guarantee.

### Model caching

Ollama model files are **not stored in the Git repository**. The bot workflow uses the GitHub Actions cache and checks whether the model is already present before calling `ollama pull`. A cache hit normally avoids downloading the model again, but Actions caches are not permanent: GitHub may evict a cache, so a future download cannot be ruled out. For persistent model storage, use an always-on host with persistent disk; GitHub-hosted runners are ephemeral.

## Daily quotas

Quotas are keyed by Telegram user ID and reset at midnight Tehran time.

| Mode | Limit |
|---|---:|
| Local deep analysis | 3 per user per day |
| Cloud API analysis | 1 per user per day |
| Fast answers | Unlimited |

Quota state is persisted to the `bot-state` branch when configured. Infrastructure failures refund the relevant deep/API quota. A model response that ran but failed answer validation still consumes quota.

> Telegram user IDs are not strong identity verification. A person can use another Telegram account to obtain a separate quota.

## Deploy on GitHub Actions

The repository is configured to run the bot through GitHub Actions. **Netlify is not suitable for hosting this bot**: this is a long-running Python Telegram polling process, not a static website.

1. Create a Telegram bot with [@BotFather](https://t.me/BotFather).
2. In the GitHub repository, open **Settings → Secrets and variables → Actions**.
3. Add a repository secret named `TELEGRAM_BOT_TOKEN` with the bot token as its value.
4. Open **Actions → Run Telegram Bot 24/7 → Run workflow** to start it.

The workflow also runs on pushes to `main` and on a scheduled rotation. It uses concurrency controls to avoid running multiple polling instances at once. GitHub Actions has execution-time limits; this is a scheduled, continuously rotated process—not a dedicated always-on server guarantee.

### Enable the optional API

1. Create an API key with an OpenAI-compatible provider (the default configuration targets OpenRouter).
2. Add it in **Settings → Secrets and variables → Actions** as `OPENROUTER_API_KEY`.
3. The default model is `qwen/qwen-2.5-72b-instruct`. To use another compatible provider, configure `API_BASE_URL` and `API_MODEL` in the workflow.

Never commit API keys or bot tokens to the repository.

## Run locally (development)

Python 3.10 or newer is required.

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt

# Run the model-free bot
TELEGRAM_BOT_TOKEN="your-token" python EntekhabVahedBot.py
```

To exercise local model analysis, install Ollama separately, pull the configured model, and set the relevant environment variables. Local development is optional; normal bot operation is configured through GitHub Actions.

Ask a question without Telegram:

```bash
python ask.py "استاد آذر ابوالقاسمی چطور استادی هستن"
python ask.py --context "بهینه سازی خطی برای ورودی ۱۴۰۴ مجازه؟"
python ask.py --json "ساختمان داده و الگوریتم ها"
python ask.py --deep "غلامیان یا تهرانیان؟"
python ask.py --api "غلامیان یا تهرانیان؟"  # requires API_KEY
```

## Configuration reference

| Variable | Default | Purpose |
|---|---|---|
| `TELEGRAM_BOT_TOKEN` | — | Required Telegram bot token |
| `MODEL_SUMMARY` | `0` | Add a local-model summary automatically to fast answers (`1` enables it) |
| `DEEP_MODE` | `1` | Enable the local-analysis button and `/deep` |
| `MODEL_NAME` | `qwen2.5:7b` | Ollama model name |
| `DEEP_CONTEXT_CHARS` | `14000` | Maximum analysis context size |
| `DEEP_MAX_TOKENS` | `500` | Maximum local analysis output tokens |
| `DEEP_NUM_CTX` | `8192` | Local analysis context window |
| `DEEP_TIMEOUT` | `900` | Local analysis timeout in seconds |
| `API_KEY` | — | Cloud API key; empty disables the API option |
| `API_MODEL` | `qwen/qwen-2.5-72b-instruct` | OpenAI-compatible model identifier |
| `API_BASE_URL` | OpenRouter URL | OpenAI-compatible API base URL |
| `API_TIMEOUT` | `120` | API request timeout in seconds |
| `API_MAX_TOKENS` | `700` | Maximum API response tokens |
| `QUOTA_PERSIST` | `1` | Persist quota state to the state branch |
| `QUOTA_STATE_BRANCH` | `bot-state` | Branch used for quota persistence |
| `MAX_CONTEXT_CHARS` | `4000` | Fast-path model context limit |
| `MAX_PROFESSOR_BLOCKS` | `2` | Maximum professor blocks in fast context |
| `MAX_COURSE_ROWS` | `5` | Maximum course rows in fast context |
| `BOT_RUN_MINUTES` | `320` | Runtime for one scheduled bot instance |
| `BOT_JOB_MINUTES` | `335` | Total job runtime; must remain below the Actions limit |

## Data sources

| File | Purpose |
|---|---|
| `courses.xlsx` | Current-term course offerings, instructors, schedules, capacity, and cohort fields |
| `professors.txt` | Instructor profiles and archived student feedback |
| `knowledge_base.txt` | Cohort-specific course eligibility rules |
| `curriculum.pdf` | Curriculum and degree-plan reference |

The repository data is the source of truth. Update the term-specific files when course offerings or enrollment rules change.

## Architecture

```text
Telegram update
      │
      ▼
EntekhabVahedBot.py  — command handling, routing, message splitting
      │
      ├── retrieval.py — Persian normalization, course/professor matching, eligibility rules
      │
      ├── fallback.py  — fast data-backed answers, summaries, selected comments
      │
      └── deep.py      — analysis context, local/API provider routing, answer verification
             ├── llm.py     — Ollama client
             └── api_llm.py — optional OpenAI-compatible API client

quota.py — per-user daily quotas and optional state-branch persistence
```

## Testing and evaluation

Create a virtual environment, install dependencies, then run:

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt

python tests/test_offline.py
python scripts/eval_deep.py --provider local --limit 5 --show
python scripts/eval_deep.py --provider api --limit 5 --show
python bench.py --models qwen2.5:7b,qwen3:8b
```

- `tests/test_offline.py` exercises retrieval, fast answers, model/API clients with fake servers, Telegram handlers, validation, quota logic, and workflow configuration without requiring a live model or Telegram account.
- The fast-path tests include the golden questions, every instructor profile, and every distinct course name in the current repository data.
- `eval/golden.json` contains 10 representative questions. `scripts/eval_deep.py` reports format, entity-coverage, and verification checks. Run it with an API provider only if a valid `API_KEY` is configured; API usage may incur provider charges.
- GitHub Actions workflows provide scheduled bot execution, model checks, deep-mode evaluation, and model benchmarking.

## Workflows

| Workflow | Purpose |
|---|---|
| `bot.yml` — Run Telegram Bot 24/7 | Runs and rotates the Telegram bot; checks tests before startup and reports test failures in an issue |
| `model-check.yml` — Test Model Quality | Runs model quality checks |
| `deep-check.yml` — Deep Mode Check | Runs example analysis and optionally evaluates the golden set |
| `bench.yml` — Benchmark Models | Compares selected local models |

Generated reports are published as workflow artifacts or issues; they are not committed as build outputs.

## Known limitations

- Fast retrieval is keyword-based, not embedding-based. Unfamiliar aliases, misspellings, and ambiguous questions may not match correctly.
- Sentiment and theme counts use rules. Sarcasm and informal Persian can be misclassified; inspect the quoted comments and source data before making a high-stakes decision.
- Local Qwen analysis runs on CPU in GitHub-hosted runners and can take several minutes. Its qualitative reasoning is not guaranteed to be correct, even when its numeric claims pass validation.
- The API option requires a user-configured provider key and may incur charges. It is disabled without a key.
- Non-text messages such as voice notes, images, and stickers are not supported.
- GitHub Actions is subject to runtime and scheduling limits. The bot is automatically rotated; this is not equivalent to a dedicated always-on server.
- The assistant can only answer from repository data. Keep the course and eligibility files up to date.

## Repository layout

```text
EntekhabVahedBot.py   Telegram bot entry point and handlers
retrieval.py          Persian text normalization, matching, and eligibility logic
fallback.py           Fast data-backed answer engine and validation helpers
deep.py               Deep analysis context construction and provider routing
api_llm.py            Optional OpenAI-compatible API client
quota.py              Per-user daily quotas and persistence
llm.py                Ollama client
prompts.py             System and analysis prompts
ask.py                 Command-line question interface
bench.py               Model benchmarking utility
scripts/run_bot.sh     Bot process supervision and scheduled rotation
eval/golden.json       Golden evaluation questions
scripts/eval_deep.py   Deep-analysis evaluator
tests/test_offline.py  Offline regression tests
.github/workflows/     GitHub Actions automation
```

## License

This project is licensed under the [MIT License](LICENSE).
