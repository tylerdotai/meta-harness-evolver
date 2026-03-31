#!/bin/bash
# Lightweight validation before running full benchmark.
set -e

CANDIDATE_DIR="$1"
if [ -z "$CANDIDATE_DIR" ]; then
    echo "Usage: $0 <candidate_dir>"
    exit 1
fi

HARNESS_DIR="$CANDIDATE_DIR/harness"

echo "[VALIDATE] Checking $HARNESS_DIR..."

# Check required files
for f in SOUL.md IDENTITY.md AGENTS.md TOOLS.md; do
    if [ ! -f "$HARNESS_DIR/$f" ]; then
        echo "[VALIDATE] FAIL: Missing required file: $f"
        exit 1
    fi
done

# Check no forbidden git push rules
if grep -q "git push.*~/flume/" "$HARNESS_DIR/AGENTS.md" 2>/dev/null; then
    echo "[VALIDATE] FAIL: AGENTS.md contains forbidden ~/flume/ git push rule"
    exit 1
fi

# Check SOUL.md not suspiciously small
SOUL_SIZE=$(wc -c < "$HARNESS_DIR/SOUL.md")
if [ "$SOUL_SIZE" -lt 500 ]; then
    echo "[VALIDATE] WARNING: SOUL.md is suspiciously small ($SOUL_SIZE bytes)"
fi

echo "[VALIDATE] OK — all checks passed"
exit 0
