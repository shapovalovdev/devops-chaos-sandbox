#!/usr/bin/env bash
# Disk capacity failure injection scenario
# Resolves #4.

echo "--- Injecting disk exhaustion scenario ---"

TARGET_DIR="/var/log"
JUNK_FILE="$TARGET_DIR/system-journal-cache.tmp"
HEADROOM_MB=100

if [ -f "$JUNK_FILE" ]; then
  echo "Junk file $JUNK_FILE already exists. Disk already filled. Skipping."
  exit 0
fi

# Calculate free blocks on targeted volume in MB
FREE_MB=$(df -m "$TARGET_DIR" | tail -n1 | awk '{print $4}')

echo "Current free disk space on $TARGET_DIR: ${FREE_MB}MB"

if [ "$FREE_MB" -le "$HEADROOM_MB" ]; then
  echo "Disk is already below the target headroom of ${HEADROOM_MB}MB. No-op."
  exit 0
fi

FILL_SIZE=$(( FREE_MB - HEADROOM_MB ))
echo "Writing dummy file of size ${FILL_SIZE}MB to $JUNK_FILE..."

# Write zero-blocks safely
dd if=/dev/zero of="$JUNK_FILE" bs=1M count="$FILL_SIZE" status=progress

echo "Disk filled up to ${HEADROOM_MB}MB headroom."
echo "Restore command: sudo rm -f $JUNK_FILE"
exit 0
