# Handoff: laptop → CM4, 2026-09-01 — settle has no positive control. Fix that, and make it faster in the same change.

Triggered by reviewing the eight-carton run set of 2026-08-31 (spool
`inventory-2026-08-31.jsonl`, nine commissioned tags, all `SETTLED`, 72/72 sightings, no miss).

The runs are clean. The result they produce is not as strong as it looks, and the reason is
structural rather than anything that went wrong on the bench.

**One defect and one improvement, and they are the same change.** `hasSettled()` proves a clock ran.
It should prove the reader was listening. Making it prove that also lets a healthy carton close
sooner than the fixed window allows.

---

## 0. Scope, and what this does NOT touch

This is **not** a change to the carton sequence, which is now stated in `CLAUDE.md` under
"Tunnel v1 — in Super Fast Mode a sensor opens the read".

| Committed in handoff-05 | Status here |
|---|---|
| IN1 rising edge opens the read | unchanged |
| IN2 rising edge closes it → `PACKAGE_EXITED` | unchanged |
| Settle closes it → `SETTLED` | unchanged as an outcome; **the test behind it changes** |
| `exitOnCount` defaults false, stays a settable flag | unchanged |
| `exitOnSettle` true unconditionally | unchanged |
| `complete` and `stopReason` independent | unchanged |
| The three wire `stopReason` values (+ `PACKAGE_EXITED`) | **unchanged — no new value is proposed** |

Everything below happens inside `InventorySession.hasSettled()` and the spec that feeds it. The
customer contract does not move. That is deliberate: `Intelli-RFID-RestAPI.docx` already owes the
integrator an explanation of a fourth `stopReason`, and a fifth would be worse than the problem.

**Provenance.** Everything here is derived from the 08-31 spool and from reading the tree at
`db2567d`. **Nothing in this document was measured on a module by me.** Claims that came off the
hardware are marked MEASURED and carry their source. §2 has one action that must run before the
constants in §7 are chosen.

---

## 1. The defect: `SETTLED` is absence of evidence with no positive control

`InventorySession.hasSettled()` today:

```java
public boolean hasSettled() {
    return durationMs() >= spec.minDurationMs()
            && msSinceNewTag() >= spec.settleMs()
            && !tags.isEmpty();
}
```

Three conditions, **none of which involve the reader.** `msSinceNewTag()` is
`(System.nanoTime() - lastNewTagNanos) / 1e6` — a wall clock. `lastNewTagNanos` advances only when a
previously-unseen EPC arrives (`accept()` sets it under `if (sawNew)`). Reads of already-known tags
update the accumulator — `reads`, `bestRssi`, `lastSeen`, `antennas` — and deliberately do not touch
it.

**That rule is correct and stays.** It is the one in `CLAUDE.md`: a box sitting in the field re-reads
its own tags forever, so settle must key on *new* EPCs. The defect is the missing other half.

### 1.1 Five causes, one outcome

All of these close `SETTLED` with `complete: true`, indistinguishably:

1. no more tags in the carton — **the intended meaning**
2. **the reader faulted** — `InventoryService.checkSettle()` never consults reader state
3. the tags went quiet on their S1/S2 inventoried flag
4. the bounded queue dropped the batch carrying the next EPC — counted on `/api/reader/status`, **not consulted here**
5. the carton left the reading zone early — only IN2 catches this, and only when sensors are live

Case 2 is the sharp one. A read exception at t=1310 ms leaves `msSinceNewTag()` climbing on wall
clock, crossing `settleMs` at ~2810 ms. The carton is spooled as a verified 9/9 inventory **on the
strength of a reader that was dead for the entire proving window**, the callback goes to the WMS, and
`rfid-supervise` reconnects a few seconds later with nothing in the result ever saying so.

`min-duration-ms: 500` guards the front of the session. **Nothing guards the back.**

### 1.2 This got more load-bearing after handoff-05, not less

With `exitOnCount` defaulting to false, count-met is an observation and **settle is the primary close
condition in Super Fast Mode**. On a line where cartons settle before IN2 arrives, this test decides
essentially every carton. It is now the least-defended thing in the read path and the most used.

---

## 2. ACTION FIRST: is the reader hearing anything during the settle window?

**This is unanswered, it is cheap to answer, and it changes the constants in §7.**

`InventoryTag` is `(epc, tid, reads, bestRssi, antennas, firstSeen, lastSeen)` with no Jackson
annotations, so those are the JSONL field names. `lastSeen` is already in the spool — the analysis we
did on 08-31 only plotted `firstSeen`, which is why the question is still open.

```bash
jq -r '[.startedAt, .durationMs, ([.tags[].firstSeen]|max), ([.tags[].lastSeen]|max), .endedAt] | @tsv' \
  /var/lib/intelli/tunnel/spool/inventory-2026-08-31.jsonl
```

Two possible answers, and they point different ways:

- **`max(lastSeen)` lands inside the settle window** → the reader was demonstrably alive, re-reads
  arrive during settle, and the §3 quorum will fire quickly. Proceed with §7 as written.
- **`max(lastSeen)` ≈ `max(firstSeen)`** (~1.0–1.3 s) → the reader heard **nothing at all** for the
  final 1.5 s of every carton. The settle window is proving nothing and only burning time — which
  makes §3 more urgent, but means the quorum needs its constants re-derived from whatever the real
  re-read interval turns out to be, and the §4 fallback carries more of the load.

Please put the answer in the reply handoff either way. Also worth reporting: the distribution of
`lastSeen - firstSeen` per tag. **That number is the S1 re-read interval on this stock, and we do not
have it.** It is the single most useful missing measurement for this design.

---

## 3. The change: two paths to `SETTLED`, one of them fast

### 3.1 Definitions

**Reference instant** — `lastNewTagNanos`. Not session start, not count-met. Everything below is
measured from the last previously-unseen EPC.

**Re-read quorum** — the number of **distinct EPCs** that have been seen again **strictly after the
reference instant**.

*Distinct EPCs, not total reads.* Five reads could all be one strong tag parked in front of an
antenna. Five distinct tags answering proves the field is still illuminating the population, which is
the thing we actually want to know. The extra bookkeeping is worth it.

**Quorum target K** — `max(2, min(5, ceilDiv(expectedTags, 4)))`.

The floor of 2 is a change from the rule as first proposed. `min(5, n/4)` alone gives K=1 at n=4 and
K=2 at n=9, so small cartons get the least proof — but a single spurious tag distorts a small carton
more, not less. The floor costs nothing and removes the degenerate end.

### 3.2 The two paths

```
FAST   count met AND quorum >= K  AND no new EPC since the reference instant
SLOW   msSinceNewTag() >= settleMs                          (today's rule, unchanged)
```

Either closes the carton with `stopReason: SETTLED`. Both remain subject to `minDurationMs`.

The fast path buys a shorter window by demanding stronger evidence: the count corroborates the
population **and** the reader has demonstrably been heard from since the last new tag. The slow path
is exactly today's behaviour and exists so that this can never be slower than what we have — see §4.

### 3.3 The quorum resets on a new EPC

When a new EPC arrives, `lastNewTagNanos` advances **and the quorum resets to zero**. Evidence
gathered before a late tag must not count toward proving that nothing came after it. This falls out
naturally if the quorum is a set cleared in the same branch that stamps `lastNewTagNanos`.

### 3.4 Sketch

`TagAccumulator` needs one field:

```java
/** Nano timestamp of the most recent read of this EPC. Compared against the reference instant. */
private volatile long lastReadNanos;
```

`InventorySession`:

```java
/** EPCs seen again since lastNewTagNanos. Cleared whenever a new EPC arrives. */
private final Set<String> reReadSinceNewTag = ConcurrentHashMap.newKeySet();

/** Distinct EPCs re-read since the last new EPC. The liveness proof. */
public int reReadQuorum() {
    return reReadSinceNewTag.size();
}

public int quorumTarget() {
    int n = spec.expectedTags();
    return n <= 0 ? Integer.MAX_VALUE : Math.max(2, Math.min(5, (n + 3) / 4));
}

public boolean hasSettled() {
    if (durationMs() < spec.minDurationMs() || tags.isEmpty()) {
        return false;
    }
    if (spec.fastSettleEnabled()
            && countReachedAt != null
            && reReadQuorum() >= quorumTarget()
            && msSinceNewTag() >= spec.minQuorumWindowMs()) {
        return true;                    // FAST
    }
    return msSinceNewTag() >= spec.settleMs();   // SLOW - unchanged
}
```

In `accept()`, inside the existing loop:

- **new EPC** → after stamping `lastNewTagNanos`, `reReadSinceNewTag.clear()`
- **known EPC** → `if (read arrived after lastNewTagNanos) reReadSinceNewTag.add(epc)`

Ordering matters and is the one place to be careful: a batch can contain both a new EPC and re-reads
of known ones. Process the batch, then decide — clear the set **once, after** the batch, if the batch
contained any new EPC. Doing it per-read inside the loop lets a re-read that arrived in the same batch
survive a clear that should have removed it.

`quorumTarget()` returning `MAX_VALUE` when `expectedTags <= 0` is deliberate: with no expected count
there is no count to corroborate, the fast path can never fire, and the diagnostic
`SessionSpec.of(...)` shape keeps exactly its current behaviour.

### 3.5 `minQuorumWindowMs`

A small floor — suggest **200 ms** — between the last new EPC and the earliest possible fast close.
Without it, a batch that happens to carry the Nth new EPC alongside K re-reads satisfies the quorum in
the same instant the population completes, and the fast path proves nothing. The floor makes "no new
tag has come in that period" mean an actual period.

---

## 4. Why the timer stays as a backstop — two reasons, one of them measured

The rule as first sketched replaced the settle window outright. It must not, for two reasons.

**Under S1 the quorum is clocked by tag decay, not by reader health.** A tag that has just answered
goes to B and will not answer again until its S1 flag decays — 0.5 to 5 s, per tag, unpredictable. So
"wait for K tags to be read a second time" is really "wait for K decay events to land." With nine tags
and K=2 that is the 2nd of 9 decays; under a uniform 0.5–5 s assumption that is ~1.4 s, and K=3 is
~1.85 s. **That arithmetic is illustrative, not a prediction** — the decay distribution is a property
of the silicon and we have not measured it, which is what §2 is for. But it is the same order as the
1500 ms it would replace, and it could land the wrong side.

What the 08-31 data does establish: every tag in every carton reached `reads: 2` inside the carton,
and the tightest bound is run 7, where some tag was re-read within **1514 ms** of its first sighting.
So the quorum is reachable. Whether it is reachable *quickly* is exactly what §2 answers.

**Under S2 it would never fire at all.** MEASURED, `HANDOFF-CM4-TO-LAPTOP-TUNNEL-01.md`: S2 with the
carrier continuously on gives **0.1 callbacks/s against S0's 16.0** — the tag is silenced by design.
Second reads essentially never arrive, so a quorum-only rule would run every carton to
`max-duration-ms: 8000`. A change meant to save a second would cost five.

And **`application.yml` still has `session: 2`.** Whatever the 08-31 runs used, the committed default
is the mode in which a quorum-only settle degenerates. See §8.1.

With the timer retained as the slow path, the change is **strictly non-regressive**: a healthy carton
closes sooner, an unhealthy one closes exactly when it does today, and a session-mode change cannot
turn a fast tunnel into an 8-second-per-carton one.

---

## 5. The trap: "read a second time" must not be implemented as `reads >= 2`

This is the single most likely way to build this and get a rule that passes review, passes tests, and
proves nothing.

A cumulative check — "K tags have `reads >= 2`" — is satisfied by **history**. On the 08-31 runs every
tag ends at exactly `reads: 2`. If several tags took their second read early, before the count was
met, a cumulative quorum is already satisfied the instant the Nth tag arrives, fires immediately, and
demonstrates nothing about whether the reader is alive *now*.

The quorum must count re-reads observed **after the reference instant**, which is why `TagAccumulator`
needs `lastReadNanos` in §3.4 rather than the existing `lastSeen` `Instant` — same information, but
the comparison is against a nano baseline and should not go via the wall clock.

**Please write the test for this case specifically**: a session where every tag reaches `reads >= 2`
before the count is met must **not** fast-settle on the count-met batch. `InventorySessionTest` is the
right home.

---

## 6. What to report — no new `stopReason`

The wire contract does not move. What is missing is that a `SETTLED` result carries no indication of
which path produced it or whether the reader was heard from.

Add to `InventoryResult` (additive fields only, unlike `PACKAGE_EXITED` — no integrator has to branch
on these and the document can absorb them at leisure):

| Field | Meaning |
|---|---|
| `reReadQuorum` | distinct EPCs re-read since the last new EPC, at close |
| `quorumTarget` | K as computed, so the number is self-explaining in the spool |
| `fastSettle` | true when the fast path closed it |

**The diagnostic that matters most:** a carton that closed on the slow path with `reReadQuorum: 0`
heard nothing at all during its settle window. That is case 2 or case 4 from §1.1 and it should be
logged at WARN with the session id. It is not necessarily a fault — under S1 with a long decay it can
be normal — but it is exactly the signature of a dead reader, and today it is invisible.

Do **not** map it to a different `stopReason`. If it later turns out to be a real fault indicator, it
belongs in `/api/v1/reader/status`, not in a value the WMS branches on.

---

## 7. Config

```yaml
tunnel:
  settle-ms: 1500              # unchanged - the slow path and the backstop

  # The fast path: close as soon as the count is met AND K distinct tags have been heard
  # again since the last new EPC. Evidence in place of elapsed time. Never slower than
  # settle-ms, because settle-ms remains as the other path.
  fast-settle: true
  min-quorum-window-ms: 200    # floor between the last new EPC and the earliest fast close
```

**How to derive the real values** (per the project rule on site-dependent constants): run §2, get the
distribution of `lastSeen - firstSeen`. If the median re-read interval is well under 500 ms, K can go
up and `min-quorum-window-ms` can stay at 200. If it is above a second, the fast path will rarely beat
the timer on a nine-tag carton and the honest thing is to say so in the reply and leave `fast-settle`
off until a 40-tag carton is available — a full carton is a much better case for this rule, because K
stays at 5 while the number of tags available to answer goes up eightfold.

K itself is deliberately **not** configurable. It is derived from `expectedTags` and a config knob for
it would only ever be used to weaken the proof.

---

## 8. Three things from the same review that are not this change

### 8.1 The 08-31 runs did not use the committed configuration

The run set was **session 1, 27 dBm**. `application.yml` has **`session: 2`** and
**`read-power-dbm10: 3000`**. The profile that produced eight clean cartons exists nowhere in the
repo.

Given the MEASURED S2 result in §4, the committed default is the configuration in which the tags go
quiet. Please either land the passing profile in `application.yml` or record it explicitly in the
reply, and say which of the two is intended to be the default going forward. This is the kind of thing
that costs a day when someone reproduces from a clean checkout.

### 8.2 `isMarginal()` is one decay cycle from flipping

```java
public boolean isMarginal() {
    return reads <= 1 || bestRssi < -70;
}
```

The whole "a neighbouring box bleeding into the field" heuristic hinges on **1 read versus 2** — and
under S1 whether a tag earns its second read is decay timing, not whether it is in the box. On 08-31
every tag got exactly 2 and `marginal` was 0, with no margin behind that at all. Not urgent, but it
should not be relied on as a discriminator until §2 says what the re-read interval actually is.

### 8.3 `matching` is decided by EAN, not by a per-carton manifest

Any tag of the armed SKU inside the zone counts toward `expectedCount`. Two cartons of the same SKU
nose-to-tail on a conveyor is the failure this permits, and the only defences are the IN1/IN2 bracket
and RF containment. Worth noting that **the fast path in §3 slightly reduces the exposure** — it
requires the count *and* corroborating liveness rather than closing the instant the count is met — but
it does not remove it. Flagging rather than proposing; it is a physical and contract question, not a
`hasSettled()` one.

---

## 9. Actions, in order

1. **Run the §2 `jq`.** Report `max(lastSeen)` versus the settle window, and the per-tag
   `lastSeen - firstSeen` distribution. **Everything else is gated on this.**
2. Implement §3 — `TagAccumulator.lastReadNanos`, `reReadSinceNewTag`, `quorumTarget()`, the
   `hasSettled()` rewrite, the batch-ordering rule in §3.4.
3. Write the §5 test first. It is the one that fails silently if built wrong.
4. Add the §6 fields and the WARN on `reReadQuorum: 0`.
5. Answer §8.1 — which session and power are the default.
6. Measure the fast path against the timer on the bench and report both numbers. If it is not
   materially faster on nine tags, say so and leave it off until a real carton is available.

## 10. `CLAUDE.md`

Whatever comes back from §2, please put the re-read interval and the settle rule into `CLAUDE.md`
before replying. The current note there says settle is measured from the last new EPC, which stays
true — it needs the second half: **that settle now also requires evidence the reader is live, and why
the timer remains behind it.**
