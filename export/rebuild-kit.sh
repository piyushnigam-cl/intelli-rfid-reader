#!/usr/bin/env bash
# rebuild-kit.sh - refresh the CM4 clone kit from THIS board (intellisbc, the production unit).
#
#   cd ~/rfid/intelli-rfid-reader/export && bash rebuild-kit.sh
#
# Starts from the newest existing intelli-cm4-kit-*.tar.gz, so what cannot be regenerated here
# unprivileged (the SIM7500 firmware kit, the sudoers file, the system snapshot) carries over
# byte-for-byte, and replaces everything that goes stale as this unit moves on:
#
#   workspace/intelli-rfid-reader   the root repo and EVERY apps/*/ repo, with .git, no target/
#   home/api                        vendor SDK + compiled probes
#   m2                              ~/.m2 (offline builds)
#   claude/memory                   Claude Code project memory
#   opt/intelli/...                 the jar and .so actually deployed in /opt/intelli
#   system/site/application.yml     the live site config (API key HASHES only, no plaintext keys)
#   system/intelli-rfid-tunnel.service, system/intelli-lamp.shutdown   as installed
#
# Run as intelli-sbc. No sudo needed: the site config is root:intelli-sbc 0640.
# Secrets are never bundled - build intelli-cm4-secrets-*.tar.gz by hand as before.
set -euo pipefail

HERE="$(cd "$(dirname "$0")" && pwd)"
WS="$(cd "$HERE/.." && pwd)"
DATE=$(date +%F)
OLD="$(ls -1 "$HERE"/intelli-cm4-kit-*.tar.gz | tail -1)"
NEW="$HERE/intelli-cm4-kit-$DATE.tar.gz"
WORK="$(mktemp -d)"; trap 'rm -rf "$WORK"' EXIT
K="$WORK/intelli-cm4-kit"

[ "$(id -un)" = intelli-sbc ] || { echo "run as intelli-sbc"; exit 1; }
echo "base: $(basename "$OLD")"
tar -xzf "$OLD" -C "$WORK"
[ -d "$K" ] || { echo "unexpected layout: no intelli-cm4-kit/ in $OLD"; exit 1; }

echo "== workspace (every apps/*/ must be a repo)"
for d in "$WS"/apps/*/; do
    [ -d "$d/.git" ] || { echo "  $d has NO .git - git init it before exporting"; exit 1; }
    git -C "$d" status --porcelain | grep -q . && echo "  WARN $(basename "$d"): uncommitted changes (exported as they are)"
    echo "  $(basename "$d") $(git -C "$d" log -1 --format='%h %cs %s' | cut -c1-70)"
done
rm -rf "$K/workspace"; mkdir -p "$K/workspace"
rsync -a --exclude 'target/' --exclude 'export/*.tar.gz' "$WS" "$K/workspace/"

echo "== ~/api, ~/.m2, Claude memory"
rm -rf "$K/home/api"; mkdir -p "$K/home"; rsync -a "$HOME/api" "$K/home/"
rsync -a --delete "$HOME/.m2/" "$K/m2/"
rm -rf "$K/claude/memory"; mkdir -p "$K/claude"
cp -a "$HOME/.claude/projects/-home-intelli-sbc-rfid-intelli-rfid-reader/memory" "$K/claude/memory"

echo "== deployed runtime"
JAR=/opt/intelli/intelli-rfid-tunnel/intelli-rfid-tunnel.jar
install -D -m 644 "$JAR" "$K/opt/intelli/intelli-rfid-tunnel/intelli-rfid-tunnel.jar"
install -D -m 755 /opt/intelli/lib/libModuleAPIJni.so "$K/opt/intelli/lib/libModuleAPIJni.so"
JAR_TIME=$(stat -c %y "$JAR" | cut -d. -f1)
JAR_COMMIT=$(git -C "$WS/apps/intelli-rfid-tunnel" log -1 --before="$JAR_TIME" --format=%h)
echo "tunnel $JAR_COMMIT (jar installed $JAR_TIME)" > "$K/opt/intelli/intelli-rfid-tunnel/JAR-COMMIT"
echo "  jar: $(cat "$K/opt/intelli/intelli-rfid-tunnel/JAR-COMMIT")"

install -D -m 644 /etc/intelli/intelli-rfid-tunnel/application.yml "$K/system/site/application.yml"
install -D -m 644 /etc/systemd/system/intelli-rfid-tunnel.service "$K/system/intelli-rfid-tunnel.service"
install -D -m 755 /usr/lib/systemd/system-shutdown/intelli-lamp.shutdown "$K/system/intelli-lamp.shutdown"
grep -q 'pinctrl set 17 op dl' "$K/system/intelli-rfid-tunnel.service" \
    || echo "  WARN the installed unit has no antenna-LED ExecStopPost - is the 09-24 unit installed?"
if grep -qiE '^\s*(key|api-key|secret|password):\s*[A-Za-z0-9_-]{20,}' "$K/system/site/application.yml"; then
    echo "  WARN the site config may hold a plaintext secret - check before handing the kit over"
fi

echo "== pack"
tar -czf "$NEW" -C "$WORK" intelli-cm4-kit
( cd "$HERE" && sha256sum "$(basename "$NEW")" > SHA256SUMS )
ls -lh "$NEW"; cat "$HERE/SHA256SUMS"
echo "Copy $(basename "$NEW"), SHA256SUMS and setup-new-cm4.sh to the new board (and the secrets tarball if any)."
[ "$NEW" != "$OLD" ] && echo "The old kit $(basename "$OLD") can be deleted once the new one is checked."
