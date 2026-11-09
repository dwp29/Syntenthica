#!/system/bin/sh
# Synthetica Manager 4.0: opt-in, runtime-only Boost. No boot scripts are installed.
# SP_* overrides are for fake-filesystem host tests. The Manager explicitly
# unsets them before invoking this bundled script on a device.
PROCROOT=${SP_PROCSYS:-/proc}
STATE_DIR=${SP_STATE_DIR:-/data/adb/synthetica40/boost}
SERVICE_DIR=${SP_SERVICE_DIR:-/data/adb/service.d}
ACTION=${1:-}
set -f  # Never expand command output as glob patterns.
OK=0
SKIP=0
FAIL=0

fail() { printf 'ERROR: %s\n' "$*"; FAIL=$((FAIL + 1)); }
skip() { printf 'SKIPPED: %s\n' "$*"; SKIP=$((SKIP + 1)); }

case "$ACTION" in
    status|remove_legacy|network_apply|network_restore|audio_restore) ;;
    audio_apply:8[4-9]|audio_apply:9[0-6]) ;;
    *) printf 'ERROR: unsupported Boost action\n'; exit 2 ;;
esac
[ "$(id -u)" = 0 ] || { printf 'ERROR: root required; no values changed\n'; exit 2; }

# Do not automatically delete, migrate or infer the originals of 2.x/3.x scripts.
legacy_status() {
    if [ -L "$SERVICE_DIR" ]; then fail 'legacy service directory is a symlink'; return; fi
    found=0
    for legacy in synthetica-boost.sh rc-boost.sh synthetica-sound.sh rc-sound.sh; do
        if [ -e "$SERVICE_DIR/$legacy" ] || [ -L "$SERVICE_DIR/$legacy" ]; then
            printf 'LEGACY STARTUP PRESENT: %s\n' "$SERVICE_DIR/$legacy"
            found=$((found + 1))
        fi
    done
    [ "$found" -gt 0 ] || printf 'No known legacy Boost startup scripts found.\n'
    printf 'Existing settings may have been changed before this Manager could snapshot them.\n'
}
remove_legacy() {
    if [ -L "$SERVICE_DIR" ]; then fail 'legacy service directory is a symlink'; return; fi
    for legacy in synthetica-boost.sh rc-boost.sh synthetica-sound.sh rc-sound.sh; do
        target="$SERVICE_DIR/$legacy"
        if [ -L "$target" ] || [ -f "$target" ]; then
            if rm -f -- "$target"; then printf 'REMOVED: %s\n' "$target"; OK=$((OK + 1))
            else fail "could not remove $target"; fi
        elif [ -e "$target" ]; then
            fail "not a regular file or link: $target"
        fi
    done
    printf 'Past values are not inferred or restored by removing startup scripts.\n'
}
case "$ACTION" in
    status) legacy_status; [ "$FAIL" -eq 0 ]; exit $? ;;
    remove_legacy) remove_legacy; [ "$FAIL" -eq 0 ]; exit $? ;;
esac

BOOT_ID=$(cat "$PROCROOT/sys/kernel/random/boot_id" 2>/dev/null) || BOOT_ID=''
case "$BOOT_ID" in ''|*[!0-9a-fA-F-]*) printf 'ERROR: boot ID unavailable; no values changed\n'; exit 2 ;; esac
[ "${#BOOT_ID}" -le 64 ] || { printf 'ERROR: invalid boot ID; no values changed\n'; exit 2; }
case "$ACTION" in network_*) GROUP=network ;; audio_*) GROUP=audio ;; esac
umask 077
if [ -L "$STATE_DIR" ] || ! mkdir -p "$STATE_DIR" || ! chmod 700 "$STATE_DIR"; then
    printf 'ERROR: private state directory unavailable; no values changed\n'; exit 2
fi
LOCK="$STATE_DIR/lock-$BOOT_ID"
if ! mkdir "$LOCK" 2>/dev/null; then printf 'ERROR: another Boost action is running; no values changed\n'; exit 2; fi
trap 'rmdir "$LOCK" 2>/dev/null || true' 0
trap 'exit 2' HUP INT TERM
if [ -L "$STATE_DIR/$BOOT_ID" ] || [ -L "$STATE_DIR/$BOOT_ID/$GROUP" ] ||
   ! mkdir -p "$STATE_DIR/$BOOT_ID/$GROUP"; then
    printf 'ERROR: snapshot directory unavailable; no values changed\n'; exit 2
fi
SNAP="$STATE_DIR/$BOOT_ID/$GROUP"

node_for() {
    case "$1" in
        rmem) printf '%s' "$PROCROOT/sys/net/core/rmem_max" ;;
        wmem) printf '%s' "$PROCROOT/sys/net/core/wmem_max" ;;
        fastopen) printf '%s' "$PROCROOT/sys/net/ipv4/tcp_fastopen" ;;
        qdisc) printf '%s' "$PROCROOT/sys/net/core/default_qdisc" ;;
        congestion) printf '%s' "$PROCROOT/sys/net/ipv4/tcp_congestion_control" ;;
        *) return 1 ;;
    esac
}
valid_value() {
    case "$1" in
        rmem|wmem|fastopen|rx0|rx1|rx2)
            case "$2" in ''|*[!0-9]*) return 1 ;; esac
            [ "${#2}" -le 9 ] ;;
        qdisc|congestion)
            case "$2" in ''|*[!a-zA-Z0-9_-]*) return 1 ;; esac
            [ "${#2}" -le 32 ] ;;
        wifi) [ "$2" = on ] || [ "$2" = off ] ;;
        *) return 1 ;;
    esac
}
# Accept only a single line of numeric values (or a known tinymix range
# suffix). Refuse different channel originals: one write may update them all.
parse_audio() {
    printf '%s\n' "$1" | awk -v ctl="$2" '
        NR > 1 { bad = 1; next }
        {
            line = $0
            prefix = ctl ":"
            if (index(line, prefix) == 1) line = substr(line, length(prefix) + 1)
            sub(/[[:space:]]*\(range [0-9]+->[0-9]+\)[[:space:]]*$/, "", line)
            gsub(/,/, " ", line)
            gsub(/^[[:space:]]+|[[:space:]]+$/, "", line)
            if (line !~ /^[0-9]+([[:space:]]+[0-9]+)*$/) { bad = 1; next }
            count = split(line, values, /[[:space:]]+/)
            if (count < 1 || count > 16) { bad = 1; next }
            first = values[1]
            for (i = 2; i <= count; i++) if (values[i] != first) bad = 1
        }
        END { if (!bad && first != "") print first; else exit 1 }
    '
}
audio_read() {
    case "$1" in rx0) ctl='RX0 Digital Volume' ;; rx1) ctl='RX1 Digital Volume' ;; rx2) ctl='RX2 Digital Volume' ;; *) return 1 ;; esac
    command -v tinymix >/dev/null 2>&1 || return 1
    # Android vendor tinymix and upstream tinyalsa use different CLI styles.
    for mode in value legacy modern; do
        case "$mode" in
            value) raw=$(tinymix -v "$ctl" 2>/dev/null) || continue ;;
            legacy) raw=$(tinymix "$ctl" 2>/dev/null) || continue ;;
            modern) raw=$(tinymix get "$ctl" 2>/dev/null) || continue ;;
        esac
        parsed=$(parse_audio "$raw" "$ctl") || continue
        printf '%s' "$parsed"
        return 0
    done
    return 1
}
read_value() {
    case "$1" in
        wifi)
            command -v iw >/dev/null 2>&1 || return 1
            result=$(iw dev wlan0 get power_save 2>/dev/null) || return 1
            case "$result" in 'Power save: on') printf on ;; 'Power save: off') printf off ;; *) return 1 ;; esac
            ;;
        rx0|rx1|rx2) audio_read "$1" ;;
        *) node=$(node_for "$1") || return 1; [ -f "$node" ] || return 1; cat "$node" 2>/dev/null ;;
    esac
}
write_value() {
    case "$1" in
        wifi) iw dev wlan0 set power_save "$2" >/dev/null 2>&1 ;;
        rx0|rx1|rx2)
            case "$1" in rx0) ctl='RX0 Digital Volume' ;; rx1) ctl='RX1 Digital Volume' ;; rx2) ctl='RX2 Digital Volume' ;; esac
            tinymix "$ctl" "$2" >/dev/null 2>&1 || tinymix set "$ctl" "$2" >/dev/null 2>&1 ;;
        *) node=$(node_for "$1") || return 1; [ -w "$node" ] || return 1; printf '%s\n' "$2" > "$node" 2>/dev/null ;;
    esac
}
atomic_state() {
    dest=$1
    data=$2
    if [ -L "$dest" ] || [ -L "$dest.tmp" ]; then return 1; fi
    printf '%s\n' "$data" > "$dest.tmp" && mv -f -- "$dest.tmp" "$dest"
}
apply_key() {
    A_KEY=$1
    A_WANT=$2
    A_ORIG="$SNAP/$A_KEY.orig"
    A_LAST="$SNAP/$A_KEY.last"
    if [ -L "$A_ORIG" ] || [ -L "$A_LAST" ]; then fail "$A_KEY snapshot is a symlink"; return; fi
    A_BEFORE=$(read_value "$A_KEY") || { skip "$A_KEY missing or not reliably readable"; return; }
    valid_value "$A_KEY" "$A_BEFORE" && valid_value "$A_KEY" "$A_WANT" || { fail "$A_KEY value cannot be verified"; return; }
    if [ -f "$A_ORIG" ]; then
        A_SAVED=$(cat "$A_ORIG" 2>/dev/null) || { fail "$A_KEY saved value unreadable"; return; }
        valid_value "$A_KEY" "$A_SAVED" || { fail "$A_KEY saved value invalid"; return; }
        if [ -f "$A_LAST" ]; then
            A_PREV=$(cat "$A_LAST" 2>/dev/null) || { fail "$A_KEY last value unreadable"; return; }
            valid_value "$A_KEY" "$A_PREV" || { fail "$A_KEY last value invalid"; return; }
            if [ "$A_BEFORE" != "$A_PREV" ] && [ "$A_BEFORE" != "$A_SAVED" ]; then
                fail "$A_KEY changed externally; not overwritten"; return
            fi
        elif [ "$A_BEFORE" != "$A_SAVED" ]; then
            fail "$A_KEY snapshot incomplete; not overwritten"; return
        fi
    else
        atomic_state "$A_ORIG" "$A_BEFORE" || { fail "$A_KEY not changed: could not save original"; return; }
    fi
    # Record intent before the write. A crash/failure can leave an ambiguous
    # snapshot; restore then refuses to overwrite an unrelated value.
    atomic_state "$A_LAST" "$A_WANT" || { fail "$A_KEY not changed: could not save target"; return; }
    if ! write_value "$A_KEY" "$A_WANT"; then fail "$A_KEY write failed; snapshot retained"; return; fi
    A_AFTER=$(read_value "$A_KEY") || A_AFTER='[unreadable]'
    if [ "$A_AFTER" != "$A_WANT" ]; then fail "$A_KEY read back $A_AFTER, wanted $A_WANT; snapshot retained"; return; fi
    printf 'VERIFIED: %s = %s (original %s)\n' "$A_KEY" "$A_AFTER" "$A_BEFORE"
    OK=$((OK + 1))
}
restore_key() {
    R_KEY=$1
    R_ORIG="$SNAP/$R_KEY.orig"
    R_LAST="$SNAP/$R_KEY.last"
    if [ -L "$R_ORIG" ] || [ -L "$R_LAST" ]; then fail "$R_KEY snapshot is a symlink"; return; fi
    [ -f "$R_ORIG" ] || return
    R_SAVED=$(cat "$R_ORIG" 2>/dev/null) || { fail "$R_KEY saved value unreadable"; return; }
    valid_value "$R_KEY" "$R_SAVED" || { fail "$R_KEY saved value invalid"; return; }
    R_BEFORE=$(read_value "$R_KEY") || { fail "$R_KEY no longer readable; snapshot retained"; return; }
    if [ "$R_BEFORE" = "$R_SAVED" ]; then
        rm -f -- "$R_ORIG" "$R_LAST" || { fail "$R_KEY snapshot cleanup failed"; return; }
        printf 'ALREADY ORIGINAL: %s = %s\n' "$R_KEY" "$R_SAVED"; OK=$((OK + 1)); return
    fi
    [ -f "$R_LAST" ] || { fail "$R_KEY target missing; not overwritten"; return; }
    R_TARGET=$(cat "$R_LAST" 2>/dev/null) || { fail "$R_KEY target unreadable"; return; }
    valid_value "$R_KEY" "$R_TARGET" || { fail "$R_KEY target invalid"; return; }
    [ "$R_BEFORE" = "$R_TARGET" ] || { fail "$R_KEY changed externally; not overwritten"; return; }
    if ! write_value "$R_KEY" "$R_SAVED"; then fail "$R_KEY restore write failed"; return; fi
    R_AFTER=$(read_value "$R_KEY") || R_AFTER='[unreadable]'
    if [ "$R_AFTER" != "$R_SAVED" ]; then fail "$R_KEY restore read back $R_AFTER; snapshot retained"; return; fi
    rm -f -- "$R_ORIG" "$R_LAST" || { fail "$R_KEY snapshot cleanup failed"; return; }
    printf 'RESTORED: %s = %s\n' "$R_KEY" "$R_AFTER"
    OK=$((OK + 1))
}

case "$ACTION" in
    network_apply)
        apply_key rmem 8388608
        apply_key wmem 8388608
        apply_key fastopen 3
        apply_key qdisc fq_codel
        available=$(cat "$PROCROOT/sys/net/ipv4/tcp_available_congestion_control" 2>/dev/null) || available=''
        if printf '%s\n' "$available" | tr ' ' '\n' | grep -Fxq bbr; then apply_key congestion bbr
        else skip 'bbr congestion control not reported available'; fi
        apply_key wifi off
        ;;
    network_restore) for key in rmem wmem fastopen qdisc congestion wifi; do restore_key "$key"; done ;;
    audio_apply:*) gain=${ACTION#audio_apply:}; for key in rx0 rx1 rx2; do apply_key "$key" "$gain"; done ;;
    audio_restore) for key in rx0 rx1 rx2; do restore_key "$key"; done ;;
esac
case "$ACTION" in *_restore)
    if [ "$OK" -eq 0 ] && [ "$FAIL" -eq 0 ]; then
        printf 'No snapshots recorded for this boot; older settings cannot be inferred.\n'
    fi ;;
esac
printf 'RESULT: verified=%s skipped=%s failed=%s\n' "$OK" "$SKIP" "$FAIL"
if [ "$FAIL" -ne 0 ] || [ "$SKIP" -ne 0 ]; then exit 1; fi
case "$ACTION" in *_apply|audio_apply:*) [ "$OK" -gt 0 ] || exit 1 ;; esac
exit 0
