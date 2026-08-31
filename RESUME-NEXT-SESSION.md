# Resume here — CM4 session, next sitting

Written at the end of 2026-08-28, **updated 2026-08-31**. Everything below is measured on hardware
unless it says otherwise.

**Read `HANDOFF-LAPTOP-TO-CM4-TUNNEL-05.md` first — it is the current work list.** The PLC interface
is closed and sent to the vendor, who is writing ladder against it now; it changes Super Fast Mode's
close condition and adds three pieces of firmware plus one endpoint. The ordered plan is in §−1
"Next, in order". `HANDOFF-CM4-TO-LAPTOP-TUNNEL-03.md` remains the full build report for the
`/api/v1` layer and answers the laptop's five audit questions. This file is the short version plus
what to do next.

---

## −1. If you are on the production CM4, start here — bring-up COMPLETE (2026-08-29)

The v2.x unit is through `CM4-PRODUCTION-BRINGUP.md` **except step 10**. As of 2026-08-29 the
tunnel runs on this board and serves v1 reads against the real module.

| Step | State |
|---|---|
| 0 SDK, 1 packages, 4 native lib, 5 clones, 6 build | **done** |
| 2 UART | **done, verified** — reader is `/dev/ttyAMA0`, `uart3` took `ttyAMA3` |
| 3 directories, 6 site config | **done** — `/etc/intelli/intelli-rfid-tunnel/application.yml` installed `root:intelli-sbc 640`, three API keys issued |
| 7 GPIO enable | **done by hand** — and it needs a third pin, see below |
| 8 probe | **done: 18 of 18 tags, five sweeps, 27 dBm, `RG_EU3`, Java 21** |
| 9 run by hand | **done: two v1 reads, 18 distinct EPCs through the full contract path** |
| 10 systemd | **not started** — the only step left |

### Step 9, what it actually returned

`matched: 0` / `unexpected: 2` / `undecodable: 16` on a 3 s timed read for
`ean 8905527164445` — the whole 18-tag bench population, and `matched` is 0 only because no tag
here carries that SKU. `sequence` advanced 1 → 2, `spoolDepth` 0, module 34 °C. First read stopped
`TIMEOUT`, second `SETTLED`.

- **The site config runs `session: 0`, marked bring-up only.** Packaged `session: 2` plus a
  continuously-on carrier (the sensors are disabled) makes this tag stock answer once and go silent
  for >15 s. Revert to 2 when the sensors are live.
- **`/api/v1/reader/status` needs the INVENTORY scope**, not ADMIN. The operator key gets
  `403 insufficient_scope` there — scope rules working, not a misconfiguration.
- **`degraded` is absent and should be**: it only speaks for a broken spool or a reader *armed*
  for Super Fast Mode. The runbook used to claim otherwise and is corrected.
- **Open item 5 reproduced on production hardware:** the tags' own EAN `8905190881260` is rendered
  in read results next to `gtin14: 98905190881260`, but rejected as a *request* parameter with
  `400 invalid_ean` (mod-10). It is a GTIN-14 variable-measure item, so its 13-digit form is not a
  valid EAN-13. The read path and the request path disagree about what an `ean` is.

### What the probes settled

- **`/dev/ttyAMA0` is the reader**, on this board as on the bench. Nothing needs renaming.
- **The vendor JNI is clean at call time on Java 21.** Both halves of that risk are now closed.
- **`RG_IN` is refused here too.** This module accepts `RG_NA`, `RG_EU3`, `RG_PRC`, `RG_OPEN` — a
  wider SKU than the bench's, same firmware — and **arrives set to `RG_NA`**, which must not be
  keyed up in India. Run `RG_EU3`.
- **The hop table is writable, and that is the India answer.** `RG_EU3` hops
  865.7/866.3/866.9/**867.5**; the last is outside 865–867. Writing `{865700, 866300, 866900}`
  under `RG_EU3` sticks. **Setting the region rewrites the table**, so order matters, and
  `ReaderSession.applyConfig()` does not do it yet.
- Module: hw `31.00.00.80`, sw `20.26.03.30`, `MODULE_ONE_ANT`, `antportnumbers = 1` — the module
  itself confirms `antenna-count: 1`. Power reads 5–30 dBm; **the 27 dBm ceiling is the carrier's
  and the module does not enforce it.** 29 °C idle, 32 °C after five sweeps.

### The thing that will cost you an hour if you forget it

**`RFID_NRST` (GPIO10) has to be driven HIGH, not just `RFID_EN` (GPIO22).** Both boot as inputs
with the BCM2711 pull-down, so the module comes up powered *and held in reset*. Measured: with
GPIO10 released, `InitReader_Notype` returns **`MT_UNKNOWN_READER_TYPE`** — which looks like a baud
or SDK problem and is not. The full sequence, in order:

```bash
pinctrl set 8 op dh && pinctrl set 9 op dl   # ANT1 first - never key up into an open port
pinctrl set 22 op dh                          # RFID_EN
pinctrl set 10 op dh                          # RFID_NRST out of reset
```

These do not survive a reboot and nothing in the app does them. Step 10's `ExecStartPre` must.

### Commissioning was rewritten this afternoon — read this before writing tags

`POST /api/v1/tags/write` with `count > 1` now **targets each tag by its factory TID** through a
Select filter, rather than writing whichever tag answers. The old path wrote the wrong tags and
misreported which: a count=18 batch reported 2 written and 16 failed when five of the "failures"
were on tags. Both halves of write-then-verify are now pinned to one tag, with a TID read-back
proving the filter applied, and the whole batch runs inside **one** `whilePaused` instead of three
inventory restarts per tag.

Proven on hardware 2026-08-29 with 11 tags in the field: **8 written, 3 refused, and 8 of 8 verified
on the right tag afterwards** — every failure naming its own TID and leaving that tag untouched.

Two things go with it:

- **`write-power-dbm10` must be 2700, not 2000** — and it is, in the site config since
  2026-08-29. At 20 dBm every targeted write returns `MT_CMD_NO_TAG_ERR` on tags being read
  perfectly at that moment. Unfiltered writes hid it, because they land on the strongest tag.
  Do not lower it back towards the packaged default.
- **The core change is uncommitted and has no test.** `CommissioningController`,
  `CommissionRequest.targetTids`, `CommissionResponse.Failed.tid`. It was proven at the module, not
  in CI, and the TID path deserves a test before it is trusted anywhere but this bench.

Serials 1–18, 45, 46, 99, 101–103 and 301–311 are consumed on the bench stock; start above 312.
`bench-tag-register.jsonl` is stale — it still lists every tag as `to-write`.

### Where the unit was left, end of 2026-08-29

- **Bring-up is COMPLETE.** `intelli-rfid-tunnel.service` is installed, enabled and active, running
  the config-driven launch with no overrides. The unit raises all four GPIO pins itself in
  `ExecStartPre`, so a reboot now comes up reading without a person. Source of truth for the file:
  `~/intelli-rfid-tunnel.service`, and runbook step 10 matches it.
- **`systemctl {start,stop,restart} intelli-rfid-tunnel`** — and stop it before running any probe:
  one process owns `/dev/ttyAMA0`.
- **All 18 bench tags are commissioned** to GTIN-14 `08905527164445`, serials 1–17 plus 312, and
  `bench-tag-register.jsonl` is reconciled. **All four control tags were written over**, so this
  bench can no longer exercise `undecodable` or `unexpected` — restore them from `originalEpc`
  before running contract tests here. See `tools/bench-tag-register.md`.
- **Nothing is committed.** Docs at the workspace root, `bench-tag-register.{jsonl,md}` and the
  commissioning change in core are all uncommitted, and nothing has been pushed.

### Next, in order — re-planned 2026-08-31 after the laptop's handoff-05

**The PLC work below is now the largest item in the project and it has an external deadline: the
vendor is writing ladder against the sent document right now.** It outranks the loose ends in B.

#### A. The PLC interface — `HANDOFF-LAPTOP-TO-CM4-TUNNEL-05.md`

The interface is **closed**. `docs/Intelli-RFID-Reader-DVP12SA211R-PLC-Integration.docx` went to the
PLC vendor on 2026-08-30 and none of its numbers will move. **Where the code and that document
disagree, the code is wrong.** Do not round any timing to a nicer figure.

> **Progress, 2026-08-31 — items 1–6 are ALL done. Section A's build work is complete.**
> 136 tests pass, up from 74. What is left in A is item 8, the bench tests, which need the app
> running against real pins.
>
> | # | Item | State |
> |---|---|---|
> | 1 | Close condition: settle or the exit edge, not the count | **done** `b0acefd` |
> | 2 | `exitOnCount` as an API-settable flag | **done** `b0acefd` |
> | 3 | `RESULT` on OUT5, width-encoded | **done** `d113515` |
> | 4 | `HEARTBEAT` on OUT6 | **done** `87516ab` |
> | 5 | `SHUTDOWN_REQUEST` on IN3 + the shutdown sequence | **done** `9f2492f` |
> | 6 | `/api/v1/diagnostics/io` | **done** `7c6024c` + core `d93bdc0` |
> | 7 | The "do not" list | partly enforced: `FieldIo.write()` refuses parked channels |
> | 8 | Bench tests 1–15 | **next** — needs the app running against real pins |
>
> **`com.intelli.rfid.tunnel.plc` now exists and items 5 and 6 both sit on it**: `FieldChannel` is
> the authoritative channel map, `FieldIo` owns the field-sense inversion, `PinctrlFieldIo` drives
> the pins, and `HeartbeatDriver` / `ResultSignal` are the two consumers so far.
>
> **Measured on this board while building it** — all of it now in `CLAUDE.md`: field outputs boot
> `ip pd | lo` (the failsafe holding SPEED at 000), field inputs boot `ip pd | hi` with the internal
> pull-down still opposing the carrier's external pull-up, `pinctrl get` has two output shapes, and
> OUT5 pulses landed at **PASS 496–504 ms / FAIL 98–100 ms** over 20 cartons with none outside the
> decode band. That last number was taken on a near-idle machine and **bench test 6 still wants 100
> cartons under read load** before it is trusted.
>
> ### The carrier is now triggered, and the restart-rate risk is measured and cleared
>
> **Carrier-off-between-cartons was documented as the design and was not implemented.** The carrier
> ran from boot and nothing in the carton path stopped it; IN1 only opened a *logical* session over
> a running tag stream. Observed on this board: `session: 2` plus a continuous carrier read 15 tags
> once and heard **nothing for three minutes** — S2 holds the inventoried flag for as long as the
> tag stays powered, so a second carton would read empty *permanently*, not for the ">15 s" on
> record (that figure was measured across carrier-*off* gaps). Fixed in `b5cefd6`:
> `tunnel.v1.triggered-carrier`, on by default, active only when the sensors are watching.
>
> **The risk that could have killed it is measured and gone.** One stop/start per carton looked
> unsafe against CLAUDE.md's "four restarts in thirty seconds gives `MODULE_NEED_RESTART`".
> Measured 2026-08-31 with `ProbeRestartRate`: **30 restarts in 30 s, all clean, ~50 tags every
> cycle**, `StartReading` 0–3 ms, `StopReading` 20–60 ms. The old rule does not apply to bare
> start/stop — both recorded failures changed a *parameter* alongside each restart, and that is the
> remaining unisolated suspect.
>
> ### The edge polarity is wrong and is NOT yet fixed — decide this before bench testing
>
> **Field-asserted on an input is GPIO LOW** (24 V on the pin lights the opto and pulls it down),
> but `GpioEdgeMonitor` watches **GPIO rising** edges on all three lines. Confirmed empirically on
> this board 2026-08-31 by driving line 18: a field-assert produced **0** events, the de-assert
> produced **1**.
>
> So against the interface as documented — the PLC asserting a 2 s `ZONE_ARRIVE` pulse — the read
> window opens on the **trailing** edge, two seconds after the carton arrived. Same for
> `ZONE_EXIT`. **IN3 is unaffected in substance**: five asserted pulses still give five trailing
> edges, so the burst count and window still work, shifted by 200 ms.
>
> **Left unchanged deliberately, on Piyush's instruction** — the optical sensor may be configured to
> match instead, and a push button gives a rising edge on *release*, which is fine for manual
> testing. Three ways out, and the choice is not made:
>
> 1. **Wire/configure the sensor** so the channel is de-asserted at the moment of interest. Check it
>    against the `.docx`, which specifies `ZONE_ARRIVE` as a 2 s *pulse* — inverting at the panel
>    means the vendor's ladder and the wiring must agree on which state is idle.
> 2. **`gpiomon -l / --active-low`** — present on both v1 and v2. Flips edge sense so "rising" means
>    *the channel became active*, matching what `FieldIo` already does for levels and the handoff's
>    own wording ("a rising edge on IN1", where IN1 is the channel, not the pin). One flag.
> 3. Watch falling edges explicitly.
>
> **Whichever is chosen, note the inconsistency it leaves today:** `/api/v1/diagnostics/io` reports
> **field sense** (an asserted IN1 shows `HIGH`) while the edge monitor triggers on **raw GPIO**, so
> on a real PLC the screen shows IN1 asserted at a moment the trigger has not fired. Those two
> should end up agreeing.
>
> **A latent bug found and fixed while doing item 5, worth the laptop knowing.**
> `GpioEdgeMonitor` built **libgpiod v1** arguments and this CM4 has **v2.2.1**, which renamed all
> three: `--rising-edge` → `--edges=rising`, the chip → `-c`, `%s.%n` → `%S`. **v2 prints an unknown
> format specifier literally**, so every edge would have arrived as the text `18 %s.%n`, failed to
> parse, and left the monitor reporting itself broken while `gpiomon` worked perfectly. It had not
> bitten only because this unit's site config has `gpio.enabled: false` — it would have failed the
> instant the sensors were switched on and looked exactly like bad wiring. Now auto-detected from
> `gpiomon --version`, overridable by `tunnel.v1.gpio.libgpiod-major`, both syntaxes pinned by tests.
> **The bench rig is v1.6.3 and stays a valid comparison point; this is another axis on which the
> two machines differ.**
>
> **Also: the internal-pull trick for faking an edge does not work on this carrier.** The external
> 10 kΩ pull-up dominates the internal pull, so an input reads high in both states. Drive the pin
> instead — `pinctrl set 18 op dl` then `op dh` — verified 2026-08-31, and put it back to `ip pd`.
>
> **One decision made rather than asked, and the laptop should hear it:** removing the
> `matched >= expected` short-circuit from `ResultMapper` also changed **Managed Reading**. A
> `timed: true` read that ran its full window with its count met used to report `COUNT_REACHED` and
> now reports `SETTLED` or `TIMEOUT` on the evidence. Handoff-05 §3.3 is scoped to Super Fast Mode
> and did not call this path out; one rule over one field was chosen deliberately, because two rules
> over one field is how `V1Service` and `ResultMapper` drifted apart before. **`countReachedAt` is
> the name chosen for §6.3's new field**, which the laptop asked to be told.

1. ~~**Super Fast Mode's close condition changes**~~ **— DONE** (handoff §3.3). Count-met no longer ends a carton —
   it is recorded with a timestamp. **Settle or the IN2 edge closes, whichever comes first**; the
   read budget stays as the `TIMEOUT` backstop. In code this is `V1Service.superFastSpec()`:
   `exitOnSettle` becomes unconditionally **true**, `exitOnCount` defaults **false**.
   - `stopReason` and `complete` become **fully independent**. A carton that settles short is
     `SETTLED` + `complete: false`; one that met its count then left is `PACKAGE_EXITED` +
     `complete: true`. Neither softens the other.
   - **`ResultMapper`'s stop-reason precedence must be re-derived** — the old ordering let
     count-not-met beat everything, and that is wrong twice over now.
   - Publish **once per carton**: the IN2 edge following a settle-closed carton is consumed and
     discarded. Only an IN1 edge opens a window.
   - Fix the now-wrong javadoc on `ArmRequest.expectedCount` and `SessionSpec.exitOnSettle` **in the
     same commit** — that javadoc is the only place this policy is written down in code.
2. ~~**`exitOnCount` stays a real API-settable flag**~~ **— DONE** (§3.3.1) — optional on the arming call,
   defaulting to false, absent must never read as true, same name on the wire as in the code, and
   reported by `GET /api/v1/mode`. It is an arming-time decision, not per-carton.
3. ~~**`RESULT` on OUT5 (BCM 21) — new firmware**~~ **— DONE** (§2.2). One width-encoded pulse per carton:
   **100 ms = FAIL, 500 ms = PASS**. Exactly one, never a retry. Emit **asynchronously** so a 500 ms
   hold cannot block the next carton, and **log the achieved width** so drift shows up here rather
   than as a customer complaint. There is no "no verdict" — reaching the end undecided emits FAIL.
   The real deadline is the next carton's ZONE_ARRIVE, not the PLC's 60 s window.
4. ~~**`HEARTBEAT` on OUT6 (BCM 12) — new firmware**~~ **— DONE** (§2.3). 1 Hz, 500 ms high / 500 ms low, **on its
   own thread with nothing else on it**. The PLC faults the line if it sees no transition for 3 s,
   so it must survive a read, a callback retry storm and a spool replay. It means only "the
   application is running" — deliberately not "the module is up".
5. ~~**`SHUTDOWN_REQUEST` on IN3 (BCM 18) — new firmware**~~ **— DONE.** Pulse count is
   configurable: `--tunnel.plc.shutdown.pulses=1` for a push-button bench test. Original spec: (§4). Five 200 ms pulses inside 5 s;
   four or six is not a request and is discarded silently. `GpioEdgeMonitor` needs a **third line**
   plus a burst recogniser — and note that adding line 18 changes the `gpiomon` command line and its
   parse. Keep "missing hardware is degradation, not failure": a bench with no PLC must still start.
   - **The shutdown ordering is the whole point.** Heartbeat keeps toggling through steps 1–5 and
     goes low **only after the serial counter is committed and fsynced**. Dropping it at step 1
     tells the PLC "safe to cut power" while we are still writing — building the exact corruption
     the sequence exists to prevent. Whole sequence must fit in 60 s.
   - **IN3 is no longer `READER_ENABLE`.** Any code holding the reader up or down on an IN3 *level*
     must go.
6. ~~**`GET`/`POST /api/v1/diagnostics/io`**~~ **— DONE.** Original spec: (§5a) — ADMIN scope, explicit `ScopeRules` entry rather
   than relying on default-deny. The admin UI's PLC I/O tab is already built against it and shows
   404 until this lands.
   - **`level` is the FIELD sense, not the GPIO level.** Inputs are inverted at the GPIO, so do the
     inversion inside the reader. Get this wrong and the screen, the vendor's drawing and the
     multimeter all disagree — and the person with the multimeter is right. This is the single most
     likely thing to get wrong here, and it looks like working software until someone is on a ladder.
   - `POST` returns **`409 reader_armed`** while Super Fast is armed; `GET` is never refused.
     Read every channel back after applying and return the read-back, never what was asked for.
7. **Do not**: drive OUT7 (BCM 13) or read IN4 (BCM 25) — both parked; use the SIM7500's own GPI for
   the trigger; treat IN3 as a level; emit more than one RESULT pulse.
8. **← NEXT. Bench tests 1–15 in handoff §7.** Test 6 is the one not to skip: a 380 ms pulse where 500 ms
   was meant fails as a **silent wrong answer** at the customer, while everything else fails loudly.
   Edges can still be produced by flipping the pins' internal pulls, as before.

> **Already correct — do not "fix" these** (handoff §0.1): the J26 field-input trigger path, the
> `stdbuf` wrapper in the gpio config, and the `degraded` fallback and its reporting.

#### B. The board's own loose ends

9. **Test the TID commissioning path.** Proven at the module 2026-08-29, still has no unit test.
10. **Reboot once and confirm the service comes up reading** — the pins, the UART and the systemd
    unit have never been exercised together from cold.
11. **`RG_IN`: the updated vendor Java API doc set was expected today, 2026-08-31.** Everything runs
    on `RG_EU3` by decision until it lands. When it does, the first question is whether it carries
    new module firmware or an unlock procedure — **a doc change alone cannot alter what the module
    accepts.**
12. **The hop-table narrowing in `applyConfig()`** (open item C in the runbook). Until it lands this
    board hops 867.5 MHz, outside the Indian allocation, and its channel plan is whatever the last
    probe left. Region must be written **before** the table, because setting the region rewrites it.
13. **Re-probe `bench-tag-register.jsonl`.** All 18 tags were written on the 29th, so its `role`
    values record what was planned on the 28th rather than the state of the rig. The TID keying
    survives, which is why it was keyed that way. Any test assuming "2 of 18 valid GS1" needs its
    assumption re-checked against what is actually on the tags.

### One contradiction in the new documents — resolve before building to it

`PLC-INTEGRATION-DVP12SA2.md` §4 carries the **superseded** channel map and calls itself
authoritative (§4.3: *"§4 above is now the authoritative copy"*). Verified against the `.docx`
itself on 2026-08-31 — the `.docx` and handoff-05 agree, and the `.md` does not:

| | `PLC-INTEGRATION-DVP12SA2.md` §4 | **The `.docx` + handoff-05 (authoritative)** |
|---|---|---|
| OUT5 | `RESULT_OK` | **`RESULT`**, width-encoded |
| OUT6 | `RESULT_FAIL` | **`HEARTBEAT`** |
| OUT7 | `SPARE_OUT` | **parked** |
| IN3 | `SPARE_IN` | **`SHUTDOWN_REQUEST`** |
| IN4 | `SPARE_IN` | **parked** |

Handoff-05's "Changed?" column is written as a diff *against* that §4 map, so it is the intended
baseline — but nothing in the file says so. **Take channel functions from the `.docx`, never from
§4**, and ask the laptop to add a supersession header. Its §8 open item *"locate
`PLC-Digital-IO-Interface.md`, not present on this machine"* can also be closed: it is here at
`docs/PLC-Digital-IO-Interface.md`, and handoff-05 §0 already rules it superseded on channel
assignment and semantics, still sound for electrical reasoning.

**Committed and pushed 2026-08-31** across all four repos — root docs, the TID commissioning change
in core, the Java 21 poms, `bench-probe/run.sh` and the tag register. Nothing is outstanding.

---

## 0. What changed on 2026-08-29 — and the thing that changed the priorities

**The project moved to production hardware.** Piyush is standing up the real unit: a **CM4 on our
own IntelliRFID v2.x carrier**, with the SIM7500 soldered on (U20), instead of the vendor dev board.
This bench — a Pi 4B plus the "Develop Component A" board — is now the *second* machine, not the
only one.

**`CM4-PRODUCTION-BRINGUP.md` is the runbook for that unit**, and it is the first thing to read if
you are on the new CM4. Fresh flash → packages → UART → SDK → the four clones → build → site config
→ systemd, each step with a verification line. Steps 1–6 are what is installed and working here;
steps 7 and 8 have now been run on the v2.x board (§−1), and **steps 3, 9 and 10 are still read off
`docs/Hardware-IntelliRFIDv2.md` rather than measured**.

Its action box is the part that matters: **five things about that carrier the code does not handle**,
each enough on its own to make a correctly installed unit read nothing — `RFID_EN` on GPIO22 leaves
the module **off at boot**; the SIM7500 is **mono-static**, so `antenna-count` is 1 and both antennas
sit behind an SP4T on GPIO8/9 that nothing drives; **GPIO23/24 are active-LOW field inputs** while
`GpioEdgeMonitor` is hardcoded to rising edges; the power ceiling is **27 dBm**, not 30; and the
antenna port must be selected **before** the reader is enabled. To that five, add a sixth found on
the board itself: **`RFID_NRST` on GPIO10 boots low and holds the module in reset** (§−1). Region
`RG_IN` is answered — refused on this module too; run `RG_EU3` with a narrowed hop table.

**Open item 6 is done: a faulted reader now reconnects on its own** (see §4.6). Verified on hardware
against a real `IO_RECV_TIMEOUT`.

Everything below this line was written about **this bench**. Where it says "the CM4" it means the
Pi 4B, and a claim about wiring or pinout does not carry over to the carrier — see
`docs/Hardware-IntelliRFIDv2.md`, which is authoritative for that board.

---

## 1. Where the work is now

**The customer contract is implemented and running.** `/api/v1` — all five endpoints, the result
object, the three-bucket classification, `COUNT_REACHED`, the durable sequence, the callback sender
with retry/spool/replay, the mode state machine, scope enforcement with security **on**. Driven
end to end against the real module: Super Fast armed and reported thirty cartons autonomously, both
Managed Reading forms work, every documented error slug and status code checked.

The priority change in `HANDOFF-LAPTOP-TO-CM4-TUNNEL-04.md` is done. The audit was folded into the
build, as instructed.

### The two things a next session should pick up first — on this bench

(If you are on the **production CM4**, your list is `CM4-PRODUCTION-BRINGUP.md` instead.)

**1. Run the laptop's REST client against this reader.** That is the acceptance evidence nobody has
yet — it shares no code with the reader and checks every response against the `.docx`. Port 8081,
`callbackUrl` must be the laptop's LAN address. The one case I could not test is a **slow** WMS: a
5 s delay against the 2 s deadline is what proves the carton release really does not wait on the
callback.

**2. Commission the bench tags — this needs a person.** Gen2 cannot address "the next unwritten
tag", so someone has to present tags **one at a time**. All 18 tags were written on 2026-08-29. The
register — `apps/intelli-rfid-tunnel/tools/bench-tag-register.jsonl`, keyed on TID, 18 tags, all
Impinj — is therefore stale in its EPC column and needs re-probing; the TID keying survives, which
is why it was keyed that way. Read `bench-tag-register.md` beside it.

---

## 2. Running it

```bash
cd apps/intelli-rfid-tunnel
mvn -o package
java -Djava.library.path=/opt/intelli/lib \
     -jar target/intelli-rfid-tunnel-1.0.0-SNAPSHOT.jar \
     --spring.config.additional-location=file:/etc/intelli/intelli-rfid-tunnel/
```

`/etc/intelli/intelli-rfid-tunnel/application.yml` holds the bench overrides and the two API keys. It is **not**
in git and it is not in the jar, which is the point: rotating a key is a config change and a
restart.

- **`-Djava.library.path=/opt/intelli/lib` on every java command.** Still mandatory.
- **Security is on and the app refuses to start with no keys.** The bench keys are in that file
  (SHA-256 only). They are disposable and must be revoked before this unit goes near a customer.
- **The bench runs `session: 0`, set in that file.** With the packaged `session: 2` and a continuous
  carrier, a static bench population answers once and then goes silent — the first v1 read I ran
  returned zero tags and looked exactly like a broken layer. This does **not** settle the S2
  question; see §4.
- `--tunnel.auto-trigger=true` if you want the old bench behaviour on `/api/inventory/**`. It is off
  by default now, because arming Super Fast sets the trigger itself with the armed SKU and count.

One-shot probes still work the same way and are still the right tool for anything hardware-shaped:

```bash
cd apps/intelli-rfid-reader-test/tools/bench-probe
./run.sh ProbeVerify    /dev/ttyAMA0 3000 2 0 -250 107   # does the module keep what you set?
./run.sh ProbeFastId    /dev/ttyAMA0 3000 4000           # FastID: mechanism and cost
./run.sh ProbeRegister  /dev/ttyAMA0 3000 5000 out.jsonl # population register + FastID identity check
./run.sh ProbeSettle    /dev/ttyAMA0 3000 2 4 1500 20000 50 0
```

**Stop the app before running a probe** — one process owns `/dev/ttyAMA0`.

---

## 3. What changed under the hood, in one paragraph each

**The verified setter.** `applyConfig()` now sets *and reads back* rf-mode, session, target, Q,
region and power, and throws naming what was written and what came back. The general rule is in
`CLAUDE.md`: **a return code from this SDK is a lower bound on success, not a confirmation.** Do not
extend this to the per-read path.

**The dead read modes fail loudly.** `EX_FAST` and `IMPINJ_FAST` throw at `startReading` with a
message naming the firmware cause. No `GENERAL_FAST` value was added. `NORMAL` is the packaged
default.

**FastID is on, at connect.** The TID arrives appended to `EpcId` with the PC word grown to match —
*not* in `EmbededData`. Verified: 18 of 18 EPCs identical with it off and on. It costs ~25% of raw
read rate. **Do not toggle it per request**: four inventory restarts in thirty seconds made the
module raise `MODULE_NEED_RESTART` and stop reading.

**`tid: true` is now a rendering flag**, not a radio one.

---

## 3a. Super Fast is sensor-driven

GPIO23 rising opens the read, GPIO24 rising ends it, and the count and settle are recorded rather
than acted on. Stop reason: count not met is `PACKAGE_EXITED`; count met and settled is `SETTLED`;
count met and still yielding is `COUNT_REACHED`. `endedAt` is the moment the count was met — not
when the carton left — and `settledAt` is new. All three tested on hardware.

**No sensors are wired.** The edges were produced by flipping the pins' internal pulls, which is a
real edge as far as the kernel is concerned:

```bash
pinctrl set 23 ip pu && sleep 4 && pinctrl set 23 ip pd    # carton enters, dwells
pinctrl set 24 ip pu && sleep 1 && pinctrl set 24 ip pd    # carton leaves
```

`gpiomon` holds the lines exclusively, so a probe on those pins while the app is running gets
`Device or resource busy` — that is the app working, not a fault.

**`stdbuf -oL` in front of `gpiomon` is load-bearing.** Without it every edge is detected and then
sits in a 4 KB stdio buffer, and the tunnel silently never triggers. See CLAUDE.md.

## 4. Open, in rough priority order

1. **Run the laptop's REST client** (§1) — the missing acceptance evidence.
2. **Commission the tags** (§1) — needs a person, and an answer on write-14-or-16.
3. **The document needs `PACKAGE_EXITED`, `settledAt` and the new `endedAt` semantics** —
   §7a of the handoff lists them. The laptop is updating the `.docx`.
4. **The four invented error slugs** — `invalid_mode`, `timed_required`, `expected_count_required`,
   `invalid_direction`. The `.docx` has no slug for a malformed body. They are the only slugs a
   caller can see that the customer has not been told about.
5. **`ean` cannot always be an EAN-13.** The bench SKU is GTIN-14 `98905190881260` — indicator 9, a
   variable-measure item. Confirmed in the read path now, not just the write path.
6. ~~**A faulted reader does not reconnect.**~~ **Done 2026-08-29.** `ReaderService` now runs an
   `rfid-supervise` thread that closes, reopens and restarts inventory after a fault, with a backoff
   that only resets once the reader has stayed up for a minute. Verified on hardware against a real
   `IO_RECV_TIMEOUT` (de-mux RXD0 with `pinctrl set 15 ip pd` to reproduce): five failed attempts
   backing off 5→10→20→40→60 s, recovery as soon as the module was reachable, second fault recovered
   in 5.5 s. `recoveries`/`lastRecoveryAt` on `/api/reader/status` and `/actuator/health`.
   See `CLAUDE.md` for the two non-obvious parts (why the backoff does not reset on reconnect, and
   why recovery is a latch rather than a state observation).
7. **The lock path has never touched a tag.** Implemented in full — write → verify → password →
   lock → confirm, `BANK1_LOCK` never `BANK1_PERM_LOCK`. Run it on a sacrificial tag before it goes
   near stock.
8. **S2 persistence** — still parked, still unresolved, and now also the reason the bench cannot run
   the packaged config. Bracket at 20/30/45/60/120 s with `ProbeSettle`; also worth testing S1 and a
   Select forcing inventoried → A. *Ask before starting: about 30 minutes.*
9. Everything else in `HANDOFF-LAPTOP-TO-CM4-TUNNEL-04.md` §3 — Select action control, `TAG_FILTER`
   on-air vs post-filter, mixed-silicon FastID (needs a sourced NXP tag; there is no non-Impinj tag
   on this bench any more), TagFocus, the discovery curve.

---

## 5. Things that will waste your time if you forget them

- **`-Djava.library.path=/opt/intelli/lib` on every java command.**
- **One process owns the serial port.** Stop the app before a probe, and vice versa.
- **`--rfid.reader.region=RG_EU3`** — in the bench config file now. The module refuses `RG_IN`.
- **Ask the operator to start and stop long-running apps** if backgrounded JVMs are being killed at
  tool-call boundaries. In this session the harness's background tasks survived across turns and
  `TaskStop` shut them down cleanly, which made driving the live API practical for the first time.
- **Do not test S2 with the carrier left on.** It looks exactly like a dead reader. Twice now.
- **`/api/inventory/**` is not the contract.** It is the diagnostic surface. Do not reshape it to
  match v1 and do not put it in customer documentation.
- **The internal `CloseReason` has four values; the contract's `stopReason` has three.** Map at the
  boundary. Do not rename the internal enum.

---

*CM4 bench session, 2026-08-28; updated 2026-08-29 with the production bring-up and the
fault-recovery fix.*
