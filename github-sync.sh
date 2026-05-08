#!/bin/bash
# GitHub Sync - Every 5 minutes: pull latest code only
set -euo pipefail

LOGFILE="/mnt/c/Users/q1138/game-news-daily/github-sync.log"
DATE=$(date "+%m-%d %H:%M")

cd /mnt/c/Users/q1138/game-news-daily || exit 1

# Handle detached HEAD gracefully
CURRENT_BRANCH=$(git branch --show-current 2>/dev/null)
if [ -z "$CURRENT_BRANCH" ]; then
  CURRENT_BRANCH="main"
  git checkout main 2>/dev/null || true
fi

LOCAL=$(git rev-parse --short=7 HEAD 2>/dev/null || echo "???")
MSG=$(git log -1 --format="%s" 2>/dev/null || echo "unknown")

# Must fetch first, otherwise origin/main is stale. Exit gracefully on DNS failure.
git fetch origin "$CURRENT_BRANCH" --quiet 2>/dev/null || true
REMOTE=$(git rev-parse --short=7 "origin/$CURRENT_BRANCH" 2>/dev/null || echo "")

if [ "$LOCAL" != "$REMOTE" ] && [ -n "$REMOTE" ] && [ "$REMOTE" != "" ]; then
  echo "[$DATE] PULL  $LOCAL -> $REMOTE | $MSG" >> "$LOGFILE"
  MAX_RETRIES=3
  for i in $(seq 1 $MAX_RETRIES); do
    NOW=$(date "+%m-%d %H:%M")
    if git pull origin "$CURRENT_BRANCH" --quiet 2>>"$LOGFILE"; then
      NEW=$(git rev-parse --short=7 HEAD)
      NEWMSG=$(git log -1 --format="%s")
      echo "[$NOW] OK    $LOCAL -> $NEW | $NEWMSG" >> "$LOGFILE"
      break
    else
      echo "[$NOW] FAIL  attempt $i/$MAX_RETRIES" >> "$LOGFILE"
      if [ $i -lt $MAX_RETRIES ]; then
        sleep $((i * 10))
      fi
    fi
  done
else
  echo "[$DATE] SYNC  $LOCAL | $MSG" >> "$LOGFILE"
fi