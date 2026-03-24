#!/bin/bash
# Auto-deploy script: pulls from GitHub and restarts service if there are changes.
# Run by cron every minute.

set -e

REPO="/home/rudolfkischer/Projects/HabbitTracker"
LOG="/home/rudolfkischer/deploy.log"
MAX_LINES=200

cd "$REPO"

# Fetch and check for changes
git fetch origin main --quiet

LOCAL=$(git rev-parse HEAD)
REMOTE=$(git rev-parse origin/main)

if [ "$LOCAL" = "$REMOTE" ]; then
  exit 0
fi

# There are new commits — pull and restart
TIMESTAMP=$(date '+%Y-%m-%d %H:%M:%S')
echo "[$TIMESTAMP] Deploying $(echo $REMOTE | head -c 7)..." >> "$LOG"

git pull origin main --quiet >> "$LOG" 2>&1
sudo systemctl restart habittracker >> "$LOG" 2>&1

echo "[$TIMESTAMP] Done." >> "$LOG"

# Trim log to last MAX_LINES lines
tail -n "$MAX_LINES" "$LOG" > "$LOG.tmp" && mv "$LOG.tmp" "$LOG"
