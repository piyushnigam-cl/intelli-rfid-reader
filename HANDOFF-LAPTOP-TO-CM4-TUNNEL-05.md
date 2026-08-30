# Handoff: laptop → CM4, 2026-08-30 — the PLC interface is closed. Build the firmware to it.

`docs/Intelli-RFID-Reader-DVP12SA211R-PLC-Integration.docx` went out to the PLC vendor today. It is
a **closed specification**: every timing, every decode rule and every channel assignment in it is
committed, and the vendor is writing their ladder against it now. Nothing in it is provisional and
none of the numbers will move.

That makes this document different in kind from the earlier handoffs. It is not a set of proposals
to react to. **Where this document and the code disagree, the code is wrong** — because the vendor
has already been told what the reader does.

There is one deliberate behaviour change on top of the interface, in §3. Read that first if you read
nothing else: **Super Fast Mode's close condition changes.**

---

## 0. Document authority — and a stale design note you must stop trusting

| Document | Status |
|---|---|
| `docs/Intelli-RFID-Reader-DVP12SA211R-PLC-Integration.docx` | **Authoritative.** Sent to the vendor. |
| This handoff | Authoritative for the reader side of the same interface. |
| `docs/PLC-Digital-IO-Interface.md` | **Superseded on channel assignment and semantics.** Still useful for electrical reasoning. Do not take pin functions from it. |
| `docs/Hardware-IntelliRFIDv2.md` §2.1 | BCM numbers still correct. The PLC-function column is **stale** — it predates the merge. |

`PLC-Digital-IO-Interface.md` describes a design that no longer exists: it has `RESULT_OK` and
`RESULT_FAIL` on separate wires, `ZONE_OCCUPIED` as a level on pin 10, `READER_ENABLE` as a level on
pin 11, and the inventory trigger running inside the SIM7500 module. **All four of those are now
wrong.** If you find code written against any of them, it is code to change.

### 0.1 I have read the tunnel at `c6f8665`, so this is scoped to what is actually there

`GpioEdgeMonitor`, `V1Service.superFastSpec()`, `SessionSpec.exitOnCount` / `exitOnSettle`,
`StopReason` and the `tunnel.v1.gpio` config block. Three things you already got right and that this
handoff does **not** ask you to change:

- **The trigger already reads the J26 field inputs via the CM4**, lines 23 and 24, not the module's
  GPI. §3.1 below is a prohibition on reintroducing the module path, not a request to move anything.
- **`lineBufferCommand: stdbuf` is already in the config**, so the block-buffering trap you found is
  already closed. Leave it closed.
- **The degraded fallback and its reporting in `/api/v1/reader/status`** are right and stay.

What follows is a change to §3.3 — the close condition — plus firmware that does not exist yet
(RESULT, HEARTBEAT, IN3). Read §3.3 as a diff against `superFastSpec()`, not as a rewrite.

---

## 1. The channel map, as committed to the vendor

BCM numbers are unchanged and still come from `Hardware-IntelliRFIDv2.md` §2.1. The **functions**
changed. Three channels were reassigned and two are now parked.

### Outputs — reader → PLC

| J26 | Channel | BCM | Function | Changed? |
|---|---|---|---|---|
| 1 | OUT1 | 26 | `SPEED0` (LSB) | no |
| 2 | OUT2 | 20 | `SPEED1` | no |
| 3 | OUT3 | 16 | `SPEED2` (MSB) | no |
| 4 | OUT4 | 19 | `DIRECTION` | no |
| 5 | OUT5 | 21 | **`RESULT` — pass AND fail, width-encoded** | **YES — was `RESULT_OK`** |
| 6 | OUT6 | 12 | **`HEARTBEAT`** | **YES — was `RESULT_FAIL`** |
| 7 | OUT7 | 13 | **parked — drive nothing, ever** | **YES — was the proposed heartbeat** |

### Inputs — PLC → reader

| J26 | Channel | BCM | Function | Changed? |
|---|---|---|---|---|
| 9 | IN1 | 23 | `ZONE_ARRIVE` — 2 s pulse | semantics fixed |
| 10 | IN2 | 24 | **`ZONE_EXIT` — 2 s pulse** | **YES — was `ZONE_OCCUPIED`, a level** |
| 11 | IN3 | 18 | **`SHUTDOWN_REQUEST` — five pulses** | **YES — was `READER_ENABLE`, a level** |
| 12 | IN4 | 25 | **parked — read nothing, ever** | **YES** |

> ### The naming collision that will cost someone a day
>
> **`IN1` and `IN2` in this document mean the field connector channels on J26 — CM4 BCM 23 and 24.**
>
> They do **not** mean the SIM7500 module's own `IN1`/`IN2` GPI pins. Both pairs exist, both are
> called IN1 and IN2 in their own documentation, and they are different pieces of silicon.
>
> Everything in this handoff is the J26 channels. The module's GPI is covered in §3.1 and the answer
> there is: do not use it.

---

## 2. What the reader must drive — outputs

### 2.1 SPEED (OUT1–3) and DIRECTION (OUT4)

Unchanged, except that DIRECTION now has a committed polarity.

- `SPEED` is a 3-bit binary value 0–7 on OUT1/2/3, LSB first. **000 = stop.**
- `DIRECTION`: **de-asserted = FORWARD, asserted = REVERSE.** This is now fixed in the vendor
  document; do not change it.
- DIRECTION is a level, held while that direction applies. It carries no meaning while SPEED = 000.

Outputs are active-HIGH at the GPIO (`Hardware-IntelliRFIDv2.md` §3). The boot failsafe holds:
every field output is on BCM ≥ 9 and resets pull-DOWN, so SPEED = 000 before any of our software
runs. Do not add anything at start-up that disturbs that.

### 2.2 RESULT (OUT5) — one channel carries both verdicts

This is new firmware. Pass and fail share one wire, encoded by **pulse width**:

| Verdict | Emit on OUT5 |
|---|---|
| **FAIL** | one pulse, **100 ms** |
| **PASS** | one pulse, **500 ms** |

The PLC decodes 60–200 ms as FAIL and 400–600 ms as PASS, and treats **everything else** — any other
width, more than one pulse, or nothing at all — as FAIL.

Requirements on our side:

1. **Exactly one pulse per carton.** Never two. Never a retry.
2. **Width accuracy matters.** The decode bands are ±40 % on FAIL and ±20 % on PASS. A pulse
   generated by a sleeping thread on a loaded JVM can miss that. Drive it from something that does
   not depend on scheduler latency for its *width* — take the timestamp, hold the line, release on a
   deadline you actually measure, and log the achieved width so a drift shows up in the field rather
   than in a complaint.
3. **A 500 ms assertion is a long time to hold a line.** It must not block the read path for the
   next carton. Emit asynchronously and let the inventory loop carry on.
4. **There is no "no verdict".** If we reach the end of a carton without deciding, we emit FAIL.
   Silence is not an option we get to take — the PLC reads silence as FAIL anyway, so emitting it
   explicitly is the difference between an outcome and a guess that happened to match.

The PLC opens its verdict window when it pulses ZONE_ARRIVE and closes it on the verdict, the next
ZONE_ARRIVE, or 60 s — whichever comes first. **So the verdict must be emitted before the next
carton's ZONE_ARRIVE.** On a fast line that is the real deadline, not the 60 s.

### 2.3 HEARTBEAT (OUT6) — new firmware, and the shutdown handshake rides on it

- **Toggle at 1 Hz: 500 ms high, 500 ms low.** The PLC faults if it sees no transition for 3 s.
- It must keep toggling through everything the application does. A heartbeat that stalls because a
  read is in progress, a callback is retrying, or the spool is being replayed will stop the
  conveyor. **Put it on its own thread with nothing else on it**, and do not let it share a
  scheduler with work that can block.
- It means only "the application is running". It deliberately does **not** promise the RFID module
  is up — that is stated in the vendor document, so a reader with a dead module will show ready and
  fail every carton, and that is the agreed behaviour.
- **It stops only at the very end of a commanded shutdown** — see §4. Nowhere else.

### 2.4 OUT7 — parked

Wired to a spare terminal in the panel, connected to nothing. Do not drive it. If anything in the
code currently drives BCM 13, remove it.

---

## 3. Super Fast Mode — the close condition changes

This is the behaviour change. §7a of your handoff-03 describes what is built today; this replaces
the closing half of it.

### 3.1 Trigger source: the J26 field inputs, not the module

**Super Fast Mode must not use the SIM7500's own digital inputs.** No `BackReadOption.IsGPITrigger`,
no `gpiStats[].State` trigger condition, no module-side start/stop. That path is described in
`PLC-Digital-IO-Interface.md` §2 and §5 and it is abandoned.

The trigger is the **J26 field input channels, read by the CM4**: IN1 (BCM 23) and IN2 (BCM 24).

**Your current implementation is already correct on this point.** `tunnel.v1.gpio.entry-line: 23`
and `exit-line: 24` *are* field IN1 and IN2 on J26. Nothing needs undoing. What follows is a change
to when the read closes, not to where the edges come from.

Worth renaming for the next person, though: `entry-line` / `exit-line` are good names for what they
do, but a comment tying them to **J26 IN1 / IN2** — and saying explicitly that they are not the
SIM7500's IN1/IN2 — would have saved me a lookup and will save someone a mistake.

Why the module path is dropped, so it does not get reintroduced as an optimisation: the module can
start a read on its own GPI faster than we can, but it cannot participate in the verdict, the
heartbeat, the shutdown handshake, or the zone state machine. Splitting the interface across two
pieces of silicon buys microseconds on one edge and costs us a single place where the carton's
lifecycle is known. The read is not latency-bound; it is bounded by the carton's transit.

### 3.2 Open on IN1 rising edge

A **rising edge on IN1** opens the read window for a carton. Start inventory on that edge.

Not on the first tag seen. Not on a timer. Not on the module's own trigger. The PLC drives IN1
straight from the optical sensor at the zone entry, in real time — that edge is the carton arriving,
and it is the only thing that is.

### 3.3 The carton sequence, exactly

This is the change, and it is specified step by step so there is nothing to infer.

1. **Start reading on a rising edge on IN1.**
2. **Note the time the expected count was first reached.** Record it. Do **not** close on it.
3. **Note the time the tag count settled** — no new distinct tag for the settle interval. Record it.
4. **If IN2 has not gone high by then, the settle closes the carton.** Publish the callback with
   `stopReason: SETTLED`.
5. **If IN2 goes high before the population has settled, the exit edge closes the carton.** Publish
   with `stopReason: PACKAGE_EXITED`.
6. **Whether the count was as expected is reported the same way either way.** It is computed from
   the matching count against `expectedCount` and nothing else.

So: **settle and the exit edge are the only two things that close a carton**, and whichever happens
first is the one that closes it and names the stop reason. A read budget expiring stays as the
backstop for a carton that neither settles nor leaves — `TIMEOUT`, as now.

| What closed the carton | `stopReason` |
|---|---|
| The population settled, IN2 not yet seen | `SETTLED` |
| IN2 rising edge, population had not settled | `PACKAGE_EXITED` |
| Neither, and the read budget expired | `TIMEOUT` |

> **With the default settings, `COUNT_REACHED` does not occur in Super Fast Mode.** Reaching the
> count is an observation with a timestamp, not an ending. It becomes an ending only if the caller
> deliberately asks for that — see §3.3.1. This is a correction to what I told you in my previous
> draft of this section; step 2 above is the default and the authority.

**Step 6 is the part most likely to be got subtly wrong, so to be explicit:** `complete` and
`stopReason` are independent. A carton that settled with 18 of 20 is `SETTLED` with
`complete: false`. A carton that reached 20 of 20 and then left before settling is
`PACKAGE_EXITED` with `complete: true`. Neither reason implies anything about the count, and the
count implies nothing about the reason. Do not let one soften or override the other.

**Publish once per carton.** When the settle closes a carton, the IN2 edge that follows for that
same carton is consumed and discarded — no second callback, and no new window. Only an IN1 edge
opens a window.

`endedAt` is the moment the window actually closed. `settledAt` stays as you built it. The
count-met moment from step 2 needs somewhere to live — see §6.

**In the code this is one boolean in `V1Service.superFastSpec()`.** It computes
`boolean sensorOwnsTheEnd = gpio.isWatching()` and passes `!sensorOwnsTheEnd` for both `exitOnCount`
and `exitOnSettle`, so with sensors present both are false and only the exit edge closes.

- `exitOnCount` **defaults to false**. The count does not close anything — step 2. But it stays a
  real, settable flag; see §3.3.1 immediately below.
- `exitOnSettle` becomes **true**, unconditionally. Settle closes — step 4.

That is the whole change to the close policy. `sensorOwnsTheEnd` no longer describes anything true:
the sensor owns the *latest possible* end, not the end.

### 3.3.1 `exitOnCount` stays a flag, settable from the API

`exitOnCount` is **not** to be hard-wired to false. Keep it as a real parameter that can be flipped
per arming, from `POST /api/v1/mode`, without a rebuild or a config change.

| `exitOnCount` | Behaviour |
|---|---|
| **`false` — the default** | The §3.3 sequence. Count-met is recorded; settle or the IN2 edge closes the carton. |
| `true` | Count-met closes the carton immediately, `stopReason: COUNT_REACHED`. Settle and the IN2 edge remain as the other two close conditions for a carton whose count is never met. |

Notes on building it:

- **Optional in the request, defaulting to false when absent.** An arming call that does not mention
  it must behave exactly as §3.3 describes. A missing field must never be read as `true`.
- **Same name on the wire as in the code** — `exitOnCount` — unless you have a better one. One name
  for one concept across `ArmRequest`, `SessionSpec` and the document removes the commonest kind of
  translation bug, and this flag changes what a carton's result *means*, so it is worth being
  pedantic about.
- **`ArmRequest`'s javadoc is already wrong** and gets worse with this change: it says
  `expectedCount` "ends each read as soon as it is reached". That has not been true since sensors
  arrived and is the opposite of the default now. Fix it in the same commit.
- **It is an arming-time decision, not a per-carton one.** It belongs beside `ean` and
  `expectedCount` in the arming call, and re-arming is how it changes — consistent with the
  document's existing "no partial update" rule.
- **`/api/v1/mode` GET should report it**, so an operator can see which way a running tunnel is set
  without inferring it from results.

Why it is worth keeping rather than deciding once: with it false the reader keeps looking until the
carton settles or leaves, which is the honest reading and the right default. With it true the reader
stops the moment the WMS's expected count is satisfied, which is faster and is the right answer on a
line where the count is trusted absolutely. That is a line-by-line judgement, not a product-wide one,
and it should not need me or you to rebuild anything to change our minds.

Two follow-ons that are not mechanical:

- **`SessionSpec`'s javadoc for `exitOnSettle` becomes wrong.** It says settle is false "when
  something else owns the end of the read — a fixed duration, or the carton physically leaving the
  zone". The carton leaving no longer suppresses settle. Fix the prose in the same commit; that
  javadoc is the only place this policy is written down in the code.
- **`ResultMapper`'s stop-reason precedence must be re-derived from step 6.** Your §7a ordering was
  built for a world where everything was observed and judged at the exit — count-not-met beat
  everything, and a population that settled short still reported `PACKAGE_EXITED`. That ordering is
  now wrong twice over: the reason is **what closed the window**, and the count is reported
  separately and never changes the reason. A carton that settles short of its count is `SETTLED`
  with `complete: false`.

### 3.4 The fallback when no edges arrive

Your §7a fallback — open on the first tag, close on settle — stays, and stays reported as `degraded`
in `/api/v1/reader/status`. It is what happens on a bench with no PLC. It is not equivalent and the
document does not promise it.

---

## 4. Clean shutdown — new firmware, and the reason it exists

The PLC can request a controlled shutdown. The whole sequence exists to protect one file: the
serial-number high-water mark. A duplicate serial is invisible from the reader and invisible from
the tags, and surfaces weeks later as two cartons claiming to be the same carton.

### 4.1 Recognising the request on IN3

The PLC emits **five pulses on IN3** (BCM 18): 200 ms on, 200 ms off, all five inside a 5 s window.

- Exactly five. Four or six is not a request — discard it silently, no error, no log noise beyond
  debug.
- A partial or slow burst is discarded and nothing happens.
- **IN3 is no longer `READER_ENABLE`.** It is not a level any more. Any code holding the reader up
  or down based on the IN3 level must go.

`GpioEdgeMonitor` already does exactly the right thing for this — rising edges, kernel timestamps,
one handler per line — so it wants a **third line** (BCM 18) and a small burst recogniser on top:
count rising edges, require five inside 5 s, reset the tally when the window lapses. The existing
`debounceMs: 50` is comfortable against 200 ms pulses; do not raise it past ~150 ms or the burst
starts eating its own edges.

One thing to watch: `gpiomon` is spawned once for the configured lines, so adding line 18 changes
the command line and the parse. Keep the "missing hardware is degradation, not failure" property —
a bench with no PLC must still come up, and a reader that cannot watch IN3 should log that it cannot
accept a shutdown request rather than refusing to start.

### 4.2 What we do on acceptance, in this order

1. Stop inventory, drop the RF carrier.
2. Set `SPEED = 000` and `DIRECTION = 0`.
3. Finish or abandon any in-flight tag write.
4. Commit and close the serial counter — fsync, then confirm.
5. Flush every outstanding write; put storage into a state that is safe to interrupt.
6. **Only now: drive HEARTBEAT (OUT6) low and leave it low.**
7. Power down.

**Step 6 is the whole point.** The heartbeat is the reader's statement that it is safe to cut power.
If it stops at step 1, the PLC signals "safe" while we are still writing, and we have built an
elaborate sequence that causes the exact corruption it exists to prevent.

The PLC waits for 3 s of continuous heartbeat absence before showing safe-to-power-down, and raises
a fault if we have not stopped within 60 s. **So the sequence has a 60 s budget.** If any step can
block longer than that, it needs a bound.

### 4.3 Power-up

Nothing new to build, but confirm the behaviour: SPEED reads 000 throughout boot (hardware, §2.1),
and the heartbeat begins toggling once the application is up. The PLC counts three clean transitions
before declaring READY and allows 60 s. Our 20–40 s cold start is inside that. If start-up ever
grows past ~50 s, that is an interface problem, not just a slow boot.

---

## 5. Input handling — the rules that apply to all four channels

- **Debounce ≥ 10 ms**, and the 15 ms already configured is fine. EFT bursts couple through the
  opto barrier capacitance and register as false edges; all eleven channels share one return and
  that return is how cross-channel disturbance arrives.
- **Inputs are inverted relative to outputs.** Field-asserted reads as GPIO low. Keep that inversion
  inside a `FieldIo` boundary so nothing above it sees raw levels — `Hardware-IntelliRFIDv2.md` §3
  calls this the highest-probability day-one bug and it is right.
- **Disable the internal pulls on BCM 18/23/24/25** explicitly at start-up. They sit in the
  pull-DOWN group and oppose the external 10 k pull-up: 2.75 V reads high with 0.44 V of margin
  instead of 1.0 V.
- **Use kernel edge events, not polling** — `GpioEdgeMonitor` already does, and already carries the
  `stdbuf` wrapper that closes your block-buffering finding. The trap is closed; the note here is so
  nobody "simplifies" the wrapper away later, because the symptom of removing it is missed edges,
  which points at the wrong diagnosis.
- **Timestamp from the kernel's edge event**, not from when the JVM got around to noticing —
  `onRisingEdge` already hands the handler the kernel's monotonic nanos. The window boundaries end
  up in `startedAt` / `endedAt` and go to the customer.

---

## 6. What this changes in the API document

`docs/Intelli-RFID-RestAPI.docx` still does not describe Super Fast Mode as built, and §3.3 changes
what it needs to say. Updated list — I will make these changes:

1. **`PACKAGE_EXITED`** as a fourth `stopReason`. Still needed. Under §3.3 it means precisely: the
   carton left before the population settled. It says nothing about the count.
2. **`settledAt`** in the result object. Unchanged.
3. **`countReachedAt`** — a new field, and the home for step 2 of §3.3. The moment the expected
   count was first met, absent when it never was. It cannot ride on `endedAt` any more, because
   reaching the count no longer ends anything. **Name it whatever reads best beside `settledAt` and
   tell me; I will document what you build.**
4. **`endedAt`** — now simply "when the read window closed", by whichever of settle, exit edge or
   budget closed it. The mode-specific meaning you documented in §7a goes away.
5. **`stopReason` and `complete` are independent**, stated explicitly in the document. The WMS
   branches on `stopReason` and it must not infer the count from it — §3.3 step 6.
6. **`exitOnCount`** on the arming call — optional, default false, and what each setting does to
   `stopReason` (§3.3.1). The WMS needs to know that the same tunnel can be armed either way and
   that `COUNT_REACHED` is therefore a value it must handle.
7. **The two-sensor assumption**, and the `degraded` fallback.

Plus the four invented error slugs from your §2.5 (`invalid_mode`, `timed_required`,
`expected_count_required`, `invalid_direction`) — going in as documented values.

---

## 7. What to test on the bench

The edges can still be produced by flipping the pins' internal pulls, as you did. That exercises the
path; it says nothing about a real beam's bounce.

| # | Test | Pass |
|---|---|---|
| 1 | IN1 edge opens a read | Window opens on the edge, not on the first tag |
| 2 | Count met, then settle, then IN2 | Closes on **settle**, `SETTLED`, both the count-met time and `settledAt` present, `complete: true`. The later IN2 edge produces **no second callback** |
| 3 | Count met, then IN2, never settled | Closes on **IN2**, `PACKAGE_EXITED`, **`complete: true`** — the count was met and the reason does not soften it (§3.3 step 6) |
| 4 | Settled short of the count, no IN2 | Closes on **settle**, `SETTLED`, `complete: false`. Must **not** report `PACKAGE_EXITED` — the carton had not left |
| 4b | Neither count nor settle, then IN2 | `PACKAGE_EXITED`, `complete: false` |
| 4c | Arming call with no `exitOnCount` | Default false. `COUNT_REACHED` **never appears** on any carton in the run |
| 4d | Arming call with `exitOnCount: true` | Count-met closes immediately, `COUNT_REACHED`, and the later IN2 edge produces no second callback |
| 5 | Two cartons back to back | Two callbacks, two sequence numbers, no window opened by an IN2 edge. `onCartonLeft` already returns early when `activeSession()` is empty, so this should pass unchanged — confirm it rather than assume it |
| 6 | RESULT pulse width | Scope or log the achieved width on OUT5 over 100 cartons. **Every** pulse inside 400–600 or 60–200 ms. Report the spread — that number decides whether the encoding survives a loaded JVM |
| 7 | Verdict before next ZONE_ARRIVE | At the shortest carton pitch you can produce, the pulse completes before the next IN1 edge |
| 8 | Heartbeat under load | Toggling stays within tolerance during a read, a callback retry storm and a spool replay |
| 9 | Five pulses on IN3 | Accepted. Four pulses, six pulses, and a slow burst are all silently ignored |
| 10 | Shutdown ordering | Heartbeat still toggling at steps 1–5, goes low only after the serial counter is committed. **Verify by log timestamps, not by assertion** |
| 11 | Shutdown budget | Whole sequence completes inside 60 s with a full spool and a write in flight |
| 12 | Boot | SPEED = 000 from power-on through to application ready |

Test 6 is the one I would not skip. Everything else fails loudly; a verdict pulse that is 380 ms
instead of 500 ms fails as a **silent wrong answer** at the customer.

---

## 8. What NOT to do

- Do not drive OUT7 (BCM 13) or read IN4 (BCM 25). Both are parked.
- Do not use the SIM7500's GPI for the inventory trigger.
- Do not treat IN3 as a level.
- Do not emit more than one RESULT pulse per carton, and do not retry one.
- Do not let the heartbeat share a thread with anything that can block.
- Do not change any timing in this document to a rounder number. The vendor's ladder is being
  written to these exact figures, and a mismatch will surface as an intermittent fault on the first
  end-to-end test, which is the most expensive place to find it.

---

## 9. Open on my side

Nothing on the interface. The vendor document is closed.

One thing still owed to you: the API document changes in §6 above.

**And one fact that changes your bench, which is not a question.** All 18 tags were written on
2026-08-29. Nothing was held back as a control and nothing is in a `to-write` state, so the
`role` values in `bench-tag-register.jsonl` are a record of what was planned on the 28th rather than
the state of the rig, and every EPC in it is stale — **re-probe before relying on it.** The TID
keying survives, which is the reason it was keyed that way.

The population's mix of decodable and undecodable EPCs has therefore changed, so any test that
assumed "2 of 18 valid GS1" needs its assumption re-checked against what is actually on the tags.
When a particular mix is wanted for a classification test, the tags will be rewritten in the format
that test needs. How many tags to write is a closed question and is not to be raised again.

---

*Laptop session, 2026-08-30. The interface figures here are quoted from the vendor document as sent
and are not open to adjustment. Where I have reasoned about firmware structure rather than
specified it — the threading in §2.3, the pulse generation in §2.2 — that is advice and you are
closer to the code than I am; the numbers are not.*
