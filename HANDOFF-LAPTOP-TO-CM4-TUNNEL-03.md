# Handoff: laptop → CM4, 2026-08-28 — audit the tunnel against the contract before building

`docs/Tunnel-v1-Implementation-Spec.md` is now in the repo: the implementation spec for the
`/api/v1` layer, transcribed from `docs/Intelli-RFID-RestAPI.docx`, the document issued to Reliance.

**Do not start implementing it yet.** This document asks for an audit first: what the tunnel app
actually has today, measured against what the contract requires. Two reasons.

**First, my reading of your code was done from a laptop with nothing running.** I have read
`InventoryResult`, `InventoryTag`, `InventoryController`, `ReaderSession` and `ReaderConfig` as text.
Several claims in the spec depend on that reading being right, and where it is wrong the spec is
wrong. §3 below lists the specific things I am least sure of.

**Second, the gap is structurally larger than a missing-fields list**, and it is worth both of us
agreeing on its size before you spend a session on it. See §2.

---

## 1. What I believe you have

`InventoryResult` today:

```
id, label, direction, startedAt, endedAt, durationMs, lastNewTagMs, closeReason,
expectedTags, tagCount, marginalCount, complete, totalReads, tags, sequence
```

`InventoryTag` today:

```
epc, reads, bestRssi, antennas, firstSeen, lastSeen
```

Against the contract's result object, field by field:

| Contract field | Today | Note |
|---|---|---|
| `id` | ✅ `id` | |
| `sequence` | ✅ `sequence` | **but is it durable across a restart?** See §3.1 |
| `mode` | ❌ | No SUPERFAST / MANAGED_READ concept exists |
| `direction` | ✅ | |
| `ean` / `gtin14` | ❌ | **A session does not know what SKU it is reading.** See §2 |
| `startedAt` / `endedAt` | ✅ | |
| `durationMs` | ✅ | |
| `stopReason` | ⚠️ `closeReason` | Different name, and none of `CLOSED_BY_CALLER` / `TIMED_OUT` / `ABORTED` are in the contract |
| `expectedCount` | ⚠️ `expectedTags` | Rename at the boundary |
| `complete` | ✅ | Confirm it is exact equality, not `isTrustworthy()` — see §3.2 |
| `matched.count` / `matched.tags` | ⚠️ `tagCount` / `tags` | Flat list, no three-way split |
| `unexpected` | ❌ | |
| `undecodable` | ❌ | |
| tag `epc` | ✅ | |
| tag `rssi` | ✅ `bestRssi` | |
| tag `reads` | ⚠️ | You reported this null; the field I see is `int reads`, which cannot be null. See §3.3 |
| tag `firstSeenMs` | ⚠️ `firstSeen` | `Instant`; derive the ms offset at the boundary |
| **tag `tid`** | ❌ | **The field does not exist anywhere** |
| **tag `serial`** | ❌ | Requires SGTIN decoding, which does not exist |

---

## 2. The five structural gaps — this is the real work

Not missing fields. Missing concepts.

1. **A session has no SKU.** `InventoryRequest` is `{label, direction, expectedTags, settleMs,
   maxDurationMs}` — there is no `ean`. Everything downstream depends on this: `matched` versus
   `unexpected` is defined entirely by whether a tag's decoded GTIN matches the requested EAN.
2. **No SGTIN-96 decoding in the read path.** Needed for `serial`, and for the three-way
   classification. `tools/sgtin96.py` is the reference; the Java equivalent must agree with it on the
   two test vectors.
3. **No TID capture.** `InventoryTag` has no `tid`, so `tid: true` is not "wire it to FastID" — the
   field, the plumbing and the decision about when to ask for it are all absent. The good news from
   your §8 is that the stock is Impinj, so FastID can return it alongside the EPC rather than costing
   a second pass.
4. **No three-way classification.** One flat `tags` list. And per your §9, on real stock this is not
   a rare branch: **only 2 of 19 tags carried a valid GS1 EPC header**, so `undecodable` is the
   common case, not the edge case.
5. **No mode concept.** No arming, no autonomous per-carton cycle, no mode state machine, no callback
   sender. Super Fast is the largest single piece and has no counterpart in the current app.

**`marginalCount` and `isMarginal()` have no home in the contract**, and that is worth a decision
rather than a silent drop. A weak sighting is a different axis from a wrong SKU — it is not
`unexpected`. My inclination is that it stays internal and, if it surfaces at all, does so as a
per-tag boolean rather than a top-level count. Tell me if you disagree; you have seen what the RSSI
distribution actually looks like and I have not.

---

## 3. Where my reading is most likely wrong — check these specifically

**3.1 Is `sequence` durable across a restart?** It is documented as "monotonic spool sequence number,
for polling clients", which suggests it comes from the spool. The contract requires it to survive a
reader restart, because the WMS uses it as a reconciliation cursor. **Restart the app and see what
the next `sequence` is.** If it resets, that is a real defect and I want it in the spec explicitly.

**3.2 Which rule does `complete` actually use?** There are two in the file: the stored `complete`
field, and `isTrustworthy()` which additionally returns false for `TIMED_OUT` and `ABORTED`. The
contract's `complete` is **exact equality only** (`matched.count == expectedCount`), and `stopReason`
carries the timeout information separately. Confirm which one populates the field, because they are
not the same and the WMS will branch on it.

**3.3 The `readCount` null you reported.** You reported `InventoryTag.readCount` as null, but the
field I see is `int reads` — a primitive, which cannot be null. Either the name has changed, there
is another type involved, or it is serialising as `0`. Worth pinning down, because "always 0" and
"null" are different bugs and the contract's `reads` field depends on it.

**3.4 Does `default-property-inclusion: non_null` actually apply to these responses?** The contract
says null fields are omitted, not sent as null, and absent means *not applicable* rather than zero.
It is set in `application.yml`; confirm it survives into the JSON you actually get.

**3.5 Anything else in the spec that does not match what you see.** I would rather revise the spec
now than have you build to a wrong description of your own code.

---

## 4. What to report back

A short document, `HANDOFF-CM4-TO-LAPTOP-TUNNEL-02.md`:

1. **Corrections to §1 and §2.** Anything I have got wrong about the current code.
2. **Answers to §3.1–3.4**, measured rather than read.
3. **Your estimate of the shape of the work** — which of the five gaps in §2 is largest, and whether
   you would sequence them differently. You know the codebase's grain better than I do now.
4. **Anything in the spec that is impossible, ambiguous, or contradicts the document.** The `.docx`
   is the authority and has been sent to the customer; if it asks for something the module cannot do,
   that is a finding for the customer, not something to route around quietly.
5. **Whether the two `/api/v1` gaps I flagged are real**: the undefined `reader/status` response
   body, and batch commissioning having no way to address "the next unwritten tag".

## 5. Fix now, while you are in there

Only the ones that are cheap and that make later measurement trustworthy:

- **`readCount` / `reads`** (§3.3), because the confidence signal is currently unusable.
- **Spool startup crashing** when the directory is unwritable — degrade and report unhealthy, per the
  project's own rule. Your instinct on this was right.
- **`configureFastMode()` not clearing a sticky fast mode in POLLED** — from
  `docs/RF-Modes-E710.md` §6.3. This one matters now rather than later, because the acceptance suite
  and most diagnostics run in POLLED, so a measurement taken after a fast-mode run may not be what it
  claims.

**Do not** build `COUNT_REACHED`, the classification, or any part of `/api/v1` yet. Not because they
are wrong — `COUNT_REACHED` is still the cheapest second in the budget — but because they are the
spec's work and it should not start until the audit has had a chance to change the spec.

---

## 6. Then

Once the audit is back and the spec is corrected, build order will be roughly: the result object and
SGTIN decoding first (everything depends on them), then Managed Reading, then Super Fast and the
callback sender, then Managed Writing. The spec's §9 has the tests, and the laptop's REST client has
a `WMS API v1` tab that drives all five endpoints and checks every response against the document —
including a WMS simulator that validates arriving callbacks and can inject a 5 s delay or a 500.

It shares no code with the reader on purpose, so it cannot rubber-stamp the reader's own output.

---

*Laptop design session, 2026-08-28. §1 is read from source, not run. Correct it.*
