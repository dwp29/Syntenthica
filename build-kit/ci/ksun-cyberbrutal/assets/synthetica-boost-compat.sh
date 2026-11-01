#!/system/bin/sh
# Optional Synthetica 2.0-compatible userspace network/audio controls.
# Runs only on an explicit user action; status performs no writes.

ACTION=${1:-}
VALUE=${2:-}
SERVICE_DIR=${SP_SERVICE_DIR:-/data/adb/service.d}
PROCROOT=${SP_PROCSYS:-/proc}
NETWORK="$SERVICE_DIR/synthetica-boost.sh"
NETWORK_OLD="$SERVICE_DIR/rc-boost.sh"
AUDIO="$SERVICE_DIR/synthetica-sound.sh"
AUDIO_OLD="$SERVICE_DIR/rc-sound.sh"

if [ "$(id -u)" != 0 ]; then echo 'ERROR: root required'; exit 2; fi

validate_gain() {
    case "$VALUE" in 8[4-9]|9[0-6]) return 0 ;; *) return 1 ;; esac
}
prepare_dir() {
    [ ! -L "$SERVICE_DIR" ] && mkdir -p "$SERVICE_DIR" && [ -d "$SERVICE_DIR" ]
}

case "$ACTION" in
    status)
        if [ -f "$NETWORK" ] || [ -f "$NETWORK_OLD" ]; then echo 'NETWORK_BOOT=installed'; else echo 'NETWORK_BOOT=not installed'; fi
        if [ -f "$AUDIO" ] || [ -f "$AUDIO_OLD" ]; then echo 'AUDIO_BOOT=installed'; else echo 'AUDIO_BOOT=not installed'; fi
        TCP=$(cat "$PROCROOT/sys/net/ipv4/tcp_congestion_control" 2>/dev/null) || TCP='unavailable'
        echo "TCP=$TCP"
        if command -v iw >/dev/null 2>&1; then
            WIFI=$(iw dev wlan0 get power_save 2>/dev/null) || WIFI='unavailable'
        else WIFI='iw unavailable'; fi
        echo "WIFI=$WIFI"
        if command -v tinymix >/dev/null 2>&1; then echo 'TINYMIX=available'; else echo 'TINYMIX=unavailable'; fi
        exit 0
        ;;
    network_once)
        OK=0; FAIL=0
        set_value() {
            NODE="$PROCROOT/sys/$1"; WANT=$2
            if [ ! -w "$NODE" ]; then echo "SKIPPED: $1 unavailable"; FAIL=$((FAIL + 1)); return; fi
            if ! printf '%s\n' "$WANT" > "$NODE" 2>/dev/null; then echo "ERROR: $1 write failed"; FAIL=$((FAIL + 1)); return; fi
            READ=$(cat "$NODE" 2>/dev/null) || READ='unavailable'
            if [ "$READ" = "$WANT" ]; then echo "VERIFIED: $1 = $READ"; OK=$((OK + 1)); else echo "ERROR: $1 read back $READ"; FAIL=$((FAIL + 1)); fi
        }
        set_value net/core/rmem_max 8388608
        set_value net/core/wmem_max 8388608
        set_value net/ipv4/tcp_fastopen 3
        set_value net/core/default_qdisc fq_codel
        if grep -qw bbr "$PROCROOT/sys/net/ipv4/tcp_available_congestion_control" 2>/dev/null; then
            set_value net/ipv4/tcp_congestion_control bbr
        else echo 'SKIPPED: BBR unavailable'; FAIL=$((FAIL + 1)); fi
        if command -v iw >/dev/null 2>&1 && iw dev wlan0 set power_save off 2>/dev/null; then
            WIFI=$(iw dev wlan0 get power_save 2>/dev/null) || WIFI='unavailable'
            case "$WIFI" in *off*) echo 'VERIFIED: Wi-Fi power save off'; OK=$((OK + 1)) ;;
                *) echo "ERROR: Wi-Fi readback: $WIFI"; FAIL=$((FAIL + 1)) ;;
            esac
        else echo 'SKIPPED: wlan0/iw unavailable'; FAIL=$((FAIL + 1)); fi
        echo "RESULT: verified=$OK unavailable_or_failed=$FAIL"
        [ "$OK" -gt 0 ] && [ "$FAIL" -eq 0 ]
        ;;
    network_boot_on)
        prepare_dir || { echo 'ERROR: service.d unavailable'; exit 1; }
        TMP="$SERVICE_DIR/.synthetica-boost.$$.tmp"
        [ ! -e "$TMP" ] && [ ! -L "$TMP" ] || { echo 'ERROR: temporary path exists'; exit 1; }
        umask 077
        cat > "$TMP" <<'SYNTHETICA_NET'
#!/system/bin/sh
# User-enabled Synthetica network tuning, same targets as 2.0.
(
  sleep 12
  sysctl -w net.core.rmem_max=8388608 2>/dev/null
  sysctl -w net.core.wmem_max=8388608 2>/dev/null
  sysctl -w net.ipv4.tcp_fastopen=3 2>/dev/null
  sysctl -w net.core.default_qdisc=fq_codel 2>/dev/null
  if grep -qw bbr /proc/sys/net/ipv4/tcp_available_congestion_control 2>/dev/null; then
    sysctl -w net.ipv4.tcp_congestion_control=bbr 2>/dev/null
  fi
  iw dev wlan0 set power_save off 2>/dev/null
) &
SYNTHETICA_NET
        if chmod 0755 "$TMP" && mv -f "$TMP" "$NETWORK" && rm -f "$NETWORK_OLD"; then
            echo 'Network startup script installed. Individual effects depend on ROM and tools.'
        else rm -f "$TMP"; echo 'ERROR: startup script installation failed'; exit 1; fi
        ;;
    network_boot_off)
        rm -f "$NETWORK" "$NETWORK_OLD" || { echo 'ERROR: could not remove network startup scripts'; exit 1; }
        echo 'Network startup scripts removed. Existing live values were not changed.'
        ;;
    audio_once)
        validate_gain || { echo 'ERROR: gain must be in 84..96'; exit 2; }
        command -v tinymix >/dev/null 2>&1 || { echo 'ERROR: tinymix unavailable'; exit 1; }
        OK=0; FAIL=0
        for CTL in 'RX0 Digital Volume' 'RX1 Digital Volume' 'RX2 Digital Volume'; do
            if tinymix "$CTL" "$VALUE" 2>/dev/null; then echo "ACCEPTED: $CTL = $VALUE"; OK=$((OK + 1));
            else echo "ERROR: $CTL unavailable or write failed"; FAIL=$((FAIL + 1)); fi
        done
        echo "RESULT: accepted=$OK failed=$FAIL; audio effect not measured"
        [ "$OK" -gt 0 ] && [ "$FAIL" -eq 0 ]
        ;;
    audio_boot_on)
        validate_gain || { echo 'ERROR: gain must be in 84..96'; exit 2; }
        prepare_dir || { echo 'ERROR: service.d unavailable'; exit 1; }
        TMP="$SERVICE_DIR/.synthetica-sound.$$.tmp"
        [ ! -e "$TMP" ] && [ ! -L "$TMP" ] || { echo 'ERROR: temporary path exists'; exit 1; }
        umask 077
        {
            echo '#!/system/bin/sh'
            echo '# User-enabled Synthetica audio gain; ROM-specific controls.'
            echo '( sleep 15'
            printf '  for ctl in '\''RX0 Digital Volume'\'' '\''RX1 Digital Volume'\'' '\''RX2 Digital Volume'\''; do\n'
            printf '    tinymix "$ctl" %s 2>/dev/null\n' "$VALUE"
            echo '  done'
            echo ') &'
        } > "$TMP"
        if chmod 0755 "$TMP" && mv -f "$TMP" "$AUDIO" && rm -f "$AUDIO_OLD"; then
            echo "Audio startup script installed with gain $VALUE. Actual output was not measured."
        else rm -f "$TMP"; echo 'ERROR: audio startup script installation failed'; exit 1; fi
        ;;
    audio_boot_off)
        rm -f "$AUDIO" "$AUDIO_OLD" || { echo 'ERROR: could not remove audio startup scripts'; exit 1; }
        echo 'Audio startup scripts removed. Current mixer values were not changed.'
        ;;
    *) echo 'ERROR: unsupported action'; exit 2 ;;
esac
