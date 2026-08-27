# Handoff: laptop → CM4, 2026-08-27 — starting `intelli-rfid-tunnel`

Reply to `HANDOFF-CM4-TO-LAPTOP.md` §8. Your report is merged; `CLAUDE.md` at the root is now your
version, and the corrections in it are the ones future design sessions will start from.

**Read the direction rule the same way you did.** Everything below is design intent from the laptop.
The numbers are derived from Gen2 arithmetic and the vendor docs, **not measured**. Where the module
contradicts them, the module is right — change the code and record it.

One thing to fix in your mental model first: **the tunnel does not run continuous inventory.** Your
§8.2 assumes it does, reasonably, because `CLAUDE.md` said so. That was superseded by the thermal
and read-time work in `docs/SGTIN-96-Encoding-Reliance.md`. See §2.

---

## 1. Tunnel source exists — all of it. You are missing a repo, not code.

`apps/intelli-rfid-tunnel` is on this laptop, is a git repo with one commit, builds, and passes 13
tests. It is a complete Spring Boot app:

```
InventoryController  InventoryRequest  InventoryResult  InventoryService
InventorySession     InventoryTag      TunnelProperties  TunnelApplication
src/main/resources/application.yml     deploy/{install.sh,intelli-rfid-tunnel.service}
src/test/java/.../InventorySessionTest.java
```

Repo name: **`intelli-rfid-tunnel`**, exactly as you guessed.

**The blocker is repo creation, and it is mine, not yours.** You have IAM HTTPS Git credentials,
which cannot call `CreateRepository` — that is the trap your §1 already documented. I will create
`intelli-rfid-tunnel` in the console and push this working copy. **Do not try to push it first**;
you would get `repository not found` and spend an hour on what looks like an auth failure.

Wait for me to confirm the push, then:

```bash
cd apps
git clone https://git-codecommit.ap-south-1.amazonaws.com/v1/repos/intelli-rfid-tunnel
```

`intelli-rfid-wayside` also exists here and is in the same position. It is **not** part of this
milestone — leave it alone until tunnel reads a box.

### What you should distrust in it

It was written before your bench session, so it carries the same never-compiled status your bundle
had, plus one thing worse: **its packaged `application.yml` predates the read-time design work and
several defaults in it are now known to be wrong.** §8 lists them. Fix the config before you tune
anything, or you will be tuning against the wrong baseline.

---

## 2. The read path — TRIGGERED, not continuous

### The design of record

Antennas are energised **only while a box is in the portal**, driven by a photo-eye on a GPI, with
the module starting and stopping the read internally. Three power states:

| State | When | Thermal load |
|---|---|---|
| Module unpowered | service stopped | none |
| **Module initialised, carrier OFF** | between boxes — **hold here** | low |
| Carrier ON | box in the portal, ~2 s | essentially all of it at 30 dBm |

This wins twice over continuous inventory. Heat: ~10% RF duty at one box per 20 s. Latency: the
photo-eye fires **before** the WMS HTTP call lands, so the read is already underway when the request
arrives. It also gives the previous box's session flags a carrier-off window to decay back to A,
which is what §3's always-Target-A needs.

The vendor has reference code for exactly this — start from it rather than building a host-side
trigger loop:

```
demos/JniMoudleAPItest/src/demo/trigger/maintest_trigger.java
BackReadOption.IsGPITrigger + GpiTrigger
GpiTrigger_Type.GPITRIGGER_TRI1START_TRI2STOP     two photo-eyes: 1 starts, 2 stops
GpiTrigger_Type.GPITRIGGER_TRI1START_TIMEOUTSTOP  one photo-eye + StopTriggerTimeout
```

**You cannot test this on the dev board** — no opto field I/O, no GPI. So for the bench:

> Bring the tunnel up in a **host-triggered** mode: the HTTP call starts the read, the settle logic
> stops it. Same session state machine, same callback → queue → dispatcher path, same code — only
> the trigger source differs. `rf.triggerSource` is a config value for this reason. The GPI path
> waits for the v2.1 carrier.

That is not a workaround. It is the same code exercised through a different entry point, and it is
what lets you test everything in §7 without field I/O.

### NORMAL or a fast mode — answer: NORMAL first, deliberately

Intended production default is **Ex10 fast mode, dense scenario 0** (`read-mode: EX_FAST`). Reasons:
40 tags in a box is a dense population by the vendor's own scenario split (0/2/4 dense, 1/3/5
sparse), and in Ex10 mode the module auto-switches RFMODE internally, so it adapts within the read
instead of us guessing one RF mode for every box.

**But do not start there.** Your §7 says the continuous path — `startReading()`, the JNI callback,
the bounded queue, the dispatcher, SSE, drop counting — has never executed. Bringing that up in fast
mode means debugging the plumbing and the RF configuration simultaneously, and fast mode produces
hundreds of callbacks per second per tag, which is the worst possible environment for finding a race
in a queue that has never run.

So:

1. **`read-mode: NORMAL`, one tag.** Prove the callback fires, the queue fills, the dispatcher fans
   out, SSE emits, and stopping is clean. Fuller metadata, a callback rate you can read in a log.
2. **NORMAL, a handful of tags.** Prove dedup and the session state machine.
3. **Then** sweep `EX_FAST` against NORMAL, and Impinj fast mode against Ex10.

On the mutual exclusivity you flagged: `ReaderSession` clears the other mode on every change, which
is right and must stay. If you find a case where it does not, that is a bug — a reader whose
behaviour depends on what ran before it is the worst failure mode this project has.

Impinj fast mode is not merely the alternative — it is the gate on **FastID**
(`tagcustomcmd/fastid`), which returns TID alongside EPC in one operation and would make `tid:true`
nearly free instead of doubling the read. It needs Monza silicon. **Worth an explicit check: are
Reliance's tags Monza?** If they are, that changes the Impinj-vs-Ex10 answer.

---

## 3. Session lifecycle — the numbers, and how to replace them

Starting values. Every one is a guess with a stated derivation; none has seen a box.

| Setting | Start with | Where it comes from | How you replace it |
|---|---|---|---|
| `tunnel.settle-ms` | **1500** | ~3× the expected gap between late tags | Discovery curve: the flat tail after the last new EPC. Set to ~2× the longest observed gap. |
| `tunnel.min-duration-ms` | **500** | must exceed the time for the back of a box to enter the field | Time from first tag to last new tag across 50 boxes; take the max. |
| `tunnel.max-duration-ms` | **8000** | 5 s target + margin — **not the packaged 30000** | A box that takes 30 s has already failed. This is a failure ceiling, not a budget. |
| `rfid.reader.dedup-window-ms` | **200** | keeps re-reads for the read-count confidence signal without the flood fast mode produces | Raise if the queue drops under load; lower if read counts look too coarse. |
| `rfid.reader.rssi-threshold-dbm` | **-72** | rejects bleed-through from a box at the next station | Watch `bestRssi` on the articles at the **centre** of a real box — the shadowed ones — and leave headroom below the worst. |

**The settle rule itself is the part to get right, and it is not "no reads for N ms".** Settle is
measured from the last ***new*** EPC. A box sitting in the field re-reads its own tags forever, so a
last-read timer never fires while the box is present. `min-duration-ms` guards the other end so a
session cannot close in the gap before the rest of the box has entered the field. If you find
yourself simplifying this, don't — it is the single most load-bearing rule in the app.

**Settle is the fallback path, not the normal one.** With `expectedCount` supplied and
`stopOnCount: true`, a healthy box exits on count and never waits out the settle window. Settle only
runs when the count is absent or not reached — i.e. when something is already wrong. Worth whole
seconds of the budget.

### The instrument that replaces all of these: the discovery curve

`diagnostics.discoveryCurve.enabled`. One JSONL per box, one line per **first** sighting (~40 lines).
The measurement itself is free — `firstSeenMs` is a `putIfAbsent` on the dedupe map the app needs
anyway — so the flag gates only file I/O and enabling it never perturbs the timing you are measuring.

The curve shape names the constraint directly:

| Shape | Constraint |
|---|---|
| Long flat tail | RF coverage — physical, fix the antennas |
| Slow even rise | Collisions — Q and session |
| Fast to N then a wait | Settle window too long |
| Flat start | Start-up cost in the critical path |

Always log `stopReason` and `durationMs` alongside. **Build this early** — it is how every other
number in this document gets replaced with a measured one, and retrofitting it later means redoing
the runs.

---

## 4. `expectedTags` — from the WMS, on session open. Never configured.

It arrives as `expectedCount` in the `POST /api/v1/inventory` body, per box. `tunnel.default-expected-tags: 0`
means exactly that: the caller supplies it, and 0 is honest about not knowing.

Why it matters more than it looks: it is the whole difference between "the population settled" and
"nothing is missing". A settled session with no `expectedCount` says the reader stopped finding new
tags — which is also what a box with two shadowed articles looks like.

Rules that follow, and please keep them intact:

- **A `TIMED_OUT` session is never trustworthy, even when the count happens to match.** Hitting the
  right number after running to the ceiling means the count was reached at an unknown moment by an
  unknown path. Report it as timed out.
- `stopReason` is one of **`COUNT_REACHED` | `SETTLED` | `TIMEOUT`** and goes in every result. The
  customer document already promises these three strings; do not invent a fourth.
- The config knob exists only for a site where every box genuinely holds the same count. Passing it
  per session is the honest default.

---

## 5. The third-party API contract — and a gap you need to know about

**The customer-facing contract is documented and the code does not implement it yet.** This is the
biggest single discrepancy in this handoff, so it goes first:

> The tunnel today exposes `/api/inventory/**` (`InventoryController`) — session endpoints.
> The document issued to the customer, `docs/Intelli-RFID-RestAPI.docx`, specifies a **three-mode
> `/api/v1/...` surface**. The mode endpoints and the callback contract **are not built**.

The document is a specification ahead of the code, and it says so in its own §3.1. Do not treat the
current controller as the contract.

### What the WMS actually calls

| Endpoint | Mode | Shape |
|---|---|---|
| `POST /api/v1/mode` | Super Fast (arm/disarm) | `{mode, ean, expectedCount, callbackUrl, direction}` |
| `GET /api/v1/mode` | read current arming | |
| `POST /api/v1/inventory` | Managed Reading | `timed:true` = synchronous, always consumes `durationMs`. `timed:false` = **202 + callback**, exits early on `expectedCount` |
| `POST /api/v1/tags/write` | Managed Writing | COMMISSION scope — see §6 |
| `GET /api/v1/reader/status` | connectivity check | |

Armed Super Fast mode runs per-carton off the optical sensor and POSTs each result. **The carton is
released BEFORE the callback is sent** — a slow WMS must never be able to stall the conveyor.
Failed callbacks retry, then spool to disk (`tunnel.spool-dir`).

Counter-intuitive but documented and correct: **`timed:false` is usually faster than `timed:true`**,
because it can exit on count while the timed form always burns its full `durationMs`.

### Auth

- **`rfid.security.enabled: true` for tunnel.** Core defaults it on; keep it. `reader-test` sets it
  false, which is right for a bench tool and wrong here. Note this means the API-key package —
  which by your §7 has never run over the wire — is now in the path. Expect to be the first to
  exercise it.
- **Two keys, deliberately separate:** `INVENTORY` for the WMS reading modes; `COMMISSION` held only
  by commissioning. Do not issue one key with both.
- Callbacks authenticate the other direction with a **shared secret the WMS issues**: reader sends
  `X-Callback-Token` on every callback.
- **HTTP, not HTTPS** — warehouse LAN only, documented as a deployment decision with four conditions
  (same VLAN, no internet route, port not published through NAT or proxy, keys minimally scoped and
  rotated). If TLS is ever required, only the URL scheme changes.

### Promises made to the customer that the code must not break

- Delivery is **at-least-once by design**; the WMS deduplicates on `id`. Their endpoint must answer
  2xx within 2 s.
- `read.responseMode: DETAILED | CONCISE`. CONCISE returns **only epc + tid** per tag and omits
  `unexpected`, `totalUnique` and `stopReason`. Live with the caveat but know it: in CONCISE a
  wrong-SKU article is invisible to the WMS, so `complete:true` can coexist with a picking error.
  It is still decoded and server-logged.

---

## 6. Commissioning — same write path, SGTIN-96 payload

Same `writeEpc` path you already proved on the bench. What changes is what goes into it.

**Encoding (confirmed with the customer):** SGTIN-96. Company prefix `8905527` — 7 digits, therefore
**partition 5**. Filter value **1**. Reliance's two EANs are `8905527164445` and `8905527168207`.
Test vectors, serial 1: `30361F8CDC100F0000000001` and `30361F8CDC106D0000000001`. If your encoder
does not reproduce those two strings exactly, it is wrong.

**The API is deliberately thin** — `{ean, count, startSerial, lock, accessPassword}` and nothing
else. Everything tunable lives in config.

- **The GS1 partition is deliberately not an API parameter.** A wrong partition still decodes to the
  right GTIN, so the error would be invisible — the worst possible property for a parameter. It is
  config, set once per site.
- `startSerial > 0` uses the supplied value and neither reads nor advances the local counter;
  `startSerial: 0` uses the local counter.
- Multi-site serial allocation: `(reader.id << 30) | counter`, `reader.id` 0–255, ~1.07 bn serials
  each. Local allocation only — a caller-supplied serial bypasses it entirely.
- **Never permalock.** The permanent `Lock_Type` values are irreversible and there is no recovery
  from one on a customer's tag.
- An all-zeros `accessPassword` is **rejected**, not accepted-as-none.
- `Reader/isWriteReadFlag` makes the module read back after writing — this is our `verifyAfterWrite`.
  It needs an oversized array and **must be disabled afterwards or it corrupts subsequent writes.**

Still open with Reliance, so do not hard-code around them: serial authority per site, lock policy
and who holds the password, and the box's own tag scheme (an SSCC header `0x31` will **not** match
the SGTIN mask, so a Select suppresses it entirely — today it lands in `undecodable`).

---

## 7. First bench milestone with one antenna

Your constraint is the right one to design around, and more is reachable under it than it looks.
**A meaningful milestone here is not a fast box read — it is the continuous read path proven to
work at all**, since by your own §7 none of it has ever executed.

### Milestone: a host-triggered session over the real callback path

> Start a session over HTTP with `expectedCount: 5`. Five tags in front of the antenna. The session
> opens, tags arrive through callback → queue → dispatcher, SSE streams them, the session closes
> with `stopReason: COUNT_REACHED`, and the result carries five distinct EPCs with RSSI and read
> counts. Then remove one tag and confirm it closes with `SETTLED` and reports four.

That single test exercises the JNI callback thread, the bounded queue, the dispatcher fan-out, SSE,
the dedup window, the settle rule, the min-duration guard, early exit on count, and `stopReason` —
which is most of what has never run.

### Order

1. **NORMAL mode, one tag, continuous.** Does `startReading()` come up and the callback fire at all?
2. **Queue and dispatcher under fast mode.** Switch to `EX_FAST` with the same one tag purely to
   generate callback pressure, and watch the drop counter on `/api/reader/status` and
   `/actuator/health`. **Drops here are the finding**, not a nuisance — the queue is 8192 and
   drops-oldest-first, and nobody has ever seen it under real pressure.
3. **The milestone above**, in NORMAL.
4. **Dedup and settle behaviour** with tags added and removed mid-session.
5. **The security package over the wire** — first real exercise of it. Both scopes, and a rejected
   request.
6. **Commissioning**: write an SGTIN-96 EPC, verify against the test vectors in §6, restore.
7. **The discovery curve**, on every run from step 3 onward.

### Then, the questions only hardware can answer

Ranked by how much design depends on the answer:

1. **Carrier-on → first-tag latency.** Decides whether TRIGGERED RF works as designed. If carrier-up
   costs 800 ms, the whole §2 architecture needs rethinking and I need to know now.
2. **Is `MTR_PARAM_TAG_FILTER` a true on-air Gen2 Select or a firmware post-filter?** The docs call
   it a "single-rule filter" and never say. Test: does `durationMs` move when foreign tags are in
   range? If it post-filters, §9 of the SGTIN note is worthless and Select must go through
   `Gen2/selectcommandconfig` instead.
3. **Session sweep S0 / S1 / S2, plus TagFocus, at Q = `{6 | -256}`.** Even with five tags the
   *relative* ordering is informative.
4. **Ex10 scenario 0 vs 4 vs Impinj vs a static RF mode.**
5. **Module temperature across a long run**, via the free CC33 telemetry — it uploads per-antenna
   VSWR and module temperature every time the PA is enabled, in the normal read path.

### Explicitly blocked until the v2.1 carrier — do not burn time on these

- **Anything multi-antenna**, including the top risk in the SDK notes: `MTR_PARAM_RF_HOPANTTIME` is
  documented as modifiable **only in the China region**; elsewhere the module uses 4 s internally and
  will not let you change it. On a 5 s box budget that is potentially fatal, and it is untestable on
  one port. It needs per-antenna attribution of every first sighting on the real carrier.
- GPI triggering and field I/O.
- A real 40-article box, and therefore any absolute read-time number.

Do not report a read time from this bench as if it meant anything for the tunnel. Five tags on one
antenna at close range is a plumbing test, not a performance test.

---

## 8. Corrections to the packaged `application.yml` — apply before tuning

These defaults were written before the read-time design work and are known-wrong. They are still in
the file you will clone.

| Key | Packaged | Change to | Why |
|---|---|---|---|
| `rfid.reader.session` | `1` | **`2`** | S2 drains a dense population monotonically. S1 self-decays **even while powered** (500 ms–5 s), so a tag can re-answer mid-box. S2's inter-box carryover is handled by the carrier-off window in §2. |
| `rfid.reader.q` | `-1` (fully automatic) | **`{6 \| -256}`** | Dynamic with initial Q=6. Rule: Q = round(log2(count)) + 1, so 40 tags → 6. **`{6}` alone is a STATIC Q** — easy to set by accident and quite different. |
| `rfid.reader.antenna-count` | `4` | **`2`** | The tunnel portal uses two antennas; 4 is the v2.1 carrier's SP4T maximum. On your dev board use **1**. |
| `tunnel.max-duration-ms` | `30000` | **`8000`** | See §3. |
| `rfid.reader.target` | `0` (A) | **keep `0`** | Confirming, because it looks like a knob and is not — see below. |

### The one that will bite you if you "improve" it

**Do not alternate Gen2 target A/B per box.** An earlier design note advised it; that advice was
wrong and would break reads badly. Tags power up with the inventoried flag at **A**, so a Target-B
round does not see fresh tags — **every second box would read as near-empty**. Alternation is only
for re-reading a *static* population.

For a same-box retry, in order of preference: let the carrier drop and wait out the ≥2 s persistence,
then re-read with A; or issue a Select that sets inventoried → A; or, last resort, Target B for that
one retry.

Good news on the middle option, from the SDK docs: **Select action control exists.**
`SelCmd_Target` = `SelC_Inventoried_S0/S1/S2/S3` or `SL`, and
`SelCmd_Action.Mat_SLorA_NMat_no` = "Match: Set SL or A; No Match: No Action". So a same-box retry
should cost one Select rather than a 2 s persistence wait. **Unverified on the module** — worth
confirming while you are in there.

Two more from the notes, both cheap and both likely to matter:

- `Reader/rssifilter` is a **module-internal RSSI floor**. It is probably a better foreign-tag
  suppressor than any Select: it cuts distant racking and adjacent-box tags regardless of EAN, at no
  airtime cost, and unlike a SKU-scoped Select it does **not** blind us to a wrong-SKU article
  actually inside the box.
- `BackReadOption.FastReadDutyRation` — **keep at 0 during a box read.** In-window standby slows the
  read you are trying to speed up. Heat is managed by the macro duty cycle in §2, not by this.

---

## 9. What I need back

In priority order — 1 and 2 are the ones that change what I design next:

1. **Carrier-on → first-tag latency**, measured in isolation. §2 stands or falls on it.
2. **Does the continuous path work?** The §7 milestone, pass or fail, with the drop counter from
   step 2 either way.
3. Whether `MTR_PARAM_TAG_FILTER` is on-air or post-filter.
4. Anything in §8 that the module contradicts — and put it in `CLAUDE.md` before you reply, the way
   you did last time. That worked.
5. Whether the API-key package survives contact with a real request.

And confirm one thing I cannot check from here: **are Reliance's tags Monza silicon?** If they are,
FastID makes `tid:true` nearly free and the Impinj-vs-Ex10 question changes shape.

---

*Laptop design session, 2026-08-27. Nothing in this document has been run against hardware. The
numbers are derived, not measured — replace them.*
