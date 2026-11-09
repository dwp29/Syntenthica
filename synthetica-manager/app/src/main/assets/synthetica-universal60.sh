#!/system/bin/sh
# Synthetica Manager 6.0.0: Universal Kernel Telemetry, .ko Module Loader & Diagnostics.
# SP_* overrides are used only by host-side fake-filesystem unit tests; production
# execution explicitly unsets them before running this helper.

SYSROOT=${SP_SYSROOT:-/sys}
PROCROOT=${SP_PROCSYS:-/proc}
MOD_DIR=${SP_MOD_DIR:-/data/adb/modules/synthetica_extra/vendor/lib/modules}
VENDOR_MOD_DIR=${SP_VENDOR_MOD_DIR:-/vendor/lib/modules}
ACTION=${1:-}
set -f

read_one() {
    [ -r "$1" ] || return 1
    cat "$1" 2>/dev/null | head -n 1 | tr -d '\r'
}

print_telemetry() {
    UNAME_R=$(uname -r 2>/dev/null || printf 'unknown')
    UNAME_M=$(uname -m 2>/dev/null || printf 'unknown')
    printf 'KERNEL: %s (%s)\n' "$UNAME_R" "$UNAME_M"

    # CPU policies (works across all SoCs: miatoll policy0/policy6, tri-cluster policy0/4/7, etc.)
    set +f
    for POLICY in "$SYSROOT"/devices/system/cpu/cpufreq/policy*; do
        set -f
        [ -d "$POLICY" ] || continue
        PNAME=${POLICY##*/}
        CUR=$(read_one "$POLICY/scaling_cur_freq" || read_one "$POLICY/cpuinfo_cur_freq" || printf '0')
        MIN=$(read_one "$POLICY/scaling_min_freq" || read_one "$POLICY/cpuinfo_min_freq" || printf '0')
        MAX=$(read_one "$POLICY/scaling_max_freq" || read_one "$POLICY/cpuinfo_max_freq" || printf '0')
        GOV=$(read_one "$POLICY/scaling_governor" || printf 'unknown')
        case "$CUR" in ''|*[!0-9]*) CUR_MHZ='?' ;; *) CUR_MHZ=$((CUR / 1000)) ;; esac
        case "$MIN" in ''|*[!0-9]*) MIN_MHZ='?' ;; *) MIN_MHZ=$((MIN / 1000)) ;; esac
        case "$MAX" in ''|*[!0-9]*) MAX_MHZ='?' ;; *) MAX_MHZ=$((MAX / 1000)) ;; esac
        printf 'CPU_%s: cur=%sMHz range=%s-%sMHz gov=%s\n' "$PNAME" "$CUR_MHZ" "$MIN_MHZ" "$MAX_MHZ" "$GOV"
    done
    set -f

    # GPU (Qualcomm KGSL or generic devfreq)
    if [ -d "$SYSROOT/class/kgsl/kgsl-3d0" ]; then
        GCUR=$(read_one "$SYSROOT/class/kgsl/kgsl-3d0/gpuclk" || printf '0')
        GPWR=$(read_one "$SYSROOT/class/kgsl/kgsl-3d0/min_pwrlevel" || printf '?')
        GLVL=$(read_one "$SYSROOT/class/kgsl/kgsl-3d0/num_pwrlevels" || printf '?')
        case "$GCUR" in ''|*[!0-9]*) GMHZ='?' ;; *) GMHZ=$((GCUR / 1000000)) ;; esac
        printf 'GPU_KGSL: clk=%sMHz min_pwrlevel=%s/%s\n' "$GMHZ" "$GPWR" "$GLVL"
    fi

    # Thermal zones (battery & SoC)
    BATT_T=$(read_one "$SYSROOT/class/power_supply/battery/temp" || printf '')
    case "$BATT_T" in
        ''|*[!0-9-]*) ;;
        *) printf 'THERMAL_BATTERY: %s.%s C\n' "$((BATT_T / 10))" "$((BATT_T % 10))" ;;
    esac

    # Memory, Swap & ZRAM
    if [ -r "$PROCROOT/meminfo" ]; then
        awk '
            /^MemTotal:/ { mt = int($2 / 1024) }
            /^MemAvailable:/ { ma = int($2 / 1024) }
            /^SwapTotal:/ { st = int($2 / 1024) }
            /^SwapFree:/ { sf = int($2 / 1024) }
            END {
                if (mt > 0) printf "MEMORY: used=%dMB / %dMB (avail=%dMB) swap_used=%dMB / %dMB\n", (mt - ma), mt, ma, (st - sf), st
            }
        ' "$PROCROOT/meminfo"
    fi

    # MGLRU, VM, TCP Congestion & Block Scheduler
    MGLRU=$(read_one "$SYSROOT/kernel/mm/lru_gen/enabled" || printf 'unavailable')
    MGLRU_TTL=$(read_one "$SYSROOT/kernel/mm/lru_gen/min_ttl_ms" || printf 'n/a')
    SWAP_VAL=$(read_one "$PROCROOT/sys/vm/swappiness" || printf '?')
    TCP_CC=$(read_one "$PROCROOT/sys/net/ipv4/tcp_congestion_control" || printf '?')
    QDISC=$(read_one "$PROCROOT/sys/net/core/default_qdisc" || printf '?')
    printf 'VM_MGLRU: enabled=%s min_ttl_ms=%s swappiness=%s\n' "$MGLRU" "$MGLRU_TTL" "$SWAP_VAL"
    printf 'NET_STACK: congestion=%s qdisc=%s\n' "$TCP_CC" "$QDISC"

    for BLK in sda sdc mmcblk0; do
        if [ -r "$SYSROOT/block/$BLK/queue/scheduler" ]; then
            SCHED=$(cat "$SYSROOT/block/$BLK/queue/scheduler" 2>/dev/null | tr -d '\r')
            printf 'IO_%s: %s\n' "$BLK" "$SCHED"
        fi
    done
}

find_ko_path() {
    MNAME=$1
    for DIR in "$MOD_DIR" "$VENDOR_MOD_DIR"; do
        if [ -f "$DIR/$MNAME.ko" ] && [ ! -L "$DIR/$MNAME.ko" ]; then
            printf '%s/%s.ko' "$DIR" "$MNAME"
            return 0
        fi
    done
    return 1
}

is_mod_loaded() {
    MNAME=$1
    [ -r "$PROCROOT/modules" ] || return 1
    awk -v m="$MNAME" '$1 == m { found = 1; exit } END { exit !found }' "$PROCROOT/modules"
}

kmod_status() {
    for MOD in ntfs wireguard zsmalloc lz4_compress zstd_compress; do
        if is_mod_loaded "$MOD"; then
            STATE_LBL="LOADED"
        else
            STATE_LBL="UNLOADED"
        fi
        if KO_PATH=$(find_ko_path "$MOD"); then
            printf 'KMOD %s: state=%s file=%s\n' "$MOD" "$STATE_LBL" "$KO_PATH"
        else
            printf 'KMOD %s: state=%s file=BUILT_IN_OR_NOT_FOUND\n' "$MOD" "$STATE_LBL"
        fi
    done
}

kmod_load() {
    MOD=$1
    if [ "$(id -u)" != 0 ]; then printf 'ERROR: root required to load module %s\n' "$MOD"; exit 2; fi
    if is_mod_loaded "$MOD"; then
        printf 'OK: module %s is already loaded\n' "$MOD"
        return 0
    fi
    KO_PATH=$(find_ko_path "$MOD") || {
        printf 'ERROR: %s.ko not found in %s or %s\n' "$MOD" "$MOD_DIR" "$VENDOR_MOD_DIR"
        exit 1
    }
    if insmod "$KO_PATH" 2>&1; then
        printf 'LOADED: %s (%s)\n' "$MOD" "$KO_PATH"
        return 0
    else
        printf 'ERROR: insmod failed for %s\n' "$KO_PATH"
        exit 1
    fi
}

kmod_unload() {
    MOD=$1
    if [ "$(id -u)" != 0 ]; then printf 'ERROR: root required to unload module %s\n' "$MOD"; exit 2; fi
    if ! is_mod_loaded "$MOD"; then
        printf 'OK: module %s is not currently loaded\n' "$MOD"
        return 0
    fi
    if rmmod "$MOD" 2>&1; then
        printf 'UNLOADED: %s\n' "$MOD"
        return 0
    else
        printf 'ERROR: rmmod failed for %s (module may be in use)\n' "$MOD"
        exit 1
    fi
}

diag_dmesg() {
    if [ "$(id -u)" != 0 ]; then printf 'ERROR: root required for dmesg\n'; exit 2; fi
    dmesg 2>/dev/null | tail -n 80 | cut -c 1-240
}

diag_pstore() {
    PSTORE_DIR=${SP_PSTORE_DIR:-/sys/fs/pstore}
    if [ ! -d "$PSTORE_DIR" ]; then
        printf 'PSTORE: /sys/fs/pstore directory not present.\n'
        return 0
    fi
    set +f
    FOUND=0
    for F in "$PSTORE_DIR"/*; do
        set -f
        [ -f "$F" ] || continue
        FOUND=1
        printf '=== %s ===\n' "${F##*/}"
        tail -n 40 "$F" 2>/dev/null | cut -c 1-240
    done
    set -f
    [ "$FOUND" -eq 1 ] || printf 'PSTORE: clean (no crash/ramoops logs present).\n'
}

diag_boot() {
    printf 'UNAME: %s\n' "$(uname -a 2>/dev/null || printf 'unknown')"
    printf 'SELINUX: %s\n' "$(getenforce 2>/dev/null || printf 'unknown')"
    if command -v getprop >/dev/null 2>&1; then
        for PROP in ro.product.device ro.product.model ro.build.version.release ro.boot.slot_suffix ro.boot.verifiedbootstate ro.boot.vbmeta.device_state; do
            VAL=$(getprop "$PROP" 2>/dev/null | tr -d '\r')
            printf 'PROP %s = %s\n' "$PROP" "${VAL:-n/a}"
        done
    fi
    if [ -r "$PROCROOT/cmdline" ]; then
        printf 'CMDLINE: %s\n' "$(cat "$PROCROOT/cmdline" 2>/dev/null | cut -c 1-400)"
    fi
}

case "$ACTION" in
    telemetry) print_telemetry ;;
    kmod_status) kmod_status ;;
    kmod_load:ntfs|kmod_load:wireguard|kmod_load:zsmalloc|kmod_load:lz4_compress|kmod_load:zstd_compress)
        kmod_load "${ACTION#kmod_load:}" ;;
    kmod_unload:ntfs|kmod_unload:wireguard|kmod_unload:zsmalloc|kmod_unload:lz4_compress|kmod_unload:zstd_compress)
        kmod_unload "${ACTION#kmod_unload:}" ;;
    diag_dmesg) diag_dmesg ;;
    diag_pstore) diag_pstore ;;
    diag_boot) diag_boot ;;
    *) printf 'ERROR: unsupported universal60 action\n'; exit 2 ;;
esac
