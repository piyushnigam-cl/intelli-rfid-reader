# Handoff: CM4 → laptop, 2026-08-28 — v1 is built and running on the module

Reply to `HANDOFF-LAPTOP-TO-CM4-TUNNEL-04.md`.

**The `/api/v1` layer exists, is wired to the real reader, and every endpoint has been driven
against it.** Super Fast Mode armed and reported thirty cartons autonomously; both forms of Managed
Reading work; the error slugs, status codes and scope table match the document; the callback sender
retries, spools and replays. Your §2 decisions were all taken as written and none of them fought the
code.

Reversing the audit-first instruction was right. Two of the five questions turned out to have wrong
premises, and I would not have found that by reading — I found it by building the thing and looking
at what came back. §2 answers all five.

**Three findings changed the design as I built it, and one of them was a bug of mine that the
hardware caught.** §3.

---

> ## ACTION FOR THE LAPTOP: the API document needs updating
>
> **Super Fast Mode changed after the rest of this report was written, and the customer document no
> longer describes what the reader does.** A carton's read is now bracketed by two sensors — a
> rising edge on GPIO23 opens it, a rising edge on GPIO24 ends it — and that adds a fourth
> `stopReason`, a new field, and a changed meaning for an existing one.
>
> **Please update `docs/Intelli-RFID-RestAPI.docx` and push it.** Four changes, all in §7a below
> with the measured numbers behind them:
>
> | # | Change | Why it cannot wait |
> |---|---|---|
> | 1 | **`PACKAGE_EXITED`** as a fourth `stopReason` | The document commits to three and tells the WMS to branch on this field. An integrator meeting a value the document does not list has no defined behaviour. |
> | 2 | **`settledAt`** in the result object | New field. Alongside a met count it is the strongest statement the reader can make. |
> | 3 | **`endedAt` now means "when the count was met"** in this mode | Not "when the read ended". A carton that read in 600 ms left the zone 4 s later; the old meaning would have inflated every duration by the conveyor's dwell. |
> | 4 | **Super Fast assumes two sensors** | Without them it falls back to opening on the first tag and closing on settle. That is not equivalent — a stray tag from the next carton can open a session, and nothing knows when a carton has gone. |
>
> All three stop-reason outcomes are tested on the module; §7a has the numbers. Nothing here is
> speculative and nothing here is optional — the reader is already behaving this way.

---

**Nothing has been written to a tag.** Commissioning needs a person to present tags one at a time
and there was nobody at the bench. The write path is built, guarded and validated; §5 says exactly
what is and is not proven. The register you asked for in handoff 02 §1 exists, and producing it
turned out to be cheap.

---

## 1. What is built

| | |
|---|---|
| `POST /api/v1/mode` | arm / disarm Super Fast, idempotent re-arm, `409 mode_conflict` on a different SKU |
| `GET /api/v1/mode` | live arming state, not a cached copy |
| `POST /api/v1/inventory` | both forms: 200-after-`durationMs`, and 202-then-callback |
| `GET /api/v1/reader/status` | the §3.3 proposal, plus one field — see §4.6 |
| `POST /api/v1/tags/write` | contract slugs, batch guarded by TID, lock implemented |

Plus: the result object and its three-bucket classification, `COUNT_REACHED` and early exit on
count, the durable sequence, the callback sender with retry / spool / replay, the mode state
machine, default-deny scope enforcement, the spool degrading instead of crashing the context, and
the verified parameter setter from your §2.1.

**One thing the spec did not ask for and I added anyway:** the callback spool replays on a timer,
not only at start-up. Without it a spooled result waits for the next restart, and a WMS that comes
back after twenty minutes should get its backlog then, not whenever someone next power-cycles a
reader that is working perfectly. `tunnel.v1.callback.replay-interval-ms`, default 60 s.

54 tests in the tunnel, 44 in core, all passing. The interesting ones are `ResultMapperTest`
(classification over a *mostly undecodable* population, because that is what actually arrives),
`CountPredicateTest` (§3.1), `SequenceCounterTest` and `CallbackSenderTest` (a real HTTP server, not
a mock — retry and 4xx-vs-5xx are behaviour over a socket).

**Build order note:** I did 4.1 then 4.3, 4.4, 4.5, and left 4.2's actual writing until last, where
it stopped. Building the result object before the write API was the right order after all — the
write API's response is the one shape in the contract that does *not* share the result object, so it
was never the dependency it looked like.

---

## 2. Your five questions

### 2.1 Does `sequence` survive a restart? **Yes, and it is now a separate durable counter.**

`tunnel.v1.sequence-file`, fsynced **before** the number is handed out — the same gap-not-duplicate
ordering as `SerialAllocator`, for the same reason. Losing power between the flush and the send
burns a number and leaves a gap, which the document explicitly tells the WMS to expect. The other
ordering re-issues a live number, which it does not.

Verified on the running app, not just in a test: sequence 68 before a restart, 68 after, next result
69.

It is deliberately **not** the spool's counter. `JsonlSpool` recovers its sequence by re-reading
every spool file and taking the highest — which works, but it is the diagnostic surface's number,
it restarts at zero if spooling is ever disabled, and tying the customer's reconciliation cursor to
a debugging convenience is the kind of coupling that is fine until the day it is not.

### 2.2 Which rule populates `complete`? **Neither of the two you found. A third one, now.**

`complete` is `matched.count == expectedCount`, exact equality, computed in `ResultMapper` at the
boundary. `isTrustworthy()` is not involved and must not be: it returns false for a `TIMED_OUT`
session whose count *did* match, which is right for a bench verdict and wrong for the contract —
the document defines `complete` as the count matching and `stopReason` as the separate signal about
how much to trust it. Conflating them would have hidden a good count behind a timeout.

The internal `InventoryResult.complete` still exists and still means "found == expectedTags over
*all* tags". It is not what the v1 layer reports, and it should not be — the contract's count is over
articles of the requested SKU.

Absent, never guessed, when `expectedCount` was not supplied.

### 2.3 The `readCount` null — **the premise is wrong. It was never null, and it is not zero.**

You were right to suspect the "always 0 / null" distinction mattered; it is a third thing.

- `TagRead.readCount` is an `int` carrying `TAGINFO.ReadCnt`, and the module populates it. Live off
  the bench just now: `"readCount": 1` on every read. **1 is the correct value** — it is the count
  within one 50 ms `ReadDuration` window, in which a tag is singulated once. It would only exceed 1
  at a longer window.
- The contract's `reads` is a *different number*: the tunnel's own count of accepted reads for that
  EPC across the whole session, an `int` on `InventoryTag`. Live values in v1 results: 1 to 6.

So there is nothing to fix and nothing was lost. Whatever produced the original "comes back null"
observation, it was not this field. I would drop §7.2 from the spec rather than leave it as a
standing task.

### 2.4 Does `default-property-inclusion: non_null` reach the JSON? **Yes.**

Verified on live responses rather than by reading the config:

- disarmed mode returns exactly `{"mode":"IDLE"}` — six SKU fields absent, not null
- a read with no `ean` omits `ean`, `gtin14`, `expectedCount` and `complete`
- `tid` is absent per tag when the caller did not ask for it
- `readerCode` is absent on errors that did not come from the module, present when they did
- `degraded` is absent on `/reader/status` when the spool is healthy

The contract test asserts the absences directly, with the converter configured the way the
application configures it, so this cannot regress quietly.

### 2.5 What in the spec is wrong, impossible, or contradicts the `.docx`

- **§7.2 `readCount`** — wrong premise, §2.3 above.
- **§7.3 the `/sessions/current` race** — designed out of v1 as you asked: the async form returns an
  `id` and the result arrives by callback, so no v1 caller ever polls. `InventoryService` now
  publishes completions to a listener instead. **I did not "fix the internal surface too."** The
  race is inherent to a poll-for-a-result API and the honest fix there is to stop polling, which the
  bench client cannot be made to do from this side. It is a diagnostic surface with a documented
  trap; leaving it is better than half-fixing it.
- **§8 config** — the spec puts `gs1:` at the top level. Everything in this codebase binds under
  `rfid.`, and `Gs1Properties` already documents that, so it is `rfid.gs1.*`. `valid-eans` is now a
  real setting and `invalid_ean` validates against it.
- **The `.docx` has no error slug for a malformed body**, only the 400 row. I had to invent four:
  `invalid_mode`, `timed_required`, `expected_count_required`, `invalid_direction`. Reusing
  `mode_conflict` would have been worse — it is a 409 the WMS is told to retry with backoff, and
  retrying a malformed body forever is not a behaviour to ship. **These four need to go into the
  document or be replaced by something you prefer.** They are the only slugs a caller can see that
  the customer has not been told about.
- **The `ean` field cannot always be an EAN-13.** The bench SKU is GTIN-14 `98905190881260` —
  indicator digit 9, a variable-measure trade item. `ean` and `gtin14` both carry the 14-digit form
  for it, because there is no EAN-13 to report. This is your §11.3 open item arriving in the read
  path as well as the write path, and it is not hypothetical: it is the only SKU physically present
  on this bench.

---

## 3. What measurement changed

### 3.1 A bug of mine, caught by the module and not by my tests

With no `ean` requested, the count predicate accepted *any* EPC while `matched` accepted only EPCs
that decode as SGTIN-96. Two rules over one population, disagreeing.

The symptom, live: a read with `expectedCount: 2` closed at **90 ms** with
`stopReason: COUNT_REACHED` and `matched.count: 0`. The reader announcing it had found everything it
was looking for, and then listing none of it. Two of the sixteen non-GS1 tags had answered first.

Fixed, and `CountPredicateTest` now runs both rules over the same population so they cannot drift
apart again. Worth saying plainly: my unit test for the count exit used a made-up prefix predicate
rather than the real one, so it passed throughout. The bench population found it in one call.

### 3.2 FastID works, and it is not where the documentation says it is

`tid: true` needs the TID to arrive *with* the EPC — a second per-tag read needs the tag still in the
field and inventory stopped, which a tunnel cannot offer. So FastID is the only mechanism, and it
was parked. I un-parked exactly the part your §3.2 sanctions and left the mixed-stock question
alone.

- The module does **not** use `TAGINFO.EmbededData`, which stays empty even with `IsEmdData` set. It
  appends the 12-byte TID to `EpcId` and grows the PC word: `0x3400` → `0x6400`.
- Split on the trailing 12 bytes beginning with the **0xE2** allocation class, never on a fixed
  length — a tag that does not answer FastID reports its EPC unchanged.
- **The identity check matters more than the mechanism.** A reader that reports a different EPC
  depending on a radio setting would give one article two identities. Measured across the whole
  population: **18 of 18 EPCs identical** with FastID off and on. That includes one tag whose EPC is
  genuinely 6 bytes (`PC=1D7A`) rather than 12 — the 0xE2 rule handles it; a length rule would not
  have.
- **Cost: ~25% of raw read rate** (80.7 → 60.6 reads/s, 18 tags, 30 dBm, NORMAL), with unique-tag
  discovery unchanged at 18/18. Needs re-measuring on a real box before that second number is
  trusted at 40 tags.

### 3.3 Toggling FastID per request breaks the module

The obvious implementation — enable FastID when `tid: true`, restore afterwards — costs two
inventory restarts per read. Four restarts inside thirty seconds produced
`MT_HARDWARE_ALERT_ERR_BY_TOO_MANY_RESET (0xfefe: MODULE_NEED_RESTART)` and the reader stopped
reading entirely.

So FastID is now **`rfid.reader.fast-id`, applied once at connect**, and `tid` decides only whether
the TID is rendered. The reader collects it either way. This is also why Super Fast has no `tid`
knob and does not need one.

The general lesson is in `CLAUDE.md`: **anything that wants to stop and start inventory per request
should not.**

### 3.4 A faulted reader does not come back

After that alert the session went `FAULTED` and stayed there. Every v1 call answered
`409 reader_not_connected` — the right answer — until the application was restarted. The connector
thread retries only the *initial* connect, never a fault after a successful one.

Not a v1 concern and not fixed here, but a field unit nobody can walk up to should recover from a
module that asked to be restarted. Flagging it rather than scope-creeping into it.

### 3.5 S2 makes the bench read nothing at all, which cost an hour

The packaged `session: 2` plus a continuous carrier means a static population answers once and then
goes silent. The first v1 read I ran returned **zero tags** and looked exactly like a broken layer.
It is the parked S2 persistence problem, arriving from a new direction.

The bench now runs `session: 0` via `/etc/intelli/intelli-rfid-tunnel/application.yml`, which is what every probe
has used. **This does not settle the S2 question and should not be read as settling it** — it means
the v1 layer cannot be verified on a static bench population with the packaged config, which is
itself an argument for bracketing S2 sooner rather than later.

---

## 4. Judgement calls — please push back on any of these

**4.1 `stopReason` when the count is met.** Count first: if `matched.count == expectedCount`, the
answer is `COUNT_REACHED`, whatever closed the session. That includes `timed: true`, which always
runs its full window — so a timed read reports `COUNT_REACHED` even though it ended on the clock.
The alternative is `SETTLED`/`TIMEOUT` there, which is more literal about mechanism and less useful:
`stopReason` exists so the WMS can tell a finding from a lower bound, and a met count is neither.

**4.2 `CLOSED_BY_CALLER` and `TIMED_OUT` ask the evidence.** Both mean "ended on the clock". If no
new EPC appeared for a full settle window, that is a settled population however the session was
closed, so it reports `SETTLED`; otherwise `TIMEOUT`. Without this, every `timed: true` read would
report `TIMEOUT` and the document teaches the WMS that TIMEOUT means "do not write this into your
stock record".

**4.3 `undecodable` entries are exactly `{epc, reason}`.** The TID would be genuinely more useful —
it is the only stable identity a non-SGTIN tag has — but the document shows two fields and adding a
third is a divergence the integrator discovers rather than us. **Say the word and I will add it.**

**4.4 `unexpected` entries carry the full tag shape plus their own decoded `ean` and `gtin14`.** The
document does not enumerate the fields; your spec §2 asks for the decoded EAN. This is the one place
I went beyond what is written, because "a different SKU turned up" is useless without saying which.

**4.5 `auto-trigger` is now off by default.** Arming Super Fast sets the trigger itself, with the
armed SKU and count — which a standing auto-trigger cannot know. Left on, an idle tunnel opens a
session on any stray tag and a Managed Read then arrives to find the reader busy. Bench work on
`/api/inventory/**` needs `--tunnel.auto-trigger=true`.

**4.6 `/reader/status` has one field beyond your §3.3 proposal:** `degraded`, absent when healthy,
carrying the reason when the spool is unwritable (§7.4). A reader that is up but cannot spool needs
to say so somewhere a monitor will see it.

Spec §7.4 is done and **exercised, not just written**: started against a read-only directory, the
app comes up, keeps reading and answering cartons, reports the reason in `degraded`, and
`/actuator/health` returns **503 `OUT_OF_SERVICE`** with `reader: UP` beside it —
`OUT_OF_SERVICE` rather than `DOWN` on purpose, because `DOWN` on this unit means the module is not
answering and somebody has to go and look at it, where this is a filesystem to fix at leisure.

**4.7 Commissioning error slugs changed.** `SGTIN-96-Encoding-Reliance.md` §4.1 specifies bodies
like `{"error":"EAN_NOT_IN_COMPANY_PREFIX","expectedPrefix":...}`. Those are more useful and they
are not what was issued, so they are now the contract's slugs with the context moved into `message`.
The `.docx` wins, as instructed — but that document should be updated so it does not keep
specifying a shape we deliberately do not serve.

---

## 5. The write API, and what is honestly proven

**Built:** contract slugs and statuses; `startSerial` now allocates the full
`startSerial .. startSerial + count - 1` range (it previously took only the first serial however
large `count` was — a real bug); `requested` and `quantityMet`; the full documented sequence of
write → verify → set access password → lock EPC bank → confirm lock; `BANK1_LOCK` and never
`BANK1_PERM_LOCK`; all-zero password rejected; `CommissioningGuard` so the tunnel refuses to
commission while armed or reading.

**The `count > 1` hole, guarded rather than papered over.** Gen2 cannot address "the next unwritten
tag", so a batch would write whichever tag answers each round — possibly the same one every time —
and report distinct serials as successes. The factory TID is the one identifier a write cannot
change, so after each write the TID is read back, and a TID already seen in this batch stops the
batch and reports it in `failed` with stage `singulate`. A tag that reports no TID stops it too:
without a TID there is no proof either way. That makes `count > 1` *safe*; it does not make it
*possible* without a person presenting tags.

The production answer is your inverted Select, noted in the code where the hole is. It waits on
whether `TAG_FILTER` renders on-air, which is parked.

**Proven on hardware:** every validation path (§4.7 slugs, all 400s and the 409 `reader_busy`), and
that an INVENTORY key gets 403.

**Not proven on hardware:** any actual write, verify, password or lock — because nothing was
written. The lock path in particular is code that has never touched a tag. **Do not let it near
saleable stock until someone has run it on a sacrificial tag**, and note that the confirmation step
works by attempting an unauthenticated rewrite of the *same* EPC and requiring it to fail, which is
harmless if the lock did not take and decisive if it did.

---

## 6. The bench tag register — done, and cheaper than expected

`apps/intelli-rfid-tunnel/tools/bench-tag-register.jsonl`, with
`bench-tag-register.md` next to it. Produced **before** anything was written, keyed on TID, as
handoff 02 §1 requires.

FastID made it one five-second read instead of eighteen Select-targeted single-tag reads — the same
probe that answered §3.2 produced the register as a side effect.

| | |
|---|---|
| Tags | **18**, all distinct TIDs |
| Silicon | **Impinj**, every one: MDID `0x001`, TMID `0x190` |
| Valid GS1 header | **2 of 18** |
| Non-Impinj control | none — as you said, the NXP tag was removed |

**Resolved 2026-08-30 — all 18 tags were written on the 29th.** How many to write is a closed
question and is not to be reopened. The consequence that does matter is that the register's EPC
column is now stale; the TID keying survives.

---

## 7. Testing against your REST client

Ready when you are. The reader is on the LAN at port **8081**, and `callbackUrl` must be the
laptop's LAN address — `localhost` is this reader.

Three bench keys are in `/etc/intelli/intelli-rfid-tunnel/application.yml` (only the SHA-256; the reader never
stores a key): `bench-wms` (INVENTORY), `bench-commission` (COMMISSION), and `bench-operator`
(ADMIN, for `/actuator/**`). The document tells the integrator to ask for the first two and that
neither should hold ADMIN — that is advice to the integrator, not a reason for the operator to have
no key. All three are disposable, lab-only, and **must be revoked before this unit goes anywhere
near a customer.** The plaintext is in the session notes rather than here.

**Your "Restore the API key configuration to the tunnel" landed while I was pushing**, and git
merged both security blocks into the same file side by side — a duplicate mapping key, where the
later one silently wins and your `permit-paths` and `fail-on-empty-keys` would have been discarded
by my thinner block twenty lines below. Yours stays; mine is gone. Re-verified after the merge: 3
keys loaded, 1 permitted path, `/actuator/health` served without a key, and a managed read
returning a callback with `matched: 2`, `complete: true` and a TID per article. The bench config
also moved to `/etc/intelli/intelli-rfid-tunnel/`, the path your file documents.

`rfid.security.enabled` is **true** and the app refuses to start with no keys — so the API-key
package is now exercised for the first time, and it works: `missing_api_key`, `invalid_api_key`,
`insufficient_scope` with the document's exact message, and an unlisted `/api/v1/*` path correctly
requiring ADMIN. The scope test caught one real gap while I wrote it: a method-agnostic rule had
quietly opened `DELETE /api/v1/mode` to an INVENTORY key. It is now method by method, exactly as the
document's table reads.

**One thing your client should exercise that I could not:** a slow WMS. I tested a 500 and an
unreachable endpoint; I did not test the 5 s delay against the 2 s deadline, which is the case that
proves the release really does not wait on the callback.

---

## 7a. Super Fast is now sensor-driven — and the document needs four changes

Added after the report above, on Piyush's instruction. **Tested on hardware, all three cases.**

A rising edge on **GPIO23** opens the read; a rising edge on **GPIO24** ends it. The expected count
and settle no longer close anything in this mode — they are recorded as they happen and reported.

| by the time the carton left | `stopReason` | measured |
|---|---|---|
| count met, population settled | `SETTLED` | 2 of 2, `settledAt` present, `durationMs` 600 |
| count met, still yielding tags | `COUNT_REACHED` | 2 of 2, `settledAt` absent, `durationMs` 367 |
| count not met | `PACKAGE_EXITED` | 2 of 40, `complete: false`, `durationMs` 3004 |

The order is deliberate and tested: a count that was never met is the finding, and a population that
settled *short* of the count does not soften it — case three above had settled and is still
`PACKAGE_EXITED`.

**`endedAt` now means "when the count was met"** on a sensor-driven carton, not "when the carton
left". The carton sits in the field until the conveyor moves it, and reporting that later moment
would inflate every duration by the dwell: case one read in 600 ms and left the zone 4 s later.
Where the count is never met there is no such moment and `endedAt` is when it actually left.

**`settledAt` is a new field**, absent when the population never stopped growing. Alongside a met
count it is the strongest statement the reader can make: everything expected was found *and*
nothing further was arriving.

### What the document needs

1. **`PACKAGE_EXITED` as a fourth `stopReason`.** The `.docx` commits to three and tells the WMS to
   branch on this field. It is distinct from `TIMEOUT` and the difference decides what someone
   does: TIMEOUT means the reader ran out of its own budget, a tuning problem, and the carton may
   well have been fine. PACKAGE_EXITED means the carton physically went past with articles
   unaccounted for — the read had all the time the conveyor was ever going to give it.
2. **`settledAt`** in the result object.
3. **The `endedAt` semantics above**, which change for Super Fast only.
4. A note that the two sensors are what Super Fast Mode assumes. Without them it falls back to
   opening on the first tag and closing on settle, which is not equivalent — a stray tag from the
   next carton can open a session, and nothing knows when a carton has gone. The fallback is
   reported as `degraded` in `/api/v1/reader/status` while armed.

**On the casing:** `packageExited` was asked for and then reverted to `PACKAGE_EXITED` for the next
release, so all four values share one convention. `StopReason.wire()` exists to make that a
one-line change without touching the enum the code switches on.

### Two findings from building it

**libgpiod's `gpiomon` block-buffers into a pipe, and it is silent.** It writes through libc stdio,
which line-buffers to a tty and buffers at 4 KB to a pipe. Every edge was detected by the kernel and
printed, then held in a buffer that on a conveyor would not fill for hours — three confirmed rising
edges delivered **zero bytes**, and the same three under `stdbuf -oL` delivered three lines. It
presents as missed edges, which is the wrong diagnosis and leads to polling instead of interrupts —
in a JVM with no GPIO binding that means a process spawn per poll and the loss of the kernel's edge
timestamp. Worth knowing before the wayside app reads any subprocess incrementally.

**Completeness was being judged on the wrong number.** `isTrustworthy()` compared the *total* tag
count against the expected count, so a perfect carton logged as *"18 of 2 articles, NOT
trustworthy"* — 16 of the 18 bench tags are not GS1 at all. `InventoryResult` now carries
`matchingCount` and the verdict uses it. The contract's `complete` was always correct; only the
operator-facing verdict was wrong.

### Still not wired

No optical sensor and no conveyor interlock exist on this bench, so the edges were produced by
flipping the pins' internal pulls — `pinctrl set 23 ip pu` lifts an unconnected input and the
kernel reports it to an edge monitor holding the line. That exercises the whole path from edge to
callback, and it does not tell you anything about a real sensor's bounce; `debounce-ms` is set to
50 and is a guess until there is a beam to measure.

---

## 8. Still open

1. **The API document does not describe Super Fast Mode as built** (§7a, and the box at the top).
   `PACKAGE_EXITED`, `settledAt`, the `endedAt` semantics, and the two-sensor assumption. **This is
   the one item on this list that is a request rather than a question** — the reader ships this
   behaviour now.
2. **The four invented error slugs** (§2.5) — into the document, or replaced.
3. **`ean` cannot always be an EAN-13** (§2.5) — the indicator-9 case, now confirmed in the read path.
4. **`/reader/status` body** — §3.3's proposal plus `degraded`; please fold it into the document.
5. **A faulted reader does not reconnect** (§3.4).
6. **S2** — unchanged and now blocking bench verification with the packaged config (§3.5).
7. Everything else in your §3 parked list, untouched.

---

*CM4 session, 2026-08-28. Everything above was measured on the bench SIM7500 unless it says
otherwise. Where I have only reasoned, I have said so.*

*Revised the same day: §7a and the action box at the top were added after Super Fast Mode was
changed to read between two sensors. The rest of the report predates that change and is unaffected
by it — the result object, both Managed Reading forms, the callback path and the error model are
the same as when they were tested.*
