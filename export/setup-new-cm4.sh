#!/usr/bin/env bash
# setup-new-cm4.sh - bring a fresh CM4 on an IntelliRFID v2.x carrier up to the state of the
# production unit it was exported from (kit rebuilt 2026-09-28; first used for intellisbc2 on 09-23).
#
# Run it TWICE, as the user intelli-sbc, from the folder holding the kit tarball:
#
#   bash setup-new-cm4.sh [--hostname NAME] [--reader-id N] [--ant 1|2]
#
#   pass 1  packages, groups, UART in config.txt, hostname, files, /opt, /etc, unit, sudoers.
#           Ends by asking for a reboot (the UART change needs one).
#   pass 2  (after the reboot, same command) checks the UART, probes the SIM7500's firmware and
#           auth region, reads tags on both antenna ports, picks the region the module can
#           actually run, then enables and starts the tunnel and checks its health.
#
# It is safe to re-run: every step checks before it acts. It sudoes for the privileged steps
# itself - do NOT run the whole script under sudo (Maven as root leaves root-owned build trees).
#
# It will NEVER flash firmware or write the module's auth region. Those are irreversible module
# writes and stay manual; the script tells you exactly when and how.
set -euo pipefail

HERE="$(cd "$(dirname "$0")" && pwd)"
KIT_TGZ="$(ls -1 "$HERE"/intelli-cm4-kit-*.tar.gz 2>/dev/null | tail -1 || true)"
SECRETS_TGZ="$(ls -1 "$HERE"/intelli-cm4-secrets-*.tar.gz 2>/dev/null | tail -1 || true)"

NEW_HOSTNAME=""
READER_ID=""
ANT=""
while [ $# -gt 0 ]; do
    case "$1" in
        --hostname)  NEW_HOSTNAME="$2"; shift 2 ;;
        --reader-id) READER_ID="$2";    shift 2 ;;
        --ant)       ANT="$2";          shift 2 ;;
        -h|--help)   sed -n '2,20p' "$0"; exit 0 ;;
        *) echo "unknown argument: $1" >&2; exit 2 ;;
    esac
done

USER_NAME=intelli-sbc
HOME_DIR=/home/$USER_NAME
WS=$HOME_DIR/rfid/intelli-rfid-reader
KIT=$HOME_DIR/intelli-cm4-kit
SITE_CFG=/etc/intelli/intelli-rfid-tunnel/application.yml
UNIT=/etc/systemd/system/intelli-rfid-tunnel.service
STATE=$HOME_DIR/.intelli-setup.conf
LOG=$HOME_DIR/intelli-setup-$(date +%Y%m%d-%H%M%S).log
TODO=()

exec > >(tee -a "$LOG") 2>&1

c_ok=$'\e[32m'; c_warn=$'\e[33m'; c_err=$'\e[31m'; c_b=$'\e[1m'; c_0=$'\e[0m'
step() { echo; echo "${c_b}== $*${c_0}"; }
ok()   { echo "  ${c_ok}ok${c_0}    $*"; }
warn() { echo "  ${c_warn}WARN${c_0}  $*"; }
die()  { echo "  ${c_err}FAIL${c_0}  $*"; exit 1; }
todo() { TODO+=("$*"); }
ask()  { local q="$1" d="$2" a; read -r -p "  $q [$d]: " a </dev/tty || true; echo "${a:-$d}"; }

# ------------------------------------------------------------------------------------------------
step "Preconditions"
[ "$(id -u)" -ne 0 ] || die "run as $USER_NAME, not root (the script sudoes for what needs it)"
[ "$(id -un)" = "$USER_NAME" ] || die "run as $USER_NAME: the unit file, sudoers and every path assume it. \
Create it in Raspberry Pi Imager when you flash the OS."
[ "$(uname -m)" = aarch64 ] || die "not aarch64 - the vendor .so is aarch64 only (64-bit Raspberry Pi OS)"
. /etc/os-release
ok "$PRETTY_NAME, $(uname -m), user $(id -un)"
[ "${VERSION_CODENAME:-}" = trixie ] || warn "exported from Debian 13 trixie; this is ${VERSION_CODENAME:-?}. \
On bookworm there is no openjdk-21 in the archive and gpiomon is v1 - expect to adapt."
sudo -v || die "sudo is needed for packages, /boot, /opt and /etc"

# Settings chosen on the first pass are remembered for the second.
[ -f "$STATE" ] && . "$STATE"
if [ -z "$NEW_HOSTNAME" ]; then
    NEW_HOSTNAME="${SAVED_HOSTNAME:-$(ask "Hostname for this board (taken: 'intellisbc', 'intellisbc2'; two boards with the same name clash on mDNS)" intellisbc3)}"
fi
if [ -z "$READER_ID" ]; then
    READER_ID="${SAVED_READER_ID:-$(ask "rfid.gs1.reader-id for this board (taken: 1 intellisbc, 2 intellisbc2; must be unique per unit)" 3)}"
fi
if [ -z "$ANT" ]; then
    ANT="${SAVED_ANT:-$(ask "Antenna port the service selects: 1 = J20, 2 = J25 (the old unit runs 2 because ITS J20 is faulty)" 2)}"
fi
case "$ANT" in 1|2) ;; *) die "--ant must be 1 or 2" ;; esac
[[ "$READER_ID" =~ ^[0-9]+$ ]] || die "--reader-id must be a number"
printf 'SAVED_HOSTNAME=%q\nSAVED_READER_ID=%q\nSAVED_ANT=%q\n' "$NEW_HOSTNAME" "$READER_ID" "$ANT" > "$STATE"
ok "hostname=$NEW_HOSTNAME reader-id=$READER_ID ant=ANT$ANT   (saved in $STATE)"

# ------------------------------------------------------------------------------------------------
step "1. Unpack the kit"
if [ -d "$KIT" ]; then
    ok "already unpacked at $KIT"
else
    [ -n "$KIT_TGZ" ] || die "no intelli-cm4-kit-*.tar.gz beside this script"
    ( cd "$HERE" && [ -f SHA256SUMS ] && sha256sum -c --ignore-missing SHA256SUMS ) || warn "no checksum file or mismatch - check the copy"
    tar -xzf "$KIT_TGZ" -C "$HOME_DIR"
    ok "unpacked $(basename "$KIT_TGZ") -> $KIT"
fi

# ------------------------------------------------------------------------------------------------
step "2. OS packages and groups"
PKGS=(openjdk-21-jdk maven git gpiod raspi-utils python3-serial tmux rsync curl unzip p7zip-full avahi-daemon)
MISSING=()
for p in "${PKGS[@]}"; do dpkg -s "$p" >/dev/null 2>&1 || MISSING+=("$p"); done
if [ ${#MISSING[@]} -gt 0 ]; then
    echo "  installing: ${MISSING[*]}"
    sudo apt-get update
    sudo apt-get install -y "${MISSING[@]}"
fi
ok "packages present"
for g in dialout gpio; do
    if id -nG "$USER_NAME" | tr ' ' '\n' | grep -qx "$g"; then ok "in group $g"
    else sudo usermod -aG "$g" "$USER_NAME"; warn "added to group $g - takes effect after the reboot"; fi
done

# ------------------------------------------------------------------------------------------------
step "3. UART for the SIM7500 (config.txt, serial console off)"
CFG=/boot/firmware/config.txt
NEED_REBOOT=0
sudo mount -o remount,rw /boot/firmware 2>/dev/null || true
if grep -q '^# --- IntelliRFID' "$CFG" || { grep -qx 'dtoverlay=disable-bt' "$CFG" && grep -qx 'dtoverlay=uart3' "$CFG"; }; then
    ok "config.txt already has disable-bt + uart3"
else
    sudo cp -a "$CFG" "$CFG.bak.$(date +%Y%m%d-%H%M%S)"
    # NO trailing comments on a setting line: config.txt parses them as part of the value and
    # silently ignores the setting (cost a reboot 2026-08-29).
    sudo tee -a "$CFG" >/dev/null <<'EOF'

[all]
# --- IntelliRFID -----------------------------------------------------------
# frees the PL011 (ttyAMA0) on GPIO14/15 for the SIM7500
enable_uart=1
dtoverlay=disable-bt
# SAMD21 supervisor on GPIO4/5 (ttyAMA3; not used by the app)
dtoverlay=uart3
EOF
    NEED_REBOOT=1; warn "appended the IntelliRFID block to $CFG (backup beside it)"
fi
if grep -q 'console=serial0\|console=ttyAMA0\|console=ttyS0' /boot/firmware/cmdline.txt; then
    sudo raspi-config nonint do_serial_cons 1
    NEED_REBOOT=1; warn "serial login console removed from cmdline.txt"
else
    ok "no serial console on the UART"
fi
sudo systemctl disable --now serial-getty@ttyAMA0.service >/dev/null 2>&1 || true

# ------------------------------------------------------------------------------------------------
step "4. Hostname"
if [ "$(hostname)" = "$NEW_HOSTNAME" ]; then ok "hostname is $NEW_HOSTNAME"
else
    OLD="$(hostname)"
    sudo hostnamectl set-hostname "$NEW_HOSTNAME"
    sudo sed -i "s/^127\.0\.1\.1\s.*/127.0.1.1\t$NEW_HOSTNAME/" /etc/hosts
    grep -q "^127\.0\.1\.1" /etc/hosts || echo -e "127.0.1.1\t$NEW_HOSTNAME" | sudo tee -a /etc/hosts >/dev/null
    NEED_REBOOT=1; warn "hostname $OLD -> $NEW_HOSTNAME (reachable as $NEW_HOSTNAME.local after reboot)"
fi

# ------------------------------------------------------------------------------------------------
step "5. Workspace, vendor SDK, Maven cache, Claude memory"
if [ -d "$WS/.git" ]; then ok "workspace already at $WS (left untouched)"
else
    mkdir -p "$HOME_DIR/rfid"
    rsync -a "$KIT/workspace/intelli-rfid-reader" "$HOME_DIR/rfid/"
    ok "workspace -> $WS (root repo + every app repo under apps/, with history)"
fi
if [ -d "$HOME_DIR/api/run" ]; then ok "~/api already present"
else rsync -a "$KIT/home/api" "$HOME_DIR/"; chmod +x "$HOME_DIR/api/run/run.sh"; ok "vendor SDK v260827 + probes -> ~/api"; fi
mkdir -p "$HOME_DIR/.m2"
rsync -a --ignore-existing "$KIT/m2/" "$HOME_DIR/.m2/"
ok "Maven repository merged into ~/.m2 (offline build: mvn -o)"
MEM=$HOME_DIR/.claude/projects/-home-intelli-sbc-rfid-intelli-rfid-reader/memory
if [ -d "$MEM" ]; then ok "Claude memory already present"
else mkdir -p "$(dirname "$MEM")"; cp -a "$KIT/claude/memory" "$MEM"; ok "Claude Code project memory -> $MEM"; fi
git config --global user.name  >/dev/null || git config --global user.name  "Piyush Nigam"
git config --global user.email >/dev/null || git config --global user.email "piyush.nigam@intellirail.in"
git config --global credential.helper >/dev/null || git config --global credential.helper store

# ------------------------------------------------------------------------------------------------
step "6. Runtime: /opt/intelli, /var/lib/intelli, site config, unit, shutdown hook, sudoers"
sudo install -d -m 755 /opt/intelli/intelli-rfid-tunnel /opt/intelli/lib
sudo install -d -m 755 -o "$USER_NAME" /opt/intelli/logs
sudo install -d -m 755 -o "$USER_NAME" -g "$USER_NAME" /var/lib/intelli /var/lib/intelli/tunnel /var/lib/intelli/tunnel/spool
if [ -f /opt/intelli/intelli-rfid-tunnel/intelli-rfid-tunnel.jar ]; then ok "jar already installed (redeploy.sh owns it from now on)"
else sudo install -m 644 "$KIT/opt/intelli/intelli-rfid-tunnel/intelli-rfid-tunnel.jar" /opt/intelli/intelli-rfid-tunnel/
     ok "prebuilt tunnel jar ($(cat "$KIT/opt/intelli/intelli-rfid-tunnel/JAR-COMMIT" 2>/dev/null || echo 'see kit')) -> /opt/intelli"; fi
sudo install -m 755 "$KIT/opt/intelli/lib/libModuleAPIJni.so" /opt/intelli/lib/
ok "libModuleAPIJni.so (v260827, aarch64) -> /opt/intelli/lib"

sudo install -d -m 755 /etc/intelli/intelli-rfid-tunnel
if sudo test -f "$SITE_CFG"; then ok "site config already present (left untouched)"
else
    TMP=$(mktemp)
    # Start on RG_EU3: every SIM7500 firmware accepts it. Pass 2 moves to RG_IN only if this
    # module proves it can run it (fw 20260819 AND auth region INDIA).
    sed -e "s/^\(    reader-id:\).*/\1 $READER_ID/" \
        -e "s/^\(    region:\) RG_IN$/\1 RG_EU3/" "$KIT/system/site/application.yml" > "$TMP"
    sudo install -o root -g "$USER_NAME" -m 640 "$TMP" "$SITE_CFG"; rm -f "$TMP"
    ok "site config -> $SITE_CFG (reader-id $READER_ID, region RG_EU3 for now, same API key hashes)"
fi

TMP=$(mktemp); cp "$KIT/system/intelli-rfid-tunnel.service" "$TMP"
if [ "$ANT" = 1 ]; then
    sed -i -e 's|^ExecStartPre=+/usr/bin/pinctrl set 8 op dl$|ExecStartPre=+/usr/bin/pinctrl set 8 op dh|' \
           -e 's|^ExecStartPre=+/usr/bin/pinctrl set 9 op dh$|ExecStartPre=+/usr/bin/pinctrl set 9 op dl|' "$TMP"
fi
if ! cmp -s "$TMP" "$UNIT"; then
    sudo install -m 644 "$TMP" "$UNIT"; sudo systemctl daemon-reload; ok "unit installed, selecting ANT$ANT (not enabled until pass 2)"
else ok "unit up to date (ANT$ANT)"; fi
rm -f "$TMP"
sudo install -d -m 755 /usr/lib/systemd/system-shutdown
sudo install -m 755 "$KIT/system/intelli-lamp.shutdown" /usr/lib/systemd/system-shutdown/intelli-lamp.shutdown
ok "shutdown lamp hook (0755, runs after root is remounted read-only)"
sudo install -m 440 -o root -g root "$KIT/system/intelli-poweroff.sudoers" /etc/sudoers.d/intelli-poweroff
sudo visudo -c -q && ok "sudoers: $USER_NAME may run 'systemctl poweroff' (IN3 shutdown)" || die "visudo check failed"

# ------------------------------------------------------------------------------------------------
step "7. Secrets (optional tarball)"
if [ -n "$SECRETS_TGZ" ]; then
    SEC=$HOME_DIR/intelli-cm4-secrets; mkdir -p "$SEC"; chmod 700 "$SEC"
    tar -xzf "$SECRETS_TGZ" -C "$SEC"
    if [ ! -f "$HOME_DIR/.git-credentials" ] && [ -f "$SEC/git-credentials" ]; then
        install -m 600 "$SEC/git-credentials" "$HOME_DIR/.git-credentials"; ok "CodeCommit credentials -> ~/.git-credentials"
    fi
    ok "VPN config and plaintext site keys unpacked to $SEC (NOT installed - see the instructions)"
    todo "VPN: $SEC/vpn/client.conf is the OLD board's client certificate. Two boards on one certificate \
kick each other off the server. Get a certificate issued for $NEW_HOSTNAME, then: \
sudo install -m 600 client.conf /etc/openvpn/client/intelli.conf && sudo systemctl enable --now openvpn-client@intelli"
    todo "Delete $SEC once the credentials and VPN are sorted (it holds plaintext API keys)."
else
    warn "no intelli-cm4-secrets-*.tar.gz beside the script - git will prompt for CodeCommit credentials on first pull"
fi

# ------------------------------------------------------------------------------------------------
if [ "$NEED_REBOOT" = 1 ]; then
    step "Pass 1 done - REBOOT NOW, then run the same command again"
    echo "    sudo reboot"
    echo "    cd $HERE && bash $(basename "$0")"
    echo "  Log: $LOG"
    exit 0
fi

# ================================================================================================
step "8. UART check (pass 2)"
if pinctrl get 14 | grep -q 'TXD0' && [ -e /dev/ttyAMA0 ]; then ok "GPIO14/15 on the PL011, /dev/ttyAMA0 present"
else pinctrl get 14,15; die "the PL011 is not on GPIO14/15 - disable-bt did not apply. Check $CFG for trailing comments."; fi
id -nG | tr ' ' '\n' | grep -qx dialout || die "this login is not yet in 'dialout' - log out and back in (or reboot)"
if pgrep -x java >/dev/null; then
    if systemctl is-active -q intelli-rfid-tunnel; then
        warn "the tunnel is already running - stopping it for the probes (it powers the module off; the probes raise it again)"
        sudo systemctl stop intelli-rfid-tunnel; sleep 3
    fi
    pgrep -x java >/dev/null && die "a JVM still holds the port: $(pgrep -ax java)"
fi

step "9. Module firmware and auth region (read-only)"
FWP=$KIT/firmware-sim7500-20260819
# Antenna select first, then EN, then release reset - never RF into an unterminated port.
if [ "$ANT" = 2 ]; then pinctrl set 8 op dl; pinctrl set 9 op dh; else pinctrl set 8 op dh; pinctrl set 9 op dl; fi
pinctrl set 22 op dh; pinctrl set 10 op dh; sleep 1
FWOUT=$(python3 "$FWP/probe/fw_probe.py" /dev/ttyAMA0:115200 --to-app 2>&1) || true
echo "$FWOUT" > "$HOME_DIR/probe-fw-$(hostname)-$(date +%Y%m%d-%H%M).txt"
echo "$FWOUT" | grep -E '^(fw date|hw version|auth region|serial number|Impinj|module name|  )' || true
FW_DATE=$(echo "$FWOUT" | awk -F': *' '/^fw date/{print $2}' | awk '{print $1}')
AUTH=$(echo "$FWOUT" | awk -F': *' '/^auth region/{print $2}')
SERIAL=$(echo "$FWOUT" | awk -F': *' '/^serial number/{print $2}')
[ -n "$FW_DATE" ] || die "the module did not answer fw_probe. Check pins: $(pinctrl get 8,9,10,22 | tr '\n' ' ')"
NEED_FLASH=0; NEED_AUTH=0
[ "$FW_DATE" = 20260819 ] && ok "firmware 20260819 (the build the old unit runs)" || { NEED_FLASH=1; warn "firmware $FW_DATE - NOT the 20260819 build"; }
echo "$AUTH" | grep -q INDIA && ok "auth region INDIA" || { NEED_AUTH=1; warn "auth region is '$AUTH', not INDIA"; }

step "10. Tags on both antenna ports (ProbeBasic, region set volatile to RG_EU3)"
declare -A READS
for a in 1 2; do
    OUT=$(ANT=$a "$HOME_DIR/api/run/run.sh" ProbeBasic 2>&1) || true
    echo "$OUT" > "$HOME_DIR/probe-basic-ant$a-$(date +%Y%m%d-%H%M).txt"
    READS[$a]=$(echo "$OUT" | awk '/after set:/{print $3}')
    echo "  ANT$a ($( [ $a = 1 ] && echo J20 || echo J25 )): ${READS[$a]:-no answer} reads   $(echo "$OUT" | grep -m1 'InitReader' )"
done
[ "${READS[$ANT]:-0}" -gt 0 ] 2>/dev/null && ok "ANT$ANT hears tags" || \
    todo "ANT$ANT heard NO tags in ProbeBasic. Put tags in front of it, or re-run with --ant $([ $ANT = 1 ] && echo 2 || echo 1). \
Then check both ports with the VSWR sweep (below)."
# Put the port back to what the unit will select.
if [ "$ANT" = 2 ]; then pinctrl set 8 op dl; pinctrl set 9 op dh; else pinctrl set 8 op dh; pinctrl set 9 op dl; fi

step "11. Region in the site config"
CUR=$(sudo awk '/^    region:/{print $2}' "$SITE_CFG")
if [ $NEED_FLASH = 0 ] && [ $NEED_AUTH = 0 ]; then WANT=RG_IN; else WANT=RG_EU3; fi
if [ "$CUR" != "$WANT" ]; then
    sudo cp -a "$SITE_CFG" "$SITE_CFG.bak-$(date +%Y%m%d-%H%M%S)"
    sudo sed -i "s/^\(    region:\) .*/\1 $WANT/" "$SITE_CFG"
fi
ok "region: $WANT"
[ "$WANT" = RG_EU3 ] && todo "The unit runs RG_EU3, whose 4th channel (867.5 MHz) is OUTSIDE India's 865-867 MHz band. \
Bring the module to 20260819 + auth INDIA (below), re-run this script, and it switches to RG_IN."

step "12. Enable and start the tunnel"
sudo systemctl enable intelli-rfid-tunnel >/dev/null 2>&1
sudo systemctl restart intelli-rfid-tunnel
echo "  waiting for /actuator/health ..."
H=""
for i in $(seq 1 45); do
    H=$(curl -s --max-time 2 localhost:8081/actuator/health || true)
    # The TOP-LEVEL status, not any "UP": diskSpace and ping are UP long before the reader connects,
    # so matching '"UP"' anywhere reported a tunnel still OUT_OF_SERVICE as up (2026-09-23).
    HS=$(echo "$H" | grep -o '^{"status":"[A-Z_]*"' | cut -d'"' -f4)
    [ "$HS" = UP ] && break; sleep 2
done
echo "  $H" | cut -c1-400
[ "$HS" = UP ] && ok "tunnel is UP" || todo "The tunnel is not UP yet: journalctl -u intelli-rfid-tunnel -n 100 --no-pager"
ls -l /opt/intelli/logs/ | tail -n +2 | head -3

# ================================================================================================
step "WHAT IS LEFT FOR YOU TO DO"
n=1
say() { echo; echo "${c_b}$n.${c_0} $*"; n=$((n+1)); }

if [ $NEED_AUTH = 1 ] || [ $NEED_FLASH = 1 ]; then
say "Bring the SIM7500 (serial ${SERIAL:-?}) to the old unit's module state. IRREVERSIBLE module writes -
   read $FWP/CM4-Firmware-Update-Handoff.md first. The order used on the old unit: auth region (09-07), then firmware (09-11).
     sudo systemctl stop intelli-rfid-tunnel; pgrep -x java; fuser -v /dev/ttyAMA0   # both must print nothing
     # the stop powered the module off - raise it again, ANT$ANT first:
     pinctrl set 8 op $([ $ANT = 2 ] && echo dl || echo dh); pinctrl set 9 op $([ $ANT = 2 ] && echo dh || echo dl); pinctrl set 22 op dh; pinctrl set 10 op dh"
fi
if [ $NEED_AUTH = 1 ]; then
say "Auth region -> RG_IN (it reads '$AUTH' now; record that, it is the only way back):
     ANT=$ANT ~/api/run/run.sh ProbeAuthRead | tee ~/authread-before.txt
     ANT=$ANT ~/api/run/run.sh ProbeAuthWrite
     pinctrl set 22 op dl; sleep 2; pinctrl set 22 op dh; sleep 0.3                  # re-power the module
     ANT=$ANT ~/api/run/run.sh ProbeAuthRead        # expect RG_IN; hw string 3rd octet becomes 0E"
fi
if [ $NEED_FLASH = 1 ]; then
say "Flash firmware $FW_DATE -> 20260819 (the kit the old unit was flashed from), inside a DETACHED tmux
   so a dropped ssh session cannot cut the write (tmux new -s flash; Ctrl-b d to detach, tmux a -t flash to return):
     tmux new -s flash
     cd $FWP && sha256sum -c SHA256SUMS
     python3 probe/fw_probe.py /dev/ttyAMA0:115200 | tee probe-before.txt          # leave it in BOOT
     python3 tools/pinned_run.py probe/read_app_flash.py   # BACKUP this module's app; address: /dev/ttyAMA0:115200 (never blank)
     printf '/dev/ttyAMA0:115200\\n\\n' | python3 tools/pinned_run.py mcu/upgrade_mcu.py | tee flash.txt
     #   30-80 s (31.9 s on intellisbc2, 79 s on intellisbc), checksum verified. Address and EXACTLY one
     #   newline: the newline answers the upgrade confirmation. If a 'wrong family' warning appears
     #   instead, it eats the newline and the script exits at EOF WITHOUT writing - start from BOOT and re-run.
     # Impinj E710 only if fw_probe did NOT say 'SKIP impinj/upgrade_impinj.py':
     #   cd impinj && PYTHONPATH=../lib python3 upgrade_impinj.py
     pinctrl set 22 op dl; sleep 2; pinctrl set 22 op dh; sleep 0.3
     python3 probe/fw_probe.py /dev/ttyAMA0:115200 --to-app | tee probe-after.txt  # expect 20260819, auth still INDIA
   Rollback image, if ever needed: rollback/*.bin1 (the 03-30 build). Powering up in the BOOTLOADER is
   normal - do NOT run tools/set_autoboot_app.py."
say "Then re-run this script: it sees 20260819 + INDIA, switches the site config to RG_IN and restarts the tunnel."
fi

say "Antenna check, per port - the old board's J20 branch was 24 dB down, this board's may not be.
   With an antenna on BOTH connectors (never judge a port with the antenna on the other one):
     ANT=1 ~/api/run/run.sh ProbeBasic ; ANT=2 ~/api/run/run.sh ProbeBasic
   and the VSWR sweep on the running app, per port: GET /api/diagnostics/antennas (old unit: J25 1.377 good, J20 3.0095 bad).
   If J20 is healthy here, re-run with --ant 1 (the unit's default is ANT2 only because of the old board's fault)."

say "Antenna LEDs: D18 (GPIO17, J20) and D19 (GPIO27, J25). Lit = the selected port swept <= 2.0 VSWR at
   reader connect; blinks at 4 Hz while tags arrive; the other port's LED is always dark. Check this carrier
   has D18/D19 fitted before trusting a dark LED."

say "Review the carried-over site config ($SITE_CFG) for THIS line - it is the old unit's, as it stood:
   the reverse nudge (tunnel.field.conveyor.reverse), the bench test surface, session: 1, and
   rzc-always-run: false (with no working IN2 exit sensor that stops the RZC after every carton)."

say "API keys: this board carries the SAME key hashes as the old one, so the WMS, admin and wms-test
   keys work on both. If the two readers must be distinguishable, issue new keys and put their sha256 in
   $SITE_CFG (see CM4-PRODUCTION-BRINGUP.md 'The API keys')."

say "Laptop apps (intelli-rfid-admin, intelli-wms-test) address the reader as intellisbc.local. Point them at
   $NEW_HOSTNAME.local for this board."

say "Field wiring on J26 and the Tunnel Manager is copper, not software: follow docs/Tunnel-Interconnect.md.
   With nothing wired to J26 the inputs float (disable-input-pulls: true) and IN1 can fire phantom cartons;
   on a bare bench set tunnel.field.disable-input-pulls: false in $SITE_CFG."

say "Claude Code for this board: curl -fsSL https://claude.ai/install.sh | bash, then 'claude' in $WS.
   CLAUDE.md and the project memory came across; 'claude /login' needs you."

say "Optional: persistent journald (it is volatile on the old unit too):
     sudo systemd-tmpfiles --create --prefix /var/log/journal && sudo systemctl restart systemd-journald"

for t in "${TODO[@]}"; do say "$t"; done

echo
echo "Not carried over, on purpose: the spool and carton sequence counter (this board starts at 1),"
echo "logs, shell history, and the legacy intelli-heartbeat-off.service (it drove the old PLC heartbeat;"
echo "BCM 12 is the green lamp now)."
echo
echo "Deploy from here on, as on the old unit:  cd $WS/apps/intelli-rfid-tunnel && deploy/redeploy.sh"
echo "Log of this run: $LOG"
