# Production bring-up — CM4 on the IntelliRFID v2.x board

Freshly flashed CM4 → the `intelli-rfid-tunnel` app running against the on-board SIM7500.
Written on the bench rig (a Raspberry Pi 4B + SIM7500 "Develop Component A" dev board) on
2026-08-29, from what is actually installed there.

**Run the steps in order.** Every step has a verification line; if it does not print what it says
it should, stop there rather than continuing — each later step assumes the earlier ones held.

> **Partially run for real on 2026-08-29** against the production CM4, and corrected in place where
> it was wrong. **Steps 0, 1, 2, 4, 5, 6, 7 and 8 are now *measured* on that unit** rather than read
> off the bench: the module answers on `/dev/ttyAMA0` and reads 18 of 18 tags at 27 dBm on `RG_EU3`,
> under Java 21. Two classes of correction came out of it — **this unit is Debian 13 (Trixie), the
> bench is Bookworm**, so several commands were written for the wrong userland; and two hardware
> facts this file had wrong or soft (`RFID_NRST` must be driven, and the `bluetooth` DT node is
> disabled rather than removed). **Steps 3, 6, 9 and 10 completed later the same day** — the site
> config is installed, the tunnel serves reads on this board, and it now runs as
> `intelli-rfid-tunnel.service`. **This runbook has been run end to end on the v2.x carrier.**

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

- ~~**Region.**~~ **Answered 2026-08-29: this module refuses `RG_IN` as well, and it ships on
  `RG_NA`.** It accepts `RG_NA`, `RG_EU3`, `RG_PRC` and `RG_OPEN` — a wider SKU than the bench's
  EU3-only module, but not a wider one where it matters. Run it on `RG_EU3` **with the hop table
  narrowed to `{865700, 866300, 866900}`**, which this firmware does allow and which is what keeps
  the unit inside 865–867 MHz. Details under step 8; the code change is open item C.
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
sudo apt install -y openjdk-21-jdk maven git gpiod python3-libgpiod python3-serial ethtool
sudo usermod -aG dialout,gpio "$USER"     # takes effect at next login
```

Verify:

```bash
java -version        # expect openjdk 21.x  (was 17 on the bench - see below)
mvn -v | head -1     # expect Apache Maven 3.8+
gpiomon --version    # NOTE the version — see below
cat /etc/os-release | head -2
```

**If `gpiomon` reports v2.x** (Debian 13 / Trixie), the CLI changed incompatibly: v2 wants
`gpiomon --edges=rising -c gpiochip0 23 24` where v1 wants `gpiomon --rising-edge gpiochip0 23 24`,
and `gpioinfo` needs `-c`. The tunnel builds the **v1** command line
(`GpioEdgeMonitor.commandLine()`), so on a v2 host the sensor monitor will fail to start and report
itself degraded rather than crash. The bench is v1.6.3 on Bookworm. Note which you have.
**Answered on the production CM4 2026-08-29: it is v2.2.1**, so the sensor monitor will not start
there and the tunnel will report `degraded`. Not blocking — step 6 disables GPIO anyway, for the
separate active-LOW reason (open item B) — but the two now need fixing together.

**On Java 17 vs 21 — settled 2026-08-29, and this paragraph used to say the opposite.** Debian 13
(Trixie) has no `openjdk-17-jdk` in the archive, only 21. Rather than pin a JDK the distribution has
dropped, **this project now targets 21**: Spring Boot 3.4.1 supports it, and a field unit is better
off on the platform's maintained default than on a hand-installed tarball nobody will patch.

The bench rig stays on 17/Bookworm, so **the two machines differ here** — say which JDK you are on in
any report-back. The open question is not the build, which merely recompiles; it is **the vendor JNI
under 21**, a native `.so` with nothing to recompile. Step 8's probe is the first thing that actually
loads it on 21, so run Step 8 before concluding anything about this module.

---

## 2. UART: give the reader GPIO14/15 and take the console off it

The reader is UART0 (PL011) on GPIO14/15 at 115200 8N1. The Bluetooth modem owns PL011 by default
and the Linux serial console fights whatever is left.

```bash
# /boot/firmware may be mounted read-only on a hardened image; harmless if it is already rw
sudo mount -o remount,rw /boot/firmware 2>/dev/null || true

sudo tee -a /boot/firmware/config.txt >/dev/null <<'EOF'

# --- IntelliRFID -----------------------------------------------------------
# config.txt has NO trailing comments. A comment on the same line as a setting is
# parsed as part of the value and the setting is SILENTLY ignored - no error, no
# log. Keep every comment on its own line. This cost a reboot on 2026-08-29: both
# dtoverlay lines below carried trailing comments and neither was applied, while
# enable_uart=1 on the line above them was.
enable_uart=1
# frees PL011 for GPIO14/15 (the SIM7500)
dtoverlay=disable-bt
# SAMD21 supervisor on GPIO4/5 (not used by this app)
dtoverlay=uart3
EOF

sudo raspi-config nonint do_serial_hw 0     # UART hardware on
sudo raspi-config nonint do_serial_cons 1   # login console OFF
sudo systemctl disable hciuart    # no-op on Trixie: the unit does not exist there (harmless error)
sync
sudo reboot
```

After the reboot, verify — **all four lines matter**:

```bash
grep -c "console=serial0" /boot/firmware/cmdline.txt   # expect 0
ls -l /dev/serial0                                     # expect -> ttyAMA0
pinctrl get 14,15                                      # expect a0, TXD0 / RXD0
# NOTE: this line used to say `raspi-gpio`, which is NOT installed on Trixie. pinctrl is.
dmesg | grep -i ttyAMA                                 # note which ttyAMA is fe201000 (UART0)

# Did disable-bt actually apply? This is the decisive check, and the only one that
# distinguishes "overlay ignored" from "overlay applied but numbered differently":
tr -d '\0' < /proc/device-tree/aliases/serial0                    # expect /soc/serial@7e201000
tr -d '\0' < /proc/device-tree/soc/serial@7e201000/bluetooth/status  # expect: disabled
```

**The `bluetooth` child node does not disappear** - an earlier draft of this step said to expect
`No such file or directory` and that is wrong. `disable-bt` sets the node's `status` to `disabled`
and leaves it in the tree, so the presence of the directory says nothing either way. Read its
`status` property. Corrected 2026-08-29 on this unit.

If `serial0` still reads `/soc/serial@7e215040`, or the bluetooth `status` still reads `okay`, the
overlay was **not applied** - do not go looking for a numbering problem. Check config.txt for a
trailing comment on the `dtoverlay` line first.

**Verified on this unit 2026-08-29** (second reboot, after the trailing comments were removed):
`serial0 -> ttyAMA0`, `serial0` alias = `/soc/serial@7e201000`, bluetooth `status = disabled`,
GPIO14/15 both `a0` TXD0/RXD0 and idling high, `console=serial0` absent from cmdline. `uart3` gives
`ttyAMA3` at `fe201600`. **The reader's port on this board is `/dev/ttyAMA0`**, the same as the
bench, so no config, unit file or probe invocation needs changing.

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

**`/opt/intelli/lib` is the only one of these three you can skip.** It exists to hold the vendor
`.so`, and the `.so` runs perfectly well straight out of the SDK tree — which needs no root at all.
The production CM4 does it that way (step 4). The other two are not optional:
`/var/lib/intelli/tunnel` must be writable or `JsonlSpool.initialise()` throws
`UncheckedIOException` out of the `InventoryService` constructor and kills the Spring context, and
`/etc/intelli/intelli-rfid-tunnel` is where the site config and the API key hashes live.

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

**Or skip the copy entirely and point at the SDK tree**, which is what the production CM4 does — it
needs no root, and there is then only one copy of the `.so` to keep straight:

```bash
export RFID_NATIVE_LIB=~/rfid/intelli-rfid-reader/API-linux-java-v260721/libs/aarch64
```

Either way **it must be the `aarch64` directory specifically** — `libs/32` and `libs/64` hold
same-named builds that will not load — and it must be handed to the JVM as
`-Djava.library.path`, never as `rfid.reader.native-lib-path` alone. Whichever you choose, the
systemd unit in step 10 has to agree with it.

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

    # Only if step 4's copy into /opt/intelli/lib was skipped, as it was on this unit.
    # NativeLibraryLoader THROWS when the configured directory holds no .so, and the packaged
    # default is /opt/intelli/lib - so a missing /opt stops the app at start-up rather than
    # falling back. This does NOT replace -Djava.library.path; both are needed.
    native-lib-path: /home/intelli-sbc/rfid/intelli-rfid-reader/API-linux-java-v260721/libs/aarch64

    # ONE. The SIM7500 is mono-static; the two tunnel antennas are behind the board's SP4T on
    # GPIO8/9, which the module knows nothing about. The packaged default of 2 is wrong here.
    antenna-count: 1

    # 27 dBm, not the packaged 30. The board's thermal path does not close at 30 dBm continuous
    # at +55 C. Treat it as an ambient-dependent ceiling.
    read-power-dbm10: 2700
    write-power-dbm10: 2000

    # RG_EU3, not RG_IN: measured 2026-08-29, THIS module refuses RG_IN as well (it accepts only
    # RG_NA, RG_EU3, RG_PRC, RG_OPEN) and it ships on RG_NA, which is 902-928 MHz and must not be
    # keyed up in India. RG_EU3 hops 865.7/866.3/866.9/867.5 and only the first three are inside
    # the Indian allocation - narrowing the hop table to those three is open item C, and until
    # that lands the unit legally wants a 3-channel table written after connect.
    region: RG_EU3

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
sudo chown root:"$USER" /etc/intelli/intelli-rfid-tunnel/application.yml
sudo chmod 640 /etc/intelli/intelli-rfid-tunnel/application.yml
```

**The `chown` is not optional, and this file used to omit it.** `sudo tee` leaves the config
`root:root`; `chmod 640` then means owner-read only, and the app runs as the service user, *not* as
root. It cannot read its own site configuration — so it silently falls back to the packaged
defaults, finds no API keys there, and refuses to start. The failure surfaces at step 9 as a reader
that will not come up, with nothing in the log pointing at a permissions problem. Group-owning the
file to the service user keeps the key hashes off every other account while letting the app read it.

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

# 3. RFID_NRST (GPIO10) HIGH. NOT OPTIONAL - see below.
pinctrl set 10 op dh
sleep 0.2

# optional, on top of that: a clean module reset - NRST low >2 ms, then wait >110 ms
# pinctrl set 10 op dl && sleep 0.05 && pinctrl set 10 op dh && sleep 0.2

pinctrl get 8,9,10,22
```

**GPIO10 must be driven high, and this was measured, not assumed (2026-08-29).** `RFID_NRST` is
LOW = reset, and the BCM2711 brings GPIO10 up as an **input with a pull-down**, so the module boots
*held in reset* even with `RFID_EN` high. The failure signature is not silence but a wrong answer:

| GPIO10 | `InitReader_Notype("/dev/ttyAMA0", 1)` |
|---|---|
| released (`ip pd`, the boot state) | `MT_UNKNOWN_READER_TYPE` |
| driven high (`op dh`) | `MT_OK_ERR`, full identity, tags read |

`MT_UNKNOWN_READER_TYPE` reads like a baud-rate or SDK-version problem and it is neither. Raise
GPIO10 with GPIO22, in the app's `ExecStartPre` as well as by hand.

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

# Only needed if you skipped the /opt copy in step 4. run.sh defaults to /opt/intelli/lib.
export RFID_NATIVE_LIB=~/rfid/intelli-rfid-reader/API-linux-java-v260721/libs/aarch64

bash run.sh Probe                          # identity, region, power range, temperature
bash run.sh Probe2 /dev/ttyAMA0 2700 1000  # region acceptance scan + inventory sweeps
```

`bash run.sh`, not `./run.sh`: the script comes out of a fresh clone without its exec bit.

What you are looking for:

- `InitReader_Notype` → `MT_OK_ERR`. Anything else and the module is not answering: check GPIO22 is
  high, check the UART mux, check 5 V.
- Hardware and software versions printed (the bench module is hw `31.00.00.80`, sw `20.26.03.30`).
- **Does it accept `RG_IN`?** `Probe2` scans the regions. This is the answer the whole project has
  been waiting for — record it either way.
- A tag in front of the antenna shows up in the sweeps.

If `Probe` throws `UnsatisfiedLinkError`, `-Djava.library.path=/opt/intelli/lib` is missing or the
`.so` is the wrong architecture. It is mandatory on **every** java command in this project.

### What this unit answered, 2026-08-29

Run with `RFID_NATIVE_LIB` pointing at the SDK tree, on OpenJDK 21.0.12.1, ANT1 fitted, 27 dBm.

- **The module answers and reads.** `InitReader_Notype` → `MT_OK_ERR`; hw `31.00.00.80`, sw
  `20.26.03.30` — **identical firmware to the bench module**; temperature 29 °C idle, 32 °C after
  five sweeps. `GetHardwareDetails` reports `logictype = MODULE_ONE_ANT`, `antportnumbers = 1`,
  confirming the mono-static SIM7500 from the module's own side: **`antenna-count` is 1.**
- **The vendor JNI is clean at call time on Java 21.** Five 1 s sweeps, **18 of 18 tags on every
  pass**, RSSI −27 to −51 dBm, tag structs marshalled back through the JNI intact. Load and bind
  were already verified; this closes the other half. Nothing on this board needs Java 17.
- **`RG_IN` is refused here too — but this module is a wider SKU than the bench's.** Set-and-read-
  back over every `Region_Conf`: **accepted = `RG_NA` (1), `RG_EU3` (8), `RG_PRC` (6), `RG_OPEN`
  (255)**; everything else, `RG_IN` included, returns `MT_CMD_FAILED_ERR`. The bench module accepts
  only `RG_EU3`. **It ships on `RG_NA`** — 902–928 MHz, illegal in India — so region is not a
  setting that can be left at its default on this board.
- **`RF_MINPOWER` / `RF_MAXPOWER` read 500 / 3000** (5–30 dBm). The module will accept 30 dBm
  happily; **the 27 dBm ceiling is the carrier's, and nothing in the module enforces it.** It has to
  come from configuration.
- `MTR_PARAM_RF_SUPPORTEDREGIONS` still returns `MT_INVALID_PARA`, as on the bench. Set-and-read-back
  remains the only way to enumerate regions.

### The Indian band without `RG_IN`: narrow the hop table

`MTR_PARAM_FREQUENCY_HOPTABLE` is readable *and writable* on this firmware, which the region scan
alone would not have shown. Measured channel plans (kHz):

| Region | len | channels |
|---|---|---|
| `RG_EU3` | 4 | 865700 866300 866900 **867500** |
| `RG_NA` | 50 | 902750 … 927250 |
| `RG_PRC` | 16 | 920625 … 924375 |
| `RG_OPEN` | 11 | 860000 870000 880000 … 960000 — a 10 MHz grid, **not** a free-form band |

Only three of `RG_EU3`'s four channels sit inside India's 865–867 MHz allocation; 867.5 does not.
**Writing `{865700, 866300, 866900}` under `RG_EU3` is accepted and reads back as a 3-entry table**,
so this unit can be held inside the Indian band without `RG_IN`. Two rules that came out of it:

- **The table must be a subset of the region's own grid.** The same Indian channels written under
  `RG_OPEN` are refused (`MT_CMD_FAILED_ERR`) — its grid has no 865.7.
- **Setting the region rewrites the table.** `ParamSet(FREQUENCY_REGION, RG_EU3)` restores the stock
  four channels, so the hop table must be written **after** the region, every session. Nothing in
  `ReaderSession.applyConfig()` does this yet — see open item C.

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

`/api/v1/reader/status` should report `connected: true`, `readerState: READING`, a firmware string
and `antennas: 1`.

**It will not report `degraded`, and that is correct** — an earlier draft of this step said to expect
it naming the disabled sensors. `V1Service.degraded()` only speaks when the spool is broken or when
the reader is **armed for Super Fast Mode**; an idle reader with sensors switched off is not
degraded, because nothing is relying on them yet. With `default-property-inclusion: non_null` the
field is simply absent. Arm Super Fast and it appears. Corrected 2026-08-29 from a real run.

Note the key scopes: `/api/v1/reader/status` needs **INVENTORY**, not ADMIN — the operator key gets
`403 insufficient_scope` here, which is the scope rules working, not a misconfiguration.

Then a real read, with the WMS key:

```bash
curl -s -X POST -H "X-API-Key: <the wms key>" -H 'Content-Type: application/json' \
  -d '{"ean":"8905527164445","durationMs":3000,"timed":true}' \
  http://localhost:8081/api/v1/inventory | python3 -m json.tool
```

**Run on this unit 2026-08-29 and it works.** Two reads, `sequence` 1 then 2, `spoolDepth` 0,
`matched: 0` / `unexpected: 2` / `undecodable: 16` — **18 distinct EPCs, the whole bench population,
through the full v1 path.** `matched` is 0 because no tag on this bench carries the requested SKU;
the two decodable ones are SGTIN-96 for a different EAN and land in `unexpected`, which is the
contract behaving. The first read stopped `TIMEOUT` (a tag first seen at 850 ms kept the population
unsettled inside the 3 s window) and the second `SETTLED`.

Two things that will look like faults and are not:

- **`session: 0` is why the population keeps answering.** With the packaged `session: 2` and no
  sensors — so a continuously-on carrier — this tag stock answers once and then goes silent for
  >15 s. Revert to 2 when the sensors are live, not before.
- **The tags' own EAN is rejected as a request parameter.** `{"ean":"8905190881260"}` returns
  `400 invalid_ean` — "check digit should be 7, not 0" — while a *read* renders exactly that EAN
  beside `gtin14: 98905190881260`. The stock is a GTIN-14 variable-measure item (indicator 9), so
  its 13-digit form is not a valid EAN-13. Known open item, now demonstrated on production hardware:
  the read path and the request path disagree about what an `ean` is.

---

## 10. Run it as a service (once Step 9 works by hand)

> **Installed and running on this unit 2026-08-29** as `intelli-rfid-tunnel.service`, enabled at
> boot. The unit below is the corrected one — it differs from the first draft in two ways that both
> stop the reader working: the `RFID_NRST` `ExecStartPre`, and a library path that exists on this
> machine.

A ready-to-install copy is at `~/intelli-rfid-tunnel.service` on the production CM4; it passes
`systemd-analyze verify`.

```bash
sudo install -o root -g root -m 644 \
  ~/intelli-rfid-tunnel.service /etc/systemd/system/intelli-rfid-tunnel.service
sudo systemctl daemon-reload
sudo systemctl enable --now intelli-rfid-tunnel
systemctl status intelli-rfid-tunnel --no-pager
journalctl -u intelli-rfid-tunnel -f
```

Stop anything already holding the serial port first — one process owns `/dev/ttyAMA0`, and a
hand-started JVM will make the service fail to open the reader.

```ini
[Unit]
Description=Intelli RFID tunnel (v2.x carrier, production CM4)
After=network-online.target
Wants=network-online.target

[Service]
Type=simple
User=intelli-sbc
WorkingDirectory=/home/intelli-sbc/rfid/intelli-rfid-reader/apps/intelli-rfid-tunnel

# The board comes up with the reader off AND held in reset, and nothing in the application
# does any of this. Antenna port first, then power - never the other way round.
# The leading + runs these as root.
ExecStartPre=+/usr/bin/pinctrl set 8 op dh
ExecStartPre=+/usr/bin/pinctrl set 9 op dl
ExecStartPre=+/usr/bin/pinctrl set 22 op dh
ExecStartPre=+/usr/bin/pinctrl set 10 op dh

ExecStart=/usr/bin/java \
  -Djava.library.path=/home/intelli-sbc/rfid/intelli-rfid-reader/API-linux-java-v260721/libs/aarch64 \
  -jar /home/intelli-sbc/rfid/intelli-rfid-reader/apps/intelli-rfid-tunnel/target/intelli-rfid-tunnel-1.0.0-SNAPSHOT.jar \
  --spring.config.additional-location=file:/etc/intelli/intelli-rfid-tunnel/

# A stopped service should be a quiet radio. EN only - NRST stays high, because idle is the
# right resting state for the module, not held in reset.
ExecStopPost=+/usr/bin/pinctrl set 22 op dl

Restart=on-failure
RestartSec=10

[Install]
WantedBy=multi-user.target
```

Four things in there are load-bearing, and each one has cost this project time:

- **`ExecStartPre` for GPIO10.** `RFID_NRST` boots low, so the module is powered *and* in reset.
  `InitReader` then answers `MT_UNKNOWN_READER_TYPE` — a wrong answer, not silence. Step 7.
- **The pin order.** ANT1 select, then `RFID_EN`. Never bring RF up into an unterminated port.
- **`-Djava.library.path`.** `rfid.reader.native-lib-path` does not substitute for it: the vendor's
  static initialiser calls `System.loadLibrary`, which reads only `java.library.path`. This unit
  points at the SDK tree because `/opt/intelli/lib` does not exist here.
- **`--spring.config.additional-location`.** Without it the app finds no API keys and refuses to
  start, which is by design.

Two caveats worth knowing before you enable it:

- **The app reconnects itself after a read exception** — an `rfid-supervise` thread closes, reopens
  and restarts inventory, backing off 5→10→20→40→60 s while the module is unreachable. So
  `Restart=on-failure` covers the JVM dying, not the module glitching. Watch `recoveries` in
  `/actuator/health`: a count that climbs steadily is a reader that keeps breaking, and on this
  board the first thing to suspect is `RFID_EN` — recovery cannot help a module that has been
  switched off underneath it.
- The jar path is versioned. It changes when the version does.

Once installed: `sudo systemctl {start,stop,restart} intelli-rfid-tunnel`, and
`journalctl -u intelli-rfid-tunnel -f` for the log. It is up when `/actuator/health` reports `UP`
with the reader component `READING` — that endpoint needs no API key.

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

**C. Region — answered, and it turned into a code change.** This module refuses `RG_IN` and **boots
on `RG_NA`**, which is not legal to key up on in India. `RG_EU3` is the operating region, as on the
bench, and its stock hop table includes one channel (867.5 MHz) outside the Indian allocation.
The hop table *is* writable, so the fix is `RG_EU3` **plus** an explicit
`{865700, 866300, 866900}` hop table, written after the region on every connect.
`ReaderSession.applyConfig()` sets and reads back six parameters and the hop table is not one of
them; it should be the seventh, with the same read-back. Until it is, this board's channel plan
depends on whichever probe last touched it.

**An updated vendor Java API doc set is due Monday 2026-08-31 and is expected to enable `RG_IN`**,
so everything until then runs on `RG_EU3` by decision rather than by discovery. When it lands, the
first question is whether it brings **new module firmware** or documents an **unlock / `initregion`
procedure the project is not calling** — a documentation change alone cannot alter what the module
accepts, and re-running the scan would return the same four regions.

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

*Written on the bench rig, 2026-08-29, and corrected the same day from two real runs on the
production CM4 — see the note at the top for which steps that covers. **Steps 3, 9 and 10 have
still never been run against the v2.x board**: they are the best available reading of
`docs/Hardware-IntelliRFIDv2.md`, not measured fact. Keep correcting this file as you go; the
2026-08-29 pass found the errors were systematic (a Bookworm runbook meeting a Trixie machine)
rather than one-off, so when one command here is wrong, suspect its neighbours.*
