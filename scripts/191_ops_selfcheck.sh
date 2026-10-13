#!/usr/bin/env bash
# =============================================================================
# scripts/191_ops_selfcheck.sh - periodic ops self-check / anti-stall probe.
#
#   scripts/191_ops_selfcheck.sh                 # one check, human report
#   scripts/191_ops_selfcheck.sh --watch 300     # loop every 300 s; transitions
#                                                # + one line per check to
#                                                # logs/ops/watch.log
#   scripts/191_ops_selfcheck.sh --selftest      # offline synthetic-stall test
#   scripts/191_ops_selfcheck.sh --help
#
# WHAT IT CHECKS (all read-only; the tool never kills, restarts or moves
# anything - recovery commands are PRINTED, the operator or wrapper runs them):
#
#   sims      running simulator processes, matched by a PATH-ANCHORED pattern
#             (`(^|/)python\.sh( |$)` / `(^|/)kit/python/bin/python3( |$)`, so
#             a stray `foo_python.sh` helper is not read as a sim), deduplicated
#             by process group. Each is mapped to its log (fd 1, fallback: the
#             newest *.log under logs/, excluding logs/ops), and the report
#             shows that log's size, mtime age and the growth since the
#             previous check (state: logs/ops/state.tsv).
#   claims    logs/claims/slotN.lock + slotN.owner: live owner, stale owner
#             (dead pid - the kernel already released the lock) or free/locked
#             (probed with `flock -n`, no content change).
#   lanes     claim wrappers / lane drivers alive (default pattern
#             `[1]54_claim_run|[1]80_claim_slot|_driver`): while one is alive
#             the `[wrap]` action is downgraded to a hint - the lane may still
#             be wrapping, and a manual wrap could collide with it.
#   artifacts the newest logs per area (default logs/*/*.log, logs/ops/
#             always excluded), top OPS_TOP_N by mtime, with age and size.
#   git       current branch, dirty-path count, last commit's age, the newest
#             tags and whether HEAD is tagged.
#   gpu       `nvidia-smi --query-gpu=utilization.gpu,memory.used ...`; the
#             section degrades to n/a when there is no GPU/nvidia-smi.
#   load      /proc/loadavg.
#   perms     best effort (skipped silently when absent): pending permission
#             asks in the OpenCode session store (session_pending) and recent
#             external_directory asks (permission rows) of this machine's
#             opencode.db, queried read-only via sqlite3.
#
# VERDICTS (and exit codes - a wrapper can branch on 2):
#
#   OK            nothing to do.                                         (0)
#   STALLED-SIM   a sim runs but its log has not grown for > OPS_STALL_S;
#                 no recovery is confidently identified (e.g. no corroborating
#                 evidence yet) - report-only.                           (0)
#   STALLED-CHAIN no sim runs and the newest chain log is stale, or there is
#                 no chain activity at all - report-only.                (0)
#   ACTION        a stall with an identified recovery: the exact kill/resume,
#                 wrap-finish, stale-claim or permission lines are printed
#                 under `actions:`.                                      (2)
#
# The five stall classes this targets (P-PLAN, .slim/deepwork/...):
#   (a) a lane stuck on an unanswerable permission (detect pending asks;
#       respawn the lane with a corrected prompt);
#   (b) a renderer wedge - a sim process whose log stops growing (kill the
#       stale session, resume its chain by re-running the wrapper invocation);
#   (c) a dead lane after a detached chain - "chain done, wrap never
#       happened" (detect the completion marker + a dirty tree, finish the
#       wrap - unless a claim wrapper is still alive);
#   (d) long idle lanes (STALLED-CHAIN: flag and ping/respawn);
#   (e) resource waste - stale claims, a wedged sim with an idle GPU (the
#       GPU-idle clause escalates only once the log has been frozen >= 2x
#       OPS_STALL_S: an idle GPU alone is not corroboration).
# The recovery playbook per class is in docs/OPS.md.
#
# DEFAULT MODE IS SAFE TO RUN WHILE A SIM IS RUNNING: it only reads (stat,
# readlink /proc, pgrep, ps, git, flock probe, read-only sqlite). Nothing is
# signalled and nothing is written outside logs/ops/.
#
# ENVIRONMENT (all optional):
#   OPS_ROOT            repo root                  (default: script's parent)
#   OPS_LOGS_DIR        log root                   (default: $OPS_ROOT/logs)
#   OPS_CLAIM_DIR       slot dir                   (default: $OPS_LOGS_DIR/claims)
#   OPS_STATE_FILE      growth state               (default: $OPS_LOGS_DIR/ops/state.tsv)
#   OPS_WATCH_LOG       watch records              (default: $OPS_LOGS_DIR/ops/watch.log)
#   OPS_STALL_S         sim-log frozen threshold   (default: 300 s)
#   OPS_CHAIN_S         chain-log stale threshold  (default: 600 s)
#   OPS_TOP_N           artifact rows              (default: 5)
#   OPS_CHAIN_GLOB      chain-log glob under logs  (default: */*.log; the
#                       logs/ops/ dir is always excluded from the scan)
#   OPS_SIM_PATTERN     pgrep -f pattern, path-anchored
#                       (default: (^|/)[p]ython\.sh( |$)|(^|/)[k]it/python/bin/python3( |$))
#   OPS_LANE_PATTERN    pgrep -f pattern for claim wrappers / lane drivers
#                       (default: [1]54_claim_run|[1]80_claim_slot|_driver)
#   OPS_GPU_QUERY       nvidia-smi command; set empty to skip (default: query)
#   OPS_GPU_IDLE_PCT    idle-clause escalation pct (default: 5; the clause
#                       needs the log frozen >= 2x OPS_STALL_S to escalate)
#   OPS_WEDGE_MARKERS   grep -E crash/wedge regex used on log tails
#   OPS_DONE_MARKERS    grep -E completion regex   (dirty-tree wrap hint;
#                       default: fingerprint: matches|[claim_(run|slot)] exit=0|[fruit] DONE)
#   OPS_PERMISSION_S    "recent permission ask" window (default: 3600 s)
#   OPS_OPENCODE_DB     session store path; point at a missing file to skip
#
# EXIT CODES: 0 OK/STALLED-*; 2 ACTION; 1 --selftest failure; 64 usage error.
# =============================================================================
set -uo pipefail

script_dir=$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)
self_path=$script_dir/$(basename "${BASH_SOURCE[0]}")
repo=${OPS_ROOT:-$(cd "$script_dir/.." && pwd)}

logs=${OPS_LOGS_DIR:-$repo/logs}
claims=${OPS_CLAIM_DIR:-$logs/claims}
state_file=${OPS_STATE_FILE:-$logs/ops/state.tsv}
watch_log=${OPS_WATCH_LOG:-$logs/ops/watch.log}
stall_s=${OPS_STALL_S:-300}
chain_s=${OPS_CHAIN_S:-600}
top_n=${OPS_TOP_N:-5}
chain_glob=${OPS_CHAIN_GLOB:-'*/*.log'}
sim_pattern=${OPS_SIM_PATTERN:-'(^|/)[p]ython\.sh( |$)|(^|/)[k]it/python/bin/python3( |$)'}
lane_pattern=${OPS_LANE_PATTERN:-'[1]54_claim_run|[1]80_claim_slot|_driver'}
# NOTE the `-` (not `:-`): an explicitly empty OPS_GPU_QUERY disables the probe.
gpu_query=${OPS_GPU_QUERY-nvidia-smi --query-gpu=utilization.gpu,memory.used --format=csv,noheader}
gpu_idle_pct=${OPS_GPU_IDLE_PCT:-5}
wedge_re=${OPS_WEDGE_MARKERS:-'Too many open files|\[collect\] STALL|Texture creation failed|core dumped|SIGSEGV|Segmentation fault|Traceback \(most recent call last\)|TIMEOUT'}
done_re=${OPS_DONE_MARKERS:-'fingerprint: matches|\[claim_(run|slot)\] exit=0|\[fruit\] DONE'}
# The group-kill line is refused when the sim's pgid equals this tool's own:
# `kill -- -$pgid` would take the tool (and the shell that launched it) down.
own_pgid=$(ps -o pgid= -p $$ 2>/dev/null | tr -d ' ')
[ -n "$own_pgid" ] || own_pgid=$$
permission_s=${OPS_PERMISSION_S:-3600}
opencode_db=${OPS_OPENCODE_DB:-$HOME/.local/share/opencode/opencode.db}

is_num() { case "$1" in ''|*[!0-9]*) return 1 ;; *) return 0 ;; esac; }
for v in stall_s chain_s top_n gpu_idle_pct permission_s; do
    eval "val=\$$v"
    is_num "$val" || eval "$v=$(case $v in stall_s) echo 300;; chain_s) echo 600;; top_n) echo 5;; gpu_idle_pct) echo 5;; permission_s) echo 3600;; esac)"
done

usage() {
    awk 'NR > 1 && /^#/ { sub(/^# ?/, ""); print; next } NR > 1 { exit }' "$self_path"
}

now=$(date +%s)

fmt_age() { # seconds -> 12s / 5m / 2h30m / 3d
    local s=$1
    [ "$s" -lt 0 ] 2>/dev/null && { echo "?"; return; }
    if [ "$s" -lt 120 ]; then echo "${s}s"
    elif [ "$s" -lt 7200 ]; then echo "$((s / 60))m"
    elif [ "$s" -lt 172800 ]; then echo "$((s / 3600))h$(((s % 3600) / 60))m"
    else echo "$((s / 86400))d"; fi
}

fmt_bytes() {
    local n=$1
    if [ "$n" -lt 1024 ]; then echo "${n}B"
    elif [ "$n" -lt 1048576 ]; then echo "$((n / 1024))K"
    else echo "$((n / 1048576))M"; fi
}

# --- state (growth since the previous check) --------------------------------
declare -A PREV_SIZE=() PREV_EPOCH=()
load_state() {
    local e p s
    [ -f "$state_file" ] || return 0
    while IFS=$'\t' read -r e p s; do
        [ -n "${p:-}" ] || continue
        PREV_EPOCH[$p]=$e
        PREV_SIZE[$p]=$s
    done < "$state_file"
}

growth_str() { # path size
    local p=$1 s=$2 pe ps dt d
    pe=${PREV_EPOCH[$p]:-}
    if [ -z "$pe" ]; then printf 'n/a (first check)'; return; fi
    ps=${PREV_SIZE[$p]:-0}
    dt=$((now - pe))
    [ "$dt" -lt 0 ] && { printf 'n/a (clock)'; return; }
    d=$((s - ps))
    printf '%+dB/%ss' "$d" "$dt"
}

save_state() { # SEEN is "path\tsize" pairs
    local dir pair p s
    local -A wrote=()
    dir=$(dirname "$state_file")
    if ! mkdir -p "$dir" 2>/dev/null; then
        echo "warning: cannot create $dir; growth will stay n/a" >&2
        return 0
    fi
    if ! { : > "$state_file"; } 2>/dev/null; then
        echo "warning: cannot write $state_file; growth will stay n/a" >&2
        return 0
    fi
    for pair in "${SEEN[@]:-}"; do
        [ -n "$pair" ] || continue
        p=${pair%$'\t'*}
        s=${pair##*$'\t'}
        [ -n "$p" ] || continue
        [ -n "${wrote[$p]:-}" ] && continue
        wrote[$p]=1
        printf '%s\t%s\t%s\n' "$now" "$p" "$s" >> "$state_file"
    done
}

# --- log discovery -----------------------------------------------------------
FILES_CHAIN=()
newest_global_log=""
newest_global_mtime=0
newest_global_size=0

scan_globs() {
    # Chain/artifact logs, newest per area. The default glob is */*.log so
    # every logs/<area>/ dir counts (w*/*.log missed logs/r5/); the ops dir is
    # always excluded because the watch log would otherwise always be the
    # newest file and mask a real stall (P1.2).
    local f
    FILES_CHAIN=()
    while IFS= read -r f; do
        [ -n "$f" ] || continue
        case "$f" in "$logs/ops/"*) continue ;; esac
        FILES_CHAIN+=("$f")
    done < <(compgen -G "$logs/$chain_glob" 2>/dev/null || true)
    # newest *.log anywhere under logs/, excluding our own ops dir
    local line
    line=$(find "$logs" -type f -name '*.log' -not -path "$logs/ops/*" -printf '%T@ %s %p\n' 2>/dev/null | sort -rn | head -1)
    if [ -n "$line" ]; then
        newest_global_mtime=${line%%.*}
        newest_global_size=$(echo "$line" | awk '{print $2}')
        newest_global_log=$(echo "$line" | cut -d' ' -f3-)
    fi
}

newest_of() { # <files...> -> "mtime size path" of the newest, or nothing
    local f m best_f="" best_m=-1
    for f in "$@"; do
        [ -f "$f" ] || continue
        m=$(stat -c %Y "$f" 2>/dev/null) || continue
        [ -n "$m" ] || continue
        if [ -z "$best_f" ] || [ "$m" -gt "$best_m" ]; then
            best_f=$f; best_m=$m
        fi
    done
    [ -n "$best_f" ] || return 1
    stat -c '%Y %s %n' "$best_f"
}

# --- sim processes -----------------------------------------------------------
declare -a SIM_PIDS=() SIM_PGIDS=() SIM_CMDS=() SIM_LOGS=() SIM_SRC=()
declare -a SIM_SIZES=() SIM_AGES=() SIM_GROWTH=() SIM_FROZEN=()

collect_sims() {
    SIM_PIDS=(); SIM_PGIDS=(); SIM_CMDS=(); SIM_LOGS=(); SIM_SRC=()
    SIM_SIZES=(); SIM_AGES=(); SIM_GROWTH=(); SIM_FROZEN=()
    local -A rep=() rep_score=()
    local order=() pid cmd pgid p m s age src fd1 score
    while read -r pid; do
        [ -n "$pid" ] || continue
        cmd=$(ps -o args= -p "$pid" 2>/dev/null) || continue
        [ -n "$cmd" ] || continue
        pgid=$(ps -o pgid= -p "$pid" 2>/dev/null | tr -d ' ')
        [ -n "$pgid" ] || continue
        # representative per process group, best score wins:
        #   4 python.sh wrapper / 3 kit-python child / +1 when fd 1 is a log
        #   under logs/ (the process that can actually answer the log question)
        score=0
        case "$cmd" in
            *python.sh*) score=4 ;;
            *kit/python/bin/python3*) score=3 ;;
        esac
        fd1=$(readlink "/proc/$pid/fd/1" 2>/dev/null || true)
        if [ -n "$fd1" ] && [ -f "$fd1" ] && [[ "$fd1" == "$logs"/* ]]; then
            score=$((score + 1))
        fi
        if [ -z "${rep[$pgid]:-}" ]; then
            rep[$pgid]=$pid; rep_score[$pgid]=$score
            order+=("$pgid")
        elif [ "$score" -gt "${rep_score[$pgid]:-0}" ]; then
            rep[$pgid]=$pid; rep_score[$pgid]=$score
        fi
    done < <(pgrep -f "$sim_pattern" 2>/dev/null | sort -n)

    for pgid in "${order[@]}"; do
        pid=${rep[$pgid]}
        cmd=$(ps -o args= -p "$pid" 2>/dev/null) || cmd="?"
        p=""; src="none"
        fd1=$(readlink "/proc/$pid/fd/1" 2>/dev/null || true)
        if [ -n "$fd1" ] && [ -f "$fd1" ] && [[ "$fd1" == "$logs"/* ]]; then
            p=$fd1; src=fd
        elif [ -n "$newest_global_log" ]; then
            p=$newest_global_log; src=global-newest
        fi
        SIM_PIDS+=("$pid"); SIM_PGIDS+=("$pgid"); SIM_CMDS+=("$cmd")
        SIM_LOGS+=("$p"); SIM_SRC+=("$src")
        if [ -n "$p" ] && [ -f "$p" ]; then
            m=$(stat -c %Y "$p" 2>/dev/null || echo "$now")
            s=$(stat -c %s "$p" 2>/dev/null || echo 0)
            age=$((now - m))
            SIM_SIZES+=("$s"); SIM_AGES+=("$age")
            SIM_GROWTH+=("$(growth_str "$p" "$s")")
            if [ "$age" -gt "$stall_s" ]; then SIM_FROZEN+=(1); else SIM_FROZEN+=(0); fi
        else
            SIM_SIZES+=(0); SIM_AGES+=(-1); SIM_GROWTH+=("n/a")
            SIM_FROZEN+=(0)
        fi
    done
}

# --- claim wrappers / lane drivers -------------------------------------------
# A live wrapper means the lane is between its own steps: the `[wrap]` action
# is downgraded to a hint while one exists (the lane may still be wrapping).
declare -a LANE_PIDS=() LANE_CMDS=()
collect_lanes() {
    LANE_PIDS=(); LANE_CMDS=()
    local pid cmd
    while read -r pid; do
        [ -n "$pid" ] || continue
        cmd=$(ps -o args= -p "$pid" 2>/dev/null) || continue
        [ -n "$cmd" ] || continue
        LANE_PIDS+=("$pid"); LANE_CMDS+=("$cmd")
    done < <(pgrep -f "$lane_pattern" 2>/dev/null | sort -n)
}

# --- claims ------------------------------------------------------------------
# prints human lines; sets CLAIM_STALE=1 when an owner file names a dead pid
CLAIM_STALE=0
claim_lines() {
    CLAIM_STALE=0
    local lock owner i pid label log
    if [ ! -d "$claims" ]; then
        echo "  none ($claims absent)"
        return 0
    fi
    local any=0
    for lock in "$claims"/slot*.lock; do
        [ -e "$lock" ] || continue
        any=1
        i=$(basename "$lock" .lock)
        owner="$claims/$i.owner"
        if [ -f "$owner" ]; then
            pid=$(grep -m1 '^pid=' "$owner" 2>/dev/null | cut -d= -f2-)
            label=$(grep -m1 '^label=' "$owner" 2>/dev/null | cut -d= -f2-)
            log=$(grep -m1 '^log=' "$owner" 2>/dev/null | cut -d= -f2-)
            if [ -n "$pid" ] && kill -0 "$pid" 2>/dev/null; then
                printf '  %s: held pid=%s label=%s log=%s\n' "$i" "$pid" "${label:-?}" "${log:-?}"
            else
                printf '  %s: STALE owner pid=%s label=%s (dead; the kernel released the lock)\n' \
                    "$i" "${pid:-?}" "${label:-?}"
                CLAIM_STALE=1
            fi
        elif command -v flock >/dev/null 2>&1; then
            if exec 9>>"$lock" 2>/dev/null && flock -n 9; then
                printf '  %s: free (lock file only)\n' "$i"
                flock -u 9 2>/dev/null || true
                exec 9>&-
            else
                printf '  %s: locked, no owner file (holder did not write one)\n' "$i"
                exec 9>&- 2>/dev/null || true
            fi
        else
            printf '  %s: lock file only (flock unavailable; state unknown)\n' "$i"
        fi
    done
    [ "$any" = 1 ] || echo "  none (no slot files in $claims)"
}

# --- git ---------------------------------------------------------------------
GIT_OK=0 GIT_BRANCH="-" GIT_DIRTY=0 GIT_AGE=-1 GIT_TAGS="" GIT_HEAD_TAG=""
collect_git() {
    GIT_OK=0 GIT_BRANCH="-" GIT_DIRTY=0 GIT_AGE=-1 GIT_TAGS="" GIT_HEAD_TAG=""
    if ! git -C "$repo" rev-parse --git-dir >/dev/null 2>&1; then
        return 0
    fi
    GIT_OK=1
    GIT_BRANCH=$(git -C "$repo" rev-parse --abbrev-ref HEAD 2>/dev/null)
    GIT_DIRTY=$(git -C "$repo" status --porcelain 2>/dev/null | wc -l)
    local ts
    ts=$(git -C "$repo" log -1 --format=%ct 2>/dev/null || echo "")
    [ -n "$ts" ] && GIT_AGE=$((now - ts))
    GIT_TAGS=$(git -C "$repo" tag --sort=-creatordate 2>/dev/null | head -n 4 | paste -sd, -)
    GIT_HEAD_TAG=$(git -C "$repo" tag --points-at HEAD 2>/dev/null | head -1)
}

# --- GPU / load / permissions ------------------------------------------------
GPU_LINE="n/a (no nvidia-smi or no GPU)"
GPU_UTIL=""
collect_gpu() {
    GPU_LINE="n/a (no nvidia-smi or no GPU)"; GPU_UTIL=""
    [ -n "$gpu_query" ] || { GPU_LINE="skipped (OPS_GPU_QUERY empty)"; return; }
    if ! command -v nvidia-smi >/dev/null 2>&1; then return; fi
    local out
    out=$(timeout 5 $gpu_query 2>/dev/null | head -1 || true)
    if [ -n "$out" ]; then
        GPU_LINE=$out
        GPU_UTIL=$(printf '%s' "$out" | sed 's/%//; s/,.*//' | tr -d ' ')
    fi
}

LOAD_LINE="n/a"
collect_load() {
    LOAD_LINE=$(cut -d' ' -f1-3 /proc/loadavg 2>/dev/null || echo "n/a")
}

PERM_PENDING=-1 PERM_RECENT=-1
collect_perms() {
    PERM_PENDING=-1; PERM_RECENT=-1
    if [ ! -r "$opencode_db" ]; then return; fi
    if ! command -v sqlite3 >/dev/null 2>&1; then return; fi
    local cutoff
    cutoff=$(((now - permission_s) * 1000))
    PERM_PENDING=$(timeout 5 sqlite3 "file:$opencode_db?mode=ro" \
        "select count(*) from session_pending where type like '%permission%' or data like '%permission%';" \
        2>/dev/null || echo "")
    PERM_RECENT=$(timeout 5 sqlite3 "file:$opencode_db?mode=ro" \
        "select count(*) from permission where time_created >= $cutoff;" \
        2>/dev/null || echo "")
    is_num "$PERM_PENDING" || PERM_PENDING=-1
    is_num "$PERM_RECENT" || PERM_RECENT=-1
}

# --- the report + verdict ----------------------------------------------------
declare -a ACTIONS=() HINTS=() SEEN=()

run_all() {
    local sim_count frozen_count lane_count chain_m chain_s_ chain_path chain_age chain_tail
    local crash_marker done_marker i verdict code

    now=$(date +%s)
    ACTIONS=(); HINTS=(); SEEN=()
    load_state
    scan_globs
    collect_sims
    collect_lanes
    collect_git
    collect_gpu
    collect_load
    collect_perms

    echo "== ops self-check =="
    echo "time: $(date -Is)   stall=${stall_s}s chain=${chain_s}s   logs=$logs"

    # ---- sims ----
    sim_count=${#SIM_PIDS[@]}
    frozen_count=0
    echo "sims: ${sim_count} process group(s)"
    if [ -n "$newest_global_log" ]; then
        echo "  newest log under logs/ (all areas, ex ops): $newest_global_log age=$(fmt_age $((now - newest_global_mtime))) size=$(fmt_bytes "$newest_global_size")"
    fi
    if [ "$sim_count" -eq 0 ]; then
        echo "  none running"
    else
        for i in "${!SIM_PIDS[@]}"; do
            local pid=${SIM_PIDS[$i]} pgid=${SIM_PGIDS[$i]} p=${SIM_LOGS[$i]}
            local age=${SIM_AGES[$i]} frozen=${SIM_FROZEN[$i]}
            printf '  pid=%s pgid=%s cmd=%s\n' "$pid" "$pgid" "${SIM_CMDS[$i]}"
            if [ -n "$p" ] && [ -f "$p" ]; then
                printf '    log=%s via=%s size=%s age=%s growth=%s%s\n' \
                    "$p" "${SIM_SRC[$i]}" "$(fmt_bytes "${SIM_SIZES[$i]}")" \
                    "$(fmt_age "$age")" "${SIM_GROWTH[$i]}" \
                    "$([ "$frozen" = 1 ] && printf ' FROZEN(>%ss)' "$stall_s")"
            else
                printf '    log=none (no discoverable log; fd 1 not under logs/)\n'
            fi
            SEEN+=("$p"$'\t'"${SIM_SIZES[$i]}")
            [ "$frozen" = 1 ] && frozen_count=$((frozen_count + 1))
            if [ "$frozen" = 1 ] && [ -n "$p" ] && [ -f "$p" ]; then
                # class (b) corroboration: an actual wedge signature, an idle
                # GPU once the log has been frozen >= 2x OPS_STALL_S, or a
                # state snapshot proving zero growth across at least OPS_STALL_S
                local marker gpu_corr=0 gpu_seen=0 state_corr=0 pe ps psd
                marker=$(tail -c 4000 "$p" 2>/dev/null | grep -Eo "$wedge_re" | head -1)
                if [ -n "$GPU_UTIL" ] && is_num "$GPU_UTIL" && [ "$GPU_UTIL" -le "$gpu_idle_pct" ]; then
                    gpu_seen=1
                    # GPU-idle alone is weak corroboration (an idle GPU with a
                    # quiet log can be a startup or a buffered writer); require
                    # the freeze to have persisted 2x OPS_STALL_S before it
                    # escalates, otherwise it only annotates the hint.
                    [ "$age" -ge $((stall_s * 2)) ] && gpu_corr=1
                fi
                pe=${PREV_EPOCH[$p]:-}
                ps=${PREV_SIZE[$p]:-}
                if [ -n "$pe" ] && [ -n "$ps" ] && [ "$ps" = "${SIM_SIZES[$i]}" ]; then
                    psd=$((now - pe))
                    [ "$psd" -ge "$stall_s" ] && state_corr=1
                fi
                if [ -n "$marker" ] || [ "$gpu_corr" = 1 ] || [ "$state_corr" = 1 ]; then
                    local why=""
                    [ -n "$marker" ] && why="wedge marker '$marker'"
                    [ "$gpu_corr" = 1 ] && why="${why:+$why, }GPU idle (${GPU_UTIL}%) and frozen ${age}s (>= 2x${stall_s}s)"
                    [ "$state_corr" = 1 ] && why="${why:+$why, }zero growth across ${psd}s"
                    local resume=""
                    case "${SIM_CMDS[$i]}" in
                        *python.sh\ *) resume="scripts/run.sh ${SIM_CMDS[$i]#*python.sh }" ;;
                    esac
                    if [ -n "$resume" ]; then
                        resume="$resume   # env not recovered from the process; prefer the claim wrapper"
                    else
                        resume="re-run the SAME wrapper invocation that wrote $p (180_claim_slot.sh / 154_claim_run.sh reclaim a slot via flock; they do NOT retry by themselves); a collector shard restarts from zero in a fresh dir - the store is the union of shard dirs, later merged"
                    fi
                    if [ "$pgid" = "$own_pgid" ]; then
                        # A group kill on our own pgid would kill this tool (and
                        # the shell that launched it): the sim was started
                        # without setsid inside the launching shell's group.
                        ACTIONS+=("[sim] pid $pid frozen ${age}s ($why): pid $pid shares this tool's own process group ($pgid) - kill from the launching shell / through the claim wrapper (a process-group kill here would take the tool down); resume: $resume")
                    else
                        ACTIONS+=("[sim] pid $pid frozen ${age}s ($why): kill -TERM -- -$pgid && sleep 5 && kill -KILL -- -$pgid 2>/dev/null; resume: $resume")
                    fi
                else
                    local gpu_note=""
                    if [ "$gpu_seen" = 1 ]; then
                        gpu_note="; the GPU is idle (${GPU_UTIL}%) but the log is frozen only ${age}s (< 2x${stall_s}s), not corroborating yet"
                    fi
                    HINTS+=("[sim] pid $pid frozen ${age}s with no corroboration yet (empty/quiet startup or buffered log): watch one more check before killing${gpu_note}")
                fi
            fi
        done
    fi

    # ---- lanes (claim wrappers / drivers) ----
    lane_count=${#LANE_PIDS[@]}
    echo "lanes: ${lane_count} claim wrapper(s) / driver(s) alive"
    for i in "${!LANE_PIDS[@]}"; do
        printf '  pid=%s cmd=%s\n' "${LANE_PIDS[$i]}" "${LANE_CMDS[$i]}"
    done

    # ---- chain (newest log per area) ----
    chain_m=""; chain_s_=""; chain_path=""; chain_age=-1
    local chain_newest
    if chain_newest=$(newest_of "${FILES_CHAIN[@]:-}"); then
        chain_m=$(echo "$chain_newest" | awk '{print $1}')
        chain_s_=$(echo "$chain_newest" | awk '{print $2}')
        chain_path=$(echo "$chain_newest" | cut -d' ' -f3-)
        chain_age=$((now - chain_m))
        SEEN+=("$chain_path"$'\t'"$chain_s_")
    fi

    # ---- claims ----
    echo "claims:"
    claim_lines
    if [ "$CLAIM_STALE" = 1 ]; then
        ACTIONS+=("[claim] a slot owner file names a dead pid: the kernel already released the lock; remove the stale logs/claims/*.owner (informational) or ignore - verify with scripts/180_claim_slot.sh --status")
    fi

    # ---- artifacts ----
    echo "artifacts (newest $top_n of $chain_glob under logs/):"
    if [ "${#FILES_CHAIN[@]}" -eq 0 ]; then
        echo "  none"
    else
        local rows="" f m s
        for f in "${FILES_CHAIN[@]}"; do
            [ -f "$f" ] || continue
            m=$(stat -c %Y "$f" 2>/dev/null) || continue
            s=$(stat -c %s "$f" 2>/dev/null || echo 0)
            rows+="$m $s $f"$'\n'
        done
        printf '%s' "$rows" | sort -rn | head -n "$top_n" | while read -r m s f; do
            printf '  %-52s age=%-6s size=%s\n' "$f" "$(fmt_age $((now - m)))" "$(fmt_bytes "$s")"
        done
    fi

    # ---- git ----
    if [ "$GIT_OK" = 1 ]; then
        echo "git: branch=$GIT_BRANCH dirty=$GIT_DIRTY last_commit=$(fmt_age "$GIT_AGE") head_tag=${GIT_HEAD_TAG:--} tags=[$GIT_TAGS]"
    else
        echo "git: n/a (not a repository: $repo)"
    fi

    # ---- gpu / load / permissions ----
    echo "gpu: $GPU_LINE"
    echo "load: $LOAD_LINE"
    if [ "$PERM_PENDING" -ge 0 ] || [ "$PERM_RECENT" -ge 0 ]; then
        echo "permissions: pending_asks=$([ "$PERM_PENDING" -ge 0 ] && echo "$PERM_PENDING" || echo n/a) recent_asks(<=${permission_s}s)=$([ "$PERM_RECENT" -ge 0 ] && echo "$PERM_RECENT" || echo n/a)"
        if [ "${PERM_PENDING:-0}" -gt 0 ]; then
            ACTIONS+=("[perms] $PERM_PENDING pending permission ask(s) in $opencode_db: a lane is likely waiting on an unanswerable permission - check it and respawn the lane with a corrected prompt (the plugin transport cannot reply; see docs/OPS.md class (a))")
        fi
        if [ "${PERM_RECENT:-0}" -gt 0 ]; then
            HINTS+=("[perms] $PERM_RECENT external_directory ask(s) recorded in the last ${permission_s}s: if a lane parked, respawn it with a no-external-dir prompt")
        fi
    else
        echo "permissions: n/a (no readable $opencode_db or no sqlite3)"
    fi

    # ---- chain stall (only when no sim is running) ----
    if [ "$sim_count" -eq 0 ] && [ "$chain_age" -ge 0 ] && [ "$chain_age" -gt "$chain_s" ]; then
        chain_tail=$(tail -c 4000 "$chain_path" 2>/dev/null || true)
        crash_marker=$(printf '%s' "$chain_tail" | grep -Eo "$wedge_re" | head -1)
        done_marker=$(printf '%s' "$chain_tail" | grep -Eo "$done_re" | head -1)
        if [ -n "$crash_marker" ]; then
            ACTIONS+=("[chain] $chain_path (stale $(fmt_age "$chain_age")) ends with a crash marker '$crash_marker': resume the failed step / re-dispatch the lane (see the log tail)")
        elif [ -n "$done_marker" ] && [ "$GIT_OK" = 1 ] && [ "$GIT_DIRTY" -gt 0 ]; then
            if [ "${#LANE_PIDS[@]}" -gt 0 ]; then
                HINTS+=("[chain] $chain_path looks finished ('$done_marker') with $GIT_DIRTY uncommitted path(s), but a claim wrapper / driver is alive (pid ${LANE_PIDS[*]}): the lane may still be wrapping - let it finish before any manual wrap")
            else
                ACTIONS+=("[wrap] chain log $chain_path looks finished ('$done_marker') but the tree has $GIT_DIRTY uncommitted path(s): finish the wrap (commit the lane's own files, tag) or re-dispatch the lane")
            fi
        else
            HINTS+=("[chain] no chain log growth for $(fmt_age "$chain_age") (newest: $chain_path) and no sim running: if work was queued this is stall class (c)/(d) - check the lane's last log and resume it")
        fi
    fi

    # ---- state + verdict ----
    save_state
    if [ "${#ACTIONS[@]}" -gt 0 ]; then
        verdict=ACTION; code=2
    elif [ "$frozen_count" -gt 0 ]; then
        verdict=STALLED-SIM; code=0
    elif [ "$sim_count" -eq 0 ] && [ "$chain_age" -ge 0 ] && [ "$chain_age" -gt "$chain_s" ]; then
        verdict=STALLED-CHAIN; code=0
    else
        verdict=OK; code=0
    fi

    if [ "${#ACTIONS[@]}" -gt 0 ]; then
        echo "actions (recommendations only - this tool never executes them):"
        for i in "${!ACTIONS[@]}"; do printf '  - %s\n' "${ACTIONS[$i]}"; done
    fi
    if [ "${#HINTS[@]}" -gt 0 ]; then
        echo "hints:"
        for i in "${!HINTS[@]}"; do printf '  - %s\n' "${HINTS[$i]}"; done
    fi
    printf '[ops] time=%s sims=%s frozen=%s chain_age=%s chain_log=%s actions=%s\n' \
        "$(date -Is)" "$sim_count" "$frozen_count" "$chain_age" "${chain_path:-none}" "${#ACTIONS[@]}"
    printf 'verdict: %s (exit %s)\n' "$verdict" "$code"
    return "$code"
}

watch_loop() {
    local interval=$1 prev="" out code verdict rec
    mkdir -p "$(dirname "$watch_log")" 2>/dev/null || true
    echo "[watch] interval=${interval}s; full report on verdict transitions; one-line records -> $watch_log"
    while :; do
        out=$(run_all); code=$?
        verdict=$(printf '%s\n' "$out" | sed -n 's/^verdict: \([A-Z-]*\).*/\1/p' | head -1)
        if [ "$verdict" != "$prev" ]; then
            printf '%s\n' "$out"
            printf '[watch] %s verdict -> %s (exit %s)\n' "$(date +%H:%M:%S)" "$verdict" "$code"
            prev=$verdict
        else
            printf '[watch] %s verdict=%s (exit %s)\n' "$(date +%H:%M:%S)" "$verdict" "$code"
        fi
        rec=$(printf '%s\n' "$out" | grep '^\[ops\]' | head -1)
        if [ -n "$rec" ]; then
            printf '%s\n' "$rec" >> "$watch_log" 2>/dev/null \
                || echo "[watch] warning: cannot append $watch_log" >&2
        fi
        sleep "$interval"
    done
}

# --- selftest ----------------------------------------------------------------
# ST_TMP/ST_FAKE/ST_WRAP are deliberately globals: the EXIT trap runs after
# this function has returned, so function-local variables would be gone by then.
ST_TMP="" ST_FAKE="" ST_WRAP=""
st_cleanup() {
    [ -n "$ST_FAKE" ] && kill "$ST_FAKE" 2>/dev/null
    [ -n "$ST_WRAP" ] && kill "$ST_WRAP" 2>/dev/null
    [ -n "$ST_TMP" ] && rm -rf "$ST_TMP"
}
selftest() {
    local fail=0 sim_pat='[o]ps-fake-sim-191' lane_pat='[o]ps-fake-lane-191'
    ST_TMP=$(mktemp -d) || { echo "FAIL: mktemp -d"; return 1; }
    ST_FAKE=""; ST_WRAP=""
    trap st_cleanup EXIT
    local tmp=$ST_TMP
    mkdir -p "$tmp/logs/w9" "$tmp/logs/claims" "$tmp/logs/ops"
    printf 'simulating: attempt 1\n' > "$tmp/logs/w9/sim.log"
    printf 'chain step 1: collecting\n' > "$tmp/logs/w9/chain.log"

    run_case() {
        # Both patterns are pinned to selftest-only names: the real `lanes`
        # pattern would otherwise see the claim-slot harness's own 180 children
        # (or a parallel lane) and change the verdict mid-test.
        OPS_ROOT="$tmp" OPS_LOGS_DIR="$tmp/logs" OPS_CLAIM_DIR="$tmp/logs/claims" \
        OPS_STATE_FILE="$tmp/logs/ops/state.tsv" OPS_WATCH_LOG="$tmp/logs/ops/watch.log" \
        OPS_STALL_S=300 OPS_CHAIN_S=600 OPS_SIM_PATTERN="$sim_pat" \
        OPS_LANE_PATTERN="$lane_pat" \
        OPS_OPENCODE_DB="$tmp/none.db" OPS_GPU_QUERY= \
        bash "$self_path"
    }

    case_ok() { # desc pattern output code want_code [must_not]
        local desc=$1 pat=$2 out=$3 code=$4 want=$5 no=${6:-}
        if ! printf '%s\n' "$out" | grep -q "$pat"; then
            echo "FAIL: $desc (missing '$pat'; exit=$code)"
            printf '%s\n' "$out" | sed 's/^/    | /'
            fail=1
            return
        fi
        if [ -n "$no" ] && printf '%s\n' "$out" | grep -q "$no"; then
            echo "FAIL: $desc (unexpected '$no')"
            printf '%s\n' "$out" | sed 's/^/    | /'
            fail=1
            return
        fi
        if [ "$code" != "$want" ]; then
            echo "FAIL: $desc (exit=$code, want $want)"
            printf '%s\n' "$out" | sed 's/^/    | /'
            fail=1
            return
        fi
        echo "ok: $desc"
    }

    start_fake_sim() { # own|shared : argv[0]=ops-fake-sim-191, stdout -> sim.log
        if [ "$1" = own ]; then
            setsid bash -c 'exec -a ops-fake-sim-191 sleep 120' >> "$tmp/logs/w9/sim.log" 2>&1 &
        else
            bash -c 'exec -a ops-fake-sim-191 sleep 120' >> "$tmp/logs/w9/sim.log" 2>&1 &
        fi
        local spawned=$!
        sleep 0.3
        ST_FAKE=$(pgrep -f '[o]ps-fake-sim-191' | head -1)
        [ -n "$ST_FAKE" ] || ST_FAKE=$spawned
    }

    echo "ops selfcheck selftest (temp dir $tmp, no simulator, no GPU, no DB)"

    # fake sim launched without setsid: it shares this script's process group,
    # which is exactly the case the own-pgid guard must catch.
    start_fake_sim shared

    # 1. OK: a sim with a fresh log does NOT fire a stall verdict
    local out code
    out=$(run_case); code=$?
    case_ok "OK case (fresh sim log)" '^verdict: OK' "$out" "$code" 0 'STALLED'

    # 2. STALLED-SIM: the same sim, log untouched for 15 min
    touch -d '15 minutes ago' "$tmp/logs/w9/sim.log"
    out=$(run_case); code=$?
    case_ok "STALLED-SIM fires (frozen sim log, no corroboration)" '^verdict: STALLED-SIM' "$out" "$code" 0

    # 3. ACTION + own-pgid guard: the wedge marker escalates, but the group-kill
    # line is refused because the sim shares this tool's process group.
    printf 'Too many open files\n' >> "$tmp/logs/w9/sim.log"
    touch -d '15 minutes ago' "$tmp/logs/w9/sim.log"
    out=$(run_case); code=$?
    case_ok "ACTION fires on a wedge marker" "shares this tool's own process group" \
        "$out" "$code" 2 'kill -TERM -- -'
    if printf '%s\n' "$out" | grep -q '^verdict: ACTION'; then
        echo "ok: ACTION verdict on a wedged sim"
    else
        echo "FAIL: expected verdict ACTION on a wedged sim"
        printf '%s\n' "$out" | sed 's/^/    | /'
        fail=1
    fi

    # 3b. ACTION with the group-kill line: the sim in its own session/pgid
    kill "$ST_FAKE" 2>/dev/null; wait "$ST_FAKE" 2>/dev/null; ST_FAKE=""
    rm -f "$tmp/logs/w9/sim.log"
    start_fake_sim own
    printf 'Too many open files\n' >> "$tmp/logs/w9/sim.log"
    touch -d '15 minutes ago' "$tmp/logs/w9/sim.log"
    out=$(run_case); code=$?
    case_ok "ACTION on a separately grouped sim (kill line printed)" \
        'kill -TERM -- -' "$out" "$code" 2 "shares this tool's own process group"

    # 4. STALLED-CHAIN: no sim, stale chain log (the wedge-marked sim log is
    # removed so it cannot be the newest chain log and mask the case)
    kill "$ST_FAKE" 2>/dev/null; wait "$ST_FAKE" 2>/dev/null; ST_FAKE=""
    rm -f "$tmp/logs/w9/sim.log"
    touch -d '15 minutes ago' "$tmp/logs/w9/chain.log"
    out=$(run_case); code=$?
    case_ok "STALLED-CHAIN fires (no sim, stale chain log)" '^verdict: STALLED-CHAIN' "$out" "$code" 0

    # 4b. widened glob (P1.2): the chain scan covers a non-w* area (logs/r5/)
    # and always excludes the ops dir. Only the r5 log is left stale, so the
    # STALLED-CHAIN verdict itself depends on the widened glob (the old
    # w*/*.log default would find no chain log and verdict OK), and the fresh
    # ops/watch.log would mask it if the ops dir were not excluded. The r5
    # fixture is removed afterwards so the mtime tie in case 6 cannot make an
    # unrelated chain log the newest one.
    rm -f "$tmp/logs/w9/chain.log"
    mkdir -p "$tmp/logs/r5"
    printf 'chain step: r5 area\n' > "$tmp/logs/r5/chain.log"
    touch -d '15 minutes ago' "$tmp/logs/r5/chain.log"
    printf 'watch loop noise (newest .log under logs)\n' > "$tmp/logs/ops/watch.log"
    out=$(run_case); code=$?
    case_ok "widened glob: a stale logs/r5/ chain log fires STALLED-CHAIN" \
        '^verdict: STALLED-CHAIN' "$out" "$code" 0 'logs/ops/watch.log'
    if printf '%s\n' "$out" | grep -q 'no chain log growth.*logs/r5/chain.log'; then
        echo "ok: widened glob: the chain hint names the logs/r5/ log"
    else
        echo "FAIL: the chain hint does not name logs/r5/chain.log"
        printf '%s\n' "$out" | sed 's/^/    | /'
        fail=1
    fi
    rm -rf "$tmp/logs/r5"; rm -f "$tmp/logs/ops/watch.log"

    # 5. ACTION: a stale claim owner (dead pid)
    printf 'chain step 2: training\n' > "$tmp/logs/w9/chain.log"
    : > "$tmp/logs/claims/slot0.lock"
    cat > "$tmp/logs/claims/slot0.owner" <<EOF
pid=99999999
label=selftest-stale
log=$tmp/logs/w9/chain.log
start=2020-01-01T00:00:00+00:00
cmd=true
EOF
    out=$(run_case); code=$?
    case_ok "ACTION fires on a stale claim (dead owner pid)" 'STALE owner' "$out" "$code" 2 'STALLED'

    # 6. ACTION [wrap]: a completion marker + a dirty tree with no live wrapper
    rm -f "$tmp/logs/claims/slot0.owner"
    printf 'fingerprint: matches\n' > "$tmp/logs/w9/chain.log"
    touch -d '15 minutes ago' "$tmp/logs/w9/chain.log"
    git -C "$tmp" init -q 2>/dev/null
    touch "$tmp/pending.txt"
    out=$(run_case); code=$?
    case_ok "ACTION [wrap] fires (done marker + dirty tree)" '\[wrap\] chain log' "$out" "$code" 2

    # 7. the wrap action is downgraded while a claim wrapper is alive
    bash -c 'exec -a ops-fake-lane-191 sleep 120' >/dev/null 2>&1 &
    ST_WRAP=$!
    sleep 0.3
    out=$(run_case); code=$?
    case_ok "wrap action suppressed while a wrapper is alive" \
        'claim wrapper / driver is alive' "$out" "$code" 0 '\[wrap\]'
    kill "$ST_WRAP" 2>/dev/null; wait "$ST_WRAP" 2>/dev/null; ST_WRAP=""

    if [ "$fail" -ne 0 ]; then
        echo "FAIL: ops selfcheck selftest"
        return 1
    fi
    echo "PASS: ops selfcheck selftest"
    return 0
}

# --- entry -------------------------------------------------------------------
case "${1:-}" in
    --help|-h)
        usage
        exit 0
        ;;
    --selftest)
        selftest
        exit $?
        ;;
    --watch)
        interval=${2:-60}
        is_num "$interval" || { echo "usage: $0 --watch <seconds>" >&2; exit 64; }
        [ "$interval" -lt 1 ] && interval=1
        watch_loop "$interval"
        ;;
    '')
        run_all
        exit $?
        ;;
    *)
        echo "usage: $0 [--watch N | --selftest | --help]" >&2
        exit 64
        ;;
esac
