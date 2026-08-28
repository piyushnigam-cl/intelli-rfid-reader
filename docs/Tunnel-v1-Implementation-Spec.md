# `intelli-rfid-tunnel` v1 — implementation spec

**For the CM4 session.** This specifies the `/api/v1` layer: the customer-facing contract in
`Intelli-RFID-RestAPI.docx`, which has been **issued to Reliance** and is not yet implemented.

## Authority

**The `.docx` is the contract. This spec is an aid to implementing it.** Where the two disagree, the
document wins — it is what the customer has. If the document is wrong or impossible, say so and
stop; do not quietly implement something else. A divergence discovered by the WMS integrator costs
far more than one raised now.

Where this spec says **MUST**, it is transcribed from the document. Where it says **SHOULD** or
**PROPOSED**, it is our choice and you may push back.

## Scope

**In:** the five `/api/v1` endpoints, the result object, the callback sender, the error model, scope
enforcement, and the changes to existing code they require.

**Out:** the S2-persistence and read-mode decisions. Those are real and unresolved, but they are
session tuning and do **not** block this layer — build against whatever session config is current.

---

## 1. What exists, what is needed

Today the tunnel serves `/api/inventory/**` (`InventoryController`): `POST /sessions`,
`GET /sessions/current`, `POST /sessions/{id}/close`, `/abort`, `/latest`, `/history`, `/completed`,
`/direction`.

**Keep it.** It is the diagnostic and bench surface, the reader-test client drives it, and it is
useful for exactly the debugging the v1 layer will need. But it is **not** the contract, it is not
customer-facing, and it MUST NOT appear in customer documentation. Mark it so in the code.

Add, as a new layer on top of the same `InventoryService`:

| Method | Path | Scope |
|---|---|---|
| POST | `/api/v1/mode` | INVENTORY |
| GET | `/api/v1/mode` | INVENTORY |
| POST | `/api/v1/inventory` | INVENTORY |
| GET | `/api/v1/reader/status` | INVENTORY |
| POST | `/api/v1/tags/write` | COMMISSION |

**Any `/api/v1` path not in that table MUST require ADMIN.** The document commits to this
explicitly: an endpoint added in a future version is then closed by default rather than accidentally
open. Implement it as a default-deny rule, not by listing paths.

---

## 2. The result object — build this first

One type, produced by Super Fast and by both forms of Managed Reading. The document says an
integration can share one parser, so **there is exactly one shape**.

```json
{
  "id":            "8f2b1c44-9a0e-4d7b-b2a1-7c5e9d3f0a11",
  "sequence":      1188,
  "mode":          "SUPERFAST",
  "direction":     "IN",
  "ean":           "8905527164445",
  "gtin14":        "08905527164445",
  "startedAt":     "2026-08-27T09:14:02.118Z",
  "endedAt":       "2026-08-27T09:14:03.948Z",
  "durationMs":    1830,
  "stopReason":    "COUNT_REACHED",
  "expectedCount": 40,
  "complete":      true,
  "matched":     { "count": 40, "tags": [ { "epc": "...", "tid": "...", "serial": 1043,
                                            "rssi": -47, "reads": 12, "firstSeenMs": 214 } ] },
  "unexpected":  [],
  "undecodable": []
}
```

### Rules that are easy to get subtly wrong

- **`id`** — UUID, stable for the life of the result. The WMS deduplicates on it. A retry MUST carry
  the same id.
- **`sequence`** — monotonic **and durable across a reader restart**. This is not an in-memory
  counter. Persist it next to the spool and fsync before use; a duplicate sequence after a power cut
  breaks the WMS's reconciliation cursor.
- **`mode`** — `SUPERFAST` or `MANAGED_READ`. Nothing else appears in a result.
- **`stopReason`** — **`COUNT_REACHED` | `SETTLED` | `TIMEOUT`. Exactly these three.** The internal
  `CloseReason` today is `SETTLED | CLOSED_BY_CALLER | TIMED_OUT | ABORTED` — it invents two and is
  missing the one that matters. Map at the boundary; do not rename the internal enum, and do not leak
  it.
- **`complete`** — **exact equality**: `matched.count == expectedCount`. Not "at least". When
  `expectedCount` was not supplied, omit `complete` rather than guessing — the document says absent
  means not applicable.
- **Null fields are omitted, never sent as `null`.** A global Jackson setting, and the app already
  has `default-property-inclusion: non_null`. Verify it applies to the v1 responses.
- **Timestamps** ISO-8601 UTC with milliseconds. **Durations** in ms, field names end `Ms`. **EPC and
  TID** uppercase hex, no separators.

### Classifying a tag — the part that carries real risk

| Bucket | Rule |
|---|---|
| `matched` | Decodes as SGTIN-96 **and** its GTIN matches the requested `ean`. |
| `unexpected` | Decodes as SGTIN-96, but a **different** EAN. A picking error, or a neighbouring carton bleeding in. Include the decoded `ean` on each entry. |
| `undecodable` | Replied, but is not SGTIN-96. Entry is `{ "epc": "...", "reason": "header 0x31 is not SGTIN-96" }`. |

**`undecodable` MUST be routine, not an edge case.** On the bench population **only 2 of 19 tags
carried a valid GS1 EPC header at all**. Every tag that answers is reported somewhere — the document
says undecodable tags are "reported, never silently discarded". All three arrays are always present,
empty rather than absent.

**When `ean` is omitted** (legal in Managed Reading), everything that decodes goes in `matched` and
`unexpected` stays empty. The document is explicit: omitting `ean` "does not discard tags, it only
changes what is reported".

---

## 3. The endpoints

### 3.1 `POST /api/v1/mode` — arm and disarm Super Fast

Request: `mode` (required, `SUPERFAST`|`IDLE`), `ean` (required when arming), `expectedCount`
(required when arming), `callbackUrl` (required when arming), `direction` (optional, `IN`|`OUT`,
defaults to the tunnel's configured direction).

200 response: `mode`, `ean`, `gtin14`, `expectedCount`, `callbackUrl`, `direction`, `armedAt`.
When disarmed, `{"mode": "IDLE"}` and the SKU fields are absent.

Once armed, the reader runs autonomously per carton:

1. Optical sensor detects the carton; antennas energise.
2. Inventory, **ending as soon as `expectedCount` distinct EPCs of the armed EAN are seen.**
3. **Release the carton.**
4. **Then** POST the result.

**Step 3 before step 4 is a hard requirement, not an optimisation.** The document promises a slow or
unreachable WMS "does not stall the conveyor". If releasing ever waits on the callback, that promise
is broken and the failure appears as a stopped line at the customer's site.

Errors: `400 invalid_ean`, `400 callback_url_required`, `409 mode_conflict`,
`409 reader_not_connected`.

`GET /api/v1/mode` returns the same object. The document tells the WMS to check it at start-up
because **a reader left armed by a previous shift keeps reading against the old SKU** — so this must
reflect real state, not a cached value.

Changing SKU requires re-arming. **No partial update.** Cartons of another SKU passing while armed
are reported in `unexpected` with `complete: false` — they are not lost, but that is not a substitute
for re-arming.

### 3.2 `POST /api/v1/inventory` — Managed Reading

Request: `ean` (optional), `expectedCount` (optional), `timed` (**required**), `durationMs`
(required when `timed`), `callbackUrl` (required when not `timed`), `tid` (optional, default false).

| `timed` | Response | How the read ends |
|---|---|---|
| `true` | **200** with the full result, after `durationMs` has elapsed | **Always runs the whole of `durationMs`**, even if the count was reached earlier |
| `false` | **202** with `{ "id", "startedAt" }` | Best effort within the configured window, **ending as soon as `expectedCount` distinct articles are found** |

The 202's `id` MUST be the same `id` the callback later carries — that is how the WMS ties the result
back to the carton it dispatched. The callback carries `"mode": "MANAGED_READ"`.

`timed: true` running short is a contract violation even though it looks like an improvement. The
customer may be holding the carton for a deterministic period.

Errors: `400 callback_url_required`, `400 duration_required`, `409 read_in_progress`,
`409 mode_conflict`, `409 reader_not_connected`.

**`409 read_in_progress`**: a tunnel reads one carton at a time. The document calls this "a physical
constraint, not a simplification". Serialise properly — a lock, not a best-effort flag.

**`tid: true` is now cheap.** The bench stock is Impinj, so FastID returns TID alongside EPC in one
operation. Wire `tid` to FastID rather than a second read pass, and note in `CLAUDE.md` that this
depends on Impinj silicon — mixed stock will need a fallback.

### 3.3 `GET /api/v1/reader/status`

**The document does not define this response body** — it appears only as a curl example in §3.2 for
confirming connectivity and a key. That is a gap in the contract.

**PROPOSED** — implement something small and obviously safe, and tell us so the document can be
updated to match:

```json
{ "connected": true, "mode": "IDLE", "readerState": "OPEN",
  "moduleFirmware": "20.26.03.30", "antennas": 2, "temperatureC": 41,
  "sequence": 1188, "spoolDepth": 0, "uptimeMs": 918273 }
```

Do not expose API keys, key ids, hashes, callback tokens, or file paths. This endpoint is the one
most likely to be polled by monitoring and left visible.

### 3.4 `POST /api/v1/tags/write` — Managed Writing, COMMISSION scope

Request: `ean` (required), `count` (required), `startSerial` (optional), `lock` (optional, default
false), `accessPassword` (required when `lock`, **rejected when not**).

Response: `ean`, `gtin14`, `serialSource` (`LOCAL`|`CALLER`), `requested`, `quantityMet`, `written[]`
(`serial`, `epc`, `tid`), `failed[]` (with the stage reached and the reason), `localSerialNext`
(**absent when `serialSource` is `CALLER`**).

The write sequence MUST be: **write EPC → read back and verify → set access password → lock EPC bank
→ confirm lock state.** A failure at any stage returns that tag in `failed` **with the stage it
reached**, so a partially commissioned tag is visible rather than silently counted as written.

- **Serial 0 is never issued.** A blank or half-written tag reading as zeros must never look like a
  valid article.
- **`accessPassword` of all zeros is rejected** — a Gen2 lock with the zero password is not a lock.
- **Never permalock.** Irreversible; a mis-encoded tag becomes scrap.
- The GS1 **partition is not an API parameter** and must not become one. A wrong partition still
  decodes to the correct GTIN, so the error would be invisible. It is site config.

Errors: `400 invalid_ean`, `400 access_password_required`, `400 access_password_unexpected`,
`403 insufficient_scope`, `409 reader_busy`.

> **Known hole, flag it rather than inventing a fix.** `count` implies batch commissioning, but Gen2
> offers no way to address "the next unwritten tag". Writing N tags needs physical singulation, or a
> Select on "does not yet match our prefix". **Neither is in the document.** Implement `count: 1`
> correctly, make N>1 behave sanely and honestly (report what it actually wrote), and write up what
> the real mechanism should be. Do not paper over it.

---

## 4. Mode state machine

One mode at a time. **PROPOSED** states and the 409s they produce:

| State | `POST /mode` SUPERFAST | `POST /inventory` | `POST /tags/write` |
|---|---|---|---|
| `IDLE` | arm | run | commission |
| `ARMED_SUPERFAST` | 409 `mode_conflict` unless identical params | 409 `mode_conflict` | 409 `reader_busy` |
| `READING` | 409 `mode_conflict` | 409 `read_in_progress` | 409 `reader_busy` |
| `COMMISSIONING` | 409 `mode_conflict` | 409 `read_in_progress` | 409 `reader_busy` |
| module not connected | 409 `reader_not_connected` | 409 `reader_not_connected` | 409 `reader_not_connected` |

Re-arming with **identical** parameters SHOULD be idempotent (200, same `armedAt`) rather than 409 —
a WMS restart re-arming defensively is normal and should not need a disarm first. Re-arming with
**different** parameters is `409 mode_conflict`; the document says disarm first.

---

## 5. The callback sender

Used by Super Fast (every carton) and Managed Reading with `timed: false`.

- **`X-Callback-Token`** on every callback, from config, issued by the WMS. One token per reader.
- **A response slower than 2 seconds is a failure** and is retried. Set the client timeout to match.
- **Retry 5xx and timeouts with backoff. Never retry 4xx.** The document tells the WMS its 4xx/5xx
  distinction will be honoured, so honour it.
- **Spool to disk when the WMS stays unreachable**, and replay on recovery. Spool depth belongs in
  `/api/v1/reader/status`.
- **At-least-once, by design.** Same `id` on every attempt. Do not attempt exactly-once.
- **Never let a callback block the carton release** (§3.1).

Ordering is not guaranteed and the document tells the WMS not to depend on it. Do not add sequencing
guarantees the contract does not promise — the WMS uses `sequence` to detect gaps.

---

## 6. Errors

Every error, without exception:

```json
{ "error": "reader_error", "message": "Reader is not connected (state=CLOSED)",
  "readerCode": "MT_HARDWARE_ERR", "timestamp": "2026-08-27T09:14:02.118Z" }
```

`error` is a **stable machine-readable slug** the caller branches on — never prose, never a sentence.
`message` is for humans and may change. `readerCode` appears **only** when the failure came from the
module.

Slugs the document commits to: `invalid_ean`, `callback_url_required`, `duration_required`,
`access_password_required`, `access_password_unexpected`, `mode_conflict`, `read_in_progress`,
`reader_busy`, `reader_not_connected`, `missing_api_key`, `invalid_api_key`, `insufficient_scope`.

Status codes: 200, 202, 400, 401, 403, **409**, 500. **409, not 500, for "the reader is not in a
state to do this"** — the document explains this keeps genuine faults visible in the customer's 5xx
alerting. `ReaderException` already maps to 409; keep that.

A `403` message names the scope required — the document shows
`"This endpoint requires the COMMISSION scope. Your key holds: [INVENTORY]."` Do not echo the key.

---

## 7. Changes to existing code

### 7.1 `COUNT_REACHED` and early exit on count — do this first

The single highest-value change, and it is measured: **discovery finished in ~0.5–1.0 s and settle
then burned another 1.5 s — settle is 60–75% of session time.** With `expectedCount` supplied, a
healthy carton should close on count and never wait out settle.

Add `COUNT_REACHED` to the internal close reasons, exit as soon as `matched.count == expectedCount`,
and map at the v1 boundary. Settle becomes the **fallback** path — it runs when the count is absent
or not reached, i.e. when something is already wrong.

### 7.2 `readCount` is null on every tag

`InventoryTag.readCount` comes back null although `TMFlags.IsReadCnt` is set and raw
`TAGINFO.ReadCnt` is populated. The result object's `reads` field depends on it, and it is the
confidence signal `dedup-window-ms` exists to preserve.

### 7.3 The `/sessions/current` race

Right after `POST /sessions` returns 201, `GET /sessions/current` can answer 204 while `/latest`
still holds the **previous** result. A polling caller silently reads the wrong session.
**Design it out of v1** — the async form returns an `id` and the result arrives by callback, so no
caller should ever need to poll. Fix the internal surface too.

### 7.4 Spool startup: degrade, do not crash

`JsonlSpool.initialise()` throws `UncheckedIOException` out of the `InventoryService` constructor and
kills the context when the spool directory is not writable. This contradicts the project's own rule
that a field unit comes up and reports unhealthy rather than crash-looping. **A spool that cannot be
written is a degraded reader, not an unusable one.** Report it in `/actuator/health` and in
`/api/v1/reader/status`, and start.

### 7.5 Security on

`rfid.security.enabled` stays **true** for tunnel. The API-key package has still never run over the
wire — v1 is the first thing to exercise it. Test both scopes and a deliberate rejection.

---

## 8. Config to add

```yaml
tunnel:
  v1:
    callback:
      token: ""                # X-Callback-Token, issued by the WMS
      timeout-ms: 2000         # the document's 2 s deadline
      retry: { attempts: 5, initial-backoff-ms: 500, max-backoff-ms: 30000 }
    sequence-file: /var/lib/intelli/tunnel/sequence
    default-direction: IN
gs1:
  company-prefix: "8905527"
  company-prefix-length: 7
  partition: 5                 # NOT an API parameter, deliberately
  filter-value: 1
  valid-eans: ["8905527164445", "8905527168207"]   # invalid_ean is validated against this
```

`invalid_ean` is "failed validation, **or is not one configured for this site**" — so the site EAN
list is config, and an unknown EAN is a 400 rather than a read that returns everything as
`unexpected`.

---

## 9. Tests

- **Contract tests per endpoint**: every documented request shape, every documented error slug, and
  the exact status code for each.
- **The result object**: `complete` as exact equality; the three-bucket classification with a
  population that is mostly undecodable (that is the real bench data); `stopReason` mapping from all
  four internal close reasons.
- **`sequence` survives a restart** — the one test most likely to be skipped and most expensive to
  discover in production.
- **Scope enforcement**: INVENTORY key against `/tags/write` gives 403; unlisted `/api/v1/*` path
  requires ADMIN.
- **Callback sender**: retries 5xx, does not retry 4xx, spools when unreachable, same `id` across
  attempts, and **the release happens before the callback**.

**Then run the laptop's REST client against it.** `apps/intelli-rfid-rest-client` has a `WMS API v1`
tab that drives all five endpoints and **checks every response against the document**, plus a WMS
simulator that validates arriving callbacks and can inject a 5 s delay or a 500 to exercise §5. It
shares no code with the reader deliberately, so it cannot rubber-stamp its own output. If it reports
conformance, that is real evidence.

---

## 10. Do not

- Do not expose `/api/inventory/**` in customer docs, or change its shape to match v1.
- Do not rename the internal `CloseReason` enum — map at the boundary.
- Do not add `partition` as an API parameter.
- Do not implement exactly-once callback delivery.
- Do not permalock, ever.
- Do not invent a fourth `stopReason`.
- Do not let a callback delay a carton release.
- Do not fix the S2 or read-mode questions as part of this work.

---

## 11. Open — needs the laptop, not you

1. `GET /api/v1/reader/status` body is undefined in the document (§3.3 above proposes one).
2. Batch commissioning has no tag-addressing mechanism (§3.4).
3. Whether the write API should accept a **GTIN-14 indicator digit** — the bench found indicator-9
   variable-measure tags that `{ean, count, startSerial}` cannot express.
4. The S2-persistence and read-mode-default decisions, tracked separately.

Same rule as always: where the module or the code contradicts this spec, say so — but where **this
spec contradicts the `.docx`, the `.docx` wins**, because that is what the customer holds.

---

*Laptop design session, 2026-08-28. Transcribed from `Intelli-RFID-RestAPI.docx`. Nothing here has
been run.*
