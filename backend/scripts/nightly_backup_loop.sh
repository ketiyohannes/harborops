#!/bin/sh
set -eu

HOUR="${BACKUP_SCHEDULE_HOUR:-2}"
MINUTE="${BACKUP_SCHEDULE_MINUTE:-0}"

while true; do
  NOW_EPOCH="$(date +%s)"
  TARGET_EPOCH="$(date -d "$(date +%Y-%m-%d) ${HOUR}:${MINUTE}:00" +%s)"

  if [ "$NOW_EPOCH" -ge "$TARGET_EPOCH" ]; then
    TARGET_EPOCH="$(date -d "tomorrow ${HOUR}:${MINUTE}:00" +%s)"
  fi

  SLEEP_SECONDS=$((TARGET_EPOCH - NOW_EPOCH))
  sleep "$SLEEP_SECONDS"

  python manage.py backup_db || true

  sleep 60
done
