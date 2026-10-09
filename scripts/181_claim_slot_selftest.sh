#!/usr/bin/env bash
# Offline invariants for scripts/180_claim_slot.sh. No simulator, no GPU.
#
#   1. SLOTS=1 mutual exclusion: two holders never overlap in time.
#   2. SLOTS=2 pool: two holders overlap (the whole point of the harness).
#   3. stale recovery: a SIGKILLed holder's slot is reclaimed by the next claim.
#   4. wait timeout: a claim against a held slot exits 2 by FRUIT_CLAIM_TIMEOUT.
#   5. duplicate namespace: a second claim with a live owner's log exits 2.
#   6. owner files are removed when the holders exit.
set -uo pipefail
cd "$(dirname "$0")/.." || exit 1

tmp=$(mktemp -d)
trap 'rm -rf "$tmp"' EXIT
export FRUIT_CLAIM_DIR="$tmp/claims"
export FRUIT_CLAIM_POLL=1
claim=scripts/180_claim_slot.sh
fail=0
pass() { echo "ok: $*"; }
bad() { echo "FAIL: $*"; fail=1; }

cat > "$tmp/holder.sh" <<'EOF'
#!/usr/bin/env bash
# holder.sh <label> <seconds> <marker-file>
echo "BEGIN $1 $(date +%s.%N)" >> "$3"
sleep "$2"
echo "END $1 $(date +%s.%N)" >> "$3"
EOF
chmod +x "$tmp/holder.sh"

elapsed() {  # elapsed <start> <end>
    awk -v a="$1" -v b="$2" 'BEGIN { printf "%.1f", b - a }'
}

# --- 1. mutual exclusion with SLOTS=1 -------------------------------------
t0=$(date +%s.%N)
FRUIT_CLAIM_SLOTS=1 RUN_LIMIT=60 "$claim" "$tmp/a.log" "$tmp/holder.sh" a 2 "$tmp/marks1" &
pa=$!
FRUIT_CLAIM_SLOTS=1 RUN_LIMIT=60 "$claim" "$tmp/b.log" "$tmp/holder.sh" b 2 "$tmp/marks1" &
pb=$!
wait "$pa"; ca=$?
wait "$pb"; cb=$?
t1=$(date +%s.%N)
el=$(elapsed "$t0" "$t1")
if [ "$ca" = 0 ] && [ "$cb" = 0 ] && [ "$(grep -c '^BEGIN' "$tmp/marks1")" = 2 ] \
    && [ "$(grep -c '^END' "$tmp/marks1")" = 2 ] \
    && [ "$(sed -n '3p' "$tmp/marks1" | cut -d' ' -f1)" = "BEGIN" ] \
    && awk -v e="$el" 'BEGIN { exit !(e >= 3.5) }'; then
    pass "SLOTS=1 serializes two holders (${el}s >= 3.5s, no interleave)"
else
    bad "SLOTS=1 did not serialize (exit=$ca/$cb elapsed=${el}s marks=$(tr '\n' ';' < "$tmp/marks1"))"
fi

# --- 2. the pool actually overlaps with SLOTS=2 ---------------------------
t0=$(date +%s.%N)
FRUIT_CLAIM_SLOTS=2 RUN_LIMIT=60 "$claim" "$tmp/c.log" "$tmp/holder.sh" c 2 "$tmp/marks2" &
pc=$!
FRUIT_CLAIM_SLOTS=2 RUN_LIMIT=60 "$claim" "$tmp/d.log" "$tmp/holder.sh" d 2 "$tmp/marks2" &
pd=$!
wait "$pc"; cc=$?
wait "$pd"; cd_=$?
t1=$(date +%s.%N)
el=$(elapsed "$t0" "$t1")
if [ "$cc" = 0 ] && [ "$cd_" = 0 ] && [ "$(sed -n '3p' "$tmp/marks2" | cut -d' ' -f1)" = "END" ] \
    && awk -v e="$el" 'BEGIN { exit !(e < 3.5) }'; then
    pass "SLOTS=2 overlaps two holders (${el}s < 3.5s)"
else
    bad "SLOTS=2 did not overlap (exit=$cc/$cd_ elapsed=${el}s marks=$(tr '\n' ';' < "$tmp/marks2"))"
fi

# --- 3. stale recovery: SIGKILL the holder, the slot is reclaimed ---------
# The holder execs into `sleep` with fd 9 held, so killing it is exactly the
# "dead PID" case the kernel's flock release must cover.
bash -c "exec 9>\"$FRUIT_CLAIM_DIR/slot0.lock\"; flock -n 9; exec sleep 60" &
hp=$!
sleep 0.5
kill -9 "$hp" 2>/dev/null
wait "$hp" 2>/dev/null
t0=$(date +%s.%N)
FRUIT_CLAIM_SLOTS=1 FRUIT_CLAIM_TIMEOUT=15 RUN_LIMIT=10 "$claim" "$tmp/s.log" true
cs=$?
t1=$(date +%s.%N)
el=$(elapsed "$t0" "$t1")
if [ "$cs" = 0 ] && awk -v e="$el" 'BEGIN { exit !(e < 8) }'; then
    pass "a SIGKILLed holder's slot is reclaimed (${el}s)"
else
    bad "stale slot not reclaimed (exit=$cs elapsed=${el}s)"
fi

# --- 4. wait timeout: held slot -> exit 2 by FRUIT_CLAIM_TIMEOUT ----------
bash -c "exec 9>\"$FRUIT_CLAIM_DIR/slot0.lock\"; flock -n 9; exec sleep 30" &
hp=$!
sleep 0.5
t0=$(date +%s.%N)
FRUIT_CLAIM_SLOTS=1 FRUIT_CLAIM_TIMEOUT=2 RUN_LIMIT=10 "$claim" "$tmp/t.log" true
ct=$?
t1=$(date +%s.%N)
el=$(elapsed "$t0" "$t1")
kill -9 "$hp" 2>/dev/null
wait "$hp" 2>/dev/null
if [ "$ct" = 2 ] && awk -v e="$el" 'BEGIN { exit !(e < 8) }'; then
    pass "wait times out with exit 2 (${el}s)"
else
    bad "wait timeout wrong (exit=$ct elapsed=${el}s)"
fi

# --- 5. duplicate namespace refusal ---------------------------------------
FRUIT_CLAIM_SLOTS=2 RUN_LIMIT=60 FRUIT_CLAIM_LABEL=dup "$claim" "$tmp/dup.log" "$tmp/holder.sh" dup 3 "$tmp/marks3" &
pe=$!
sleep 1
FRUIT_CLAIM_SLOTS=2 RUN_LIMIT=10 "$claim" "$tmp/dup.log" true
cdup=$?
wait "$pe"; ce=$?
if [ "$cdup" = 2 ] && [ "$ce" = 0 ]; then
    pass "duplicate log path refused (exit 2) while the owner completes"
else
    bad "duplicate namespace not refused (dup exit=$cdup owner exit=$ce)"
fi

# --- 6. owner files cleaned up --------------------------------------------
if [ -z "$(find "$FRUIT_CLAIM_DIR" -name '*.owner' -print -quit 2>/dev/null)" ]; then
    pass "owner files removed on exit"
else
    bad "owner files left behind: $(find "$FRUIT_CLAIM_DIR" -name '*.owner' -print | tr '\n' ' ')"
fi

if [ "$fail" -ne 0 ]; then
    echo "FAIL: claim slot selftest"
    exit 1
fi
echo "PASS: claim slot selftest"
