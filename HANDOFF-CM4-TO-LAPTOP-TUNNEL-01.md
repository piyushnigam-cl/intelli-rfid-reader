# Handoff: CM4 → laptop, 2026-08-27 — tunnel first light

Reply to `HANDOFF-LAPTOP-TO-CM4-TUNNEL.md`. Your §9 asked for five things in priority order; 1, 2
and 4 are answered, 3 and 5 are not yet. `CLAUDE.md` carries the corrections, as before.

**Headline: the triggered-RF architecture is safe. Carrier-up is not expensive — but the number you
were worried about is not a fixed cost at all, it is a config value you set.**

---

## 1. Carrier-on → first tag: `ReadDuration + ~14 ms`

Your §9.1 asked for this measured in isolation, and warned that 800 ms would sink the design.

Measured with a bare probe — no Spring, no queue — 10 trials per point, one tag at ~30 cm, 30 dBm,
S0, NORMAL, carrier fully off between trials:

| `BackReadOption.ReadDuration` | first tag, median | spread | residual |
|---|---|---|---|
| 5 ms | 65.99 ms | **28.7 – 283.6** | — |
| 10 ms | 84.95 ms | **28.2 – 321.7** | — |
| 25 ms | 41.80 ms | 36.6 – 49.3 | ~17 ms |
| 50 ms | 63.91 ms | 63.8 – 71.7 | ~14 ms |
| 100 ms | 114.49 ms | 113.5 – 122.7 | ~14 ms |
| 200 ms | 213.92 ms | 213.2 – 220.3 | ~14 ms |
| 400 ms | 412.76 ms | 412.6 – 420.5 | ~13 ms |

`StartReading()` itself returns in **0.4 ms** (median, n=10). 0 misses in 10/10 at every point ≥25 ms.

**The module does not report a tag when it reads it — it reports at the end of each read window.**
So "carrier-on → first tag" is `ReadDuration + ~14 ms`, and the ~14 ms is the real RF cost. I nearly
sent you "213 ms" from the first run before noticing it sat suspiciously close to my `ReadDuration`
of 200; the sweep is what turned a plausible number into the actual law.

**Consequences for your §2:**

- Carrier-up is **~14 ms**, not 800 ms. The architecture is comfortably viable.
- **`read-duration-ms` is now a latency knob, not a throughput one.** I have set it to **50 ms** in
  the tunnel config (first tag ~64 ms, tightly grouped).
- **Do not go below 25 ms.** Below that the window starts missing the tag entirely and latency
  becomes an erratic multiple of the window — at 5 ms the spread was 28–284 ms. That cliff is the
  reason not to simply minimise it.
- Best case floor is **~28 ms**, seen only as an outlier when a short window happened to catch the
  tag immediately.

---

## 2. The continuous path works — end to end, first execution anywhere

Your §7 order, as far as I could take it with the tags on the bench.

**Step 1 — `startReading()` and the JNI callback (raw, no app): PASS.** Covered by the latency work
above: 10/10 trials, callback fires, `TAGINFO` populated with RSSI, frequency, antenna, read count.

**Step 3 — the milestone, through the real pipeline: PASS**, with the caveat that I have **2 tags,
not 5** (there is a second tag in the field at −60 dBm, EPC `8A8070003A6D00021F0C3F9D`, alongside
the known `…3E62` at −27 dBm).

```
POST /api/inventory/sessions {"expectedTags":2}
  -> closeReason SETTLED   complete TRUE    tagCount 2/2   durationMs 1715   lastNewTagMs 1578

POST /api/inventory/sessions {"expectedTags":5}          (under-run: only 2 present)
  -> closeReason SETTLED   complete FALSE   tagCount 2/5   durationMs 1630

POST /api/inventory/sessions {"expectedTags":5,"settleMs":20000}   (settle > max-duration)
  -> closeReason TIMED_OUT complete FALSE   tagCount 2/5   durationMs 8086   (wall 8.2 s)
```

So: callback → bounded queue → dispatcher → session state machine all execute. The settle rule
fires, the min-duration guard holds, the `max-duration-ms: 8000` ceiling works and produces
`TIMED_OUT` rather than a false success, per-session `settleMs` overrides apply, and `complete`
correctly distinguishes 2/2 from 2/5. Dedup works: 66 reads with 113 suppressed at
`dedup-window-ms: 200`.

**Counters throughout: `droppedBatches: 0`, `queueDepth: 0`, `readErrors: 0`.**

### Step 2 — the drop counter: I could not stress it, and that is the finding

You asked for drops under fast-mode pressure and said drops are the finding. **I cannot generate
pressure on this bench, by roughly four orders of magnitude.** Raw callback rate, dedup off, 8 s per
point:

| Mode | Session | ReadDuration | callbacks/s | tags/s |
|---|---|---|---|---|
| NORMAL | S0 | 50 ms | **16.0** | 21.3 |
| NORMAL | S0 | 200 ms | 4.6 | 5.9 |
| NORMAL | S0 | 50 ms, interval 10 | 13.8 | 17.9 |
| **EX_FAST** | S0 | 50 ms | **1.1** | 1.5 |
| NORMAL | **S2** | 50 ms | **0.1** | 0.2 |

16 callbacks/s against a queue of 8192 is not a test of anything. The rate also independently
confirms the batching law: ~1000/`ReadDuration` per second. **The queue is unexercised and remains
unexercised** — it needs a real box, and I would rather say so than report a green counter as
evidence.

---

## 3. Two results that contradict §2 and §8 — please re-read these before designing further

### 3.1 Ex10 fast mode was **14× slower** than NORMAL here

`IsFastRead=true` gave **1.1 callbacks/s against NORMAL's 16.0**, same tag, same power, same
everything else.

I am **not** claiming fast mode is wrong. It is built for dense populations and 2 tags is the
sparsest possible case, so this may well invert on a 40-article box — that is exactly the sweep your
§7.3 calls for. But it does mean:

> **Fast mode cannot be assumed faster.** `read-mode: EX_FAST` is currently the packaged default,
> and on the only evidence that exists it is the slower option. It must be measured against NORMAL
> on a real box before it stays the default.

Your instinct to start in NORMAL was right for a second reason beyond debuggability.

### 3.2 S2 plus a continuously-on carrier silences the tag — and this is why triggered RF is necessary

**0.1 callbacks/s on S2 versus 16.0 on S0.** The tag is read once and then never answers again.

This is correct Gen2 behaviour — S2's inventoried flag persists while the tag is powered — and your
§8 reasoning for S2 over S1 is sound. But it has a sharp practical edge:

- **S2 is only usable with the carrier-off window.** Your §2 presents carrier-off as thermal and
  latency design; it is also what makes S2 function at all. Those are the same decision.
- Any bench or diagnostic test that leaves the carrier on and uses S2 **looks exactly like a broken
  reader**. It cost me a confusing run before the S0/S2 comparison explained it. This is now in
  `CLAUDE.md` so the next person does not repeat it.
- I ran the session milestone above on **S0** for this reason. S2 with a continuous carrier would
  have reported an empty box every time.

---

## 4. §8 config corrections — applied, and the module accepted them

All applied to the packaged `application.yml` and pushed. Verified via `/api/reader/config` that the
module took them:

```
session: 2      target: 0      q: -250      readDurationMs: 50
readMode: EX_FAST (packaged; overridden to NORMAL on the bench)   region: RG_IN (EU3 on bench)
```

- **`q: -250` is accepted.** Your `{6 | -256}` notation is `6 | -256` = `-250` as a signed int, and
  the module round-trips it. The vendor docs say only "QValue(Static/Dynamic)" and never document
  the encoding, so this was worth confirming rather than assuming.
- `session: 2`, `target: 0`, `antenna-count` → 2 packaged / 1 on the bench, `max-duration-ms: 8000`
  — all applied.
- Added `read-duration-ms: 50` with the measurement and the sub-25 ms cliff written into the comment,
  since §1 makes it a latency-critical value that was previously defaulting to 200 ms per antenna.

---

## 5. Three defects in the tunnel app

**5.1 There is no `COUNT_REACHED`, and no early exit on count.**

`InventoryResult.CloseReason` is `SETTLED | CLOSED_BY_CALLER | TIMED_OUT | ABORTED`. Your §4 says the
customer document promises `COUNT_REACHED | SETTLED | TIMEOUT` and to not invent a fourth — the code
predates that and has invented two, while missing the one that matters.

It is a functional gap, not just naming: with `expectedTags: 2` and both tags found, the session
**still waited out the full settle window** (1715 ms) instead of exiting on count. Your §3 says a
healthy box should exit on count and never wait out settle — "worth whole seconds of the budget".
On a 5 s budget that is the single cheapest second available, and it is currently unclaimed.

Also, the field is named **`closeReason`**, not `stopReason`.

**5.2 The tunnel refuses to start if the spool directory is not writable.**

`JsonlSpool.initialise()` throws `UncheckedIOException` out of the `InventoryService` constructor and
kills the Spring context: `AccessDeniedException: /var/lib/intelli`. `deploy/install.sh` creates it
(as user `intelli`), so a proper deployment is fine — but this contradicts the project's own rule
that a field unit should come up and report unhealthy rather than crash-loop. A spool that cannot be
written is a degraded reader, not an unusable one. Your call; I have not changed it.

**5.3 `readCount` is null on every tag in the result.**

`InventoryTag.readCount` comes back null even though `TMFlags.IsReadCnt` is set and the raw
`TAGINFO.ReadCnt` is populated (I see it in the probes). Read count is the confidence signal your §8
`dedup-window-ms` comment is explicitly preserving, so it is worth having. Not investigated further.

**One integration hazard, not a defect:** immediately after `POST /sessions` returns 201,
`GET /sessions/current` can still answer **204** for a moment while `/latest` holds the *previous*
result. A WMS that polls that way will silently read the wrong session — it fooled me once and
produced a bogus "settleMs is ignored" reading before I checked session ids. Worth designing out of
the `/api/v1` layer rather than leaving to the caller.

---

## 6. Not done

- **`MTR_PARAM_TAG_FILTER` on-air vs post-filter (your §9.3).** Not attempted. Ran out of runway
  this session; it is next.
- **The API-key package over the wire (§9.5).** Everything above ran with
  `--rfid.security.enabled=false` per your first-light instruction. Still never exercised.
- **Commissioning / SGTIN-96 test vectors (§7.6).** Not attempted. Note the write path itself is
  already proven on this module from the acceptance session — only the encoding is unverified.
- **Discovery curve (§7.7).** Not built. Agreed it should come before any tuning; it needs a real box
  to be worth anything.
- **Are Reliance's tags Monza?** Cannot determine from here — the two bench tags' TIDs were not read.
  I can read TID on request; say the word and I will.

---

## 7. What I need from you

1. **Does §3.1 change the read-mode plan?** If EX_FAST stays the intended default, it needs a real
   box to justify it, and until then I would suggest NORMAL as the packaged default rather than the
   bench override — a default that is 14× slower on the only measured evidence is a trap for whoever
   deploys next.
2. **`COUNT_REACHED` and early exit on count (5.1)** — do you want me to implement it here, or is it
   coming with the `/api/v1` layer? It is cheap and it is the most valuable second in the budget.
3. **Spool startup behaviour (5.2)** — crash or degrade? I lean degrade, on this project's own
   stated reasoning, but it is a product decision.
4. Anything you want re-measured now that `ReadDuration` is known to set both latency and callback
   rate — several §8 numbers were derived assuming those were independent.

---

*CM4 session, 2026-08-27. Every number here was measured on the module. Two tags on one antenna:
treat all rate and timing figures as relative, not as tunnel performance.*
