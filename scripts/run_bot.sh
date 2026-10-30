#!/usr/bin/env bash
# نگه‌دارنده‌ی ربات داخل یک job از GitHub Actions.
#
# ۱) اگر ربات کرش کند، بلافاصله دوباره بالا می‌آید (تا پایان سهمیه‌ی این job).
# ۲) قبل از رسیدن به سقف ۶ ساعته‌ی Actions، خودش تمیز خارج می‌شود تا run
#    بعدی (که در صف concurrency منتظر است) جایش را بگیرد.
# ۳) اگر روی main کامیت جدیدی push شود، خودش خارج می‌شود تا run جدید
#    با کد تازه فوراً فعال شود.
#
# متغیرها:
#   BOT_RUN_MINUTES   چند دقیقه ربات polling کند (پیش‌فرض 320)
#   BOT_JOB_MINUTES   کل عمر این job (پیش‌فرض 335؛ سقف Actions = 360)
#   CHECK_UPDATES     "1" = خروج در صورت وجود کامیت جدید روی main

set -u

BOT_RUN_MINUTES="${BOT_RUN_MINUTES:-320}"
BOT_JOB_MINUTES="${BOT_JOB_MINUTES:-335}"
CHECK_UPDATES="${CHECK_UPDATES:-1}"

job_deadline=$(( $(date +%s) + BOT_JOB_MINUTES * 60 ))
attempt=0
backoff=5

log() { printf '%s [supervisor] %s\n' "$(date -u +%H:%M:%S)" "$*"; }

remote_changed() {
  [ "$CHECK_UPDATES" = "1" ] || return 1
  [ -n "${GITHUB_SHA:-}" ] || return 1
  [ "${GITHUB_REF_NAME:-}" = "main" ] || return 1
  local remote
  remote=$(timeout 30 git ls-remote origin refs/heads/main 2>/dev/null | cut -f1)
  [ -n "$remote" ] && [ "$remote" != "$GITHUB_SHA" ]
}

while :; do
  now=$(date +%s)
  remaining=$(( job_deadline - now ))
  if [ "$remaining" -lt 120 ]; then
    log "سهمیه‌ی این job تمام شد؛ خروج تمیز."
    exit 0
  fi

  run_minutes=$(( remaining / 60 ))
  [ "$run_minutes" -gt "$BOT_RUN_MINUTES" ] && run_minutes=$BOT_RUN_MINUTES

  if remote_changed; then
    log "کامیت جدید روی main پیدا شد؛ خروج تا run جدید با کد تازه شروع شود."
    exit 0
  fi

  attempt=$(( attempt + 1 ))
  log "شروع تلاش #$attempt — ربات $run_minutes دقیقه اجرا می‌شود."

  RUN_DURATION_MINUTES="$run_minutes" python EntekhabVahedBot.py
  code=$?

  if [ "$code" -eq 0 ]; then
    log "ربات تمیز خارج شد (کد ۰)."
    if [ $(( $(date +%s) + 120 )) -ge "$job_deadline" ]; then
      log "پایان سهمیه؛ خروج."
      exit 0
    fi
    # خروج تمیز ولی هنوز وقت داریم ⇒ احتمالاً چرخش برنامه‌ریزی‌شده؛ ادامه بده
    continue
  fi

  log "ربات با کد $code خارج شد؛ $((backoff)) ثانیه دیگر دوباره تلاش می‌کنم."
  sleep "$backoff"
  backoff=$(( backoff * 2 ))
  [ "$backoff" -gt 120 ] && backoff=120
done
