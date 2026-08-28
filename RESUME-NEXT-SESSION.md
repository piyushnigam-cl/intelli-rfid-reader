# Resume here — CM4 session, next sitting

Written at the end of 2026-08-28. Everything below is measured on hardware unless it says otherwise.

**Read `HANDOFF-CM4-TO-LAPTOP-TUNNEL-03.md` first** — it is the full build report for the `/api/v1`
layer and it answers the laptop's five audit questions. This file is the short version plus what to
do next.

---

## 1. Where the work is now

**The customer contract is implemented and running.** `/api/v1` — all five endpoints, the result
object, the three-bucket classification, `COUNT_REACHED`, the durable sequence, the callback sender
with retry/spool/replay, the mode state machine, scope enforcement with security **on**. Driven
end to end against the real module: Super Fast armed and reported thirty cartons autonomously, both
Managed Reading forms work, every documented error slug and status code checked.

The priority change in `HANDOFF-LAPTOP-TO-CM4-TUNNEL-04.md` is done. The audit was folded into the
build, as instructed.

### The two things a next session should pick up first

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

## 4. Open, in rough priority order

1. **Run the laptop's REST client** (§1) — the missing acceptance evidence.
2. **Commission the tags** (§1) — needs a person, and an answer on write-14-or-16.
3. **The four invented error slugs** — `invalid_mode`, `timed_required`, `expected_count_required`,
   `invalid_direction`. The `.docx` has no slug for a malformed body. They are the only slugs a
   caller can see that the customer has not been told about.
4. **`ean` cannot always be an EAN-13.** The bench SKU is GTIN-14 `98905190881260` — indicator 9, a
   variable-measure item. Confirmed in the read path now, not just the write path.
5. **A faulted reader does not reconnect.** After a read exception the session stays `FAULTED` until
   the app restarts. The connector thread retries only the *initial* connect. A field unit nobody
   can walk up to should recover on its own.
6. **The lock path has never touched a tag.** Implemented in full — write → verify → password →
   lock → confirm, `BANK1_LOCK` never `BANK1_PERM_LOCK`. Run it on a sacrificial tag before it goes
   near stock.
7. **S2 persistence** — still parked, still unresolved, and now also the reason the bench cannot run
   the packaged config. Bracket at 20/30/45/60/120 s with `ProbeSettle`; also worth testing S1 and a
   Select forcing inventoried → A. *Ask before starting: about 30 minutes.*
8. Everything else in `HANDOFF-LAPTOP-TO-CM4-TUNNEL-04.md` §3 — Select action control, `TAG_FILTER`
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

*CM4 session, 2026-08-28.*
