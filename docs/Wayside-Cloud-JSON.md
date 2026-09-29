# Wayside reader → cloud: the pass JSON

**For the team that owns `mmmocl.intellirail.cloud`.** Version 1, 2026-09-29. Written from the
code (`intelli-wayside-reader`, `PassResult.java` and `CloudSender.java`). The example below is a
real pass recorded on the development reader that day.

**Status: live, but the format is our proposal.** The first pass was delivered on 2026-09-29 at
17:45 IST, and your endpoint answered `200` (§6). Once the questions in §7 are answered and the
format is agreed, this document becomes the contract, and the format changes only when the
document does.

---

## 1. What it is

A reader beside the track identifies each train that passes and makes **one POST per train**. A
train carries two RFID tags, one at each end. The reader reports:

- **Identity:** the tags it read.
- **Wheel data:** axle count, direction and speed from two wheel sensors, **once they are
  fitted**. Until then the train's start and end come from two digital inputs, and every wheel
  field is `null` (§4.4).

## 2. The request

| | |
|---|---|
| Method | `POST` |
| URL | `https://mmmocl.intellirail.cloud/rest/wpmsRfidJsonFromClient`, as configured on the reader (`wayside.cloud.url`) |
| Body | One JSON object, UTF-8, described in §4 |
| Headers | `Content-Type: application/json`, plus `Authorization: Bearer <token>` **if** a token is configured. None is configured today (§7) |
| Timeout | 5 s to connect, 5 s for the response |
| One call is | one train. Never a batch, and never a partial train |

## 3. What the reader does with your response

| You answer | The reader |
|---|---|
| **2xx** | Treats it as delivered. The response body is ignored |
| **3xx** | Treats it as rejected. It logs the `Location` and **does not follow or retry.** A redirected POST usually arrives as a GET, somewhere that never saw the data |
| **401 / 403** | Treats it as rejected and raises an operator alarm. It does not retry: a bad token needs a person |
| **Other 4xx** | Treats it as rejected and does not retry. Your 4xx means "do not send this again", and it is honoured |
| **5xx, timeout, connection failure** | Retries up to 5 attempts with backoff (1 s, doubling, capped at 30 s). Then it spools the pass to disk and re-tries the spool every 60 s. A pass still undelivered after **7 days** is set aside and not sent again |

**Delivery is at-least-once, never exactly-once.** A retry, or a replay after an outage, sends
**the same bytes with the same `id`**. **Please deduplicate on `id`.** The reader cannot tell a
response that was lost on the way back from a request that never arrived, so duplicates will occur.

**`sequence` reveals gaps.** It increases by one per pass, per reader, and survives restarts. If
you see 41 then 43, pass 42 is still in the reader's spool or was rejected.

Nothing on the reader waits for you. A slow or absent endpoint delays delivery and never delays
reading the next train.

## 4. The body

### 4.1 Example: a real pass, 2026-09-29, start and end from the digital inputs

```json
{
  "id": "573907cd-c8e4-44e5-9101-5812b4afbcc9",
  "readerId": "intellisbc2-dev",
  "sequence": 1,
  "startedAt": "2026-09-29T12:08:54.815683448Z",
  "endedAt": "2026-09-29T12:09:01.072913504Z",
  "stopReason": "CLEARED",
  "clockSynced": true,
  "train": {
    "id": null,
    "decoded": false,
    "tagsExpected": 2,
    "tagsFound": 2,
    "complete": false
  },
  "tags": [
    {
      "epc": "8A8070003A6D00021F0C3F9D",
      "tid": null,
      "decoded": false,
      "trainId": null,
      "firstSeen": "2026-09-29T12:08:54.999Z",
      "lastSeen": "2026-09-29T12:08:59.312Z",
      "reads": 3,
      "bestRssiDbm": -47.0
    },
    {
      "epc": "8A8020008A1D00021F0C12E9",
      "tid": null,
      "decoded": false,
      "trainId": null,
      "firstSeen": "2026-09-29T12:08:56.370Z",
      "lastSeen": "2026-09-29T12:08:59.312Z",
      "reads": 2,
      "bestRssiDbm": -55.0
    }
  ],
  "wheels": {
    "link": "GPIO",
    "direction": null,
    "axleCount": null,
    "speedKmh": null,
    "axles": null,
    "faults": []
  },
  "reader": {
    "app": "1.0.0-SNAPSHOT",
    "moduleFw": "20.26.08.19",
    "region": "RG_IN"
  }
}
```

### 4.2 Conventions

- **Every field is always present.** A field with no value is sent as `null`, never omitted. For
  this reader, `null` means "declined to guess", which is different from "not sent".
- **Times are ISO-8601 in UTC, with a `Z` suffix.** The fraction has **0 to 9 digits**, and it
  varies: `startedAt` usually has nanoseconds and `firstSeen` milliseconds. Parse any precision.
- Enumerations are upper-case strings. **A value not listed here may appear in a later version.**
  Treat an unknown one as "unknown", not as an error.

### 4.3 Top level

| Field | Type | Meaning |
|---|---|---|
| `id` | string (UUID) | Unique per pass. **The deduplication key.** The same on every retry |
| `readerId` | string | Which reader. Configured per unit, e.g. `charkop-01` at site. `intellisbc2-dev` is the development board |
| `sequence` | integer | Per reader, +1 per pass, never reset. For gap detection (§3) |
| `startedAt` | time | The pass opened: the first wheel, or the start input |
| `endedAt` | time | The pass closed, including the time held open for the rear tag |
| `stopReason` | enum | What closed the pass (below). **It says nothing about completeness** |
| `clockSynced` | boolean | Whether the reader's clock had synchronised with NTP when it sent this. The reader has no battery-backed clock, so after a power cut its time can be minutes or days off until NTP catches up. **When `false`, do not trust the times** |
| `train` | object | §4.5 |
| `tags` | array | §4.6. Every tag read during the pass, **including ones that do not decode** |
| `wheels` | object | §4.4 |
| `reader` | object | §4.7 |

`stopReason`:

| Value | Meaning |
|---|---|
| `CLEARED` | Normal: the wheels cleared the sensors, or the end input arrived. The reader then held the radio on 3 s more for the rear tag |
| `TIMEOUT` | Backstop: the pass ran 10 minutes without closing. Typically a train stopped over the sensors, or a stuck sensor. The data up to that point is still sent |
| `TAG_GAP` | Degraded: the wheel sensors, or the start/end inputs, were not working, so the pass opened on the first tag and closed after 5 s with no tag. Identity only |

### 4.4 `wheels`

| Field | Type | Meaning |
|---|---|---|
| `link` | enum | Where the pass boundaries came from (below) |
| `direction` | enum or null | `UP`, `DOWN`, `MIXED` (the train reversed over the sensors), `UNKNOWN` (evidence missing or conflicting), or `null` (no wheel data at all) |
| `axleCount` | object or null | `{ "headA": int, "headB": int, "consistent": bool }`. The two sensor heads count independently. `consistent: false` means they disagree, and the reader reports that rather than picking a number |
| `speedKmh` | object or null | `{ "min", "mean", "max" }`, in km/h to 0.1. `null` inside when it cannot be measured |
| `axles` | array or null | One entry per axle, in order (below) |
| `faults` | array of strings | Human-readable sensor problems seen during the pass, e.g. `"head B system 1: OPEN"`. **Wording may change: display it, do not parse it** |

`link`:

| Value | Meaning |
|---|---|
| `GPIO` | **Today.** Start and end came from two digital inputs, standing in for the wheel sensors. No wheel data exists, so `direction`, `axleCount`, `speedKmh` and `axles` are `null` |
| `OK` | Wheel sensors worked throughout |
| `LOST` | The wheel-sensor link dropped during the pass. Wheel data covers only part of the train |
| `DOWN` | No wheel sensing at all: this pass is `TAG_GAP`, and the wheel fields are `null` |

Each entry in `axles`: `{ "n": 1, "atA": time|null, "atB": time|null, "speedKmh": number|null,
"peakUa": [int|null, int|null, int|null, int|null] }`. `atA` and `atB` are when that axle passed
head A and head B. `peakUa` is the sensor current peak in µA for head A system 1, head A system 2,
head B system 1 and head B system 2, for spotting a weak sensor over months. A 12-car train is
about 50 entries.

What a pass looks like with wheel sensors (from the simulator; the sensors are not fitted yet):

```json
"wheels": {
  "link": "OK",
  "direction": "DOWN",
  "axleCount": { "headA": 8, "headB": 8, "consistent": true },
  "speedKmh": { "min": 45.0, "mean": 45.0, "max": 45.0 },
  "axles": [
    { "n": 1, "atA": "2026-09-29T10:22:18.589999304Z", "atB": "2026-09-29T10:22:16.990052556Z",
      "speedKmh": 45.0, "peakUa": [9800, 9800, 9800, 9800] }
  ],
  "faults": []
}
```

### 4.5 `train`

| Field | Type | Meaning |
|---|---|---|
| `id` | string or null | The train identity decoded from its tags. **`null` until the tag encoding is agreed (§7)** |
| `decoded` | boolean | `true` when `id` could be decoded |
| `tagsExpected` | integer | 2: one tag at each end |
| `tagsFound` | integer | Distinct tags read. **Can exceed 2** (a tag on a passing wagon, a tag on the next track) |
| `complete` | boolean | `true` only when at least `tagsExpected` tags were read and **all of them decode to the same train**. Always `false` while the encoding is unknown |

**`complete` and `stopReason` are independent.** A train that cleared normally with one tag unread
is `CLEARED` and `complete: false`. Neither field softens the other.

### 4.6 `tags[]`, ordered by `firstSeen`

| Field | Type | Meaning |
|---|---|---|
| `epc` | string | The tag's EPC, upper-case hex, no separators. Usually 24 characters (96 bits); other lengths are possible |
| `tid` | string or null | The factory chip serial, when the reader collects it. **Off today, so always `null`** |
| `decoded` | boolean | Whether this EPC decodes to a train id |
| `trainId` | string or null | That id |
| `firstSeen`, `lastSeen` | time | The first and last reads of this tag during the pass |
| `reads` | integer | How many times it was read. More reads means more confidence |
| `bestRssiDbm` | number | The strongest signal, in dBm, typically −30 to −70. Useful for rejecting a tag on an adjacent track |

**A tag that does not decode is still sent, raw.** Losing a train because its tag did not match a
rule would be worse than sending a hex string.

### 4.7 `reader`

| Field | Meaning |
|---|---|
| `app` | Reader software version |
| `moduleFw` | RFID module firmware |
| `region` | Radio region. `RG_IN` = 865–867 MHz India |

## 5. Size and rate

One POST per train, and a few kilobytes: about 1.5 KB today, and 5–10 KB once a 12-car train's
axles are included. A backlog after an outage replays one pass at a time, never in parallel.

## 6. Delivery so far

- **2026-09-29, 17:45 IST: first pass delivered**, answered `200`: pass
  `7fa62c83-4e7f-4227-a1c1-9551311f3161`, 2 tags, from the development reader `intellisbc2-dev`.
- Earlier that day the reader was configured without `/rest/`. There, every POST was answered with
  `302` to the site root, and those passes (including the example in §4.1) were not delivered and
  will not be re-sent.

## 7. What we need from you

1. **Authentication.** A bearer token (the reader supports it now), an API-key header, or
   something else. Anything but a bearer token is a small change on our side.
2. **Content type.** It accepted `application/json`. Please confirm that is what it expects.
3. **Is this body acceptable, or do you have a format of your own?** If you do, send it and we will
   map to it. A mapping is quicker to agree than a redesign.
4. **What you answer on success.** Any 2xx works. A body is fine but ignored.
5. **Deduplication on `id`**: please confirm you will do it (§3).
6. **The tag encoding**, if you know it: how a train id, and ideally which end, is written into the
   EPC. Until then `train.id` stays `null` and `complete` stays `false`.

Contact: Piyush Nigam.
