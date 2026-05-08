#!/bin/bash
# GitHub Sync - Every 5 minutes: pull latest code only

LOGFILE="/mnt/c/Users/q1138/game-news-daily/github-sync.log"
DATE=$(date)

cd /mnt/c/Users/q1138/game-news-daily || exit 1

CURRENT_BRANCH=$(git branch --show-current 2>/dev/null || echo "main")
LOCAL=$(git rev-parse HEAD 2>/dev/null)
REMOTE=$(git rev-parse "origin/$CURRENT_BRANCH" 2>/dev/null)

if [ "$LOCAL" != "$REMOTE" ] && [ -n "$REMOTE" ]; then
  echo "[$DATE] Syncing..." >> "$LOGFILE"
  MAX_RETRIES=3
  for i in $(seq 1 $MAX_RETRIES); do
    if git pull origin "$CURRENT_BRANCH" 2>>"$LOGFILE"; then
      echo "[$DATE] Pull succeeded on attempt $i" >> "$LOGFILE"
      break
    else
      echo "[$DATE] Pull failed (attempt $i/$MAX_RETRIES), retrying in ${i}0s..." >> "$LOGFILE"
      if [ $i -lt $MAX_RETRIES ]; then
        sleep $((i * 10))
      fi
    fi
  done
fi