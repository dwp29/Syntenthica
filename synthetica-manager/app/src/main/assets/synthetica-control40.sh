#!/system/bin/sh
# Synthetica 2.1: opt-in runtime controls. Nothing here flashes or modifies a boot image.
# The optional SP_* roots are for the repository's host-side fake-filesystem tests only.

SYSROOT=${SP_SYSROOT:-/sys}
PROCROOT=${SP_PROCSYS:-/proc}
STATE_DIR=${SP_STATE_DIR:-/data/adb/synthetica21/control}
ACTION=${1:-}
OK=0
SKIP=0
FAIL=0

fail() { printf 'ERROR: %s\n' "$*"; FAIL=$((FAIL + 1)); }
skip() { printf 'SKIPPED: %s\n' "$*"; SKIP=$((SKIP + 1)); }

# For block schedulers, the selected value is the one in brackets.
read_current() {
    READ_NODE=$1
    READ_VALUE=$(cat "$READ_NODE" 2>/dev/null) || return 1
    case "$READ_NODE" in
        */queue/scheduler)
            SELECTED=$(printf '%s\n' "$READ_VALUE" | sed -n 's/.*\[\([^]]*\)\].*/\1/p')
            printf '%s' "${SELECTED:-$READ_VALUE}"
            ;;
        *) printf '%s' "$READ_VALUE" ;;
    esac
}

save_original() {
    SAVE_NODE=$1
    SAVE_VALUE=$2
    if awk -F '\t' -v p="$SAVE_NODE" '$1 == p { found = 1; exit } END { exit !found }' "$STATE"; then
        return 0
    fi
    printf '%s\t%s\n' "$SAVE_NODE" "$SAVE_VALUE" >> "$STATE"
}

apply_node() {
    WRITE_NODE=$1
    WRITE_VALUE=$2
    if [ ! -e "$WRITE_NODE" ]; then skip "$WRITE_NODE not present"; return; fi
    if [ ! -w "$WRITE_NODE" ]; then fail "$WRITE_NODE not writable"; return; fi
    BEFORE=$(read_current "$WRITE_NODE") || { fail "$WRITE_NODE unreadable"; return; }
    if [ -z "$BEFORE" ]; then fail "$WRITE_NODE has no readable previous value"; return; fi
    if ! save_original "$WRITE_NODE" "$BEFORE"; then
        fail "$WRITE_NODE not changed: could not save its previous value"
        return
    fi
    if ! printf '%s\n' "$WRITE_VALUE" > "$WRITE_NODE" 2>/dev/null; then
        fail "$WRITE_NODE write failed"
        return
    fi
    AFTER=$(read_current "$WRITE_NODE") || AFTER='[unreadable]'
    if [ "$AFTER" != "$WRITE_VALUE" ]; then
        if printf '%s\n' "$BEFORE" > "$WRITE_NODE" 2>/dev/null; then
            fail "$WRITE_NODE read back $AFTER (requested $WRITE_VALUE); previous value restoration attempted"
        else
            fail "$WRITE_NODE read back $AFTER (requested $WRITE_VALUE); restoration failed"
        fi
        return
    fi
    printf 'VERIFIED: %s = %s\n' "$WRITE_NODE" "$AFTER"
    OK=$((OK + 1))
}

has_choice() {
    printf '%s\n' "$1" | tr '[] ' '\n\n\n' | grep -Fxq -- "$2"
}

apply_governor() {
    GOV_DIR=$1
    GOV_WANT=$2
    GOV_AVAILABLE=$(cat "$GOV_DIR/scaling_available_governors" 2>/dev/null) || {
        skip "$GOV_DIR governors unavailable"; return;
    }
    if has_choice "$GOV_AVAILABLE" "$GOV_WANT"; then
        apply_node "$GOV_DIR/scaling_governor" "$GOV_WANT"
    else
        skip "$GOV_DIR does not offer governor $GOV_WANT"
    fi
}

apply_scheduler() {
    SCHED_NODE=$1
    SCHED_WANT=$2
    [ -e "$SCHED_NODE" ] || { skip "$SCHED_NODE not present"; return; }
    SCHED_AVAILABLE=$(cat "$SCHED_NODE" 2>/dev/null) || { fail "$SCHED_NODE unreadable"; return; }
    if has_choice "$SCHED_AVAILABLE" "$SCHED_WANT"; then
        apply_node "$SCHED_NODE" "$SCHED_WANT"
    else
        skip "$SCHED_NODE does not offer $SCHED_WANT"
    fi
}

apply_profile() {
    PROFILE=$1
    FOUND_POLICY=0
    for POLICY in "$SYSROOT"/devices/system/cpu/cpufreq/policy*; do
        [ -d "$POLICY" ] || continue
        FOUND_POLICY=1
        if [ "$PROFILE" = gaming ]; then
            apply_governor "$POLICY" performance
            MAXF=$(cat "$POLICY/cpuinfo_max_freq" 2>/dev/null) || MAXF=''
            case "$MAXF" in ''|*[!0-9]*) FREQ='' ;;
                *)
                    TARGET=$((MAXF * 70 / 100))
                    FREQ=$(tr ' ' '\n' < "$POLICY/scaling_available_frequencies" 2>/dev/null |
                        awk -v target="$TARGET" '/^[0-9]+$/ && $1 >= target && (!best || $1 < best) { best = $1 } END { if (best) print best }')
                    ;;
            esac
            if [ -w "$POLICY/scaling_max_freq" ] && [ -n "$MAXF" ]; then
                apply_node "$POLICY/scaling_max_freq" "$MAXF"
            fi
        elif [ "$PROFILE" = battery ] || [ "$PROFILE" = cooldown ]; then
            apply_governor "$POLICY" schedutil
            FREQ=$(cat "$POLICY/cpuinfo_min_freq" 2>/dev/null) || FREQ=''
            MAXF=$(cat "$POLICY/cpuinfo_max_freq" 2>/dev/null) || MAXF=''
            CAP_PCT=80
            [ "$PROFILE" = cooldown ] && CAP_PCT=70
            case "$MAXF" in ''|*[!0-9]*) CAPF='' ;;
                *)
                    TARGET=$((MAXF * CAP_PCT / 100))
                    CAPF=$(tr ' ' '\n' < "$POLICY/scaling_available_frequencies" 2>/dev/null |
                        awk -v target="$TARGET" '/^[0-9]+$/ && $1 <= target && (!best || $1 > best) { best = $1 } END { if (best) print best }')
                    ;;
            esac
            if [ -w "$POLICY/scaling_max_freq" ] && [ -n "$CAPF" ]; then
                apply_node "$POLICY/scaling_max_freq" "$CAPF"
            fi
        else
            apply_governor "$POLICY" schedutil
            FREQ=$(cat "$POLICY/cpuinfo_min_freq" 2>/dev/null) || FREQ=''
            MAXF=$(cat "$POLICY/cpuinfo_max_freq" 2>/dev/null) || MAXF=''
            if [ -w "$POLICY/scaling_max_freq" ] && [ -n "$MAXF" ]; then
                apply_node "$POLICY/scaling_max_freq" "$MAXF"
            fi
        fi
        case "$FREQ" in
            ''|*[!0-9]*) skip "$POLICY has no verifiable target frequency" ;;
            *) apply_node "$POLICY/scaling_min_freq" "$FREQ" ;;
        esac
    done
    [ "$FOUND_POLICY" -eq 1 ] || skip 'CPU frequency policies not found'
    GPU="$SYSROOT/class/kgsl/kgsl-3d0"
    LEVELS=$(cat "$GPU/num_pwrlevels" 2>/dev/null) || LEVELS=''
    case "$LEVELS" in
        ''|*[!0-9]*) skip 'GPU power-level count unavailable' ;;
        *)
            if [ "$LEVELS" -lt 1 ] || [ "$LEVELS" -gt 32 ]; then
                skip 'GPU power-level count outside expected range'
            else
                if [ "$PROFILE" = gaming ]; then LEVEL=$(((LEVELS - 1) * 40 / 100)); else LEVEL=$((LEVELS - 1)); fi
                apply_node "$GPU/min_pwrlevel" "$LEVEL"
            fi
            ;;
    esac
    case "$PROFILE" in
        gaming) SWAP=40 ;;
        battery|cooldown) SWAP=80 ;;
        *) SWAP=60 ;;
    esac
    apply_node "$PROCROOT/sys/vm/swappiness" "$SWAP"
    apply_node "$PROCROOT/sys/vm/page-cluster" 0
    if [ "$PROFILE" != gaming ]; then
        for QUEUE in "$SYSROOT/block/sda/queue/scheduler" "$SYSROOT/block/sdc/queue/scheduler"; do
            apply_scheduler "$QUEUE" mq-deadline
        done
    fi
}

restore_originals() {
    if [ ! -s "$STATE" ]; then printf 'No prior changes recorded for this boot.\n'; return; fi
    TAB=$(printf '\t')
    while IFS="$TAB" read -r RESTORE_NODE RESTORE_VALUE; do
        [ -n "$RESTORE_NODE" ] || continue
        case "$RESTORE_NODE" in
            "$SYSROOT"/*|"$PROCROOT"/*) ;;
            *) fail 'invalid path in saved state'; continue ;;
        esac
        if [ ! -w "$RESTORE_NODE" ]; then fail "$RESTORE_NODE cannot be restored"; continue; fi
        if ! printf '%s\n' "$RESTORE_VALUE" > "$RESTORE_NODE" 2>/dev/null; then
            fail "$RESTORE_NODE restore write failed"; continue
        fi
        RESTORED=$(read_current "$RESTORE_NODE") || RESTORED='[unreadable]'
        if [ "$RESTORED" = "$RESTORE_VALUE" ]; then
            printf 'RESTORED: %s = %s\n' "$RESTORE_NODE" "$RESTORED"
            OK=$((OK + 1))
        else
            fail "$RESTORE_NODE restore read back $RESTORED (wanted $RESTORE_VALUE)"
        fi
    done < "$STATE"
    if [ "$FAIL" -eq 0 ]; then rm -f -- "$STATE"; fi
}

case "$ACTION" in
    profile_daily|profile_gaming|profile_battery|profile_cooldown|profile_revert|swap:40|swap:60|swap:80|swap:100|pcls:0|pcls:3|gpu:[0-7]|ios:*) ;;
    *) printf 'ERROR: unsupported control action\n'; exit 2 ;;
esac
if [ "$(id -u)" != 0 ]; then printf 'ERROR: root required; no values changed\n'; exit 2; fi
BOOT_ID=$(cat "$PROCROOT/sys/kernel/random/boot_id" 2>/dev/null) || BOOT_ID=''
case "$BOOT_ID" in ''|*[!0-9a-fA-F-]*) printf 'ERROR: boot ID unavailable; no values changed\n'; exit 2 ;; esac
umask 077
if [ -L "$STATE_DIR" ] || ! mkdir -p "$STATE_DIR" || ! chmod 700 "$STATE_DIR"; then
    printf 'ERROR: private state directory unavailable; no values changed\n'; exit 2
fi
# Serialize app and WebUI actions as well as separate Manager processes. A stale
# lock only lasts until reboot, because its name includes the boot ID.
LOCK="$STATE_DIR/lock-$BOOT_ID"
if ! mkdir "$LOCK" 2>/dev/null; then printf 'ERROR: another control action is running; no values changed\n'; exit 2; fi
trap 'rmdir "$LOCK" 2>/dev/null || true' 0
trap 'exit 2' HUP INT TERM
STATE="$STATE_DIR/$BOOT_ID.tsv"
if [ -L "$STATE" ] || ! touch "$STATE"; then printf 'ERROR: state file unavailable; no values changed\n'; exit 2; fi

case "$ACTION" in
    profile_daily) apply_profile daily ;;
    profile_gaming) apply_profile gaming ;;
    profile_battery) apply_profile battery ;;
    profile_cooldown) apply_profile cooldown ;;
    profile_revert) restore_originals ;;
    swap:*) apply_node "$PROCROOT/sys/vm/swappiness" "${ACTION#swap:}" ;;
    pcls:*) apply_node "$PROCROOT/sys/vm/page-cluster" "${ACTION#pcls:}" ;;
    gpu:*)
        GPU_LEVEL=${ACTION#gpu:}
        GPU_LEVELS=$(cat "$SYSROOT/class/kgsl/kgsl-3d0/num_pwrlevels" 2>/dev/null) || GPU_LEVELS=''
        case "$GPU_LEVELS" in ''|*[!0-9]*) fail 'GPU power-level count unavailable' ;;
            *) if [ "$GPU_LEVEL" -lt "$GPU_LEVELS" ]; then
                   apply_node "$SYSROOT/class/kgsl/kgsl-3d0/min_pwrlevel" "$GPU_LEVEL"
               else fail 'GPU level out of range'; fi ;;
        esac
        ;;
    ios:*)
        SCHED=${ACTION#ios:}
        case "$SCHED" in ''|*[!a-zA-Z0-9_-]*) fail 'invalid scheduler name' ;;
            *) for QUEUE in "$SYSROOT/block/sda/queue/scheduler" "$SYSROOT/block/sdc/queue/scheduler" "$SYSROOT/block/mmcblk0/queue/scheduler"; do
                   apply_scheduler "$QUEUE" "$SCHED"
               done ;;
        esac
        ;;
esac
printf 'RESULT: verified=%s skipped=%s failed=%s\n' "$OK" "$SKIP" "$FAIL"
if [ "$FAIL" -ne 0 ] || [ "$SKIP" -ne 0 ]; then exit 1; fi
if [ "$OK" -eq 0 ] && [ "$ACTION" != profile_revert ]; then exit 1; fi
exit 0
