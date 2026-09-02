# Resume here — CM4 session, next sitting

**Rewritten 2026-09-02 at the end of the PLC-removal session.** Everything below is either measured
on this hardware or read from the tree; where it is inference it says so.

The previous version of this file was a work list for the PLC interface. **That interface no longer
exists** — see `CLAUDE.md` "Naming — the Reliance warehouse tunnel". The documents it pointed at
(`HANDOFF-LAPTOP-TO-CM4-TUNNEL-05.md`, `PLC-INTEGRATION-DVP12SA2.md`,
`docs/PLC-Digital-IO-Interface.md`) have been deleted; git history has them if a number is ever
needed. `docs/Intelli-RFID-Reader-DVP12SA211R-PLC-Integration.docx` is kept as the record of what
was actually issued to the PLC vendor on 2026-08-30, and nothing is written against it any more.

---

## The state of the unit right now

**The app is NOT running.** `intelli-rfid-tunnel` shows `failed`, but it did not crash: it was
stopped deliberately at 22:16:52 on 2026-09-02 after 5 h 43 min up, and exit 143 is SIGTERM. The
unit file simply does not list 143 as a success code. No `java` process, nothing on 8081.

🔴 **The installed jar is from 2026-09-01 19:59 and is well behind the tree.** Its shutdown log line
is `c.i.rfid.tunnel.plc.HeartbeatDriver` — a class that no longer exists in source. **The board is
still running the old PLC firmware**: 1 Hz heartbeat on OUT6, width-encoded verdict on OUT5, and the
five-pulse IN3 burst. Nothing described below is live until `deploy/redeploy.sh` runs.

🔴 **`/etc/intelli/intelli-rfid-tunnel/application.yml` still has a `plc:` key, and it now binds
nothing.** The prefix is `tunnel.field.*`. Spring ignores unknown properties, so this fails
**silently** and every value in that block reverts to its packaged default — including
`disable-input-pulls`, which matters on this carrier. The block also still carries `heartbeat:` and
`result:` sections for beans that no longer exist. **Fix this before the next deploy.** It needs
root; the file is `root:intelli-sbc 0640`.

---

## What changed this session

The whole of it was one job: **remove the old PLC logic from code and markdown**. Nothing was run
against the module.

### Code

- **The field package is renamed.** `com.intelli.rfid.tunnel.plc` → `…tunnel.field`,
  `PlcProperties`/`PlcConfiguration` → `FieldProperties`/`FieldConfiguration`, prefix `tunnel.plc.*`
  → `tunnel.field.*`. Actuator logger path is now
  `/actuator/loggers/com.intelli.rfid.tunnel.field`.
- **IN3 is a held button, and the burst is deleted.** `ShutdownRequestMonitor` samples
  `FieldIo.read(IN3)` every 250 ms on its own thread; a request is the line asserted continuously
  for `hold-ms` (5000). Releasing abandons the hold — nothing is banked. Two start-up guards:
  `require-release-first` (a hold may only begin from an observed released→asserted transition, and
  the verdict is latched at the *start* of the assert) and `startup-grace-ms` (30 s). Uptime is
  measured from the **first sample**, not from construction, so the grace and the samples share one
  clock. `pulses` / `window-ms` / `quiet-ms` are gone.
- **IN3 is off the `gpiomon` command line.** A level is what is being measured, and reading it
  through `pinctrl` also stays clear of the exclusive claim `gpiomon` takes on the lines it watches.
  `tunnel.v1.gpio.shutdown-line` is removed.
- **Verdict lamps are a 5 s dwell.** `VerdictLamps` lights green on pass or red on fail, puts the
  other out, and schedules it dark after `tunnel.field.lamps.hold-ms` (5000) on its own daemon
  thread — never the caller's, which has just closed a carton and is on its way to releasing the
  conveyor. A new verdict cancels the previous dwell, so back-to-back cartons each get a full 5 s.
  `hold-ms: 0` latches, which is the previous behaviour. **The dwell carries no meaning** — the
  channel says pass or fail — which is what makes a timer safe here and is the whole difference
  from the width-encoded RESULT it replaced. `HeartbeatDriver` and `ResultSignal` are gone.
- **The admin Field I/O tab no longer holds a copy of the channel functions.** It keeps pins and BCM
  numbers — a property of the board — and takes the `function` string from
  `GET /api/v1/diagnostics/io` on every Read, so the screen cannot drift from `FieldChannel` again.
  That drift is exactly why it was still showing `SPEED0 (LSB)`. The `SPEED n of 7` pill is replaced
  by an **RZC** pill (100/75/50/STOP from the O2+O3 pair, reverse shown only while moving) and a
  **LAMPS** pill that flags "both lit" as a wiring fault.
- **`ScopeRules`**, `CartonRelease` and `GpioEdgeMonitor` prose updated. No behaviour change in core.

**Tests: tunnel 150 pass, core 61 pass, admin 37 pass.** `VerdictLampsTest` is new (8 tests, and it
waits on the lamp going out rather than sleeping a fixed time). `ShutdownRequestMonitorTest` is rewritten for the hold —
10 tests, driven through a package-private `sample(asserted, nowNanos)` so the clock is the test's
and none of them sleep. `FieldChannelTest` now pins every committed function individually rather
than pinning a disagreement with deleted documents.

### Markdown

- **Deleted:** `PLC-INTEGRATION-DVP12SA2.md`, `docs/PLC-Digital-IO-Interface.md`,
  `HANDOFF-LAPTOP-TO-CM4-TUNNEL-05.md`.
- **Rewritten in place:** `CLAUDE.md` (field interface section, IN3 rules, verdict lamps, the
  heartbeat loss), `docs/CM4-Bench-Test-Harness-Handoff.md` (§1, §2, §3, §7.2 and the §8/§11 work
  lists are now records of work done), `docs/Hardware-IntelliRFIDv2.md` (§2.1 pinout, §5 drive
  analysis, §14 findings, §15 open questions).
- **Bannered as superseded in premise, not rewritten:** `docs/Machine-Controller-Option.md` (marked
  **adopted** — it is the rationale for the current design), `docs/Field-Output-Interposer.md`,
  `docs/Board-v3-Digital-IO-Change-Request.md`, `docs/Board-Warehouse-Variant-Proposal.md`. Their
  PLC references are the context they were argued in, and the electrical reasoning is still sound.

---

## Next, in order

1. **Fix the site `application.yml`** (root). Rename `plc:` → `field:`, delete the `heartbeat:` and
   `result:` blocks, and replace the `shutdown:` block's `pulses`/`quiet-ms` with `hold-ms: 5000`.
   Compare against `apps/intelli-rfid-tunnel/src/main/resources/application.yml`, which is fully
   commented.
2. **Deploy** — `cd ~/rfid/intelli-rfid-reader/apps/intelli-rfid-tunnel && deploy/redeploy.sh
   --core`, as `intelli-sbc`, never under sudo. Core changed this session, hence `--core`.
3. **Verify the rename took.** `GET /api/v1/diagnostics/io` should return the Reliance functions
   (`EnC_ExC_RUN`, `LAMP_PASS`, …), and `/actuator/loggers/com.intelli.rfid.tunnel.field` should
   resolve rather than 404.
4. **Bench-test the held button (bench test 6's shutdown item).** A 4 s press must do nothing; a 5 s
   press must run the sequence and light O7; the input shorted to 24 V at boot must **not** shut the
   unit down, and releasing it afterwards must arm the button rather than leave it dead. Set
   `logging.level.com.intelli.rfid.tunnel.field: TRACE` first — TRACE is the only level that records
   an individual sample.
5. **`session: 1` in the site config** (§3A.3 of the bench handoff). The committed default still says
   `2` and the rig runs `1` by hand; that drift has been noted in `CLAUDE.md` for days.
6. **The trigger edge.** Decided 2026-09-02 to fix in software — `gpiomon -l` / `--active-low` on
   both libgpiod majors, behind `tunnel.v1.gpio.active-low`, default true. Until it lands, a carton
   opens its read window on beam *clear*.
7. **`ConveyorController` and a real `CartonRelease`** — the O1 state machine and the fault
   behaviour. `docs/CM4-Bench-Test-Harness-Handoff.md` §7, §8.3.

---

## Things that will bite, collected

- **A stale `plc:` key in a site config fails silently.** Spring ignores unknown properties. There is
  no warning anywhere; the symptom is defaults where you expected overrides.
- **`gpiomon` holds its lines exclusively**, so a probe run while the app is up fails with `Device or
  resource busy` — that failure is a sign the app is working. IN3 is no longer among those lines.
- **The internal-pull trick for faking an edge does not work on this carrier** — the external 10 kΩ
  pull-up dominates. Drive the pin instead: `pinctrl set 18 op dl` then `op dh`, then back to
  `ip pd`.
- **Check `pgrep -x java`, never `pkill -f`** — the latter matches Claude's own wrapper shell.
- **Ask the operator to start and stop the app.** Claude Code here cannot hold a long-running JVM
  across tool calls and cannot `sudo` (no tty).
