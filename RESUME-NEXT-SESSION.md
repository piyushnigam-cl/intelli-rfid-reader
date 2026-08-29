# Resume here — CM4 session, next sitting

Written at the end of 2026-08-28, **updated 2026-08-29**. Everything below is measured on hardware
unless it says otherwise.

**Read `HANDOFF-CM4-TO-LAPTOP-TUNNEL-03.md` first** — it is the full build report for the `/api/v1`
layer and it answers the laptop's five audit questions. This file is the short version plus what to
do next.

---

## 0. What changed on 2026-08-29 — and the thing that changed the priorities

**The project moved to production hardware.** Piyush is standing up the real unit: a **CM4 on our
own IntelliRFID v2.x carrier**, with the SIM7500 soldered on (U20), instead of the vendor dev board.
This bench — a Pi 4B plus the "Develop Component A" board — is now the *second* machine, not the
only one.

**`CM4-PRODUCTION-BRINGUP.md` is the runbook for that unit**, and it is the first thing to read if
you are on the new CM4. Fresh flash → packages → UART → SDK → the four clones → build → site config
→ systemd, each step with a verification line. Steps 1–6 are what is installed and working here;
Step 7 onwards is read off `docs/Hardware-IntelliRFIDv2.md` and **has never been run against the
v2.x board**.

Its action box is the part that matters: **five things about that carrier the code does not handle**,
each enough on its own to make a correctly installed unit read nothing — `RFID_EN` on GPIO22 leaves
the module **off at boot**; the SIM7500 is **mono-static**, so `antenna-count` is 1 and both antennas
sit behind an SP4T on GPIO8/9 that nothing drives; **GPIO23/24 are active-LOW field inputs** while
`GpioEdgeMonitor` is hardcoded to rising edges; the power ceiling is **27 dBm**, not 30; and the
antenna port must be selected **before** the reader is enabled. Region `RG_IN` is still unanswered
on the new module and Step 8 answers it in thirty seconds.

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
tag", so someone has to present tags **one at a time**. Nothing has been written. The register that
must exist first does now: `apps/intelli-rfid-tunnel/tools/bench-tag-register.jsonl`, keyed on TID,
18 tags, all Impinj, 2 of 18 with a valid GS1 header. Read `bench-tag-register.md` beside it — it
carries one open question (write 14 or 16) that the laptop has not answered yet.

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
