#!/usr/bin/env bash
# Automatisk oppdatering av COT Explorer
# Kjøres 4× daglig: 07:45, 12:30, 14:15, 17:15 CET/CEST
#
# Bruk: bash update.sh [--dry-run]
#   --dry-run  Kjør pipeline men hopp over git push

cd "$(dirname "$0")"

DRY_RUN=0
[ "$1" = "--dry-run" ] && DRY_RUN=1

LOG_DIR="$HOME/cot-explorer/logs"
mkdir -p "$LOG_DIR"
LOG="$LOG_DIR/update.log"

TOTAL=0
FAILED=0

run_step() {
    local name="$1"
    shift
    TOTAL=$((TOTAL + 1))
    echo "  $name..." >> "$LOG"
    if "$@" >> "$LOG" 2>&1; then
        echo "  $name OK" >> "$LOG"
    else
        echo "  $name FEIL (exit $?)" >> "$LOG"
        FAILED=$((FAILED + 1))
    fi
}

echo "=== $(date '+%Y-%m-%d %H:%M %Z') ===" >> "$LOG"

run_step "kalender" python3 fetch_calendar.py
run_step "COT" python3 fetch_cot.py
run_step "combined" python3 build_combined.py

# Fundamentals: kjøres kun én gang per 12 timer (FRED-data oppdateres månedlig/ukentlig)
FUND_FILE="$HOME/cot-explorer/data/fundamentals/latest.json"
if [ ! -f "$FUND_FILE" ] || [ "$(find "$FUND_FILE" -mmin +720 2>/dev/null | wc -l)" -gt 0 ]; then
    run_step "fundamentals" python3 fetch_fundamentals.py
else
    echo "  fundamentals: nylig oppdatert, hopper over" >> "$LOG"
fi

run_step "analyse" python3 fetch_all.py

# Push signaler til Telegram/Discord (kun hvis minst én er konfigurert)
if [ -n "$TELEGRAM_TOKEN" ] || [ -n "$DISCORD_WEBHOOK" ] || [ -n "$SCALP_API_KEY" ]; then
    run_step "push" python3 push_signals.py
else
    echo "  push: ingen bot konfigurert (sett TELEGRAM_TOKEN/DISCORD_WEBHOOK)" >> "$LOG"
fi

PASSED=$((TOTAL - FAILED))
echo "  Resultat: $PASSED/$TOTAL steg OK" >> "$LOG"

# Git push: kun hvis ALT lyktes og ikke dry-run
if [ "$FAILED" -gt 0 ]; then
    echo "  git: HOPPER OVER push — $FAILED steg feilet" >> "$LOG"
elif [ "$DRY_RUN" -eq 1 ]; then
    echo "  git: dry-run — hopper over push" >> "$LOG"
else
    git add data/macro/latest.json data/calendar/ data/combined/ data/fundamentals/ 2>/dev/null || true
    if git diff --cached --quiet; then
        echo "  git: ingen nye data å pushe" >> "$LOG"
    else
        git commit -m "data: oppdatering $(date '+%Y-%m-%d %H:%M')" >> "$LOG" 2>&1
        git push origin main >> "$LOG" 2>&1 && echo "  git push OK" >> "$LOG" || echo "  git push FEIL" >> "$LOG"
    fi
fi

echo "  FERDIG ($PASSED/$TOTAL steg OK)" >> "$LOG"
