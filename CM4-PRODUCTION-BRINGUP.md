# Production bring-up — CM4 on the IntelliRFID v2.x board

Freshly flashed CM4 → the `intelli-rfid-tunnel` app running against the on-board SIM7500.
Written on the bench rig (a Raspberry Pi 4B + SIM7500 "Develop Component A" dev board) on
2026-08-29, from what is actually installed there.

**Run the steps in order.** Every step has a verification line; if it does not print what it says
it should, stop there rather than continuing — each later step assumes the earlier ones held.

---

## ⚠️ READ THIS BEFORE YOU START — five things that are different on this board

The software has only ever run against the vendor dev board. Five things about the v2.x carrier are
**not handled by the code today**, and each one on its own is enough to make a correctly installed
unit read nothing. They are from `docs/Hardware-IntelliRFIDv2.md` (netlist rev `0861de5`), which is
the authoritative GPIO map — **none of them has been verified on hardware by this project yet.**

| # | What | Why it matters | Where it is handled |
|---|---|---|---|
| 1 | **`RFID_EN` = GPIO22, 10 k pull-down.** The reader is **OFF at boot**. | `InitReader` against a disabled module fails, or connects and reads nothing. Looks exactly like a dead module. | Step 7 — by hand / in the systemd unit. **No code does this.** |
| 2 | **The SIM7500 has ONE antenna port.** The two tunnel antennas hang off the board's PE42442A SP4T, switched by **GPIO8 (V1) / GPIO9 (V2)** — the module does not know the switch exists. | The packaged `antenna-count: 2` is wrong for this board and will fail antenna negotiation. Only ANT1 is reachable until someone writes the switching. | Step 6 config (`antenna-count: 1`) + open item A |
| 3 | **GPIO23/24 are field inputs IN1/IN2 and are ACTIVE-LOW** (24 V present ⇒ GPIO reads LOW). | The tunnel triggers Super Fast Mode on a **rising** edge, hardcoded. On this board a carton arriving is a **falling** edge, so it triggers on the carton *leaving*. | Step 6 — GPIO left **disabled** until this is decided. Open item B |
| 4 | **Power: 27 dBm ceiling, not 30.** The thermal path does not close at 30 dBm continuous at +55 °C. | Packaged `read-power-dbm10: 3000` overheats an enclosed unit. | Step 6 config (`2700`) |
| 5 | **Never enable the reader with no antenna on the selected port**, and select the port *before* enabling. | Board handoff §9.1. Reflected power into an unterminated port. | Step 7 order is deliberate |

Two more that are questions rather than settings:

- **Region.** The tunnel wants `RG_IN`. The **bench module refuses `RG_IN`** and runs `RG_EU3`.
  Whether the production module accepts it is unknown, and on this board the region is set once
  through `Ex/initregion` and then fixed. Step 8 finds out in thirty seconds.
- **`gs1.reader-id` must be unique across every reader that ever writes a tag.** The bench uses `0`.
  Give this unit its own number in Step 6 — a duplicate is invisible until two tags collide.

**What to report back after Step 9** is listed at the bottom, ready to paste.

---

## 0. What you need to hand

- The CM4 flashed, on the network, with SSH in.
- **The vendor SDK directory** `API-linux-java-v260721/` — it is **not in git** (`.gitignore`
  excludes it) and nothing builds without it. Copy it off the bench rig or the original vendor drop.
- **CodeCommit HTTPS Git credentials** (IAM → your user → Security credentials → HTTPS Git
  credentials for CodeCommit), region `ap-south-1`.
- An antenna **fitted to ANT1 (J20)**, or a 50 Ω load on it. Do not skip this.

Assumed throughout: user `intelli-sbc`, workspace at `~/rfid/intelli-rfid-reader`. Adjust if not.

---

## 1. OS packages

```bash
sudo apt update
sudo apt install -y openjdk-17-jdk maven git gpiod python3-libgpiod python3-serial ethtool
sudo usermod -aG dialout,gpio "$USER"     # takes effect at next login
```

Verify:

```bash
java -version        # expect openjdk 17.x
mvn -v | head -1     # expect Apache Maven 3.8+
gpiomon --version    # NOTE the version — see below
cat /etc/os-release | head -2
```

**If `gpiomon` reports v2.x** (Debian 13 / Trixie), the CLI changed incompatibly: v2 wants
`gpiomon --edges=rising -c gpiochip0 23 24` where v1 wants `gpiomon --rising-edge gpiochip0 23 24`,
and `gpioinfo` needs `-c`. The tunnel builds the **v1** command line
(`GpioEdgeMonitor.commandLine()`), so on a v2 host the sensor monitor will fail to start and report
itself degraded rather than crash. The bench is v1.6.3 on Bookworm. Note which you have.

**If `openjdk-17-jdk` is not available** the image is newer than Bookworm; do not silently take 21 —
the build targets 17 and the vendor JNI has only ever run on 17 here. Say so in the report-back.

---

## 2. UART: give the reader GPIO14/15 and take the console off it

The reader is UART0 (PL011) on GPIO14/15 at 115200 8N1. The Bluetooth modem owns PL011 by default
and the Linux serial console fights whatever is left.

```bash
# /boot/firmware may be mounted read-only on a hardened image; harmless if it is already rw
sudo mount -o remount,rw /boot/firmware 2>/dev/null || true

sudo tee -a /boot/firmware/config.txt >/dev/null <<'EOF'

# --- IntelliRFID -----------------------------------------------------------
enable_uart=1
dtoverlay=disable-bt          # frees PL011 for GPIO14/15 (the SIM7500)
dtoverlay=uart3               # SAMD21 supervisor on GPIO4/5 (not used by this app)
EOF

sudo raspi-config nonint do_serial_hw 0     # UART hardware on
sudo raspi-config nonint do_serial_cons 1   # login console OFF
sudo systemctl disable hciuart
sync
sudo reboot
```

After the reboot, verify — **all four lines matter**:

```bash
grep -c "console=serial0" /boot/firmware/cmdline.txt   # expect 0
ls -l /dev/serial0                                     # expect -> ttyAMA0
raspi-gpio get 14,15                                   # expect alt=0 func=TXD0 / RXD0
dmesg | grep -i ttyAMA                                 # note which ttyAMA is fe201000 (UART0)
```

**Confirm which `ttyAMA` is the reader.** With `uart3` added you get two of them and the numbering
varies by OS release: UART0 is the one at MMIO `fe201000`. Everything below assumes
`/dev/ttyAMA0`; if `dmesg` says otherwise, use the right one and say so in the report-back.

With the board powered and the module fitted, GPIO14 and GPIO15 should both idle **high**. Both low
means the module has no power or the pins are not muxed.

---

## 3. Runtime directories

```bash
sudo mkdir -p /opt/intelli/lib /etc/intelli/intelli-rfid-tunnel /var/lib/intelli/tunnel/spool
sudo chown -R "$USER":"$USER" /var/lib/intelli
```

`/var/lib/intelli/tunnel` holds the **durable sequence counter**, the callback spool and the
inventory spool. It must survive a restart and it must be writable by the app's user — a sequence
that resets is a WMS reconciliation failure.

---

## 4. Vendor SDK — the jar and the native library

Neither is in git. Copy the SDK directory across first (from the bench rig, or the vendor drop):

```bash
mkdir -p ~/rfid
# example, from the bench rig:
scp -r intelli-sbc@<bench-host>:~/rfid/intelli-rfid-reader/API-linux-java-v260721 ~/rfid/
```

It must end up **at the workspace root**, i.e. `~/rfid/intelli-rfid-reader/API-linux-java-v260721`,
because `install-vendor-jar.sh` locates it three levels up from itself. Move it there after Step 5
clones the workspace, or clone first and scp straight into place.

The native library, **aarch64** — the 32-bit and x86 builds sit beside it and will not load:

```bash
sudo install -D -m 0644 \
  ~/rfid/intelli-rfid-reader/API-linux-java-v260721/libs/aarch64/libModuleAPIJni.so \
  /opt/intelli/lib/libModuleAPIJni.so
ls -l /opt/intelli/lib/    # expect libModuleAPIJni.so, ~611 KB
```

---

## 5. Clone the code — four repositories, not one

This is **not** a monorepo. The workspace repo holds the docs and ignores `apps/` entirely; each app
is its own CodeCommit repository. Region `ap-south-1`.

```bash
git config --global credential.helper store
git config --global user.name  "Piyush Nigam"
git config --global user.email "this.is.piyush@gmail.com"

CC=https://git-codecommit.ap-south-1.amazonaws.com/v1/repos
mkdir -p ~/rfid && cd ~/rfid
git clone $CC/intelli-rfid-reader intelli-rfid-reader        # workspace: docs, this file
mkdir -p intelli-rfid-reader/apps && cd intelli-rfid-reader/apps
git clone $CC/intelli-rfid-core
git clone $CC/intelli-rfid-reader-test
git clone $CC/intelli-rfid-tunnel
```

The first clone prompts for the CodeCommit HTTPS username and password; `credential.helper store`
writes them to `~/.git-credentials` in the clear, which is the same trade the bench makes.

Verify — three repos on `main`, and the SDK where Step 4 wants it:

```bash
cd ~/rfid/intelli-rfid-reader
for d in . apps/*/; do echo "$d $(git -C $d rev-parse --short HEAD) $(git -C $d branch --show-current)"; done
ls -d API-linux-java-v260721/libs/aarch64
```

**Read `CLAUDE.md` and `RESUME-NEXT-SESSION.md` in the workspace root before changing anything.**
`docs/Hardware-IntelliRFIDv2.md` is the authoritative board document and the source of the warnings
above.

---

## 6. Build, and write the site configuration

Build order matters: the vendor jar is not on Maven Central and core is a local dependency.
The first build downloads Spring Boot from Maven Central — it needs the network and takes a while
on a CM4.

```bash
cd ~/rfid/intelli-rfid-reader/apps/intelli-rfid-core
./tools/install-vendor-jar.sh          # installs com.uhf:module-api-j:2.6.0721
mvn install
cd ../intelli-rfid-tunnel && mvn package
ls -l target/intelli-rfid-tunnel-1.0.0-SNAPSHOT.jar     # expect ~25 MB
```

### The API keys

Security is on and **the app refuses to start with no keys**. Only the SHA-256 is ever stored, so a
key that is lost is reissued, never recovered. Issue three — one per role:

```bash
cd ~/rfid/intelli-rfid-reader
for role in wms commission operator; do
  echo "--- $role"
  java -cp apps/intelli-rfid-core/target/classes com.intelli.rfid.spring.security.ApiKeyTool
done
```

Keep the printed keys somewhere safe **now**; the tool does not store them. Then:

```bash
sudo tee /etc/intelli/intelli-rfid-tunnel/application.yml >/dev/null <<'EOF'
# Site configuration for the production CM4 on the IntelliRFID v2.x board.
# NOT in git: it holds the API key hashes and everything that differs from the packaged defaults.

rfid:
  reader:
    # UART0 on GPIO14/15. Confirm against dmesg if uart3 renumbered the ports.
    address: /dev/ttyAMA0

    # ONE. The SIM7500 is mono-static; the two tunnel antennas are behind the board's SP4T on
    # GPIO8/9, which the module knows nothing about. The packaged default of 2 is wrong here.
    antenna-count: 1

    # 27 dBm, not the packaged 30. The board's thermal path does not close at 30 dBm continuous
    # at +55 C. Treat it as an ambient-dependent ceiling.
    read-power-dbm10: 2700
    write-power-dbm10: 2000

    # The tunnel's intent. The BENCH module refuses RG_IN and runs RG_EU3; whether this module
    # accepts it is the first thing Step 8 answers. On this board the region is set once through
    # Ex/initregion and is then fixed - get it right before commissioning.
    region: RG_IN

  gs1:
    # MUST be unique across every reader that ever writes a tag. The bench uses 0.
    reader-id: 1

  security:
    enabled: true
    keys:
      - id: site-wms
        label: WMS integration
        sha256: "<paste the wms hash>"
        scopes: [INVENTORY]
      - id: site-commission
        label: Tag commissioning
        sha256: "<paste the commission hash>"
        scopes: [COMMISSION]
      - id: site-operator
        label: Operator - actuator and reader lifecycle
        sha256: "<paste the operator hash>"
        scopes: [ADMIN]

tunnel:
  v1:
    gpio:
      # OFF until the edge polarity is settled. On this board IN1/IN2 (GPIO23/24) are ACTIVE-LOW
      # and the monitor is hardcoded to rising edges, so leaving it on would trigger the read on
      # the carton LEAVING. With it off, Super Fast Mode falls back to opening a session on the
      # first tag and closing it on settle, and says so as `degraded` in /api/v1/reader/status.
      enabled: false
EOF
sudo chmod 640 /etc/intelli/intelli-rfid-tunnel/application.yml
```

Paste the three hashes in. Everything else comes from the packaged `application.yml` inside the jar,
which is where the settings that are the same at every site belong.

---

## 7. Enable the reader — port first, then power

**The order is a safety requirement**, not a preference: the antenna switch boots to ANT1 and the
module boots disabled, so selecting the port before enabling is what guarantees RF never comes up
into an unterminated port.

```bash
# 1. Select ANT1 (J20): V1=1, V2=0. This is also the boot state, so it is a confirmation.
pinctrl set 8 op dh
pinctrl set 9 op dl

# 2. Only now, enable the module. GPIO22 HIGH = reader ON.
pinctrl set 22 op dh

# optional: a clean module reset - NRST low >2 ms, then wait >110 ms
# pinctrl set 10 op dl && sleep 0.05 && pinctrl set 10 op dh && sleep 0.2

pinctrl get 8,9,10,22
```

**Nothing in the application does this.** Until it does, GPIO22 has to be raised before the app
starts — by hand while you are bringing up, and by the systemd unit's `ExecStartPre` in Step 10.
An unpowered module on the UART is the exact failure that cost this project two days on the bench:
it echoes bytes back at every baud rate and looks like a wiring fault. See
`docs/Bench-Bringup-SIM7500-DevBoard.md` and the loopback-vs-device note in `CLAUDE.md`.

---

## 8. Prove the module before you start the app

One process owns `/dev/ttyAMA0`. Do this with the app stopped — and it is much easier to read a
probe's output than a Spring stack trace.

```bash
cd ~/rfid/intelli-rfid-reader/apps/intelli-rfid-reader-test/tools/bench-probe
./run.sh Probe                          # identity, region, power range, temperature
./run.sh Probe2 /dev/ttyAMA0 2700 1000  # region acceptance scan + inventory sweeps
```

What you are looking for:

- `InitReader_Notype` → `MT_OK_ERR`. Anything else and the module is not answering: check GPIO22 is
  high, check the UART mux, check 5 V.
- Hardware and software versions printed (the bench module is hw `31.00.00.80`, sw `20.26.03.30`).
- **Does it accept `RG_IN`?** `Probe2` scans the regions. This is the answer the whole project has
  been waiting for — record it either way.
- A tag in front of the antenna shows up in the sweeps.

If `Probe` throws `UnsatisfiedLinkError`, `-Djava.library.path=/opt/intelli/lib` is missing or the
`.so` is the wrong architecture. It is mandatory on **every** java command in this project.

---

## 9. Run the tunnel

```bash
cd ~/rfid/intelli-rfid-reader/apps/intelli-rfid-tunnel
java -Djava.library.path=/opt/intelli/lib \
     -jar target/intelli-rfid-tunnel-1.0.0-SNAPSHOT.jar \
     --spring.config.additional-location=file:/etc/intelli/intelli-rfid-tunnel/
```

Expect in the log: `Reader open: module=... fw=... antennas=[1]`, then `Inventory started`.

Smoke-test it from another shell (`jq` is not installed on the bench; `python3 -m json.tool` is the
substitute):

```bash
KEY=<the operator key>
curl -s -H "X-API-Key: $KEY" http://localhost:8081/actuator/health | python3 -m json.tool
curl -s -H "X-API-Key: $KEY" http://localhost:8081/api/v1/reader/status | python3 -m json.tool
```

`/api/v1/reader/status` should report `connected: true`, `state: READING`, a firmware string, and
`degraded` naming the disabled sensors — that last one is expected here, not a fault.

Then a real read, with the WMS key:

```bash
curl -s -X POST -H "X-API-Key: <the wms key>" -H 'Content-Type: application/json' \
  -d '{"ean":"8905527164445","durationMs":3000,"timed":true}' \
  http://localhost:8081/api/v1/inventory | python3 -m json.tool
```

---

## 10. Run it as a service (once Step 9 works by hand)

```bash
sudo tee /etc/systemd/system/intelli-rfid-tunnel.service >/dev/null <<'EOF'
[Unit]
Description=Intelli RFID tunnel
After=network-online.target
Wants=network-online.target

[Service]
Type=simple
User=intelli-sbc
WorkingDirectory=/home/intelli-sbc/rfid/intelli-rfid-reader/apps/intelli-rfid-tunnel

# The board boots with the reader disabled and the antenna switch on ANT1. Select the port
# first, then enable - never the other way round (board handoff section 9.1).
# The leading + runs these as root: pinctrl reads fine as a gpio-group user, but do not
# make RF enable depend on that holding.
ExecStartPre=+/usr/bin/pinctrl set 8 op dh
ExecStartPre=+/usr/bin/pinctrl set 9 op dl
ExecStartPre=+/usr/bin/pinctrl set 22 op dh

# -Djava.library.path is mandatory: the vendor JNI static initialiser only searches it.
ExecStart=/usr/bin/java -Djava.library.path=/opt/intelli/lib \
  -jar /home/intelli-sbc/rfid/intelli-rfid-reader/apps/intelli-rfid-tunnel/target/intelli-rfid-tunnel-1.0.0-SNAPSHOT.jar \
  --spring.config.additional-location=file:/etc/intelli/intelli-rfid-tunnel/

# Drop RF when the service stops, so a stopped service is a quiet radio.
ExecStopPost=+/usr/bin/pinctrl set 22 op dl

Restart=on-failure
RestartSec=10

[Install]
WantedBy=multi-user.target
EOF

sudo systemctl daemon-reload
sudo systemctl enable --now intelli-rfid-tunnel
systemctl status intelli-rfid-tunnel --no-pager
journalctl -u intelli-rfid-tunnel -f
```

Two caveats worth knowing before you enable this:

- **`Restart=on-failure` is the only fault recovery this unit has.** After a read exception the
  session goes `FAULTED` and stays there until the process restarts — the connector thread retries
  only the *initial* connect. Auto-reconnect is open item 6 in `RESUME-NEXT-SESSION.md`; until it
  lands, the service restart is the recovery path, and it costs a reader re-init.
- The jar path is versioned. It changes when the version does.

---

## Open items this bring-up will surface

**A. Antenna switching is not implemented.** ANT2 (J25) is unreachable from the application: nothing
drives GPIO8/9, and the module reports the same antenna ID for every read because it cannot see the
switch. Two decisions are needed — whether the tunnel runs one antenna or alternates, and, if it
alternates, the dwell. Switching is not free here: the module is unaware, so the pattern is *stop
inventory → switch → restart*, and the stop/start cost is what sets the minimum sensible dwell.
**Measure that number on this board before choosing a dwell** (`docs/Hardware-IntelliRFIDv2.md` §7.3).

**B. Sensor edge polarity.** IN1/IN2 are active-LOW on this board and `GpioEdgeMonitor` is hardcoded
to `--rising-edge`. It needs a configurable edge (and `--bias=disable`, because the BCM2711's
internal pull-down opposes the board's 10 k pull-up and leaves only ~0.44 V of margin). Small change,
but it changes behaviour on the bench too, so it wants deciding rather than assuming.

**C. Region.** Step 8 answers it. If this module also refuses `RG_IN`, that is a module/firmware
question for the vendor and not something configuration can fix — and the region is fixed once on
this board.

**D. Power.** `2700` is the ceiling, not a tuned value. The read power that actually finds every tag
in a real carton is a measurement, and it interacts with the antenna decision in A.

**E. `reader-id`.** Set per unit. It is invisible until it is wrong.

---

## Report back

Paste this into the laptop session (or back to the bench session) once Step 9 works:

```
Production CM4 bring-up, <date>:
- OS / gpiod: <os-release>, gpiomon v<x>
- Serial: reader on <ttyAMAn> (fe201000?), GPIO14/15 alt0, idle high: yes/no
- Module: InitReader <ok/err>, hw <..>, sw <..>, temp <..> C
- Region: RG_IN accepted? <yes/no>  (bench module refuses it)
- Antenna: ANT1 fitted, VSWR <..>; antenna-count=1
- Tunnel: started <yes/no>, /api/v1/reader/status connected=<..> state=<..>
- First read: <n> tags at <power> dBm
- Deviations from this runbook: <...>
```

---

*Written on the bench rig, 2026-08-29. Everything in Steps 1–6 is what is installed and working on
the bench today. Steps 7, 10 and the open items are derived from `docs/Hardware-IntelliRFIDv2.md`
and have never been run against the v2.x board — treat them as the best available reading of the
board document, not as measured fact, and correct this file as you go.*
