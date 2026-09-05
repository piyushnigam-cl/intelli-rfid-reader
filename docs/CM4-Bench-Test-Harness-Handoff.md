# Bench Test Harness — handoff to Claude Code on the CM4

**You are the session with the hardware. Prefer running the thing over reasoning about it.**
This was written on the laptop against the source, so every claim about *code* here was read from
the tree and is reliable; every claim about *module or conveyor behaviour* is inference and is
marked. Where the hardware contradicts this document, the hardware is right — fix it and write the
correction back into `CLAUDE.md`.

Version 2.1 · 2026-09-02 · for `apps/intelli-rfid-tunnel` and `apps/intelli-rfid-admin`

Changed in 1.1: session 1 measured clean (§3.3) · trigger edge confirmed (§3.1) · Double Pass is three
passes with per-pass attribution (§5) · fault behaviour decided (§7.1) · the four proposed tests are
now Tests 3-6 (§6).

Changed in 2.0, and this is a substantive revision: §2 and §3 were rewritten against `origin/main`
after 17 tunnel and 6 core commits landed. The whole field-IO layer already exists, the carrier is
already triggered rather than continuous, and five claims from v1.0 are withdrawn (§3A.6).

Changed in 2.1: reframed — this is the job of making the tunnel app the machine controller, and the
tests are its acceptance criteria (§1, §14).

Changed in 2.2 (2026-09-02, on the CM4): **§3 and §7.2 are now records of work done, not
instructions.** The channel map is migrated, the field package is renamed to
`com.intelli.rfid.tunnel.field` / `tunnel.field.*`, the verdict lamps hold levels, the heartbeat and
the width-encoded RESULT are deleted, IN3 is a held button, and the admin tab takes its labels from
the reader. No profile switch was built and none should be. §8's work list is updated to match.

Changed in 2.3 (2026-09-05): **the site was rewired and every output from O5 down moved** (§3). The
Exit Conveyor has its own channel, the lamps are O6/O7, and IN4 carries a third W26 — the Discharge
Sensor. **Any test step in an earlier copy of this document that names a lamp channel names the
wrong one**, and the step that treated IN4 as a spare to prove continuity on now has a real sensor
in front of it. J26 is full.

---

## 1. What changed this morning, and what it means for this app

**The PLC is bypassed. The reader is now the machine controller.**

The tunnel app was built against a PLC interface: it emitted a 3-bit speed word, a width-encoded
verdict and a heartbeat, and another machine decided what the conveyor did. **There is no longer
another machine.** The Intelli-RFID Reader drives three EZY-S100 driver cards through the Tunnel
Manager, reads **three** SICK W26 sensors, lights two lamps, and owns the conveyor state machine
itself. `docs/Tunnel-Interconnect.md` is the wiring; `CLAUDE.md` has the names and the J26 remap.

**So this is not a bench-harness job with some incidental refactoring. It is: make the tunnel app the
machine controller, then prove it with six tests that must pass.** The tests are the acceptance
criteria for the change, not a separate activity — §13 says what "pass" means for each one.

Three consequences worth stating before anything else:

- **The field-IO layer is `com.intelli.rfid.tunnel.field`, binding `tunnel.field.*`** — renamed
  2026-09-02, along with `FieldProperties` and `FieldConfiguration`. 🔴 **A site `application.yml`
  written before that date still has a `plc:` key, which now binds nothing.** Spring ignores unknown
  properties, so this fails **silently** and every value in that block reverts to its packaged
  default. Check `/etc/intelli/intelli-rfid-tunnel/application.yml` before blaming the pins.
- **Nothing outside this app uses the layer.** `intelli-rfid-core`, `-wayside` and `-reader-test`
  contain no reference to it, and `-admin` reaches it only over `/api/v1/diagnostics/io`. It is the
  tunnel app's alone, and the tunnel app is the Reliance product.
- **The customer contract does not move.** `/api/v1/**` is unchanged. The new test surface is
  `/api/test/**`, ADMIN scope.

## 2. What already exists — verified against `origin/main`, 2026-09-02

**v1.0 of this document was written against a tree 17 tunnel commits and 6 core commits out of
date, and several of its "findings" were already fixed.** This section replaces it. Everything below
was read from `origin/main` in both repos.

**The whole field-IO layer exists.** `com.intelli.rfid.tunnel.field`:
- **`FieldIo`** interface — `write`, `diagnosticWrite` (the only way to drive a *parked* channel —
  **and since 2026-09-05 there are none**, so every `diagnosticWrite` now lands on something with a
  committed function), `read`, `readAll`, `problem`, `isUsable`. Everything above it speaks **field
  sense**, never GPIO level. That is the inversion boundary this document asked for; it is built.
- **`PinctrlFieldIo`** — shells `pinctrl`, one process per call. Chosen over `gpioset` deliberately:
  `pinctrl` writes the pad registers so a level survives process exit, and it does not contend with
  the `gpiomon` holding lines 23/24.
- **`FieldChannel`** — the channel map, as a **hard-coded enum, explicitly not configurable**.
- **`VerdictLamps`** (**O6 green / O7 red**, latched levels — both moved on 2026-09-05),
  **`ShutdownRequestMonitor`** (IN3, a sampled level) + **`ShutdownSequence`** + **`ShutdownLamp`**
  (O7, sharing the red lamp), **`DiagnosticsIoController`** (`/api/v1/diagnostics/io`, ADMIN scope).
- `tunnel.field.*` config: `enabled`, `command`, `disable-input-pulls`, plus `lamps.*` and
  `shutdown.*` blocks.

**The carrier is already triggered, not continuous.** `tunnel.v1.triggered-carrier: true`. Armed and
idle means the antenna is **off**; it comes up on the IN1 edge via `ensureReading()` and drops in
`onSuperFastCarton`. Disarming returns it to continuous. This matters for two things in this
document — see §3.3 and Test 5.

**Fault recovery is real.** `FaultRecoveryPolicy` + a `rfid-supervise` daemon thread; the backoff
resets only after `recover-stable-ms` of health, deliberately not on a successful reconnect.
`recover-on-fault` / `recover-max-delay-ms` / `recover-stable-ms` are **live keys**, not the dead ones
v1.0 claimed. `recoveries()` and `lastRecoveryAt()` are exposed.

**Still true and still needed:**
- `GET /api/inventory/completed?since=<seq>&limit=` reads the JSONL spool and returns whole
  `InventoryResult` records — **the report's data source. Do not build a new one.**
- `InventoryTag(epc, tid, reads, bestRssi, antennas, firstSeen, lastSeen)` for **every** tag.
- `CartonRelease` **is still a logging-only stub**, called before the carrier drop and the verdict.
- The admin app: `/proxy/**` with the key injected server-side, `CallbackController` as a WMS
  simulator with runtime delay/status, `V1Contract` + `POST /api/admin/validate`, and a UI of three
  static files with no build step. No charting library anywhere.

**The width instrumentation is gone with the pulse.** `ResultSignal`'s `outOfBand` / `lastWidthMs`
counters existed because a 500 ms pulse delivered at 380 ms was silently a FAIL; lamps hold a level,
so there is no width to measure and nothing to be out of band. The 2026-08-31 baseline (PASS
496–504 ms, FAIL 98–100 ms over 20 cartons) is now only of historical interest — **and bench test 6
no longer needs its 100-carton timing run.** Assert the lamp *state* after each carton instead.

## 3. ✅ The channel map migration — DONE, 2026-09-02

`FieldChannel` now carries the Reliance functions outright. There is no profile switch and no legacy
map: the earlier plan for `profile: TUNNEL | PLC` was dropped once it was clear the field package
exists only in this app, and this app is the Reliance product. A map you can select is a map that
can come up wrong.

**Updated 2026-09-05 — the site was rewired and this table moved with it.** Anything below O4 is at a
different channel than it was; the earlier layout is in §3.1a.

| Ch | BCM | Function | Note |
|---|---|---|---|
| OUT1 | 26 | `EnC_RUN` | the Entry Conveyor **alone**. **Normally asserted** |
| OUT2 | 20 | `RZC_RUN_A` | with O3, the speed ladder |
| OUT3 | 16 | `RZC_RUN_B` | A alone 100 %, A+B 75 %, B alone 50 %, neither stop |
| OUT4 | 19 | `RZC_REVERSE` | a level, meaningless while the RZC is stopped |
| OUT5 | 21 | `ExC_RUN` | the Exit Conveyor. **Was `LAMP_PASS`** |
| OUT6 | 12 | `LAMP_PASS` | green, latched. **Was `LAMP_FAIL`** |
| OUT7 | 13 | `LAMP_FAIL` | red, latched — **and the shutdown lamp**, blinking / lit / dark. **Was parked** |
| IN1 | 23 | `ENTRY_SENSOR` | unchanged |
| IN2 | 24 | `EXIT_SENSOR` | unchanged |
| IN3 | 18 | `SHUTDOWN_REQUEST` | unchanged, a sampled level |
| IN4 | 25 | `EXIT_FULL` | the Discharge Sensor (DsS), a third W26. **Was parked** |

**Three behavioural changes came with it, and none of them would have fallen out of a rename.**

- **Speed is a pair of run lines, not a word.** There is no 3-bit encoder anywhere any more; three
  speeds on RZC only, and O1 and O5 are plain run/stop for EnC and ExC. Anything that still thinks
  in `0..7` is a bug.
- **The lamps are a 5 s dwell, and the dwell carries no meaning.** `VerdictLamps` lights one, puts
  the other out, and schedules it dark after `lamps.hold-ms` on its own daemon thread — never on the
  caller's, which has just closed a carton and is on its way to releasing the conveyor. The
  `outOfBand` counter and the spin-the-last-2-ms hold are gone with the width encoding: the *channel*
  says pass or fail now, so a hold that runs long or short is a lamp lit a moment longer rather than
  a wrong answer. `hold-ms: 0` latches. Do not encode anything in the duration.
- **There is no liveness heartbeat, and that is a real loss.** The 1 Hz toggle was a *hardware*
  liveness signal that survived a hung JVM; nothing replaces it, and the reader's liveness is now
  only visible over HTTP. It is acceptable because the failsafe still holds — outputs reset low, so
  a dead reader stops the line rather than running it — but it was a decision, not an accident.
  🔴 **And as of 2026-09-05 it can no longer be given its own channel.** O7 was the last free
  output and the earmarked home for it; the red lamp has it now. Bringing the heartbeat back costs
  a board change or the SAMD21, not a config key.

**Renamed with it:** the package is `com.intelli.rfid.tunnel.field` and the prefix is
`tunnel.field.*`. See the warning in §1 about a stale `plc:` key in the site config.

### 3.1a The 2026-09-05 rewiring — what moved, why, and what did *not* change

| Ch | Was | Is |
|---|---|---|
| OUT1 | `EnC_ExC_RUN`, both belts on one channel | `EnC_RUN` |
| OUT5 | `LAMP_PASS` | `ExC_RUN` |
| OUT6 | `LAMP_FAIL` | `LAMP_PASS` |
| OUT7 | parked spare | `LAMP_FAIL`, and the shutdown lamp |
| IN4 | parked spare | `EXIT_FULL` ← DsS |

**Why.** There is no end stop on the Exit Conveyor, so a carton reaching the discharge edge with the
belt running falls off. The ExC had to become stoppable without also stopping the EnC, and the shared
O1 made that impossible. DsS is a SICK W26 at the far edge of the ExC, landing exactly like EnS and
ExS: M12 4-pin on `cd-390`, pin 1 `brn` = +24 V control, pin 3 `blu` = control 0 V, pin 4 `blk` =
switching output to the TM input terminal, pin 2 `wht` = MF, left open and insulated.

**The side effect is the one that matters to Test 5: EnC and ExC need no longer be serialised.** The
previous carton *can* discharge while the next is being read, so cycle time need not be read *plus*
discharge — the copper no longer forces it. Read the next paragraph before believing the stopwatch
will show that yet.

> 🔴 **The subtlety that will otherwise be mis-tested. The software still commands the two belts
> TOGETHER.** `ConveyorController.setBelts()` writes O1 and O5 identically — one seam, one value —
> so **observable belt behaviour is exactly what it was before the rewiring**, and every O1
> expectation in the tests below holds for O5 as well. The copper is split; the commands are not.
>
> **Assert both channels anyway.** A test that only reads O1 would pass with O5 stuck, dead, or
> mis-landed at the TM, and the whole point of the rewiring is that O5 exists.
>
> Two decisions are **open** before the seam is actually split, and neither is guessed at here:
> whether a blocked exit (IN4 asserted) should also hold the RZC and the EnC — back-pressure — and
> whether the EnC should stay stopped until the IN2 exit edge rather than restarting at read close.
> **Do not test for behaviour that has not been decided**, and do not read the split copper as split
> behaviour.

**IN4 is wired and not yet consumed.** Nothing in the tunnel app reads `EXIT_FULL` — it appears on
`/api/v1/diagnostics/io` and in `IoSnapshot`, and no logic acts on it. That makes its polarity
un-exercised, which is the worst way for a sense error to wait: prove the level by hand at
commissioning (occupy the discharge edge, confirm the reader reports IN4 asserted) **before** any
code depends on it. A wrong sense here does not mis-time a read, it drives a carton off the end.

**J26 is now full.** No spare output, no spare input. That closes off the liveness heartbeat above,
and it also means the old habit of proving continuity by pulsing a parked channel is gone — every
loop test now moves a belt, lights a lamp or reads a real sensor.

### 3.2 ✅ The admin Field I/O tab — DONE in the same change

`apps/intelli-rfid-admin/.../app.js` no longer holds a copy of the channel functions. It keeps only
pins and BCM numbers, which are a property of the board, and **takes the `function` string from
`GET /api/v1/diagnostics/io` on every Read** — so the screen cannot drift from `FieldChannel` again,
which is exactly how it came to be showing `SPEED0 (LSB)`.

The `SPEED n of 7` pill is gone. In its place: an **RZC** pill decoding O2/O3 as the drive card does
(100 / 75 / 50 / STOP, with reverse shown only while it is moving) and a **LAMPS** pill showing the
verdict pair — including "both lit", which is not a verdict the reader ever produces and is
therefore a wiring finding. The tab is `Field I/O`.

## 3A. Fixes still outstanding — verified, not assumed

### 3A.1 The trigger edge is still wrong 🔴 CONFIRMED STILL BROKEN

`GpioEdgeMonitor.commandLine()` no longer hardcodes `--rising-edge` — it detects libgpiod v1 vs v2
and emits `--edges=rising` or `--rising-edge` accordingly. **But there is still no active-low or
polarity option of any kind**, and `FieldChannel` documents inputs as inverted (field-asserted = GPIO
low). So the monitor watches a rising GPIO edge, which with the Reliance wiring is **beam clear**.
The two halves of the codebase disagree with each other and nothing reconciles them.

The operator has decided: **change it.** Add the polarity option — `gpiomon -l` / `--active-low`
works on both v1 and v2 — so "rising" means *the channel became active* and matches `FieldIo`.

### 3A.2 Static Super Fast Mode still cannot be triggered 🔴 CONFIRMED

Unchanged: with the sensors watching, nothing opens a session without an edge; without them, the mode
falls back to first-tag open and reports `degraded`. Add the test endpoint that pulses the lines
(§8.2). Two new details from the current tree:
- **`tunnel.field.disable-input-pulls` defaults to `true`**, which turns the internal pull-downs off on
  IN1–IN4 so the carrier's external 10 k defines the level. **On a bare bench with nothing wired to
  J26, set it `false` or IN1 floats and manufactures phantom cartons.** IN4 now carries a real sensor
  too, so on a bare bench it floats as well — harmless today because nothing reads it (§3.1a), and
  not harmless the moment something does.
- `tunnel.v1.gpio.debounce-ms` is 50 and **must not go past ~150**, or it eats the IN3 burst.

### 3A.3 Session — the config still says 2 🟠 CONFIRMED

`rfid.reader.session: 2` is still in `application.yml`, and the operator measures S1 clean. Change
it. Note what the current comment records, because it is the other half of the story: **continuous
carrier + session 2 read 15 tags once and heard nothing for three minutes.** The carrier-off window
between cartons is what resets the flag today — there is no Select doing it. With `triggered-carrier`
plus S1 you are protected twice over.

**The Gen2 Select is still absent.** `TagOperations.withFilter()` now exists, but it is a *match*
Select used only by commissioning to target a TID, cleared in a `finally`. Nothing resets an
inventoried flag. Per-pass attribution in §5 still wants it.

### 3A.4 `StreamRelay` still flattens events and sends no key 🟠 CONFIRMED

Unchanged in the admin app.

### 3A.5 There is still no carton-open event 🟠 CONFIRMED

`TagBroadcaster` publishes exactly three names anywhere in either repo: `subscribed`, `tags`, and
`inventory` (on close only). Nothing fires on carton open, the IN1 edge, arm/disarm, the verdict
pulse or a shutdown request. Zone entry is observable **only from the log line** `Carton entered the
zone: session {}` at INFO. Add the event.

### 3A.6 Withdrawn from v1.0 — do not act on these
- ~~"No code drives any J26 output."~~ False; `PinctrlFieldIo` drives all seven.
- ~~"`GpioEdgeMonitor` hardcodes `--rising-edge`."~~ False; it detects the libgpiod version. The
  *polarity* problem is real, the hardcoding claim was not.
- ~~"`ResultMapper` rewrites `endedAt` to `countReachedAt`."~~ Removed. `endedAt` is simply when the
  window closed, and `countReachedAt` and `settledAt` are separate fields.
- ~~"`recover-*` keys bind to nothing."~~ They are live.
- ~~"Put the IO screen at `/api/test/io`, not under `/api/v1`."~~ `/api/v1/diagnostics/io` is built,
  ADMIN-scoped and driven by the admin Field I/O tab. Leave it; do not churn a working screen for purity.

## 4. Test 1 — Static

The conveyor does not move. The tunnel is armed in Super Fast Mode. The operator enters a run count
and presses Test; the harness simulates that many cartons and reports each one.

**Screen inputs:** number of runs · interval seconds (default 30) · EAN · expected count · Gen2
session (S0/S1/S2) · a "reset inventoried flag between runs" checkbox once §3.3 is built.

**Per run, show:**
1. **Run number**, 1..N.
2. **Number of tags read** — and this needs care. Show **two** numbers side by side:
   - `matchingCount` — tags that decode as SGTIN-96 *and* match the armed GTIN-14. **Confirmed by the
     operator: this is the number the green/red verdict keys on**, against the expected count. Big,
     bold, green on equal and red on either side of it.
   - `tagCount` — everything that answered, rendered neutrally beside it.
   They will differ on this bench, badly: 16 of 18 tags are not GS1 at all. Comparing the wrong one
   is the bug that already shipped for an afternoon and logged a perfect carton as *"18 of 2
   articles, NOT trustworthy"*. Label them so nobody has to guess which is which.
3. **The tag table** — EPC and TID per tag, plus RSSI and reads because you get them free from
   `InventoryTag`. The TID arrives with the EPC already; the reader code does the split (§3.6). **It costs about
   25 % of the raw read rate** (80.7 → 60.6 reads/s on 18 tags) with unique-tag discovery unchanged,
   so note it on screen rather than hiding it.
4. **Stop reason** and **duration**, because a run that hit `TIMEOUT` is not the same as one that
   settled even when the count matches.

**O1 and O5 are held LOW for the whole static test** — nothing moves. Both, not just O1: the belts
have separate channels since 2026-09-05 even though `setBelts()` still writes them together, so
asserting only O1 would miss an O5 stuck high, which on this test would mean the Exit Conveyor
running under a "nothing moves" heading. The admin app puts the tunnel in `HOLD` before the first run
and releases it to `AUTO` after the last. See §7.

**At the end of the run set**, render the full analytical report (§10).

**Traps:** §3A.2 — you must pulse the GPIO lines, and set `disable-input-pulls: false` on a bare
bench or IN1 will manufacture cartons on its own. §3A.3 — check the running session before believing
a low count.

**`durationMs` now means what it says.** The old substitution of `endedAt` with `countReachedAt` has
been removed; `countReachedAt` and `settledAt` are separate fields on the result. Show all three —
the gap between `countReachedAt` and `endedAt` **is** the settle cost, and it is the only lever on
carton time, because the measurement on this rig is that every tag was already found by ~1.0–1.3 s
and the rest of a 2.5–2.9 s carton was spent proving nothing more was coming.

## 5. Test 2 — Dynamic

The conveyor runs and cartons are placed on it. Start and Stop buttons; per-run results stream in as
in Test 1; Stop renders the report.

**Dropdowns:** Single Pass / Double Pass · Speed 100 % / 75 % / 50 %.

**Speed maps to the RZC only.** Run A and Run B are a pair: A only = 100 %, A+B = 75 %, B only = 50 %,
neither = stop. **EnC and ExC have Run A alone — on O1 and O5 respectively since the rewiring — so
they are run/stop at 100 % and cannot be slowed.** Separate channels did not buy them a speed ladder;
only the RZC has a Run B. Consequence for the rig is unchanged: at 50 % the carton *decelerates* as
it transfers from EnC to RZC and *accelerates* leaving it. Watch for bunching at the transfer at the
lower speeds — it is a rig problem, not a reader problem, but it will look like a read problem.

**Single pass**: EnS opens the session, the conveyor keeps running, ExS closes it.

**"Double Pass" is three passes**, and the report has to treat it that way. Keep the operator's name
for the setting, but define it in the UI so nobody miscounts:

| Pass | Motion | Ends at |
|---|---|---|
| **1 — outbound** | EnS → ExS, forward | ExS edge, first direction change |
| **2 — return** | ExS → EnS, `RZC_REVERSE` asserted | EnS edge, second direction change |
| **3 — outbound** | EnS → out through ExS, forward again | session close |

**Report tags first seen on pass 2 and on pass 3 as their own numbers.** That is the whole
justification for the mode: if pass 2 and pass 3 add nothing, the extra cycle time is being spent for
no yield, and that is the only question this test is being run to answer.

**This needs a code change — the result has no notion of a pass.** `InventoryTag` has `firstSeen` as
an absolute instant and nothing records when the direction changed. The tunnel *does* know: it
commands the reversal by driving O4. So **stamp the direction changes into the session** and put
`passBoundaries[]` (instants, or ms from `startedAt`) on `InventoryResult`. The admin app then
attributes each tag's `firstSeen` to a pass by time — no per-tag field needed and no change to the
tag record. Add `passCount` too, so a single-pass run is self-describing rather than an empty array.

**Attribution is only trustworthy with the Select-to-A reset in place** — see §3.3. Under S1 alone, a
tag whose flag has not yet decayed can go quiet through pass 2 and answer on pass 3, and it will be
reported as a pass-3 find when it was in the field throughout. That would make the mode look better
than it is, which is the worst direction for this particular error.

**O1 and O5 during the read.** Per §7, both are high by default and drop when EnS fires, so the
dynamic test also exercises the conveyor state machine. **In Double Pass they must stay low across
all three passes** — the first ExS edge is a direction change, not the end of the carton. Assert in
the test that **both** return high on
**every** outcome including `TIMEOUT`, and that `tunnel.max-duration-ms` releases them if no outcome
arrives at all. A carton stopped in the tunnel with the line dead is the failure this test exists to
catch. Read both channels even though `setBelts()` writes them together (§3.1a): they are the same
value by construction today, and the test's job is to notice the day they are not.

## 6. Tests 3 to 6 — accepted by the operator, build them all

These were proposed and are **now part of the suite**, not options.

### Test 3 — Canary tag, the liveness control. **Build this first.**

`SETTLED` is a wall-clock timer with no positive control: **a dead reader and a fully-read carton
produce identical results.** Every number in every test above inherits that blind spot.

Tape one known reference tag permanently inside the read zone and put its EPC in config. **Every run
must see it.** A run that does not is *invalid*, not *failed* — grey it out, exclude it from the
statistics, and say why. One tag, one config key, and it converts `SETTLED` from a timer into a
positive control. This is the cheapest thing in this document and the one with the highest value.

### Test 4 — Empty-field run, the control for every other number

Arm, trigger, nothing in the tunnel. Must report zero tags. Catches a mis-set RSSI threshold, a stale
Select filter, and reads leaking from a neighbouring rack. Two minutes, and until it passes none of
the other numbers mean anything. Note that a filter left set makes the reader look broken and
`TagOperations.clearFilter()` exists for exactly this.

### Test 5 — Back-to-back gap sweep, the throughput number

**Reliance will ask how many cartons per hour, and nothing in the two specified tests measures it.**
With S1 (§3.3) the Gen2 reason for a short gap to fail is gone, so what this sweep now measures is
the *real* limit: settle time and carton spacing on the belt. That is a better number than the one we
were going to get.

**The third term used to be the serialised discharge, and the 2026-09-05 rewiring removed it** — the
ExC has its own channel, so the previous carton can discharge while the next is read, and cycle time
is no longer read *plus* discharge. **But do not expect that in this sweep's numbers yet**, because
`setBelts()` still drives O1 and O5 together (§3.1a): the serialisation is gone from the *copper* and
still present in the *behaviour*. Measure the sweep as it stands and record it as the pre-split
baseline — the difference after the belts are commanded apart is the value of the rewiring, and it is
worth having both numbers.

Run it under S2 as well, once, deliberately — it reproduces the old failure and gives you the
before/after that justifies staying on S1.

> 🔴 **The gap sweep has a hardware hazard the other tests do not, and it is not about reads.**
> `triggered-carrier: true` means **one inventory stop/start per carton**. Shortening the gap raises
> the restart rate, and this module has raised
> `MT_HARDWARE_ALERT_ERR_BY_TOO_MANY_RESET (0xfefe: MODULE_NEED_RESTART)` **from four inventory
> restarts inside thirty seconds** and stopped reading. A sweep down to a 2 s gap is 15 restarts a
> minute.
> **Walk the ladder downwards and stop at the first sign of trouble** — watch `recoveries` on
> `/api/reader/status` and the log for `MODULE_NEED_RESTART` between every step. If you need the
> short end of the ladder, run it with `triggered-carrier: false` and a continuous carrier so no
> restart is involved, and report the two configurations separately. **The restart limit may turn out
> to be the throughput ceiling rather than settle time** — which would be a finding, and a good one.

Run pairs of cartons at decreasing gaps — 30 s, 20, 15, 10, 5, 3, 2 — and find the smallest gap at
which carton 2 still reads complete. That number is the throughput ceiling, it is the customer-facing
figure, and it also brackets the S2 persistence that §3.3 is trying to fix. Run it before and after
the Select fix and the difference is the business case for the fix.

Remember the settle rule while you interpret it: **settle is measured from the last _new_ EPC, not
the last read**, so a box sitting in the field re-reads its own tags forever and "no reads for N ms"
never fires while it is present.

### Test 6 — Fault injection, and what the conveyor does about it

`pinctrl set 15 ip pd` de-muxes RXD0, the module's replies stop reaching the Pi, and the vendor
library raises a genuine read exception within seconds. `pinctrl set 15 a0 pu` puts it back. This was
used to verify the recovery supervisor on 2026-08-29: five failed attempts backing off 5→10→20→40→60 s,
then recovery with inventory restarted.

Inject it **mid-carton** and assert five things:
1. The run is marked **invalid**, not merely short.
2. `recoveries` and `lastRecoveryAt` on `/api/reader/status` advance, and the reader comes back.
3. **The carton exits forward** — O4 released, RZC driven until clear, **O1 and O5 high** (§7.1).
4. **The red lamp lights** — **O7 since 2026-09-05, not O6** — and stays on per the clearing rule in
   §7.1. Assert **O6 dark** in the same check: with the lamps one channel apart from where they were,
   an inverted or off-by-one landing at the TM shows up as a *green* lamp on a failed carton, which
   is the most expensive possible way to be wrong and passes any test that only looks at "a lamp is
   lit".
5. **A result is still emitted** — `TIMEOUT`, `complete: false` — and the callback is delivered. Assert
   this in the admin app against `CallbackController`: a carton that leaves unread and produces no
   callback is worse than one that fails loudly.

Then repeat the injection **between** cartons, with the tunnel empty, and confirm the line does not
lurch: nothing to discharge, red on, and no phantom session.

Also do the **failsafe check manually**, once, and record it: kill reader power with the conveyor
running. Everything must stop. If anything runs, the TM polarity is inverted and the rig is not safe
to work around. It is in `docs/Tunnel-Interconnect.md` §14 as a commissioning step and it is the
easiest one to skip.

## 7. The belt channels are part of the test, not scenery

The conveyor outputs must be driven correctly *by the tests themselves*, not left floating while the
tests run. Two rules, both from the operator. **They now apply to two channels, not one** — O1
`EnC_RUN` and O5 `ExC_RUN`, written together by `setBelts()` (§3.1a) and therefore expected to hold
the same value in every row below:

| Test | O1 (`EnC_RUN`) and O5 (`ExC_RUN`) |
|---|---|
| **Static (§4)** | **Both held LOW for the whole test.** Nothing moves. The admin app puts the tunnel in a hold state before the first run and releases it after the last. |
| **Dynamic (§5)** | **The state machine.** High between cartons; LOW from the EnS edge; **HIGH again only once the reading for that package is finished** — and in Double Pass that means after the *second* pass completes, not after the first ExS edge. |

The Double Pass case is the one to get right. ExS is not the end of the carton in Double Pass — it is
the first direction change. The belts must stay low across the reverse pass and the final outward
pass, and release only when the session actually closes. If they go high at the first ExS edge, EnC
starts feeding the next carton into a tunnel that is still reversing the current one.

**Assert O1 and O5 separately even though they are identical by construction.** They agree because
one method writes both, not because anything in the field guarantees it; a broken TM channel, a
mis-landed core or a future split of the seam all show up first as the two disagreeing, and a test
that reads only O1 is blind to every one of them.

### 7.1 Fault behaviour — decided 2026-09-02

**On a fault the package exits forward and the red lamp comes on.** Concretely: O4 released
(forward), RZC driven until the carton is clear, **O5 high so ExC can discharge it (and O1 with it,
see below)**, **O7 `LAMP_FAIL` asserted**. The carton leaves unread rather than being trapped in the
tunnel. **The red lamp is O7, not O6, since 2026-09-05** — O6 is now green, so a stale channel
constant here lights *pass* on a faulted carton.

Four things this must get right:

- **Distinguish the two faults, because only one of them can act.** A *module or read* fault leaves
  the JVM alive and able to drive outputs — that is the case above, and it is the one to implement.
  A *dead JVM, dead CM4 or lost 24 V* drives every output low: everything stops, and the red lamp is
  dark because nothing can light it. That is the failsafe and it is correct; do not try to engineer
  around it, but do not confuse the two in the code either.
- **The carton must be reported as a failure, not omitted.** Force the session closed with
  `TIMEOUT`, `complete: false`, and let the callback go. A carton that exits unread and produces no
  result is a carton the WMS thinks never existed. The existing rule stands: a `TIMED_OUT` session is
  never trustworthy even if the count happens to match.
- **Decide when red clears.** Recommended: the lamp stays on until the reader is healthy *and* the
  next carton completes successfully. Clearing it the instant the supervisor reconnects gives a
  flicker that teaches operators to ignore the lamp.
- 🟠 **Discharging on a fault still starts EnC — but the wiring reason is gone and only the software
  reason is left.** This used to be "they share O1 and there is no way to run ExC alone"; since
  2026-09-05 the ExC has O5 and running it alone is a one-line change. What still forces the pile-up
  is that `setBelts()` writes both channels together (§3.1a), so the fault discharge feeds the
  *next* carton into a tunnel whose reader has just failed. **The fix is now available and has not
  been made**, and whether it should be made — a blocked or failed exit holding the EnC — is one of
  the two open decisions in §3.1a. **Test what exists**: on a fault today, expect O1 and O5 both
  high and expect the next carton to be fed. Record it as the reason to split the seam; do not
  assert the behaviour nobody has chosen yet.

Two implementation consequences:

- **The admin app must never touch GPIO.** It runs on the laptop; the lines are on the CM4. Every
  conveyor action is an HTTP call to the tunnel, which owns the pins. See `POST /api/test/conveyor`
  in §8.2.
- **The hold must be explicit and it must fail safe.** If the admin app crashes or the operator
  closes the tab mid-test, the tunnel must not sit in a forced state forever. Give the hold a
  deadline — a hold that is not refreshed within, say, 30 s reverts to `AUTO` — and log the revert.

### 7.2 ✅ IN3 shutdown — the held button, DONE 2026-09-02

IN3 runs to a physical push button in the panel and the request is **a level held for `hold-ms`
(5000)**, sampled every `sample-ms` (250). The five-pulse burst is deleted, not made selectable: it
was designed for a PLC interface and there is no PLC on this line, and a protocol you can select is
a protocol that can come up as the wrong one.

`ShutdownRequestMonitor` polls `FieldIo.read(IN3)` on its own thread and is deliberately **not** on
`GpioEdgeMonitor` — a level is what is being measured, and reading it through `pinctrl` stays clear
of the exclusive claim `gpiomon` takes on the lines it watches. **IN3 is therefore no longer on that
`gpiomon` command line**, and `tunnel.v1.gpio.shutdown-line` is gone.

**Releasing abandons the hold; nothing is banked.** Two four-second presses are not an eight-second
hold, so a line chattering asserted/released — which is what noise looks like — can never accumulate
its way to a request.

Both start-up guards are built, because a stuck button or a shorted line reads asserted forever and
would otherwise shut the unit down on every boot:

1. **`require-release-first` (default true)** — a hold may only begin from an observed
   released→asserted transition. The verdict is latched at the *start* of the assert, so a later
   release cannot retroactively bless it. This is the one that actually holds.
2. **`startup-grace-ms` (30 000)** — refuses to act at all early on. The weaker guard: alone it only
   *delays* the shutdown of a stuck line.

Uptime is measured from the **first sample**, not from construction, so the grace and the samples
share one clock. A non-default `hold-ms`, and turning `require-release-first` off, both warn at
start-up.

**Logging:** INFO gives the start-up line and the accepted request; DEBUG adds the assert and the
abandon; **TRACE gives every sample with its running hold time**, which is the level to use when the
question is what actually arrived on the pin. `logging.level.com.intelli.rfid.tunnel.field: TRACE`.

**The shutdown lamp is O7 (BCM 13) since 2026-09-05 — it was O6 (BCM 12).** It shares the channel
with `LAMP_FAIL`, and its three states and their producers are **unchanged** by the move:

| State | Meaning | Driven by |
|---|---|---|
| **blinking** | the shutdown sequence is running | the application (`ShutdownLamp`) |
| **solid lit** | the app is gone, the OS is still coming down | the application, on its way out |
| **dark** | **the board is down; 24 V may be removed** | `/usr/lib/systemd/system-shutdown/intelli-lamp.shutdown`, and nothing else |

The rule that dark is produced **only** by that script, after `systemd-shutdown` has remounted root
read-only, is the whole point of it and did not move — only the pin did. The script now does
`pinctrl set 13 op dl`; **it was `12`**. It must stay **0755**, because systemd-shutdown silently
skips a file it cannot execute and the symptom is a lamp that never goes dark on a board that is off.

**Test it as part of Test 6.** A 4-second press must do nothing. A 5-second press must run the full
sequence and light O7 — **check BCM 13, not 12**. A press during a reader fault must still work. And
confirm that shorting the input to 24 V at boot does **not** shut the unit down — then releasing it
must arm the button rather than leave it dead for the life of the process. `ShutdownRequestMonitorTest`
pins all of that at the unit level (10 tests); the bench run is the wiring proof.

**One check the shared channel adds**: watch O7 across a carton *and* a shutdown in the same session.
The red lamp's 5 s verdict dwell and the shutdown lamp's blink are the same physical lamp now, so a
verdict landing during a shutdown sequence, or a stale dwell timer outliving it, would show as a lamp
telling the operator the wrong thing about whether 24 V may be removed.

## 8. Tunnel-side work

Everything new lives under **`/api/test/**`**, a third surface alongside the contract and the
diagnostic ones. Say so in its javadoc: it is not the contract, it must not appear in customer
documentation, and it should be behind the `ADMIN` scope in `ScopeRules`.

### 8.1 Fixes, in this order
1. ~~**The channel map**~~ **— DONE** (§3). `FieldChannel` carries the Reliance functions, the lamps
   hold levels, the heartbeat and the width-encoded RESULT are gone, and the package and config
   prefix are `field` / `tunnel.field.*`. **Update the site `application.yml`'s `plc:` key before the
   next deploy** — it now binds nothing, silently.
2. **`session: 1`** in `application.yml` (§3A.3). One line.
3. **Polarity on the edge monitor** (§3A.1) — `gpiomon -l` / `--active-low` on both libgpiod majors,
   behind `tunnel.v1.gpio.active-low`, default true.
4. **`broadcaster.publishEvent("carton", …)`** on the entry edge (§3A.5), with the session id, the
   sequence and the edge timestamp.
5. **`resetInventoriedFlag()`** — the Gen2 Select-to-A through `MTR_PARAM_TAG_MULTISELECTORS`, called
   from `InventoryService.openSession` and at each direction change (§3A.3, §5). Not a blocker under
   S1; needed for trustworthy per-pass attribution.

### 8.2 New endpoints
- `POST /api/test/gpio/pulse` — `{line: 23|24, holdMs}`. Shells `pinctrl` to produce one real edge of
  the configured polarity. **Test-only, ADMIN scope, and it must refuse when
  `tunnel.v1.gpio.enabled` is false** so it cannot be mistaken for a production trigger.
  **Line 25 (IN4, `EXIT_FULL`) is deliberately not in that set**: it is a level, not an edge, and
  nothing consumes it yet (§3.1a). When the belts are split, what this endpoint needs for IN4 is a
  *hold*, not a pulse — do not extend the pulse form to it and produce a 200 ms blip nothing can act
  on.
- `POST /api/test/conveyor` — `{mode: "AUTO"|"HOLD", ttlMs}`. `HOLD` forces **O1 and O5** low with
  the deadline from §7; `AUTO` returns them to the state machine.
- `GET /api/test/io` — the actual state of all 7 outputs and 4 inputs, so the fault test (§6.4) can
  assert what the belts did. Note this duplicates `/api/v1/diagnostics/io`, which exists and is what
  the admin Field I/O tab already drives; prefer repointing to that over adding a second shape.
- `POST /api/test/select/reset` — issue the Select-to-A on demand, so the gap sweep (§6.3) can be run
  with and without it.

### 8.3 The conveyor outputs — build on `FieldIo`, do not replace it

**`FieldIo` and `PinctrlFieldIo` already exist and already enforce the inversion boundary.** Do not
write a second one. What is missing is the layer above:

- A **`ConveyorController`** that owns the belt state machine (§7) and the fault behaviour (§7.1),
  writing through `FieldIo`. It writes O1 and O5 through a single `setBelts()` seam — **keep that
  seam named and in one place**: it is where the two belts get told apart when the open decisions in
  §3.1a are made, and a second copy of that write somewhere else is how the split silently becomes
  a half-split.
- A **real `CartonRelease`** bean — it is still the logging stub, still wired
  `@ConditionalOnMissingBean` in `V1Configuration`, and still called before the carrier drop and the
  verdict. That ordering is the contract promise that a slow WMS never stalls the conveyor; keep it.
- `tunnel.test.o1-drop-delay-ms` (default 0) so the EnS position can be tuned on the rig without a
  rebuild.

The rules `FieldIo` already enforces, restated so nobody undoes them: outputs are active-HIGH at the
GPIO and inputs active-LOW, hidden inside the boundary; the seven outputs are all on GPIO ≥ 9 so they
reset low and a dead reader stops the line — **never move one onto GPIO 2–8**; the output GPIOs are
non-contiguous, so there is no masked `GPSET0` write.

One thing to check rather than assume: `PinctrlFieldIo` spawns a process per call. The belt state
machine writes on every carton edge, which is fine, but **the rewiring doubled the number of writes
per edge** — `setBelts()` is two processes now, not one — and if anything ends up writing per *read*
that cost will show. Measure it before putting a write anywhere near the dispatch path.

### 8.4 Config to add
`tunnel.test.canary-epc` (§6.1), `tunnel.test.hold-ttl-ms`, and make `read-duration-ms` settable
through `POST /api/reader/config` — it is currently read once in `startReading()` and no endpoint can
change it, which blocks any latency sweep. **Do not** add a runtime setter for `fast-id`: it is
connect-time by hard-won experience, and four inventory restarts inside thirty seconds raised
`MT_HARDWARE_ALERT_ERR_BY_TOO_MANY_RESET` and stopped the module reading.

While you are in `application.yml`: `recover-on-fault`, `recover-max-delay-ms` and `recover-stable-ms`
are documented at length and **bind to nothing** — there is no `recover*` field on `RfidProperties`
or `ReaderConfig` and no code references them. Either wire them or delete them; a dead key that looks
alive is worse than no key.

## 9. Admin-side work

One new tab, **Bench**, with two panels (Static, Dynamic) and a shared results area. Follow the
existing idiom: a `<section data-panel="bench">`, a `<nav>` button, and `[data-call]` attributes for
anything that is just an endpoint hit.

- **Drive everything through `/proxy/**`.** It already injects the key and times the call.
- **Live feed** from `/api/admin/stream` once §3.4 is fixed, listening for `carton` (open), `tags`
  (progress) and `inventory` (close).
- **The callback still goes to `CallbackController`** — point `callbackUrl` at the admin app as
  today. The test then exercises the *real customer path* rather than a test-only one, and
  `V1Contract` grades every carton for free. Show the contract verdict per run beside the numbers:
  a run can be electrically perfect and still emit a non-conforming result.
- **Persist the run set.** `ExchangeLog` and `CallbackStore` are in-memory and capped; a test set that
  vanishes on restart is worthless. Write each run to a JSONL file beside the admin jar and let the
  report be regenerated from it. This is also how you compare "before the Select fix" to "after".
- **A run needs a verdict object.** Nothing in this app currently grades a *session* — `V1Contract`
  grades one response. Add `RunResult { n, sequence, startedAt, durationMs, stopReason, tagCount,
  matchingCount, expectedCount, complete, canarySeen, contractViolations[], tags[] }` and a
  `TestSet { id, kind, settings, runs[], verdict }`.

## 10. The report

Reproduce the report the operator already has (`Tunnel Read Profile`), because it is the format he
reads. Its data all comes from `InventoryResult` records, which means
`GET /api/inventory/completed?since=<sequence at test start>` gives you the whole set in one call.

**Stat strip:** cartons read · complete (n/n) · tags detected (total/total) · median carton duration
with the range · "all tags found by" (median of the last tag's `firstSeen` offset) · signal range.

**Three charts**, hand-written SVG — there is no charting library in this repo and adding one means
vendoring it into `static/`:
1. **Stacked duration per carton** — discovery segment (0 → last new tag) then settle segment, so the
   settle window is visible as the fixed cost it is.
2. **Arrival strip** — one dot per tag at its first-seen offset, one row per carton. This is the chart
   that shows singulation order changing run to run.
3. **RSSI per tag, ranked weakest first** — min–max range bar with the mean as a dot. The weakest tag
   is the one that will fail first on a real box, and this is how you find it.

**Two tables:** per carton (started, stop reason, duration, matched, total reads, first tag, last tag,
settle) and per tag (EPC tail, seen n/N, mean RSSI, range, reads per carton, first-seen avg/min/max).

**Add three columns the original did not have**, because we now know to want them: **TID** per tag,
**canary seen** per carton, and for Double Pass **first seen on pass 2**.

## 11. Order of work

1. ~~**The channel map and the admin tab**~~ **— DONE** (§3, §3.2). Remaining on this item: the site
   `application.yml` still has the old `plc:` key, which binds nothing.
2. **`session: 1`**, the edge polarity, the carton event (§8.1 items 2–4). All small.
3. **Test 3, the canary tag.** Before a single number is collected.
4. **`ConveyorController` + real `CartonRelease`** (§8.3), then §7's belt behaviour on **both** O1
   and O5. **Verify the failsafe by killing reader power with the belt running before trusting
   anything else** — and check the ExC stops too, not just the EnC; it is on a different channel now
   and a TM channel that fails energised would only show up here.
5. §8.2 `/api/test/gpio/pulse`, then **Test 1 static**. Under S1 this should now just work; if runs
   2..N come back empty, check the running session first.
6. **Test 4** empty-field, then **Test 5** gap sweep — walking *down* the ladder and watching
   `recoveries` at every step, per the hazard note in Test 5.
7. The Select-to-A reset, and `passBoundaries[]` on the result (§5).
8. **Test 2 dynamic**, single pass; then Double Pass, which needs step 7 for trustworthy per-pass
   attribution.
9. **§7.2 the IN3 HOLD protocol**, then **Test 6** fault injection last — it is the one that can
   leave the rig in a strange state.

## 12. Traps, collected

- **`gpiomon` holds the lines exclusively.** A probe run while the app is up fails with `Device or
  resource busy`, and that failure means the app is working. Stop the app to probe.
- **Any long-running CLI you read incrementally needs `stdbuf -oL`.** gpiomon block-buffers at 4 KB to
  a pipe: three confirmed edges delivered **zero** bytes through a plain pipe and three lines under
  `stdbuf`. It looks exactly like missed edges and the wrong diagnosis is expensive.
- **Never conclude a setting took effect from its return code.** `MTR_PARAM_POTL_GEN2_TAGENCODING`
  returns `MT_OK_ERR` for any value at all and silently snaps to 107. Read parameters back.
- **Check `GEN2_SESSION` before believing a low tag count.** We run S1 and it is clean; the committed
  yml still says 2, and a leftover S2 reads exactly like a broken reader. It has already cost this
  project a day once. Probes should set the session explicitly rather than inherit whatever the last
  run left.
- **Maven incremental compile goes stale.** After editing core, `mvn clean install` on core, not
  `mvn install`. Verify with `javap -c -p -cp target/classes <Class>` when behaviour contradicts
  source.
- **Ask the operator to start and stop the apps.** A backgrounded JVM dies at tool-call boundaries and
  `pkill -f '<app-name>'` matches your own wrapper shell (exit 144). Use `pgrep -x java` or the
  listening port. For diagnostics prefer a one-shot Java program compiled against the vendor jar.
- **Two different `sequence` counters** share a field name: `SequenceCounter`
  (`/var/lib/intelli/tunnel/sequence`, in `ReadResult.sequence` and the callback) and `JsonlSpool`'s
  (`InventoryResult.sequence`, used by `/api/inventory/completed?since=`). They will not agree. The
  report must use the spool one.
- **`JsonlSpool.initialise()` reads every line of every spool file at startup** to recover the
  high-water sequence, and there is no retention or size cap. A long test campaign will make start-up
  slow. Rotate the spool directory between campaigns.

## 13. What "pass" means — the acceptance criteria

The operator's instruction is that **these tests must pass**, so each one needs a verdict, not just a
chart. A test is **INVALID** rather than FAILED whenever the canary is missing (Test 3) — an invalid
run proves nothing in either direction and must not be averaged into anything.

| Test | PASS when | FAIL on |
|---|---|---|
| **1 Static** | every run has `matchingCount == expectedCount`; canary seen in every run; the v1 callback conforms (`V1Contract` clean) on every run; **O1 and O5 both stayed LOW** for the whole test | any run short or over; any contract violation; **either belt channel asserted** at any point |
| **2 Dynamic, single pass** | as Test 1, plus **O1 and O5** low from the EnS edge and high again on every outcome including `TIMEOUT`; carton duration within the band you record on the first clean run | either belt channel stuck low after an outcome; a carton stopped in the zone; **O1 and O5 disagreeing at any sample** (§7) |
| **2 Dynamic, double pass** | as above; **O1 and O5** low across **all three** passes; `passBoundaries[]` present and pass 2 + pass 3 yields reported | released at the first ExS edge; missing pass attribution |
| **3 Canary** | the canary EPC appears in 100 % of runs across every other test | any absence — and that invalidates the run it was absent from, wherever it happened |
| **4 Empty field** | zero tags, no session opened, no verdict emitted | any tag at all; a phantom carton (check `disable-input-pulls`) |
| **5 Gap sweep** | a stated minimum gap at which carton 2 still reads complete, with `recoveries` unchanged across the whole sweep | `recoveries` incremented, or `MODULE_NEED_RESTART` in the log — **stop the sweep, that is a hardware result** |
| **6 Fault injection** | carton exits forward; **red lamp O7 lights and O6 stays dark**, and it holds; a `TIMEOUT` / `complete:false` result **and its callback** are delivered; reader recovers and `recoveries` advances by exactly one | no result emitted; carton trapped; red lamp dark or cleared early; **green lit on a faulted carton — that is a stale lamp channel, not a verdict bug** |
| **Shutdown (§7.2)** | a 4 s press does nothing; a 5 s press runs the sequence and **lights O7 (BCM 13)**, blinking then solid; input shorted at boot does **not** shut down; the lamp goes **dark only after the board is down**, from `intelli-lamp.shutdown` | any unprompted shutdown; O7 lit before the counter is closed; **the lamp dark while the OS is still coming down** — that is the one-phase-early failure, back again through a different route |

Two cross-cutting criteria that apply to every test above:

- **Exactly one verdict lamp lit for ~5 s after each carton, then both dark.** The pair is **O6
  green / O7 red** since 2026-09-05 — both moved up one channel, so a harness carrying the old
  constants reports every verdict inverted-by-one and O5, which is now the Exit Conveyor, as "the
  green lamp". "Both lit" is a wiring fault and is flagged as such on the admin Field I/O tab. Look
  within the dwell — polling `/api/v1/diagnostics/io` a minute later legitimately shows both dark,
  and that is not a finding. This replaces the old out-of-band width check, which went away with the
  width encoding.
- **No `degraded` string on `/api/v1/reader/status`** for the duration of a run. A degraded reader can
  still produce plausible numbers, which is exactly why it has to be an explicit check rather than
  something noticed afterwards.

Record the verdicts as a set, not one at a time. A suite where five pass and one is invalid is not a
partial pass — it is a suite that has not run.

## 14. Questions back to the operator

1. ~~Where does EnS sit relative to the EnC/RZC transfer?~~ **Closed 2026-09-02.** The operator will
   tune the EnS position on the rig so that reading starts at the right moment *and* the entry
   conveyor is safe to switch off when it fires. **Make the O1 drop easy to re-time from config**
   (`tunnel.test.o1-drop-delay-ms`, default 0) so the tuning is a config change, not a rebuild.
2. ~~What should O1 and O2 do during a reader fault mid-carton?~~ **Closed 2026-09-02: the package
   exits forward and the red lamp comes on** (§7.1). The consequence — the fault discharge also runs
   EnC, so the next carton is fed into a failed tunnel — was open because EnC and ExC shared O1.
   **The rewiring of 2026-09-05 makes it answerable**: ExC has O5 and can run alone. What remains is
   a decision, not a constraint, and it is one of the two in §3.1a: should a failed or blocked exit
   hold the EnC? **Still needs an answer before the dynamic test runs unattended** — the pile-up
   happens today, because `setBelts()` writes both.
3. **Is the reader permitted to reverse the conveyor at all** on the real rig, mechanically and for
   safety? Double Pass is built on it, and it is now three passes rather than two.
4. **What carton gap does the customer actually need?** Test 5 measures the achievable one; we should
   know the required one before we start.
5. **Should the EnC stay stopped until the IN2 exit edge**, rather than restarting when the read
   closes? The second open decision from the rewiring (§3.1a). It changes what Test 2 should assert
   about when O1 comes back, so it wants settling before the dynamic acceptance band is recorded.
6. **What should `EXIT_FULL` (IN4) actually do?** The sensor is wired and nothing reads it. Stopping
   the ExC at the discharge edge is the reason it exists; whether it should also apply back-pressure
   up the line is the open half — that is question 2's other face, and the two should be answered
   together.
