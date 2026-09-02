# Bench Test Harness — handoff to Claude Code on the CM4

**You are the session with the hardware. Prefer running the thing over reasoning about it.**
This was written on the laptop against the source, so every claim about *code* here was read from
the tree and is reliable; every claim about *module or conveyor behaviour* is inference and is
marked. Where the hardware contradicts this document, the hardware is right — fix it and write the
correction back into `CLAUDE.md`.

Version 1.2 · 2026-09-02 · for `apps/intelli-rfid-tunnel` and `apps/intelli-rfid-admin`

Changed in 1.1: session 1 measured clean (§3.3) · trigger edge confirmed (§3.1) · Double Pass is three
passes with per-pass attribution (§5) · fault behaviour decided (§7.1) · the four proposed tests are
now Tests 3-6 (§6).

Changed in 1.2: IN3 shutdown becomes a held button, not a pulse burst (§7.2).

---

## 1. What we are building and why

The operator needs to characterise the tunnel on the bench and then on the moving rig, and get a
number he can show Reliance. Two tests were specified; four more are proposed here because the two
as specified will not survive contact with what we already know about this module.

The admin app is the console. The tunnel app grows a small **test control surface** and a couple of
missing events. **Nothing in `/api/v1/**` changes** — that is the customer contract, issued to
Reliance, and it is not the bench surface. Everything new goes on the diagnostic side.

## 2. Read this before you write anything

You have more already built than you think. From a full read of both trees:

**In the tunnel app / core — exists, reuse it:**
- `GET /api/inventory/completed?since=<seq>&limit=<n>` reads the **JSONL spool** and returns whole
  `InventoryResult` records. This is the report's data source. **Do not build a new reporting
  endpoint.**
- The spool record `InventoryResult` already carries everything the analytical report needs:
  `durationMs, lastNewTagMs, closeReason, expectedTags, tagCount, matchingCount, marginalCount,
  complete, totalReads, countReachedAt, settledAt, sequence` and `tags[]` =
  `InventoryTag(epc, tid, reads, bestRssi, antennas, firstSeen, lastSeen)` — **for every tag, not
  just the GS1-decodable ones.**
- `TagBroadcaster.publishEvent(name, payload)` already exists and `InventoryService.finish()` already
  publishes an `inventory` event with the whole `InventoryResult` on every carton close.
- `GpioEdgeMonitor` reads GPIO23/24 through `stdbuf -oL gpiomon`. `V1Service.onCartonEntered` /
  `onCartonLeft` are the seams.
- `POST /api/reader/config` changes **session, target, Q, rf-mode, power, RSSI threshold, dedup
  window** at runtime, stopping and restarting inventory around the change.
- `CartonRelease` is a named interface with a logging-only implementation, wired
  `@ConditionalOnMissingBean` in `V1Configuration`. **That is your seam for the conveyor outputs** —
  provide a real bean and nothing else has to move.

**In the admin app — exists, reuse it:**
- `/proxy/**` → `ReaderHttp`: any method, any path, any body to the tunnel, with `X-API-Key` injected
  server-side and `X-Elapsed-Ms` on every response. You do not need to write an HTTP client.
- `CallbackController` + `CallbackStore`: a working WMS simulator, 200-record history, three-valued
  token check, runtime-settable **delay** and **response status** for fault injection, and it already
  runs `V1Contract.check(RESULT, …)` on every inbound callback.
- `V1Contract` + `POST /api/admin/validate?shape=` — a document-derived validator that shares no code
  with the server. Keep using it; it is the only thing that can actually fail the contract.
- `ExchangeLog` (500 entries) + `GET /api/admin/log/export` as JSONL.
- `POST /api/admin/config` mutates base URL, key, timeout, callback delay and status at runtime.
- The UI is **three static files, no build step** — `static/index.html`, `app.js`, `app.css`. A new
  screen is one `<section data-panel="…">` plus one `<nav>` button. Buttons that only hit an endpoint
  need no JavaScript: the `[data-call]` delegated dispatcher handles them.

**Does not exist and you will have to build it:** any charting (no library, no `package.json`,
nothing), any notion of a "run" or a test scenario, any persistence across an admin restart, and any
analysis of the JSONL.

## 3. Fix these first — they will make the tests lie

### 3.1 The edge polarity is wrong for real sensors 🔴 — CONFIRMED, change it

`GpioEdgeMonitor.commandLine()` hardcodes `gpiomon --rising-edge`. With the W26 wired as
`docs/Tunnel-Interconnect.md` specifies — PNP, 24 V present = carton present — the opto pulls the
GPIO **low**, so **carton arrival is a FALLING edge**. As it stands the tunnel will trigger on beam
*clear*, not beam *break*: every carton will open its session as it leaves.

**The operator has confirmed this: change the trigger edge.** Add `tunnel.v1.gpio.active-low`
(default **true**, because that is how the board is wired) and select `--falling-edge` from it. Do
not hardcode the other polarity instead — the bench technique in §3.2 asserts by pulling the pin the
other way, so both senses have to work.

### 3.2 Super Fast Mode cannot be exercised on a static bench without sensor edges 🔴

Armed `SUPERFAST` with `gpio.isWatching()` true, **nothing opens a session until a real edge
arrives** — a static test will simply hang. With gpio *not* watching, `V1Service.arm` falls back to
`setAutoTriggerSpec(armedSpec)`, sessions open on the first tag and close on count/settle, and the
status reports `degraded`. That fallback is explicitly *not equivalent* to the real thing, so a
static test that runs in it is not testing Super Fast Mode.

**Use the documented bench technique**: `pinctrl set 23 ip pu` raises an unconnected input and
`pinctrl set 23 ip pd` returns it, and the kernel reports both to an edge monitor holding the line.
That is how the entry/exit sensors were exercised with nothing attached. Add a test-only endpoint
(§7.1) that pulses the lines, so the static test drives the **production** Super Fast Mode path.

Two things to remember: `gpiomon` holds the lines exclusively — a `gpioget` or a second `gpiomon`
gets `Device or resource busy`, and that failure means the app is working. And with §3.1 done, the
pulse has to produce a *falling* edge, so the sequence is `pu` (idle) then `pd` (assert).

### 3.3 Session — S1 is what we run, and it works 🟢 MEASURED, but the config disagrees

**Measured by the operator 2026-09-02: with `session: 1` the tunnel re-reads the same tags a few
seconds later with no problem.** That is the S2 persistence problem gone, and it settles an option
that `CLAUDE.md` had listed as untested. S1's inventoried flag self-decays in 500 ms–5 s even while
the tag is powered, which is exactly the behaviour a carton-at-a-time tunnel wants.

**But `application.yml` still says `session: 2`.** That is live config drift: the committed default is
not what the rig runs. **Change it to 1 and record why in the same commit**, or the next person to
deploy from the repo will reproduce the old fault and spend a day on it. Check the running value
before believing any low tag count — a leftover S2 reads exactly like a broken reader, and that has
already cost this project a day once.

**The Select-to-A reset is therefore no longer a blocker — but it is still worth building.** There is
no Gen2 Select anywhere in the codebase (I grepped `SelC_Inventoried`, `Mat_SLorA`,
`MTR_PARAM_TAG_MULTISELECTORS` — vendor demos only). What it buys now is *determinism* rather than a
fix:

- S1 decay is a **timing window, not a guarantee**. The spec range is 500 ms–5 s and it varies with
  silicon and temperature. A carton read that closes in 600 ms and immediately reverses (§5) can
  begin its return pass while some tags are still in state B, so they answer late or not at all —
  and on a three-pass cycle that shows up as a tag "found on pass 3" when it was really in the field
  the whole time. **The per-pass attribution in §5 is only trustworthy with the Select in place.**
- One `ParamSet` on `MTR_PARAM_TAG_MULTISELECTORS` before each pass removes the dependency entirely.

Build it as `resetInventoriedFlag()`, called from `InventoryService.openSession(SessionSpec)` and at
**each direction change**. Note that the tunnel leaves the carrier on between cartons so
`ensureReading()` will not re-enter `startReading()` — it needs an explicit call, not a hook on start.
Keep the session selector (S0/S1/S2) on the test screen anyway: `session` is runtime-settable through
`POST /api/reader/config`, and being able to reproduce the S2 failure on demand is worth having.

Two things that have not changed: **the gap sweep (§6.3) is still the test that finds the throughput
ceiling**, S1 or not — it just measures a mechanical and read-time limit now rather than a Gen2 one.
And **S0 remains wrong for continuous-carrier bench work** (16.0 callbacks/s on S0 versus 0.1/s on S2
for a static tag), so if anyone reaches for S0 to "make the static test work", they have picked the
one session that breaks it.

### 3.4 `StreamRelay` cannot carry the live feed as written 🟠

Two defects, both in `apps/intelli-rfid-admin/.../StreamRelay.java`:
- It **flattens every upstream event name to `tag`**, because it forwards only lines starting with
  `data:` and discards the `event:` lines. So `inventory` (a completed carton) is indistinguishable
  from `tags` (a read batch). Pass the event name through.
- It **does not send `X-API-Key`**, so against a tunnel with `rfid.security.enabled: true` it gets
  401 while `/proxy` calls succeed. Add the header from `AdminProperties.Reader.apiKey`.

Also: one upstream connection per browser client, and no server-side reconnect. Acceptable for a
bench console; know it before you debug a "missing" event.

### 3.5 There is no carton-open event 🟠

`TagBroadcaster` only ever emits `subscribed`, `tags` and `inventory`. Nothing fires on the entry
edge, on `openSession`, or on arm/disarm — `V1Service.onCartonEntered` only logs. The UI cannot show
"carton in progress" and cannot time trigger-to-first-tag.

Add `broadcaster.publishEvent("carton", …)` in `onCartonEntered` with the session id, the sequence
and the edge timestamp. Small change, and the whole live view depends on it.

### 3.6 The TID already works — but do not read per-tag data out of the v1 result 🟠

**The reader-side TID path is done and correct — trust it.** `ReaderSession.toTagRead()` splits the
trailing 12 bytes off `EpcId` on the `0xE2` allocation class whenever `fast-id: true` (it is), and
`TagRead`, `InventoryTag`, `MatchedTag` and `Unexpected` all carry `tid`. Nothing needs building for
FastID. The caveat below is about **one DTO dropping the field**, not about the radio.

`ReadResult.Undecodable` carries only `epc` and `reason` — **no TID, no RSSI, no reads, no timing.**
On this bench population 16 of 18 tags carry no GS1 header, so a screen built on the v1 result will
show most of the population as bare EPC strings with nothing else.

The bench data source is `InventoryTag` — from `/api/inventory/**`, the `inventory` SSE event, or the
spool. It carries `epc, tid, reads, bestRssi, antennas, firstSeen, lastSeen` for **every** tag.
Use the v1 callback for **contract fidelity** (does the customer-facing path still produce a
conforming result?) and the diagnostic surface for **the numbers**. That is exactly the split
`CLAUDE.md` mandates.

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

**O1 is held LOW for the whole static test** — nothing moves. The admin app puts the tunnel in
`HOLD` before the first run and releases it to `AUTO` after the last. See §7.

**At the end of the run set**, render the full analytical report (§10).

**Traps:** §3.2 (you must pulse the GPIO lines), §3.3 (S2 will empty runs 2..N), and note that
`ResultMapper` rewrites `endedAt` to `countReachedAt` when the stop reason is `PACKAGE_EXITED`, so
`durationMs` is trigger-to-count, not trigger-to-exit. That is deliberate — the carton then sits in
the field until the conveyor moves it and reporting the later moment would inflate every duration by
the dwell time.

## 5. Test 2 — Dynamic

The conveyor runs and cartons are placed on it. Start and Stop buttons; per-run results stream in as
in Test 1; Stop renders the report.

**Dropdowns:** Single Pass / Double Pass · Speed 100 % / 75 % / 50 %.

**Speed maps to the RZC only.** Run A and Run B are a pair: A only = 100 %, A+B = 75 %, B only = 50 %,
neither = stop. **EnC and ExC have Run A alone and share one channel (O1), so they are run/stop at
100 % and cannot be slowed.** Consequence for the rig: at 50 % the carton *decelerates* as it
transfers from EnC to RZC and *accelerates* leaving it. Watch for bunching at the transfer at the
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

**O1 during the read.** Per §7, O1 is high by default and drops when EnS fires, so the dynamic test
also exercises the conveyor state machine. **In Double Pass it must stay low across all three
passes** — the first ExS edge is a direction change, not the end of the carton. Assert in the test that O1 returns high on
**every** outcome including `TIMEOUT`, and that `tunnel.max-duration-ms` releases it if no outcome
arrives at all. A carton stopped in the tunnel with the line dead is the failure this test exists to
catch.

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
the *real* limit: settle time, carton spacing on the belt, and the serialised discharge that comes
from EnC and ExC sharing O1. That is a better number than the one we were going to get.

Run it under S2 as well, once, deliberately — it reproduces the old failure and gives you the
before/after that justifies staying on S1.

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
3. **The carton exits forward** — O4 released, RZC driven until clear, O1 high (§7.1).
4. **The red lamp lights** and stays on per the clearing rule in §7.1.
5. **A result is still emitted** — `TIMEOUT`, `complete: false` — and the callback is delivered. Assert
   this in the admin app against `CallbackController`: a carton that leaves unread and produces no
   callback is worse than one that fails loudly.

Then repeat the injection **between** cartons, with the tunnel empty, and confirm the line does not
lurch: nothing to discharge, red on, and no phantom session.

Also do the **failsafe check manually**, once, and record it: kill reader power with the conveyor
running. Everything must stop. If anything runs, the TM polarity is inverted and the rig is not safe
to work around. It is in `docs/Tunnel-Interconnect.md` §14 as a commissioning step and it is the
easiest one to skip.

## 7. O1 is part of the test, not scenery

The conveyor outputs must be driven correctly *by the tests themselves*, not left floating while the
tests run. Two rules, both from the operator:

| Test | O1 (`EnC_ExC_RUN`) |
|---|---|
| **Static (§4)** | **Held LOW for the whole test.** Nothing moves. The admin app puts the tunnel in a hold state before the first run and releases it after the last. |
| **Dynamic (§5)** | **The state machine.** High between cartons; LOW from the EnS edge; **HIGH again only once the reading for that package is finished** — and in Double Pass that means after the *second* pass completes, not after the first ExS edge. |

The Double Pass case is the one to get right. ExS is not the end of the carton in Double Pass — it is
the first direction change. O1 must stay low across the reverse pass and the final outward pass, and
release only when the session actually closes. If O1 goes high at the first ExS edge, EnC starts
feeding the next carton into a tunnel that is still reversing the current one.

### 7.1 Fault behaviour — decided 2026-09-02

**On a fault the package exits forward and the red lamp comes on.** Concretely: O4 released
(forward), RZC driven until the carton is clear, O1 high so ExC can discharge it, **O6 `LAMP_FAIL`
asserted**. The carton leaves unread rather than being trapped in the tunnel.

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
- 🔴 **Discharging on a fault also starts EnC, because they share O1.** There is no way to run ExC
  alone. So the fault discharge feeds the *next* carton into a tunnel whose reader has just failed,
  and it will pile up behind the first. Either the upstream line has to be stopped by something
  outside this system, or ExC needs its own channel — which is the third time the shared O1 has cost
  something, and the second argument for RS-485 (§12 of `Tunnel-Interconnect.md`). **Raise it with
  the operator; do not quietly build the pile-up.**

Two implementation consequences:

- **The admin app must never touch GPIO.** It runs on the laptop; the lines are on the CM4. Every
  conveyor action is an HTTP call to the tunnel, which owns the pins. See `POST /api/test/conveyor`
  in §8.2.
- **The hold must be explicit and it must fail safe.** If the admin app crashes or the operator
  closes the tab mid-test, the tunnel must not sit in a forced state forever. Give the hold a
  deadline — a hold that is not refreshed within, say, 30 s reverts to `AUTO` — and log the revert.

## 7.2 IN3 shutdown — replace the pulse burst with a held button

**The five-pulse protocol was designed for the PLC interface. There is no PLC on this line.** IN3 now
runs to a physical push button in the panel, and the operator's request is **a level held for 5
seconds**, not a counted pattern.

Do not read that as `pulses: 1`. A single edge is measured unsafe — it fired twice unprompted on
2026-09-01 on a bare pin whose only pull was the carrier's external 10 k, each time running a full
controlled shutdown and leaving something that looked exactly like a dead reader. **A 5 s continuous
assert is a different signal entirely**: an EFT burst cannot hold a line for five seconds, and the
button now sits behind 24 V and the field opto through the Tunnel Manager, which is a far better
noise margin than the unwired pin that misfired. **Sample the level. Do not count edges.**

**Keep the burst.** Make the protocol selectable — `tunnel.plc.shutdown.mode: BURST | HOLD`, default
`BURST`, with `hold-ms: 5000` — so the wayside and any future PLC site are untouched and the tunnel
opts in.

Three rules the HOLD path needs and the BURST path never did:

1. **Require an inactive→active transition after start-up before a hold is accepted.** A stuck button
   or a shorted line reads active forever; without this the unit shuts down again the moment it
   finishes booting, and you have an unbootable reader with no fault anywhere to find.
2. **Refuse to act for the first N seconds after start-up**, for the same reason. Make N config.
3. **Drive O7 `SAFE_TO_POWER_OFF` at the end of the sequence** (§7.1) — it is the only signal the
   operator gets, because restart is a full power cycle and there is no other way back.

Keep the logging lesson from the burst work: at INFO the log records only the outcome, which is
useless when the question is *what actually arrived on the pin*. Log the observed level transitions
and the measured hold duration at DEBUG, and the accepted request at WARN.

**Test it as part of Test 6.** A 4-second press must do nothing. A 5-second press must run the full
sequence and light O7. A press during a reader fault must still work. And confirm that shorting the
input to 24 V at boot does **not** shut the unit down.

## 8. Tunnel-side work

Everything new lives under **`/api/test/**`**, a third surface alongside the contract and the
diagnostic ones. Say so in its javadoc: it is not the contract, it must not appear in customer
documentation, and it should be behind the `ADMIN` scope in `ScopeRules`.

### 8.1 Fixes (do these first — §3)
1. `tunnel.v1.gpio.active-low`, default true, selecting `--falling-edge`.
2. `resetInventoriedFlag()` — the Gen2 Select-to-A, called from `InventoryService.openSession` and at
   each direction change.
3. `broadcaster.publishEvent("carton", …)` on the entry edge.

### 8.2 New endpoints
- `POST /api/test/gpio/pulse` — `{line: 23|24, holdMs}`. Shells `pinctrl` to produce one real edge of
  the configured polarity. **Test-only, ADMIN scope, and it must refuse when
  `tunnel.v1.gpio.enabled` is false** so it cannot be mistaken for a production trigger.
- `POST /api/test/conveyor` — `{mode: "AUTO"|"HOLD", ttlMs}`. `HOLD` forces O1 low with the deadline
  from §7; `AUTO` returns it to the state machine.
- `GET /api/test/io` — the actual state of all 7 outputs and 4 inputs, so the admin app can show
  lamps and so the fault test (§6.4) can assert what O1 did. The admin UI's PLC tab already expects
  something like this at `/api/v1/diagnostics/io` and gets a 404; put it here instead and repoint the
  tab — **do not add a diagnostics path under `/api/v1`.**
- `POST /api/test/select/reset` — issue the Select-to-A on demand, so the gap sweep (§6.3) can be run
  with and without it.

### 8.3 The conveyor output implementation
Provide a real `CartonRelease` bean and a `FieldIo` class behind it. `CartonRelease` is already a
named seam wired `@ConditionalOnMissingBean` in `V1Configuration`, so nothing else has to move.

Rules `FieldIo` must enforce, all of them from `docs/Hardware-IntelliRFIDv2.md`:
- **Outputs are active-HIGH at the GPIO; inputs are active-LOW.** One `activeHigh` flag cannot serve
  both — hide the inversion inside `FieldIo` and let no caller see a raw edge constant.
- **Never move a field output onto GPIO 2–8.** They reset pull-up; the seven outputs are all ≥ 9 so
  they reset low, which is what makes a dead reader stop the line.
- The output GPIOs are non-contiguous (26, 20, 16, 19, 21, 12, 13) — there is no single masked
  `GPSET0` write. Use the table.
- Disable the internal pull on GPIO 18, 23, 24, 25.

Java has no GPIO binding here and pi4j is unproven on this kernel. **Prove pi4j v2 over libgpiod
early, especially bias/no-pull control**, and if it fights you, shelling `pinctrl` is acceptable for
the bench harness — but say so in the code, because it is not acceptable for the shipped product.

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

1. §3.1 edge polarity, §3.5 carton event — small, and everything else is easier with them.
2. §6.1 canary tag. Do it before collecting a single number.
3. §8.3 `FieldIo` + real `CartonRelease`, then §7's O1 behaviour. Verify the failsafe by killing
   reader power with the belt running **before** trusting anything else.
4. **`session: 1` in `application.yml`** (§3.3) — one line, and it stops the repo disagreeing with
   the rig.
5. §8.2 `/api/test/gpio/pulse`, then **Test 1 static**. Under S1 this should now just work; if runs
   2..N come back empty, check the running session before anything else.
6. **Test 4** empty-field, then **Test 5** gap sweep. The gap sweep is the number for Reliance.
7. §3.3 the Select-to-A reset, and `passBoundaries[]` on the result (§5).
8. **Test 2 dynamic**, single pass; then Double Pass, which needs step 7 for trustworthy per-pass
   attribution.
9. **Test 6** fault injection last — it is the one that can leave the rig in a strange state.

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

## 13. Questions back to the operator

1. ~~Where does EnS sit relative to the EnC/RZC transfer?~~ **Closed 2026-09-02.** The operator will
   tune the EnS position on the rig so that reading starts at the right moment *and* the entry
   conveyor is safe to switch off when it fires. **Make the O1 drop easy to re-time from config**
   (`tunnel.test.o1-drop-delay-ms`, default 0) so the tuning is a config change, not a rebuild.
2. ~~What should O1 and O2 do during a reader fault mid-carton?~~ **Closed 2026-09-02: the package
   exits forward and the red lamp comes on** (§7.1). What is *not* closed is the consequence — the
   fault discharge also runs EnC, because EnC and ExC share O1, so the next carton is fed into a
   failed tunnel. **Needs an answer before the dynamic test runs unattended.**
3. **Is the reader permitted to reverse the conveyor at all** on the real rig, mechanically and for
   safety? Double Pass is built on it, and it is now three passes rather than two.
4. **What carton gap does the customer actually need?** Test 5 measures the achievable one; we should
   know the required one before we start.
