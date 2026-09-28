# Resume here — CM4 session, next sitting

**Sections are newest first. 2026-09-24 (antenna LEDs) is on top, then 2026-09-23 late (the second
board, flashed and running), then
2026-09-23 evening (the export kit for a second CM4), then
2026-09-23 (deployed, and the RZC stops per carton again) is on top,
then 2026-09-22 (one carton at a time — written on 09-23, because that session was cut off by a
disconnect before its close-out ran), then 2026-09-14 (housekeeping) and 2026-09-11
(firmware + RG_IN). The 2026-09-09 one's two operator steps are DONE
(checked 2026-09-14: the jar in `/opt` is from 09-09 21:31 and the site config has
`rzc-always-run: true` at 100 %). Below it, the 2026-09-07 rewrite —
the session that FIXED the deafness, upgraded the SDK and made the armed EAN authoritative — which
itself supersedes the "the reader is deaf, it is hardware" head that stood here earlier that day.**

---

## 2026-09-28 (later, on `intellisbc2`): Radxa CM3 on the RFID-v2 carrier. Ethernet test in progress

The operator is swapping `intellisbc2`'s CM4 for a **Radxa CM3** (`radxa-cm3-io`, DHCP
**192.168.0.194**, user `intelli-sbc`; the password is with the operator and not in the repo). It
links fine on a Waveshare carrier. On this board it boots, but the Ethernet link never comes up
(journal boot -1, 14:31, confirmed by the operator). Details and the decision table are in
`docs/Hardware-IntelliRFIDv2.md` §16.

**State left:** on the CM3, `ethtool` is installed and `eth-probe.service` is enabled, with
`/etc/eth-probe/limit-100` ON. It is verified through a reboot on the Waveshare: the limit is
applied at about 20 s and the link comes up at 100 Mb/s. `intellisbc2` is shut down for the swap. Its
CM4 goes back in afterwards.

**Next, in order:**
1. With the CM3 on the RFID board, same cable and switch port, powered 2–3 minutes: does
   192.168.0.194 answer?
2. CM3 back on the Waveshare: `grep boot= /var/log/eth-probe.log | tail -40`, the RFID-board boot's
   lines. Read `link=`, `speed=` and `partner=` against §16.
3. Afterwards, on the CM3: `sudo rm /etc/eth-probe/limit-100` to restore gigabit, and
   `sudo systemctl disable --now eth-probe` to stop the logging.
4. The 2026-09-28 kit-refresh steps below are still open. The root repo commit `85f53e5` exists,
   but `bash -n` and `rebuild-kit.sh` have not been run.

---

## 2026-09-28: kit refresh for a THIRD board — `intellisbc3`, reader-id 3, a tunnel reader

**Nothing changed on this unit.** Bash was unavailable for the whole session (the permission check
returned no verdict on every call), so everything below was done with file edits only: **nothing
was run, syntax-checked or committed.**

- The 09-23 kit was stale: its jar predates the antenna LEDs (`f89eaff`, 09-24), its unit file lacks
  `ExecStopPost` for GPIO17/27, it has no `intelli-wayside-reader` repo, and its memory is old.
- `export/setup-new-cm4.sh` edited: defaults `intellisbc3` / `3` (lists taken names and ids); jar
  commit read from the kit's `JAR-COMMIT` instead of hardcoded `acdb2d5`; the flash step now uses a
  detached tmux and `printf '/dev/ttyAMA0:115200\n\n' |`, with 30–80 s timing; two new end-of-run
  items (D18/D19 fitted, review the carried-over site config: reverse nudge, bench surface,
  `rzc-always-run: false` with dead IN2).
- `export/rebuild-kit.sh` new: starts from the newest old tarball (keeps firmware, sudoers,
  snapshot) and replaces workspace (all `apps/*/`), `~/api`, `~/.m2`, memory, the `/opt` jar and
  `.so`, site config, unit and lamp hook. Writes `intelli-cm4-kit-<date>.tar.gz` and `SHA256SUMS`.

**Next, in order:**
1. `cd export && bash -n setup-new-cm4.sh && bash -n rebuild-kit.sh` — neither edit is checked.
2. **Commit and push the root repo** (both scripts; `SHA256SUMS` stays untracked). Not done.
3. `bash rebuild-kit.sh` (operator, or Claude if Bash works) — check its WARN lines.
4. On the new board: `bash setup-new-cm4.sh --hostname intellisbc3 --reader-id 3`, then record
   module serial / fw / auth in `CLAUDE.md` "Cloning this unit onto a new board", as for intellisbc2.

---

## 2026-09-24: antenna LEDs on GPIO17 / GPIO27. Deployed and confirmed working by the operator

The tunnel now drives the board's antenna LEDs (tunnel `f89eaff`, package `tunnel/antenna/`):
- GPIO17 → R54 → D18 is port 1 (J20).
- GPIO27 → R55 → D19 is port 2 (J25).

**What "lit" means, as the operator chose it:** the port is the one the SP4T (GPIO8/9) feeds, **and** a
VSWR sweep of it at reader connect read ≤ `tunnel.antenna-leds.max-vswr` (2.0). It **blinks at 4 Hz**
while tags arrive. The other port's LED is always dark, because the app never moves the switch. See
CLAUDE.md, Hardware.

**State of this unit:**
- The jar in `/opt` is from 09-24 15:06, the service is active, and the site config is unchanged.
- The packaged defaults apply: `enabled: true`, `max-vswr: 2.0`.
- The new unit file is installed. `ExecStopPost` drops 17 and 27.
- **The first live sweep read J25 = 1.4326 (15 dB return loss).** On 09-11 it read 1.377 (16 dB).
  That is one quantisation step, within noise, but note it if it keeps drifting.

**Next, in order:**
1. Sweep a **bare** J25, with the service stopped, the pins raised and `ANT=2`, and the antenna
   removed. That tells us whether `max-vswr: 2.0` really separates "no antenna" from "antenna".
   Until then, a dark D19 means only "not ≥ 10 dB return loss".
2. The `intellisbc2` list below still stands. That board gets the LEDs on its next deploy; check
   that its carrier has D18/D19 fitted.
3. `export/SHA256SUMS` is untracked in the root repo on purpose. It belongs to the git-ignored kit
   tarball.

---

## 2026-09-23 (late): the kit WORKED — `intellisbc2` is up on fw 20260819 + RG_IN

Run on the new board (reader-id 2, module `30262503F8`). Both passes clean; then auth region
`RG_PRC` -> `RG_IN`, dump byte-identical to 03-30, MCU flash to `20260819` (31.9 s), 26 regions
accepted, site config `RG_IN`, tunnel UP. Details and the table are in CLAUDE.md, "Cloning this
unit onto a new board". CodeCommit credentials are installed on `intellisbc2`; no VPN yet.

**Next on `intellisbc2`, in order:**
1. Antenna on BOTH ports, then `ANT=1` / `ANT=2 ~/api/run/run.sh ProbeBasic` and the VSWR sweep
   per port. J20 read 0 tags at setup, J25 read 39; unknown whether J20 had an antenna.
2. Decide the carried-over site config: reverse nudge ON, bench test surface ON, `session: 1`.
3. Laptop apps at `intellisbc2.local`; a VPN certificate for `intellisbc2`; a callback token.

Script fix committed: step 12 had matched `"UP"` anywhere in the health JSON and reported a tunnel
still `OUT_OF_SERVICE` as up.

---

## 2026-09-23 (evening): the export kit for a second CM4. If you are troubleshooting a new board, start here

**Nothing changed on this unit.** The session built a kit to clone this board onto a new CM4 and
v2.x carrier. **It has not been run on a new board yet**; it was only syntax-checked. Expect the
first real run to find something.

### What exists
- `export/setup-new-cm4.sh`: committed. It runs twice as `intelli-sbc`, with a reboot between.
  - **Pass 1:** packages and the dialout/gpio groups, the IntelliRFID block in `config.txt`
    (enable_uart, disable-bt, uart3) with the serial console off, then the hostname. It also
    installs the workspace, `~/api`, `~/.m2`, Claude memory, `/opt/intelli`, `/var/lib/intelli`,
    the site config, the unit, the lamp hook and sudoers.
  - **Pass 2:** checks GPIO14 is TXD0 and runs `fw_probe.py --to-app` (read-only). It then runs
    `ProbeBasic` on ANT1 and ANT2, sets the site region, and enables and starts the tunnel.
  - It saves its answers in `~/.intelli-setup.conf` and logs each run to `~/intelli-setup-*.log`.
    Probe outputs go to `~/probe-fw-*.txt` and `~/probe-basic-ant{1,2}-*.txt`. **Ask for these
    first when troubleshooting.**
- `export/intelli-cm4-kit-2026-09-23.tar.gz` (148 MB, **git-ignored, not pushed**):
  - the workspace with all 6 repos' `.git` (target/ excluded);
  - `firmware-sim7500-20260819/` at the top level (checksums verified), with the flash handoff and
    report docs copied in;
  - `home/api` (the v260827 SDK plus compiled probes), the deployed jar and `.so` from `/opt/intelli`
    (tunnel `acdb2d5`), the site config, unit, hook and sudoers, `~/.m2`, Claude memory, and a
    `system/snapshot/` of this board for diffing.
- **No secrets in the kit.** The permission classifier refused to bundle `.git-credentials`, the VPN
  `client.conf` and the plaintext keys file. The operator was given a one-liner to build
  `intelli-cm4-secrets-2026-09-23.tar.gz` by hand. The script picks it up if present but **only
  installs `.git-credentials`**; VPN needs a per-board certificate.

### What the script decides, and why
- **Region:** it writes `RG_EU3` first and switches to `RG_IN` only when `fw_probe` reports fw
  `20260819` **and** auth `INDIA`. A fresh module (sw `20.26.03.30`) refuses `RG_IN`, and
  `applyConfig()` would then fail on every connect. The script never flashes and never writes the
  auth region; it prints the commands. The order it gives is auth write, then flash, the same as
  this unit (09-07, then 09-11).
- **Values it asks for:** hostname (default `intellisbc2`, because of the mDNS clash; laptop apps
  still point at `intellisbc.local`), `reader-id` (default 2) and ANT (default 2).
- **ANT2 is this board's J20 fault, not a property of the design.** The new board may be fine on J20.
- **Carried over unchanged:** the same API key hashes, so the WMS, admin and wms-test keys work on
  both boards.
- **Left out on purpose:** spool, sequence counter, logs and the legacy
  `intelli-heartbeat-off.service` (still enabled on THIS unit; it drives BCM 12, now the green
  lamp, low at shutdown. Harmless, but a candidate for removal).

### Likely first failures on a new board
1. **Pass 2 exits with "not in dialout".** The login predates the usermod; log out and back in.
2. **`fw_probe` gets no answer.** Pins 8/9/22/10 are not raised, or `disable-bt` did not apply: a
   trailing comment in `config.txt`, or an existing `[cm4]` section swallowing the lines. The
   script appends an `[all]` header for this reason.
3. **The tunnel is not UP and the log shows a region failure.** The module is not on fw 20260819 +
   INDIA and the site config somehow says `RG_IN`.
4. **ProbeBasic reads 0 on both ports.** Put tags in front of the antenna. Without the explicit
   region set the module would sit on `RG_NA`; ProbeBasic does set it.

---

## 2026-09-23 — DEPLOYED; one carton at a time is live, and the RZC stops per carton again

**Short session. The operator deployed, changed `rzc-always-run` to `false`, and ran 22 cartons.**
It opened by reconstructing the 09-22 close-out that a disconnect had cut short — see the section
below, which was written today.

### What changed
- **Deployed at 12:53** (operator): `/opt/intelli/intelli-rfid-tunnel/intelli-rfid-tunnel.jar` is
  now a 12:53 build carrying `cartonInZone`. **`acdb2d5` (one carton at a time) and `9e6485b` (the
  O7 log line) are both live**, and the new behaviour is in the log:
  `Conveyor: carton in the read zone - RZC at 100 %, EnC and ExC stopped`.
- **Site config 13:43 (operator): `rzc-always-run: true` → `false`.** O2 now rises on the entry
  trigger and falls again; the arm line reads `RZC stopped`. `read-speed-percent` stays 100, so the
  gear when it does run is unchanged.
- **Docs**: `CLAUDE.md` gains the reversal note on the RZC section and two gotchas — the
  `triggered-carrier` / `rzc-always-run` distinction, and the fact that conveyor output levels
  outlive the process.

### What was asked and answered
**"OUT2 is always high even when I have set triggered = true."** They are unrelated.
`tunnel.v1.triggered-carrier` is the **RF carrier** — `V1Service.dropCarrier()` calls
`stopReading()` and touches no field channel. O2 is the RZC's Run A, held high by
`rzc-always-run`. Also worth knowing: `triggeredCarrier()` is
`isTriggeredCarrier() && gpio.isWatching()`, and `dropCarrier` logs at **DEBUG only** — so there is
no `Carrier off:` line in any of our logs and that says nothing about whether it is working.

### State the unit was left in
- Service `active`, PID **588407**, jar of 12:53, fw `20.26.08.19`, `RG_IN`, ANT2/J25, armed
  SUPERFAST for `8909477586814`, expected 40, callback to `192.168.0.177:8083`.
- Pins at close: O1 (26) **hi**, O5 (21) **hi**, O2 (20) **lo**, O3/O4/O6/O7 lo, all four inputs
  clear. That is `line running, RZC stopped`, which is correct for the new flag.
- **`intelli-wms-test` is running ON THIS BOARD** (PID 573064, `target/intelli-wms-test-0.1.0.jar`),
  which is the standard since 2026-09-23 (the laptop only browses to it). Worth knowing before
  wondering what the second JVM is.
- **A vim swap file `/etc/intelli/intelli-rfid-tunnel/.application.yml.swp` is still there** (13:48).
  Either an editor is still open on the site config or one died — clear it before the next edit.

### The 22 cartons of 09-23 — all SETTLED
Mostly a small 5-tag population: **5 of 5 and `complete: true` on 9 of the first 11**, two at 4 of 5.
The one 40-expected carton read **24 tags at 13:51 IST**. RSSI −41…−62, best of the day −35,
`lastNewTagMs` 806–890 against the 800 ms window, reads/tag 1.0–1.9.

### Still open, in order
1. **IN2 has not fired once, on either day.** Every carton logs `no exit edge 10000 ms after the
   read closed`, and **since `rzc-always-run: false` that backstop now says `stopping the RZC
   anyway` rather than merely warning** — the roller stops under a carton that IN2 never saw leave.
   Drive line 24 (`pinctrl set 24 op dl` then `op dh`, then back to `ip pd`) to prove the edge path,
   then look at the SICK W26 and its TM channel.
2. **Reads per tag is 1.0–1.9** on a 5-tag carton, thinner than the 2–3 recorded on 09-07. With
   `rzc-always-run: false` the carton is no longer being pulled through at 100 % the whole time, so
   this is worth re-reading before concluding anything about the RF.
3. **The weak RSSI** — best −35 today against −25 on 09-07 on this same J25 branch. Unexplained
   since 09-14.
4. Then the 09-11 list: radiated power under the Indian limit, bare-J25 VSWR sweep + module
   temperature, send Silion the report.
5. Open from 09-14: should the tunnel's packaged `antenna-count: 2` become 1?

---

## 2026-09-22 — one carton at a time; NOT DEPLOYED, and IN2 did not fire once all day

**The session ended in a disconnect, not a close-out.** The code and the documentation were
committed and pushed before it dropped; this section, the memory entry and the deploy were not.
Reconstructed 2026-09-23 from the repos, the log and the spool. **The deploy has since happened —
12:53 on 09-23 — so "NOT DEPLOYED" in the heading is history; see the 09-23 section above.**

### What changed — all committed and pushed
- **tunnel `acdb2d5`**: **one carton at a time.** `ConveyorController.cartonInZone` is a second
  negative term in `applyExc()`, set by `cartonEntered()` and cleared by `discharge()`, so the EnC
  **and** the ExC both drop on the IN1 entry trigger and both come back when the read is released,
  on any outcome. 281 tests pass, including the inverted `theExcKeepsRunningWhileACartonIsRead` and
  `releasingAReadNeverStartsTheExcIntoAnOccupiedEdge`. **It gives back the de-serialisation the
  09-05 rewiring bought** — cycle time is read + discharge again — deliberately, on the operator's
  decision, and reversing it is deleting one term because O5 is still the ExC's own copper.
  The IN4 interlock is untouched and still outranks it.
- **root `2141288`**: `CLAUDE.md` gains the "One carton at a time" section;
  `docs/Tunnel-Interconnect.md` goes to **0.8**.
- **memory** (17:25): `board-address-is-a-dhcp-lease.md` — address the board by `intellisbc.local`.

### State the unit was left in
- Service `active`; the running JVM is **PID 1025, started 2026-09-22 16:56**, from
  `/opt/intelli/intelli-rfid-tunnel/intelli-rfid-tunnel.jar` — which is still the **09-09 21:31**
  build. Verified by class content: the `/opt` jar has no `cartonInZone`; `target/` (built 21:06)
  has it.
- **So `acdb2d5` AND the 09-14 `9e6485b` O7 log fix are both still undeployed.** One
  `deploy/redeploy.sh` takes both.
- **`settle-ms: 800` IS live** — this corrects the 09-14 section above, which said it was not. Every
  one of the day's cartons has `lastNewTagMs` at 805–870 ms.
- Reverse nudge still on (1 pulse at 2000 ms for 1000 ms). fw `20.26.08.19`, `RG_IN`, ANT2/J25
  (`pinctrl get 8,9` → 8 lo, 9 hi, confirmed 09-23).

### The seven cartons of 09-22 — all SETTLED, none complete
| time (Z) | tags | matched / exp | marginal | lastNewTagMs | durationMs | best…worst RSSI | reads/tag |
|---|---|---|---|---|---|---|---|
| 12:02:21 | 19 | **0** / 40 | 11 | 834 | 2159 | −37…−60 | 1.4 |
| 12:03:42 | 24 | 24 / 40 | 2 | 826 | 3358 | −36…−58 | 2.4 |
| 12:22:17 | 24 | 24 / 40 | 3 | 840 | 3220 | −35…−60 | 2.2 |
| 12:22:33 | 29 | 29 / 40 | 5 | 828 | 3382 | −37…−61 | 2.2 |
| 12:59:16 | 18 | 18 / 40 | 6 | 867 | 2327 | −38…−59 | 1.7 |
| 14:47:26 | 20 | 20 / 40 | 2 | 870 | 3437 | −38…−61 | 2.5 |
| 14:49:11 | 38 | 38 / **18** | 8 | 805 | 6393 | −35…−60 | 3.2 |

Three things to carry forward, none of them explained:
- **`IN2 NEVER FIRED ONCE.`** Every carton logs `no exit edge 10000 ms after the read closed …
  check the exit sensor`. That was tolerable while `rzc-always-run` meant nothing could be
  stranded — **it is not tolerable now**, because `cartonInZone` is cleared at read release and
  `reopen-block-ms` keys off IN2 to lift. This is ahead of everything else.
- **Best RSSI is −35…−38 dBm**, against −25 on 09-07 on this same J25 branch. Still ~10 dB down and
  still the 09-14 open question. Cartons are reading 18–38 of 40.
- **12:02 matched 0 of 19 tags**, the same shape as 09-14's seq 1198 — probably armed for a
  different EAN at that moment. Check the arm log against the spool.

### Next, in order
1. **Deploy**: `cd ~/rfid/intelli-rfid-reader/apps/intelli-rfid-tunnel && deploy/redeploy.sh`
   (picks up `acdb2d5` one-carton and `9e6485b` O7 log).
2. **The dead exit sensor.** IN2 gates belt release now. Drive line 24 (`pinctrl set 24 op dl` then
   `op dh`, then back to `ip pd`) to prove the edge path, then look at the SICK W26 and its TM
   channel. The internal-pull trick does not work on this carrier.
3. **The weak RSSI / short cartons** — blocked on nothing, and it blocks the like-for-like carton
   comparison against 09-07's 38/38.
4. Then the 09-11 list: radiated power under the Indian limit, bare-J25 VSWR sweep + module
   temperature, send Silion the report.
5. Open from 09-14: should the tunnel's packaged `antenna-count: 2` become 1? (Site config says 1.)
6. Optional: make shutdown step 3 a no-op when no write is outstanding.

---

## 2026-09-14 — housekeeping; two commits NOT YET DEPLOYED, and the first cartons on the new firmware read weak

**Session closed ~21:00 by the operator ("we will resume tomorrow").** Everything is committed and
pushed in all repos.

### What changed
- **reader-test** `3ea0ec1`: packaged `antenna-count` 4 → **1**. Its `target/` jar predates this;
  rebuild before the next acceptance run.
- **tunnel** `9e6485b`: the `SHUTDOWN REQUESTED` log line said "O6 blinks"; it is **O7** since the
  09-05 rewiring. Log text only.
- **Site config** (operator): `settle-ms` 1500 → **800**, saved 20:40:39.
- Docs: the 09-09 operator steps confirmed done (jar in `/opt` is 09-09 21:31, `rzc-always-run: true`
  at 100 %).

### State the unit was left in
- Board rebooted ~20:36; service `active`, `READING`, fw `20.26.08.19`, `RG_IN`, ANT2/J25.
- **The running JVM is still the 09-09 jar and still on `settle-ms: 1500`** — it started before the
  config edit. Neither the O7 log fix nor the 800 window is live.
  **CORRECTED 2026-09-23: the 800 window IS live** — the JVM was restarted after that edit (the one
  running on 09-22 started 16:56 that day) and every 09-22 carton settles at 805–870 ms. The jar
  half of the claim still stands: `/opt` is the 09-09 build.
- Reverse nudge still on (1 pulse at 2000 ms for 1000 ms). 7 old entries in `callbacks-dead.jsonl`.

### The first two cartons of the day — read these before trusting the new firmware on cartons
| seq | IST | stop | tags | matched / expected | lastNewTagMs | durationMs | best RSSI | worst |
|---|---|---|---|---|---|---|---|---|
| 1198 | 20:55:51 | SETTLED | 23 | **0** / 40 | 1523 | 4501 | −48 | −60 |
| 1199 | 20:57:02 | SETTLED | 25 | 25 / 40 | 1561 | 4271 | −48 | −60 |

Both `complete: false`. Not yet explained, and not analysed:
- **Best RSSI −48 dBm**, against −25 on 09-07 (38/38, J25) and −32 on 09-11's hand-spread tags. That
  is ~16–23 dB down. Check the ANT2 select (`pinctrl get 8,9` → 8 lo, 9 hi), the J25 cable, and the
  tag/carton geometry before blaming the firmware.
- **1198 matched 0 of 23** with the same EPC prefix (`30361FCA9439…`) that matched 25 of 25 in 1199
  — so probably armed for a different EAN at that moment. Check the arm log.
- **durationMs − lastNewTagMs ≈ 2.7–3.0 s, not the 1.5 s window.** Something besides settle held
  both reads open; check `min-duration` and the reverse nudge (pulse ends at 3000 ms).

### Next, tomorrow, in order
1. **Deploy**: `cd ~/rfid/intelli-rfid-reader/apps/intelli-rfid-tunnel && deploy/redeploy.sh`
   (picks up `9e6485b` and `settle-ms: 800`).
2. **Explain the weak RSSI / short cartons above** — this is now ahead of the like-for-like carton
   comparison (09-11 item 2), which it blocks.
3. Then the 09-11 list below: radiated power under the Indian limit, bare-J25 VSWR sweep + module
   temperature, send Silion the report.
4. Open question from 09-14: should the tunnel's packaged `antenna-count: 2` also become 1? (Site
   config already says 1.)
5. Optional, from reading the shutdown code: make shutdown step 3 a no-op when no write is
   outstanding, so its ERROR on every idle shutdown stops being noise.

---

## ✅ 2026-09-11 — MODULE FIRMWARE FLASHED TO 20.26.08.19, AND THE UNIT RUNS RG_IN

**The long-standing `RG_IN` question is answered: the old module application was the block.** The
production module (the only board in use, serial `30262503F5`) went from sw `20.26.03.30` to
`20.26.08.19` using Silion's 2026-08-19 kit (`docs/CM4-Firmware-Update-Handoff.md`, report filed at
its end). The flash dump beforehand was byte-identical to the 03-30 MiniTP image. The MCU write took
79 s and verified. Hw `31.00.0E.80` and the auth region `RG_IN` both survived. The module now accepts
**26 regions, `RG_IN` included** (it accepted 4 before). It still powers up on `RG_NA`.

### State the unit was left in
- Tunnel service **running**, on module fw `20.26.08.19`, **`region: RG_IN`** in
  `/etc/intelli/intelli-rfid-tunnel/application.yml` (backup of the `RG_EU3` file:
  `application.yml.bak-2026-09-11`, root:root). Reads land only on 865.1/865.7/866.3/866.9 MHz.
- About 40 SGTIN tags lying spread in front of J25; 28–30 of them answer at −32 dBm best.
- The module powers up in its **bootloader** with the autoboot flag off. That is normal here; the SDK
  starts the application on connect. Do not set the flag.

**Session closed 2026-09-11 ~21:15 by the operator.** Everything is committed and pushed. The tunnel
service is running and reading on `RG_IN`: `READING`, fw `20.26.08.19`, 0 read errors.

### Next, in order
1. **Radiated power under the Indian limit.** It was always open, but `RG_IN` now means the unit
   claims to be on the Indian band. 30 dBm conducted + antenna gain has to be checked against the
   allocation.
2. **A like-for-like carton read** against 09-07 (38/38, −25 dBm best, J25), for a real
   before/after on read performance. Today's check was hand-spread tags only.
3. ~~rfMode 107 check, acceptance run~~ **done 2026-09-11**: the 107 fallback is unchanged, and
   acceptance PASSES on J25. **The VSWR sweep works:** J25 reads 1.377 (16 dB return loss) and J20
   reads 3.0095 (6 dB) in the same minute, so the 09-07 "useless" note was J20's fault; `CLAUDE.md`
   is corrected. Still to do: sweep a **bare** J25 (unscrew its antenna) to learn what "no antenna"
   reads, and record the module temperature under load.
   ~~**reader-test bug to fix:** its `application.yml` ships `antenna-count: 4`~~ **fixed
   2026-09-14** (`3ea0ec1`, ships `1`). Its jar in `target/` predates that commit, so rebuild before
   the next acceptance run. The tunnel's packaged `application.yml` still says `antenna-count: 2`;
   the site config's `1` is what corrects it on this unit.

**2026-09-14:** the operator set the site config's `settle-ms` back to **800** (it had been 1500
since at least 09-09). The board was rebooted at 20:36 and the service came up `READING` on `RG_IN`.
The reverse nudge is still on (1 pulse, 2000 ms after entry, 1000 ms wide). There are 7 old entries
in `callbacks-dead.jsonl`, none in the live queue.
4. **Send Silion the report**: `docs/Silion-SIM7500-Firmware-20260819-Report.md` (also published as
   a private page: https://claude.ai/code/artifact/15f233d2-7647-45bb-8678-8f5b0b29865d). It asks
   seven numbered questions. The one that matters is **Q2**: with an INDIA auth region the module now
   accepts 26 operating regions, and a deployed unit needs to be locked to `RG_IN`. Q3 (whether
   `RG_IN` enforces power limits in firmware) feeds item 1. Not sent as of session close; the
   operator sends it.
5. **If the firmware is ever rolled back** (`rollback/` image = exactly what ran before), put
   `region: RG_EU3` back in the site config in the same step, or the tunnel will fail at connect.

---

## ✅ 2026-09-09 — the RZC change. The two operator steps below were DONE the same evening (verified 2026-09-14).

**Session paused mid-task ("will continue in a bit"), not closed.** Everything is committed and
pushed in both repos that changed (`63246a2` docs, `bd6b724` tunnel). **Nothing is deployed.**

### What is waiting on the operator, in order

1. **Apply the site config.** The patched copy is at
   `/tmp/claude-1000/-home-intelli-sbc-rfid-intelli-rfid-reader/89dc9c6d-c9a7-46eb-90f9-25342df62b2f/scratchpad/application.yml.new`
   — **and that path is session-scoped, so if the scratchpad is gone, regenerate it** by applying
   the same two edits to `/etc/intelli/intelli-rfid-tunnel/application.yml`:
   `read-speed-percent: 50` → `100`, and add `rzc-always-run: true` under it.
   ```bash
   sudo cp /etc/intelli/intelli-rfid-tunnel/application.yml{,.bak-2026-09-09} &&    sudo cp <scratchpad>/application.yml.new /etc/intelli/intelli-rfid-tunnel/application.yml &&    sudo chown root:intelli-sbc /etc/intelli/intelli-rfid-tunnel/application.yml &&    sudo chmod 640 /etc/intelli/intelli-rfid-tunnel/application.yml
   ```
   **This step is not optional and it is the one that will be forgotten.** The site file pinned
   `read-speed-percent: 50`, and it overrides the packaged jar — so deploying without it leaves the
   belt running on **O3** with O2 dark, which is the opposite of what was asked for.
2. **`cd ~/rfid/intelli-rfid-reader/apps/intelli-rfid-tunnel && deploy/redeploy.sh`**

### What changed

**Operator decision, 2026-09-09: in Super Fast Mode the Reading Zone Conveyor runs continuously and
O2 is held high.** `tunnel.field.conveyor.rzc-always-run: true` — the RZC joins the EnC and the ExC
as a belt that simply turns while the tunnel is armed, instead of starting on the EnS entry edge and
stopping on the IN2 exit edge.

**The gear moved 50 % → 100 % with it, and it is the same decision, not a second one.** The
EZY-S100 ladder is not monotonic — Run B alone is 50 %, Run A alone is 100 %, both is 75 % — so
"the RZC is running" and "O2 is high" are different machines. Run A alone is the only gear that
leaves O2 high on its own, matching O1 and O5. `PackagedConfigTest` pins both values, because
either one alone gives the wrong machine.

- The `FieldProperties` default stays `false`: a belt turning under an empty, unattended tunnel is
  the more surprising state for a unit that has not been told otherwise. The packaged
  `application.yml` is what turns it on.
- **The exit interlock still wins** — a read closing against an occupied IN4 stops O1, O2 and O5 and
  holds the carton in the read zone, resuming by itself when the package is lifted. `allStop` and
  the bench hold are untouched. Always-run is a resting state, never an override, and there is a
  test for exactly the "pushes a box onto an occupied ExC" case.
- **`discharge-max-ms` now only warns** instead of stopping the roller: nothing can be stranded, but
  a missing IN2 edge is still a broken sensor and still says so.
- The arm log line was printing `RZC stopped` under always-run. Fixed — it was a lie in the one line
  an engineer reads to check the machine came up as configured.
- 260 tunnel tests pass. **Nothing here has been run against a moving belt.**

### What to watch on the first cartons

| | O1 | O2 | O3 | O5 |
|---|---|---|---|---|
| arm | HIGH | **HIGH** | low | HIGH |
| EnS fires | LOW | **HIGH** | low | HIGH |
| read closes | HIGH | **HIGH** | low | HIGH |
| IN2 fires | HIGH | **HIGH** | low | HIGH |
| read closes on occupied IN4 | LOW | **LOW** | low | LOW |
| disarm | LOW | LOW | low | LOW |

**At 100 % a carton crosses the read zone in half the dwell it had at 50 %, and reads per tag was
already thin at 2–3 per carton.** If a real carton starts reporting short, step
`read-speed-percent` down to **75** — both bits high, so O2 stays high — **before** touching
`settle-ms`. This is now the first thing to check ahead of next action 2 below, because it changes
the very gap distribution that action is trying to measure.

---

## ✅ 2026-09-07 — THE READER READS AGAIN. It was one antenna branch, not the module.

**38 of 38 articles, SETTLED, `complete: true`, RSSI −25 dBm.** The unit is deployed, running and
healthy. Nothing here is blocked.

### What was actually wrong

The SIM7500 has **one** antenna port; the board's PE42442A SP4T splits it to J20/J25 under
**GPIO8/9**, and the module cannot see the switch. **Every earlier "both ports tried" test was run
with a single antenna**, so flipping `ANT=2` listened into a bare connector and proved nothing.

With an antenna on both ports and the tags unmoved: **J20 best −49 dBm over 3 EPCs, J25 best
−25 dBm over 8.** −25 is this rig's baseline, so the module, PA and switch are fine and the ~24 dB
loss is inside the J20 branch. J20 is the port the systemd unit had always selected.

### State the unit was left in

- **Service running**, PID under systemd, jar and `.so` both v260827, site config patched.
- **Antenna select is ANT2 / J25** — set by `ExecStartPre` in `deploy/intelli-rfid-tunnel.service`.
  `run.sh` still defaults to `ANT=1`, so **a bare `run.sh ProbeBasic` tests the BROKEN branch.**
- Region `RG_EU3`, 27 dBm, session S1, `settle-ms` 800, FastID on, `valid-eans` empty.
- Everything committed and pushed in all four repos that changed.

### Next actions, in order

1. **Bisect the J20 branch — physical, no software.** Swap the two cables at the board, leave the
   antennas and tags where they are, re-run both ports:
   ```bash
   sudo systemctl stop intelli-rfid-tunnel && sleep 3 && pgrep -x java   # must print nothing
   ANT=1 /home/intelli-sbc/api/run/run.sh ProbeBasic
   ANT=2 /home/intelli-sbc/api/run/run.sh ProbeBasic
   ```
   Weakness follows the cable → replace the cable. Weakness stays on J20 → it is the board's J20
   connector or that arm of the SP4T. **Then put the unit back to ANT1** (`pinctrl set 8 op dh`,
   `9 op dl` in the unit file) so the documented default is the live one again.
2. **Re-derive `settle-ms` — but OPEN THE WINDOW FIRST. Done as far as the existing spool allows
   (2026-09-08); the answer is that the spool cannot answer it.** The "sort `firstSeen`, diff, take
   the worst, double it" recipe is **circular when run on cartons read at the window being tested**:
   a gap longer than `settle-ms` cannot appear, because the window closed the carton and the late
   tags are simply missing from the result. All seven 38-article cartons were read at 800, so they
   can only ever confirm 800.

   What the whole spool does say (416 SETTLED cartons, full table in `CLAUDE.md`): the honest
   evidence for 800 is the **39 cartons of 09-01…09-04 that ran at a 1500 ms window**, where a
   longer gap was free to appear and the worst was **567 ms** — a 1.4× margin, not the 2× claimed.
   The 08-29/08-31 cartons show 18 gaps between 800 and 1503 ms, and **RSSI does not explain them**
   (median −44 vs 09-07's −43), so that is a configuration difference — `session: 2` is the prime
   suspect — not the bad antenna branch. Encouragingly, the 29–38 tag cartons had the *shortest*
   gaps of all (median 200 ms).

   **To actually close it:** set `settle-ms: 1500`, run a batch of full 38-article cartons, read the
   gap distribution off *those*, then bring the window back to twice the worst. Do it over the
   matched tags only — foreign tags no longer hold the window open.
3. **Antenna multiplexing is still unwritten.** Nothing drives GPIO8/9 at runtime, so the second
   antenna is dead weight. `docs/Hardware-IntelliRFIDv2.md` §7.3 has the design question: measure
   stop-inventory → toggle → restart, then pick a dwell from that number. Start/stop is 0–3 ms and
   20–60 ms measured, and bare start/stop is NOT rate-limited, so this is cheaper than §7.3 assumes.
4. ~~`intelli-rfid-reader-test` ships `company-prefix: 8905527`~~ **DONE 2026-09-08** — it ships
   `8909478` now, matching the tunnel, so the bench harness will commission the SKU the tunnel
   writes. Tests pass.
5. ~~`SuccessExitStatus=143` in the unit file~~ **DONE 2026-09-08** — a clean `systemctl stop` will
   report `inactive` rather than `failed`. **Takes effect on the next `redeploy.sh`**, which is what
   reinstalls the unit file and reloads systemd.

### What shipped this session

- **SDK v260827** in core and tunnel (`com.uhf:module-api-j:2.6.0827`). No API signature changed;
  2.6.0721 is still in `~/.m2` so rollback is one pom line. It did **not** fix the deafness.
- **The site config was loading TWO `.so` files** — `native-lib-path` into the old SDK tree plus
  `-Djava.library.path=/opt/intelli/lib`. Byte-identical until now, two different versions after the
  upgrade. Both now point at `/opt/intelli/lib`.
- **The shipped SKU allowlist is gone.** `rfid.gs1.valid-eans: []`, so the reader arms for whatever
  EAN the WMS sends. `PackagedConfigTest` fails the build if a customer's SKUs reappear there.
- **Settle is scoped to the armed SKU, in two phases.** Foreign tags no longer extend a carton —
  but only once an article of the SKU has actually been heard, because scoping from t=0 closes
  shadowed cartons early and makes `stopReason` report SETTLED where it should report TIMEOUT.
- 251 tunnel tests, 61 core tests, all passing.

### The measurement, so it is not re-derived

Nine Super Fast cartons on the deployed jar, ANT2, v260827:

| seq | stopReason | tags | matched | lastNewTagMs | RSSI |
|---|---|---|---|---|---|
| 855 | SETTLED | 18 | 18 / 18 | 801 | −51…−29 |
| 856 | SETTLED | 29 | 29 / 38 | 801 | −51…−26 |
| 858 | SETTLED | 34 | 34 / 38 | 832 | −50…−31 |
| 859 | SETTLED | **38** | **38 / 38** | 806 | −49…−25 |

Carton time 2.09–2.98 s. `lastNewTagMs` 801–883 against `settle-ms` 800 — the watchdog's ~100 ms
tick, matching 09-04. First 38-article carton this project has read; the previous largest was 18.

---


## ⚠ 2026-09-05 — THE FIELD IO WAS REWIRED ON SITE. READ THIS BEFORE ANYTHING BELOW IT.

Bench testing at the site required a change of wiring, and it invalidates several statements further
down this file. The channel map now is:

| Ch | BCM | Was | Is |
|---|---|---|---|
| OUT1 | 26 | `EnC_ExC_RUN` — both belts on one channel | `EnC_RUN` — Entry Conveyor alone |
| OUT5 | 21 | `LAMP_PASS` green | `ExC_RUN` — Exit Conveyor Run A |
| OUT6 | 12 | `LAMP_FAIL` red | `LAMP_PASS` green |
| OUT7 | 13 | parked spare | `LAMP_FAIL` red, **and the shutdown lamp** |
| IN4 | 25 | parked spare | `EXIT_FULL` ← the Discharge Sensor (DsS) |

OUT2/3/4 and IN1/IN2/IN3 are unchanged.

**Why:** there is no end stop on the Exit Conveyor, so a carton reaching the discharge edge with the
belt running goes on the floor. DsS has to be able to stop the ExC *without* stopping the EnC, and a
shared O1 made that impossible.

**What follows.** The line is **no longer serialised** — the previous carton can discharge while the
next is read. **J26 is full**: O7 was the last free output and the earmarked home for the 1 Hz
liveness heartbeat, and it is spent. Every claim below that O7 or IN4 is parked, spare or earmarked
is **superseded**, including §3 and next-action 5.

**The exit interlock is built (`033351c`), to the operator's policy of 2026-09-05 — one package at
a time:** IN4 asserting stops the ExC in any phase and disturbs nothing else, a read always runs to
completion, a read closing against a still-occupied edge stops the whole line with the carton held
in the read zone, and it all resumes by itself when the edge clears. The result is published either
way. IN4 is a **sampled level** on its own thread, not a `gpiomon` edge, which is what makes it
independent of the `active-low` question. **The EnC still restarts at read close** rather than at
the IN2 edge — operator's call, "fine for now", and now a choice rather than a constraint.

**Also still open: the input polarity.** `tunnel.v1.gpio.active-low` is `false` and the two accounts
of the wiring still disagree (see `application.yml`'s own comment). The deciding measurement is one
line, and IN4 makes it cheap because nothing holds line 25: `pinctrl get 25` with the DsS beam clear
and blocked, no need to stop the app.

**Deployed?** The tunnel commits are pushed. Whether `deploy/redeploy.sh` has been run is not
recorded here — check the running jar. **Until it is, `/usr/lib/systemd/system-shutdown/intelli-lamp.shutdown`
still writes BCM 12**, which now darkens the *green* lamp at poweroff and leaves the red one lit for
ever.

---

## The state of the unit right now

**The app is running and healthy.** `intelli-rfid-tunnel` active, **PID 1031**, listening on 8081,
started **17:44:52**. The jar is still the one deployed at 15:51 from commit `19f3a3d` — the restart
was a reboot, not a redeploy.

**The board went down and came back at ~17:44, and nobody asked it to.** That is the *second* power
event of the day and unlike the 15:23 one it was not a test: it killed the Claude Code session
mid-work, which is how `intelli-wms-test` came to be sitting on disk uncommitted. The reader
reopened cleanly on its own (`Reader open: module=MODOULE_NONE fw=20.26.03.30`, inventory started).
**Cause not established.** The clock disagrees with itself across `who -b` (17:44), `ps` (17:48) and
the log (17:44:52), which is the no-RTC signature of a cut rather than an ordered shutdown — but
`journalctl` is volatile here, so the transcript that would settle it is gone. **Item 3 below is
what makes the next one diagnosable; do it before chasing this one.**

**The earlier power cycle at 15:23 was deliberate** — the IN3 shutdown test. See "what this session
found" below, because that test is what the whole shutdown-safety session came out of.

**Deployed and live:**

- The late shutdown-lamp hook at `/usr/lib/systemd/system-shutdown/intelli-lamp.shutdown` (0755,
  installed 15:51). `intelli-shutdown-lamp.service` is gone — `systemctl is-enabled` says
  `not-found`, which is correct and is what you want to see.
- Step 5 of the shutdown sequence now runs `/bin/sync`.

**Committed and pushed but NOT deployed:** `e71a5f2`, which parks O7. ~~It rides along on the next
`deploy/redeploy.sh` and needs nothing special.~~ **SUPERSEDED 2026-09-05** — O7 is the red and
shutdown lamp now, so that commit's premise is gone. It is history in the branch, not something to
deploy on its own.

---

## What this session found, in the order it mattered

### 1. The IN3 shutdown is a proper OS shutdown. The lamp was the problem.

The question that started it was whether the IN3 poweroff is "like a power cycle". **It is not** —
it runs `sudo systemctl poweroff`, identical to `sudo poweroff`, and the app's own five steps take
120 ms with the full OS phase after them. What makes it *feel* instant is the comparison: bare
`sudo shutdown` is `shutdown -h +1` and waits a whole minute.

**But `intelli-shutdown-lamp.service` was putting O6 dark one phase too early.** It was ordered
`After=umount.target Before=final.target`, which is systemd's *first* phase; the root filesystem is
remounted read-only and synced in the *second*, inside `systemd-shutdown`, after `final.target`. So
the lamp said "24 V may be removed" while `/` was still mounted rw with dirty pages. Fixed by moving
it to `/usr/lib/systemd/system-shutdown/`, which `systemd-shutdown` runs after that remount. Full
reasoning is in `CLAUDE.md` and in the script's own header.

**Step 5 also never synced.** It was called "leave storage safe to interrupt" but only awaited
`CallbackSender.awaitQuiet()`, which is network quiescence. `JsonlSpool.append` has no fsync and
`dirty_expire_centisecs` is 3000, so up to 30 s of carton results could be in page cache. Now
syncs, injected as a `Runnable` so the tests pin the ordering.

### 2. There was a hard power cut at ~15:17 today, before the IN3 test

Not caused by the shutdown — established by the spool: the JVM that booted afterwards logged
`resuming from sequence 802`, so record 802 and the NUL bytes after it were already on disk before
that boot. Two files carry NUL holes from it:

| File | Damage | Done? |
|---|---|---|
| `/opt/intelli/logs/intelli-rfid-tunnel.log` | 3377 NUL bytes mid-file | left alone, it is a log |
| `/var/lib/intelli/tunnel/spool/inventory-2026-09-04.jsonl` | 1689 NUL bytes at the tail | 🔴 **not trimmed** |

Everything else is clean: 1293 files scanned, `git fsck` clean on all five repos, jar intact, no
ext4 errors, no I/O errors, root mounted with no journal replay.

**To trim the spool tail** (safe with the app running — it only appends):

```bash
cp /var/lib/intelli/tunnel/spool/inventory-2026-09-04.jsonl{,.bak}
truncate -s 194919 /var/lib/intelli/tunnel/spool/inventory-2026-09-04.jsonl
```

It is harmless as it stands — both `JsonlSpool` read paths catch the bad line and skip it at DEBUG —
which is exactly why it would otherwise sit there forever.

### 3. O7 was parked; the panel drawings said otherwise — SUPERSEDED 2026-09-05

O7 had carried no traffic since the one-lamp decision on 2026-09-04, but still declared
`SAFE_TO_POWER_OFF`, so `isParked()` was false and `docs/Tunnel-Interconnect.md` v0.5 still told the
panel builder to fit a lamp beside the shutdown button. Built to that drawing, an operator would
read a dark `SAFE_TO_POWER_OFF` as "not yet safe" and wait forever, next to the lamp that was
actually telling them. It was parked in code and withdrawn from every document.

**That lasted one day.** The site rewiring of 2026-09-05 made O7 the red lamp and the shutdown lamp,
so `isParked()` is false again — for a real reason this time — and a lamp *is* fitted there. Nothing
on J26 is parked any more.

**The heartbeat has lost its home, and this is the cost worth remembering.** O7 was earmarked
because the one capability this design lost and never replaced is the 1 Hz liveness signal that let
a watchdog stop the line after 3 s of silence and survived a hung JVM. There is no free output left
to put it back on. Getting it back now means RS-485 to the drive cards, which would free O1–O5 at
the same time.

### 4. `intelli-wms-test` — a sixth repo, written 17:33–17:46 and nearly lost

A new laptop app, port 8083: **a WMS reduced to arming Super Fast Mode and showing the carton that
comes back.** Tags expected, tags found, time taken, then every tag with EPC and TID. 20 files,
~2100 lines, `mvn package` green with tests, jar built at 17:46 in `target/`.

It is not a duplicate of admin's WMS simulator. Admin asks *does the reader behave*; this asks
*could a WMS integrator use it*, and answers it by holding **nothing but the INVENTORY key** and the
five documented endpoints. The full reasoning, and the two rules that stop it flattering the reader
(found is `matched.count`; the verdict pill is the reader's own `complete`), are in `CLAUDE.md`.

**It is a temporary app** — the customer's own integration replaces it, and it is disabled by
rotating the `site-wms` key on the reader (operator's decision, 2026-09-04). That is why the live
INVENTORY key is committed in its `application.yml` in plaintext: the jar is handed over and
double-clicked with no setup.

**It had no `.git` at all until 17:5x**, and that is the lesson worth keeping. It was written,
built, and left through a reboot with nothing tracking it — and the root `git status` stayed clean
the whole time, because the root repo ignores `apps/` by design. Nothing anywhere would have said a
word. **`git init` belongs to creating an app, not to finishing one**; at close-out, walk `apps/*/`
by directory and check each one *has* a repo, rather than iterating the repos that exist. Now
`db8e136` on `origin/main` at `.../v1/repos/intelli-wms-test`.

**Never run against a live reader.** Unit tests only. See next action 0.

---

## Next actions, in order

0. 🔴 **Run `intelli-wms-test` against this reader, end to end.** It has never met a real one — every
   claim in its README is unit-tested inference. The tunnel is up on 8081, the jar is built, and the
   bench population is 18 tags. What this first run is actually testing is the **callback path**,
   which is the half no unit test can reach: arm from the page, put a carton through, and see the
   result *arrive*. If the page sits empty with the reader reporting a perfect carton, the callback
   URL is the suspect before anything else — check `callbacks.jsonl` on the reader and remember that
   the spool replays independently of arm state, so a backlog from an earlier address will retry all
   day and read as the arm path being broken.

   Two known-honest failures to expect rather than debug: `expected-token` blank reports
   `NOT_CHECKED` (the tunnel sends no token today), and an empty TID column means FastID — which is
   on, so TIDs should appear.

1. 🔴 **Reconcile `power-off-os` in the site config.** `/etc/intelli/intelli-rfid-tunnel/application.yml`
   line 282 is `power-off-os: true`, and the comment block immediately above it says **"FALSE FOR
   NOW, deliberately"**. The value is what runs; the comment is what the next person believes. Same
   shape as the old `session: 2` drift. Needs root — the file is `root:intelli-sbc 0640`.

   Decide which is meant. **True is a real hazard on a bench unit**: a spurious IN3 hold powers the
   board off and it needs hands at the panel to come back.

2. **Watch O7 through the next IN3 shutdown** — the RED lamp, BCM 13. It was O6 until the
   2026-09-05 rewiring, and watching O6 now means watching the green PASS lamp, which does nothing
   during a shutdown. **This only works once `redeploy.sh` has reinstalled the shutdown hook**, since
   the installed copy writes BCM 12. This is the acceptance test for the lamp fix and
   nothing else proves it. Expect blinking → solid → **dark**, with a visibly longer gap before
   dark than before — that gap is the root remount-ro and final sync you were previously being
   invited to interrupt. If dark never comes, check the hook is still 0755: `systemd-shutdown`
   silently skips a file it cannot execute.

3. **Make journald persistent.** `/var/log/journal` exists but is empty, so journald writes to
   `/run` and every shutdown's transcript dies at the next boot. That is why item 2 has to be
   watched by eye rather than read out of a log afterwards.
   ```bash
   sudo systemd-tmpfiles --create --prefix /var/log/journal && sudo systemctl restart systemd-journald
   ```
   After that, `journalctl -b -1` answers "did that poweroff unmount cleanly?" in one command.

4. **Trim the spool tail** (§2 above), or decide to leave it.

5. **WITHDRAWN.** This said "deploy `e71a5f2`, which parks O7". Deploying that commit *as written*
   would blank the channel the red and shutdown lamps now live on. It has been superseded by the
   2026-09-05 rewiring commits, which are what `deploy/redeploy.sh` will pull.

6. **Consider fsync per spool append.** The step-5 sync covers the shutdown path, but a carton
   result is still only durable within ~30 s of an unexpected cut. That is a hot-path change (one
   fsync per carton on eMMC) and a separate decision from anything done this session.

7. **Still open from before:** the EnC stop delay versus EnS placement (a carton is dragged if EnC
   stops the instant EnS fires) — unchanged, and still wants the real geometry.

   **The discharge-starts-EnC consequence of the module-fault path is now solvable rather than
   solved.** It was forced while EnC and ExC shared O1; they are separate channels since 2026-09-05,
   so the fault path *can* raise O5 alone. Nothing does it yet, and `setBelts()` is where it goes.

8. **Done — the IN4 discharge interlock is built** (`033351c`), see the banner. What is *not* done
   is proving it against the real sensor: `pinctrl get 25` with the beam clear and blocked, then a
   carton driven to the edge to watch O5 drop. Until that runs, the interlock is correct in tests
   and unwitnessed on hardware.

9. **Derive `tunnel.field.exit.sample-ms` from the geometry.** It is 250 ms, which at 0.5 m/s is
   125 mm of travel past the beam before the belt is told to stop. Measure beam-to-edge, divide by
   the ExC's linear speed, halve it. If the answer is under ~100 ms the sensor is too close to the
   edge and moving it is the fix.

---

## Traps this session added to the pile

- **A NUL run inside a text file is the fingerprint of a hard cut**, and it dates the cut. ext4
  journalled the inode's new size but the data blocks never landed. Nothing logs it and the app runs
  straight over it.
- **The CM4 has no RTC that survives an unclean cut**, so the boot after one restores a stale
  timestamp and the log appears to run *backwards*. Two files stamped 15:17 can sit after a boot
  line stamped 15:15. **Order by PID, not by clock** — a low PID means a fresh boot.
- **`systemd-shutdown` silently skips a non-executable file** in `system-shutdown/`. The symptom is
  a lamp that never goes dark on a board that is off, which reads as a hung shutdown and appears in
  no log at all.

---

## Repositories

**Six now, not five** — and one of them did not exist as a repo an hour ago. All clean and pushed.

| Repo | Head |
|---|---|
| `intelli-rfid-reader` (docs) | 2026-09-05: the rewiring across `CLAUDE.md`, `docs/` and this file |
| `intelli-rfid-tunnel` | 2026-09-05: `cbe8343` the rewiring, then the O5 diagnostic-write warning |
| `intelli-rfid-core` | `b058f42` unchanged |
| `intelli-rfid-reader-test` | `940c4d8` unchanged |
| `intelli-rfid-admin` | `f843370` lamps moved up a channel, BELTS pill added |
| `intelli-wms-test` | `db8e136` **root commit** — new today |

`intelli-rfid-wayside` is a sixth app in the layout table but **is not checked out on this CM4**; do
not read its absence as a deleted repo.

**Walk `apps/*/` by directory when you do this, not the list above.** The root repo ignores `apps/`,
so an app with no `.git` is invisible to every status command you would think to run — which is
exactly how `intelli-wms-test` survived a reboot on luck alone.
