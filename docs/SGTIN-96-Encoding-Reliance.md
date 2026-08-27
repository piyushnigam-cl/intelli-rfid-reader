# SGTIN-96 Encoding — Reliance (intelli-rfid-tunnel)

Status: **design note, drafted without hardware.** Encoding maths is verified by an encode/decode
round-trip in software. Everything about module and air-interface *timing* is arithmetic from the
Gen2 spec and the vendor docs — it must be measured on the CM4 before anyone quotes a number.

Customer: Reliance. Two EANs in scope:

| EAN-13 | Check digit | GTIN-14 |
|---|---|---|
| 8905527164445 | valid (5) | 08905527164445 |
| 8905527168207 | valid (7) | 08905527168207 |

**Read time is the headline requirement.** 5 s vs 10 s per box is the difference between a brilliant
system and a barely acceptable one. Everything in §7 exists to serve that.

> ### Correction to earlier advice — read this before implementing target alternation
> I previously suggested alternating the Gen2 target A/B between boxes. **That is wrong for this
> application and would break your reads.** A tag that has been unpowered longer than the session
> persistence powers up with its inventoried flag set to **A**. An inventory round with Target B
> therefore does not see fresh tags at all — a box read with Target B after the tags had gone quiet
> would return close to nothing. Target alternation is a technique for re-reading a *static*
> population quickly, not for a conveyor presenting a fresh box each time.
> **Use Target A always.** §7.1 has the correct handling, including same-box retry.

---

## 1. What the requirement actually says

Three separate things are being specified, and it helps to keep them apart.

**The EAN is the product identity.** `8905527164445` is a GTIN-13 — it says *what* the article is
(one SKU), not *which one*. Every unit of that SKU carries the same EAN. `890` is the GS1 India
prefix, so both codes are issued out of Reliance's GS1 India company prefix.

**SGTIN is "serialised GTIN".** It is the GTIN **plus a serial number**, so it names *this
individual article* rather than the SKU. That is the whole point for a tunnel: a box holding ~40
units of the same SKU produces 40 *different* EPCs, so we can count them. If the tags carried only
the GTIN, forty identical tags would be indistinguishable and "did we read all 40?" would be
unanswerable.

**SGTIN-96 is the 96-bit binary form** of that identity, written into the EPC memory bank (bank 01)
of a Gen2 tag. 96 bits = 24 hex characters = 6 words, which every commodity UHF tag supports.

---

## 2. The bit layout

| Field | Bits | Value here |
|---|---|---|
| Header | 8 | `0x30` — fixed, identifies SGTIN-96 |
| Filter | 3 | **1** (point-of-sale trade item) |
| Partition | 3 | **5** (7-digit company prefix) |
| Company Prefix | 24 | `8905527` (config) |
| Indicator + Item Reference | 20 | 6 digits, indicator `0` |
| Serial | 38 | 1 … 274,877,906,943 |

The check digit is **not** stored — it is recomputed on decode. The indicator digit is prepended to
the item reference; for item-level tags it is `0`.

Partition table, for when a future customer has a different prefix length:

| Company-prefix digits | 12 | 11 | 10 | 9 | 8 | 7 | 6 |
|---|---|---|---|---|---|---|---|
| Partition value | 0 | 1 | 2 | 3 | 4 | 5 | 6 |
| Company prefix bits | 40 | 37 | 34 | 30 | 27 | 24 | 20 |
| Item reference bits | 4 | 7 | 10 | 14 | 17 | 20 | 24 |

Filter values: 0 all others, **1 point-of-sale trade item**, 2 full case, 4 inner pack, 6 unit load.

---

## 3. The two EANs, encoded (confirmed)

| EAN-13 | Company prefix | Indicator + item ref | Pure identity URI |
|---|---|---|---|
| 8905527164445 | 8905527 | 0 + 16444 = `016444` | `urn:epc:id:sgtin:8905527.016444.<serial>` |
| 8905527168207 | 8905527 | 0 + 16820 = `016820` | `urn:epc:id:sgtin:8905527.016820.<serial>` |

Known-good vectors — use these as unit-test fixtures:

| EAN | Serial | EPC (24 hex) |
|---|---|---|
| 8905527164445 | 1 | `30361F8CDC100F0000000001` |
| 8905527164445 | 42 | `30361F8CDC100F000000002A` |
| 8905527164445 | 999999 | `30361F8CDC100F00000F423F` |
| 8905527164445 | 274877906943 (max) | `30361F8CDC100F3FFFFFFFFF` |
| 8905527168207 | 1 | `30361F8CDC106D0000000001` |
| 8905527168207 | 42 | `30361F8CDC106D000000002A` |
| 8905527168207 | 999999 | `30361F8CDC106D00000F423F` |
| 8905527168207 | 274877906943 (max) | `30361F8CDC106D3FFFFFFFFF` |

---

## 4. Configuration

The API surface is now deliberately thin: the caller supplies only what varies per box. Everything
that is a property of the *installation* lives here.

```yaml
gs1:
  companyPrefix: "8905527"        # Reliance. EANs not matching this prefix are rejected.
  companyPrefixLength: 7          # -> partition 5. NOT derivable from an EAN; never an API param.
  filterValue: 1                  # SGTIN filter: 1 = point-of-sale trade item

reader:
  id: 0                           # 0-255. Owns local serial block [id << 30, ((id+1) << 30) - 1].
                                  # Must be unique across every reader that writes tags.
  antennas: [1, 2]                # two antennas on this installation
  dwellMs: 60                     # per-antenna dwell before switching. MTR_PARAM_RF_HOPANTTIME.
                                  # RECOMMENDED 50-80 ms with 2 antennas. Rationale: short dwells,
                                  # many cycles. A long dwell means the tag only antenna 2 can hear
                                  # is not being read at all while we sit on antenna 1. Too short
                                  # (<30 ms) and switching overhead starts to dominate. Tune from
                                  # the discovery curve (§7.10), not by guesswork.
                                  # *** WARNING: THIS MAY NOT BE SETTABLE ON RG_IN. *** The vendor
                                  # docs say HOPANTTIME defaults to 0 (internally 4000 ms) and is
                                  # "modifiable but not permanently savable" ONLY in the China
                                  # region; "when initialized to other regions ... not modifiable".
                                  # The CC33 per-antenna work-time route (MODUSPARMS CMD=0x02) is
                                  # likewise documented as China-region only. Verify on the CM4
                                  # before designing around this value — see §7.8 and §10.

  # --- pushed once at start-up, then served from cache; never re-pushed per call ---
  region: RG_IN                   # 865-867 MHz Indian band. Reader.Region_Conf.RG_IN = 0x04.
                                  # Confirmed present in the SDK. Set once via "Ex/initregion";
                                  # the module then owns frequency hopping and compliance — hop
                                  # time is fixed at 500 ms for non-FCC regions and per the docs
                                  # "determined by the module itself and cannot be modified".
  powerDbm: 30                    # NOTE: the SDK works in centi-dBm (0.01 dBm) — 30 dBm = 3000.
  session: S2                     # MTR_PARAM_POTL_GEN2_SESSION, int[] {0|1|2|3}. No "S10" — §7.1.
                                  # S2 default. S3 is its functional twin, reserved for a second
                                  # reader covering the same area (§7.1.1).
                                  # NOTE the vendor's own guidance differs from ours: they suggest
                                  # S0 for "within dozens" of tags and S1 above ~50. At ~40 we sit
                                  # exactly on that boundary — sweep S0/S1/S2 on the bench (§7.10).
  target: A                       # MTR_PARAM_POTL_GEN2_TARGET, int[] {0:A, 1:B, 2:A->B, 3:B->A}.
                                  # KEEP AT A — see the correction box at the top of this file.
                                  # 2 (A->B) is a real option worth sweeping: the module runs an A
                                  # phase then a B phase in one window, giving the population two
                                  # passes without waiting out flag persistence.
  initialQ: 6                     # MTR_PARAM_POTL_GEN2_Q. 2^Q slots/round; Q=6 -> 64, sized for
                                  # ~40 tags/box. Rule of thumb: Q = round(log2(tag count)) + 1.
                                  # Q=5 (32 slots) for ~20 tags, Q=7 (128) for ~80.
                                  # ENCODING: -1 = fully automatic Q. To set an initial value AND
                                  # keep dynamic adjustment, OR with -256: ParamSet(Q, {6 | -256}).
                                  # Plain {6} is a STATIC Q — almost certainly not what you want.
  tagEncoding: FM0                # MTR_PARAM_POTL_GEN2_TAGENCODING, Reader.RFMODE enum.
                                  # FM0=0, M2=1 (Miller-2), M4=2 (Miller-4), M8=3 (Miller-8).
                                  #
                                  # This is the speed/robustness dial. Miller-M spreads each bit
                                  # over M subcarrier cycles: M8 transmits at one eighth of FM0's
                                  # rate at the same BLF. Fast = fewer bits of energy per symbol =
                                  # worst sensitivity, shortest range, least tolerance of
                                  # interference and multipath. Slow = recovers tags a fast mode
                                  # cannot hear, and coexists in dense-reader environments.
                                  # Per-tag airtime for a 96-bit EPC: FM0 ~1.6 ms, M2 ~2.4 ms,
                                  # M4 ~4.0 ms, M8 ~6.5 ms -> ~64 / 95 / 159 / 259 ms for 40 tags.
                                  #
                                  # HARD CONSTRAINT from the vendor docs (MTR_PARAM_POTL_GEN2_BLF):
                                  # BLF 640 kHz is ONLY valid with FM0; Miller encodings force
                                  # BLF 250 kHz. Encoding and BLF are not independent.
                                  #
                                  # Do NOT assume fastest is fastest overall: a robust mode that
                                  # finds all 40 tags at 1.2 s beats a fast mode that finds 38 at
                                  # 0.9 s and then runs to maxDurationMs. Pick the fastest encoding
                                  # that finds EVERY tag EVERY time, proven by discovery curve.
                                  #
                                  # Ignored when fastMode: EX10 — Ex10 auto-switches RFMODE itself.
  fastMode: EX10                  # EX10 | IMPINJ | NONE. Custom param "Reader/Ex10fastmode":
                                  # 22 bytes = mode(1: 1=Ex fast, 0=normal) + 0x20 + scenario(1).
                                  # Scenario 0-5; 0/2/4 = DENSE tag scenario, 1/3/5 = sparse.
                                  # 40 tags in a box is DENSE -> scenario 0 (or 4 to let the module
                                  # cycle all its RFMODE sets). In Ex10 mode the module auto-switches
                                  # RFMODE internally, so tagEncoding above stops applying.
                                  # Impinj path is the separate custom param "gen2op/impinj_AA5C_cmd"
                                  # / IMPINJ_FASTPARMS. Mutually exclusive and sticky — the code must
                                  # clear the other whenever this changes. See §7.6.
  rssiFilterDbm: null             # null = off. Custom param "Reader/rssifilter" — a module-internal
                                  # RSSI floor. Often a BETTER foreign-tag suppressor than a Select
                                  # (§7.9): racking and adjacent-box tags are further away, so a
                                  # floor cuts them regardless of EAN, and it costs no airtime.
                                  # Set from the observed RSSI spread of in-box vs out-of-box tags.
  fastId: false                   # Custom param "tagcustomcmd/fastid" — Impinj FastID. Returns TID
                                  # WITH the EPC in one operation instead of a separate per-tag
                                  # transaction. Requires Impinj (Monza) silicon. See §6.1.

rf:
  mode: TRIGGERED                 # TRIGGERED | CONTINUOUS. TRIGGERED keeps the module initialised
                                  # and the host link open but the carrier OFF between boxes —
                                  # this is the thermal win, see §7.3.
  triggerSource: GPIO             # GPIO photo-eye / motion sensor
  carrierOffDelayMs: 500          # keep RF up this long after the trigger clears, to catch stragglers

read:
  selectByEan: true               # apply a Gen2 Select when the call supplies an EAN
  selectScope: COMPANY            # COMPANY | SKU. KEEP AT COMPANY — see §7.9. SKU is exposed only
                                  # so the difference can be measured on site.
  selectMechanism: TAG_FILTER     # TAG_FILTER | SELECT_COMMAND. Two distinct SDK paths (§7.9):
                                  # TAG_FILTER     = MTR_PARAM_TAG_FILTER / TagFilter_ST — simple,
                                  #                  one rule, {bank, startaddr(bits), flen, fdata,
                                  #                  isInvert}. Set to null to clear. Up to 16 rules
                                  #                  via MTR_PARAM_TAG_MULTISELECTORS.
                                  # SELECT_COMMAND = custom param "Gen2/selectcommandconfig"
                                  #                  (CMDAA4DData/SELData) — the FULL Gen2 Select,
                                  #                  with seltarget and selaction. Pair with
                                  #                  "Gen2/querysel". Use this one when you need
                                  #                  flag manipulation, not just filtering.
  stopOnCount: true               # exit the instant expectedCount is reached
  settleMs: 300                   # fallback stop: no new EPC for this long. Only reached when
                                  # stopOnCount is false, or expectedCount is absent/not met.
  maxDurationMs: 5000             # hard ceiling
  responseMode: DETAILED          # DETAILED | CONCISE — see §6.2

  # --- thermal / duty, see §7.3 ---
  fastReadDutyRatio: 0            # BackReadOption.FastReadDutyRation — PROPORTION OF THE INVENTORY
                                  # WINDOW SPENT IN STANDBY. 0-10 => value x 5%; on Ex-chip readers
                                  # 11-15 => 55/60/70/80/90%. KEEP AT 0 during a box read: standby
                                  # inside the window is heat management that directly slows the
                                  # read you are trying to make fast. Manage heat with the TRIGGER
                                  # (macro duty cycle), not with this (micro duty cycle).
  powerModeIdle: MED_SAVING       # Custom param "Reader/powermode" between boxes:
                                  # 0x00 FULL, 0x01 MIN_SAVING, 0x02 MED_SAVING, 0x03 MAX_SAVING.
                                  # Must return to FULL before a read — measure the transition cost.

write:
  verifyAfterWrite: true          # read back and compare before reporting success.
                                  # SDK shortcut: custom param "Reader/isWriteReadFlag" makes
                                  # WriteTagData / WriteTagEpcEx read back automatically after
                                  # writing. Convenient, but it needs an oversized data array and
                                  # must be DISABLED afterwards or it corrupts pure writes.
  antenna: 1                      # commissioning antenna
  timeoutMs: 2000

diagnostics:
  discoveryCurve:
    enabled: false                # see §7.10
    dir: /var/log/intelli/curves
    retainFiles: 500
  moduleTelemetry: true           # CC33 / MODUSPARMS CMD=0x01: the module uploads antenna
                                  # connection status + per-antenna VSWR + MODULE TEMPERATURE
                                  # every time the power amplifier is enabled. This is how the
                                  # thermal question (§7.3) gets answered with data instead of
                                  # arithmetic — log it per box and watch it across a shift.
                                  # Also available on demand as MTR_PARAM_RF_TEMPERATURE.
```

### 4.1 EAN validation

Every EAN arriving on any endpoint is validated before anything else happens:

1. 13 digits (EAN-13) or 14 (GTIN-14, leading indicator `0`); digits only.
2. **Check digit correct.** Worth more than it looks — the GS1 mod-10 check catches *every*
   single-digit error and every adjacent transposition except pairs differing by 5.
3. **Leading digits equal `gs1.companyPrefix`.** Reject otherwise:
   `400 { "error": "EAN_NOT_IN_COMPANY_PREFIX", "ean": "...", "expectedPrefix": "8905527" }`

This validates *company*, not SKU — a typo inside the item reference (16444 → 16544) passes the
prefix test, but the check digit catches it.

---

## 5. Write API

```
POST /api/v1/tags/write
{
  "ean":            "8905527164445",   // required; validated per §4.1
  "startSerial":    0,                 // 0 = local counter; >0 = use this, ignore local entirely
  "count":          1,
  "lock":           false,
  "accessPassword": "A1B2C3D4"         // REQUIRED iff lock=true; rejected otherwise
}
```

```
200 {
  "ean": "8905527164445", "gtin14": "08905527164445",
  "serialSource": "LOCAL",             // or "CALLER"
  "written": [ { "serial": 1073742891, "epc": "30361F8CDC100F004000042B", "tid": "E2801190..." } ],
  "failed": [],
  "localSerialNext": 1073742892
}
```

Filter value, antenna, verify and timeout are configuration, not parameters.

### 5.1 Serial allocation

- `startSerial > 0` → serials are `startSerial … startSerial+count-1`. **The local counter is
  neither read nor advanced.** The WMS owns that range entirely, including the risk of colliding
  with anything the reader allocated locally in the past. Per-site policy must make one of the two
  the authority; `serialSource` is logged on every write so a collision can be traced.
- `startSerial == 0` → serials come from the local counter — **one global counter for the reader**,
  not per-EAN. GS1 requires uniqueness within a GTIN, so a global counter is strictly stronger.
- Counter starts at 1. **Serial 0 is never written** — a blank or half-written tag reads as zeros.
- fsync the counter **before** the tag write. A crash then over-allocates (a harmless gap) rather
  than replaying (a duplicate).

### 5.2 Multi-site serial space

Locally allocated serials are `(reader.id << 30) | counter`:

| reader.id | serial range |
|---|---|
| 0 | 0 … 1,073,741,823 |
| 1 | 1,073,741,824 … 2,147,483,647 |
| 2 | 2,147,483,648 … 3,221,225,471 |
| 255 | 273,804,165,120 … 274,877,906,943 |

256 readers, 1,073,741,823 serials each, no coordination between sites. `reader.id` must be unique
across every reader that writes tags — treat it as part of commissioning the unit, and log it at
start-up so a misconfigured duplicate is visible. This applies **only** to local allocation;
caller-supplied serials bypass it entirely, which is another reason not to mix the two modes on one
site.

### 5.3 Locking

- `lock: true` → `accessPassword` mandatory, 8 hex chars, **rejected if zero**. A Gen2 lock with
  password `00000000` is not a lock — anyone can unlock and rewrite. Whoever holds that password
  owns the ability to ever correct a tag.
- `lock: false` → `accessPassword` omitted; reject it if supplied.
- **Never permalock.** Irreversible: a mis-encoded tag becomes scrap, and if it is already on
  saleable stock so is the article's tag.
- Order: write EPC → verify readback → set access password → lock EPC bank → confirm lock state.
  Any failure returns the tag in `failed` with the stage reached.

---

## 6. Read API

**One box, one read, one EAN** — `ean` is a scalar, not a list.

```
POST /api/v1/inventory
{
  "ean":           "8905527164445",    // optional; single EAN, never a list
  "expectedCount": 40,                 // optional but strongly recommended — see §7.2
  "tid":           false               // read the TID bank per tag. false = best performance.
}
```

Select scope, settle window, max duration and stop policy are configuration, not parameters.

### 6.1 `tid`

`tid: true` normally adds a TID bank read **per tag** — a separate air-interface transaction, with
the tag having to stay powered and singulated for it. On a 40-tag box that is 40 extra transactions,
and it would be the single most expensive thing the caller can switch on.

**The SDK has a much cheaper path, and it changes the advice.** The custom parameter
`tagcustomcmd/fastid` enables Impinj **FastID**: the tag returns its TID *together with* the EPC in
the same inventory operation, with no second transaction. With FastID on, the TID is delivered in
`TAGINFO.EmbededData` by default, or inline in `EpcId` if `tagcustomcmd/tagfmt_impfastid_raw` is
also set (leave that off — separate fields are easier to consume).

So the guidance splits:

- **Tags on Impinj (Monza) silicon** → set `fastId: true` in config, and `tid: true` on the call
  costs close to nothing. This is very likely the case for retail item tags, but confirm the tag
  silicon with whoever supplies them.
- **Any other silicon** → FastID is unavailable, `tid: true` means 40 extra transactions, and it
  belongs on a commissioning/audit endpoint rather than the throughput path.

Either way `tid: false` stays the default at the WMS, and when it is false the `tid` field is
omitted from every tag entry, including in `CONCISE` mode.

### 6.2 `responseMode`

**DETAILED** — everything:

```
200 {
  "ean": "8905527164445", "gtin14": "08905527164445",
  "matched": { "count": 40,
               "tags": [ { "epc": "30361F8CDC100F0000000413", "tid": "E2801190A50300481234ABCD",
                           "serial": 1043, "rssi": -47, "reads": 12, "firstSeenMs": 214 } ] },
  "unexpected":  [ { "epc": "...", "ean": "8905527168207", "serial": 7 } ],
  "undecodable": [ { "epc": "AABBCC...", "reason": "header 0xAA is not SGTIN-96" } ],
  "totalUnique": 41, "expectedCount": 40, "complete": true,
  "stopReason": "COUNT_REACHED",       // or SETTLED, or TIMEOUT
  "durationMs": 1830
}
```

**CONCISE** — tags carry only `epc` and `tid`; `unexpected`, `totalUnique` and `stopReason` are
omitted:

```
200 {
  "ean": "8905527164445", "gtin14": "08905527164445",
  "matched": { "count": 40,
               "tags": [ { "epc": "30361F8CDC100F0000000413",
                           "tid": "E2801190A50300481234ABCD" } ] },
  "undecodable": [ { "epc": "AABBCC...", "reason": "header 0xAA is not SGTIN-96" } ],
  "expectedCount": 40, "complete": true,
  "durationMs": 1830
}
```

One thing to be aware of rather than to change: in `CONCISE` mode a wrong-SKU article in the box is
no longer visible in the response — it still replies, is still decoded, and is still written to the
server log, but the WMS will not see it. `complete: true` with `count: 40` can therefore coexist
with a picking error. If that matters operationally, either run `DETAILED` or have someone watch the
server-side log for non-empty `unexpected`.

`ean` stays optional in both modes — a damaged box barcode must not take the tunnel down, and
diagnostics need "read whatever is there". A wrong or absent EAN never causes tags to be discarded
internally; it only changes what is reported.

---

## 7. Read time — where the seconds actually go

All timing figures below are arithmetic from the Gen2 spec, **not measurement**. §7.10 is how to
find out which lever is actually binding on your hardware.

### 7.1 Session and target

**There is no S10.** Gen2 defines exactly four sessions — S0, S1, S2, S3 — and the number is an
*index*, not a duration. What each one gives you is a persistence time for the tag's inventoried
flag, fixed by the standard, not configurable:

| Session | Flag persistence while the tag is powered | After the tag loses power |
|---|---|---|
| S0 | indefinite | **none** — resets immediately |
| S1 | 500 ms – 5 s (self-decays *even while powered*) | 500 ms – 5 s |
| S2 | indefinite | **≥ 2 s** (nominal minimum) |
| S3 | indefinite | ≥ 2 s |

So you cannot ask for "quiet for 10 seconds" at the protocol level. What you can have:

- **While the box is in the field and the carrier is on, S2 already gives you indefinite
  persistence.** A tag that has replied stays quiet for the whole pass. This is the property that
  makes the read converge — each round surfaces only *unread* tags and the population drains
  monotonically, instead of the same 35 tags replying forever while the last 5 stay buried in
  collisions. This is the biggest algorithmic lever in the whole document.
- **Once the box leaves the field you are only guaranteed ≥2 s.** Real silicon usually holds far
  longer, but it is not guaranteed and must not be designed against.
- **If you want a deterministic 10-second suppression, do it in the application**, not the
  protocol: a seen-EPC cache with a 10 s TTL. Deterministic, testable on the CM4 without a reader,
  and immune to tag-silicon variance. That is the right way to get what you were asking for.

#### 7.1.1 S2 versus S3 — asked directly

**At the protocol level they are functionally identical.** Same persistence rules, same behaviour,
same everything in the table above. S3 is not "more persistent than S2".

What they are is *independent registers*. Every tag carries four separate inventoried flags, one per
session, and they do not interact. A tag can be in state B for S2 and simultaneously in state A for
S3. That is the entire point of having both.

So the reason to care is **coexistence**. Two readers — or two processes on one reader — can
inventory the same tag population without interfering, provided each uses its own session. Reader
one works S2 and drains its view; reader two works S3 and drains its own; neither silences tags for
the other. If both used S2, the first reader to see a tag would hide it from the second, and the
second reader would report a half-empty box with no obvious cause.

Concretely for this installation: **use S2, and hold S3 in reserve.** The moment there is an entry
tunnel and an exit tunnel whose fields overlap even slightly, or a second reader added to one
tunnel, the second one goes on S3 and the problem never arises. Record the session assignment
alongside `reader.id` as part of commissioning.

(The meaningful distinctions are elsewhere in the table: S0 has no persistence at all once the tag
is unpowered, and S1 self-decays on a 500 ms–5 s timer *even while powered*, which makes it the only
session where a tag can start replying again mid-window without you doing anything.)

**Target stays at A.** As flagged at the top of this file: tags power up with the inventoried flag
at A, so Target A sees fresh tags and Target B does not. Alternating per box would mean every second
box reads as nearly empty. Alternation is a technique for re-reading a *static* population; a
conveyor presents a fresh box each time, so it does not apply.

The case alternation was reaching for is **same-box retry** — after an incomplete read, that box's
tags are in B and will not answer Target A. Three ways out, in order of preference:

1. Let the carrier drop (it will anyway between boxes in `TRIGGERED` mode), wait out the ≥2 s
   persistence, re-read with Target A. Simple, always correct, costs 2 s.
2. Issue a **Select that sets the inventoried flag back to A** on the matching population, then
   re-read immediately. **CONFIRMED AVAILABLE IN THE SDK** — this is now the recommended path, not
   a hope. `SELData` carries `seltarget` (`SelCmd_Target`) and `selaction` (`SelCmd_Action`), and
   `SelCmd_Target` includes `SelC_Inventoried_S0/S1/S2/S3` alongside `SL`. So:

   ```java
   SELData sd = ...;
   sd.seltarget   = SelCmd_Target.SelC_Inventoried_S2.value();   // act on the S2 flag
   sd.selaction   = SelCmd_Action.Mat_SLorA_NMat_no.value();     // match -> set A; no match -> nothing
   sd.selbank     = 1;                                            // EPC bank
   sd.seladdr     = 32;                                           // EPC data starts at bit 32
   sd.selbitslen  = 38;                                           // the company-prefix mask, §7.9
   sd.seldatas    = /* 30 36 1F 8C DC */;
   // wrap in CMDAA4DData, convert with SpecialStructDataConvert,
   // write to custom param "Gen2/selectcommandconfig" (>= 590-byte buffer)
   ```

   `Mat_SLorA_NMat_no` is documented as "Match: Set SL or A; No Match: No Action" — exactly "reset
   this box's tags to unread, touch nothing else". Retry cost drops from ~2 s to one Select.
3. Retry with Target B for that one read only. Works, but it makes target a piece of per-read state,
   which is exactly the complexity the "always A" rule is buying away. Last resort.

`reader.session` and `reader.target` are exposed in config so both can be swept on the bench. They
are testing knobs, not tuning knobs — S2/A is the answer unless measurement says otherwise.

### 7.2 Early exit on `expectedCount`

`stopOnCount: true` — stop the instant the count is reached, report `stopReason: "COUNT_REACHED"`.

`settleMs` then only ever applies when the count is not reached, or `expectedCount` was not
supplied, or `stopOnCount` is false. That is the right division: a settle-based stop can never
finish sooner than `settleMs` after the last tag, so with the 40th tag found at 900 ms and a 300 ms
settle you would return at 1200 ms — 300 ms of pure waiting on every single box. Removing that is
free.

`stopOnCount: false` remains available for completeness auditing, where you want the full picture of
what is in RF range rather than the fastest correct answer.

Note what `COUNT_REACHED` means and does not mean: "found what you told me to expect", not "the box
holds nothing else". A box with 40 correct articles plus one wrong-SKU article can stop at 40 before
ever seeing the 41st.

### 7.3 Trigger the RF, not the API call — and the thermal question

**Yes, keeping the module running while the antennas are de-energised is exactly the right design,
and it is what `rf.mode: TRIGGERED` means.** Three distinct states, and it matters that they are
distinct:

| State | Power / heat | Cost to leave |
|---|---|---|
| Module unpowered / host link closed | none | full initialisation: link open, region, power, session, Q, fast mode |
| **Module initialised, carrier OFF** | low — digital only | **just switch the carrier on** |
| Carrier ON, inventory running | high — this is essentially all of the thermal load | — |

At 30 dBm the transmit chain is where nearly all the heat comes from. Holding the middle state
between boxes gives you both things at once: **no configuration push in the critical path** (the
module is already set up and cached, §7.4) **and a low RF duty cycle** (roughly 2 s of carrier per
box; at one box every 20 s that is a 10% duty cycle, thermally very comfortable compared with
transmitting continuously).

It also has a protocol benefit that falls out for free: with the carrier off between boxes, the
previous box's tags lose power and their S2 flags decay back to A. The next box always starts from a
clean slate, which is precisely what the always-Target-A design wants.

**The SDK supports this design directly, with working reference code.** Three findings:

- **`BackReadOption.IsGPITrigger` + `BackReadOption.GpiTrigger`** put the trigger inside the module:
  a GPI input starts and stops asynchronous inventory with **no host round-trip at all**. The vendor
  demo `demos/JniMoudleAPItest/src/demo/trigger/maintest_trigger.java` is a working example, using
  `GpiTrigger_Type.GPITRIGGER_TRI1START_TRI2STOP` — photo-eye 1 starts the read, photo-eye 2 stops
  it. That is precisely a tunnel. `GPITRIGGER_TRI1ORTRI2START_TIMEOUTSTOP` with `StopTriggerTimeout`
  is the single-sensor variant. Start from that demo rather than from scratch.
- **`BackReadOption.FastReadDutyRation`** is a micro duty cycle *inside* the inventory window — the
  proportion of the window spent in standby (0–10 → ×5%; on Ex-chip readers 11–15 → 55/60/70/80/90%).
  Plus the custom parameter `Reader/dutycycle` (inventory time before duty cycle, and base time).
  **Keep this at 0 for a box read.** Standby inside the window is heat management that directly
  slows down the read you are trying to speed up. The trigger already gives you a ~10% macro duty
  cycle; taking heat out of the window as well is paying twice.
- **`Reader/powermode`** (`0x00 FULL`, `0x01 MIN_SAVING`, `0x02 MED_SAVING`, `0x03 MAX_SAVING`) and
  `MTR_PARAM_POWERSAVE_MODE` (levels 0–3) give a between-boxes idle state. Worth using, but measure
  the FULL-restore transition — if it costs more than the heat it saves, drop it.

Two SDK power knobs that look relevant and are **not**: `MTR_PARAM_TRANSMIT_MODE` (high-performance
vs low-power) is documented as m5e-series only, and `MTR_PARAM_TAG_SEARCH_MODE` (high-speed
inventory) as m6e-series only. Neither applies to the E710. Do not build against them.

**And the thermal question can now be answered with data rather than arithmetic.** CC33 /
`MODUSPARMS` with `CMD=0x01` makes the module upload antenna connection status, per-antenna VSWR
**and module temperature every time the power amplifier is enabled** — i.e. once per box, for free,
in the normal read path. `MTR_PARAM_RF_TEMPERATURE` reads it on demand as well. Log it per box and
plot it across a full shift: that curve, not this document, settles whether `TRIGGERED` at 30 dBm is
thermally comfortable in the actual enclosure.

This supersedes the earlier suggestion of running inventory continuously. Continuous inventory
solved the start-up-latency problem but paid for it in heat; trigger-driven solves both, because the
trigger (photo-eye / motion sensor) fires when the box arrives — *before* the WMS's HTTP call lands —
so the read window is defined by the box, not by network timing. `carrierOffDelayMs` keeps the
carrier up briefly after the trigger clears so a trailing straggler is not cut off.

**On module start time: I do not have a figure for the SIM7500 and will not invent one.** What I can
say is which operations to time, because they differ by orders of magnitude and only one of them is
in the critical path if this is designed correctly:

| Operation | Expected order | In critical path? |
|---|---|---|
| Host link open + module handshake | tens–hundreds of ms | no — once at start-up |
| Region / power / session / Q / fast-mode set | tens of ms each, and several require inventory stopped | no — once at start-up, then cached |
| Carrier on → first Query | small; RF settling is sub-ms, the round start is microseconds | **yes** |
| Carrier off | negligible | no |

One SDK detail sharpens this: there is a **carrier-wave test primitive** — custom parameter with
`ParamName = "0"` and first byte `0x01`, taking enable/disable + antenna + power + frequency. It is
a test/certification facility rather than the operational path, but it is exactly the instrument for
timing carrier-up in isolation from inventory start.

Measure them on the CM4 with a microbenchmark that times each call in isolation — that is a
half-hour job and it settles the whole architecture. If "carrier on → first tag read" turns out to be
expensive on this module (some designs re-run a calibration on carrier-up), then `TRIGGERED` needs
`carrierOffDelayMs` raised so the carrier stays up across a run of boxes, and the thermal budget has
to be recomputed. That is the one measurement that could change this section's conclusion.

Also worth confirming for `RG_IN`: whether the Indian 865–867 MHz regime imposes its own channel
dwell or duty limits on a continuously transmitting reader. If it does, `TRIGGERED` is not just
thermally better, it is the compliant option.

### 7.4 Keep the module warm

`region`, `powerDbm`, `session`, `initialQ` and `fastMode` are pushed **once at start-up** and
thereafter served from an in-memory cache. Nothing is re-pushed per call. Several of them require
inventory to be stopped and restarted, so pushing per call would put a stop/start cycle in the
critical path of every box.

Implementation: a `ModuleConfigCache` holding the last-applied values, with a single
`applyIfChanged()` entry point. In steady state a box read pushes nothing. Log at start-up what was
actually applied, so a config drift between the file and the module is visible.

### 7.5 EPC only in the inventory path

No TID and no user-memory read during inventory unless `tid: true` was explicitly requested (§6.1).

### 7.6 Fast mode — what it actually changes

Fast mode is not a single switch labelled "go faster"; it selects the module's **RF mode**, which is
a bundle of three air-interface parameters:

- **Tari** — the reader→tag symbol period. Shorter Tari = faster commands downlink.
- **BLF (backscatter link frequency)** — the tag→reader subcarrier rate, typically 40–640 kHz.
- **Encoding** — FM0, or Miller with M = 2, 4, or 8. Miller-M spreads each bit over M subcarrier
  cycles, so Miller-8 transmits at one eighth the rate of FM0 at the same BLF.

The trade is direct and physical. FM0 at a high BLF moves bits fastest but gives the receiver the
least energy per bit, so it has the **worst sensitivity, shortest range, and least tolerance of
interference and multipath**. Miller-8 at a low BLF is the opposite: slow, but it recovers tags that
FM0 simply cannot hear, and it is what dense-reader environments use to coexist.

What that costs in time, per tag, for a 96-bit EPC (PC + EPC + CRC = 128 bits backscattered, plus
the Query/RN16/ACK exchange and turnaround times):

| RF mode | EPC reply | Per tag | 40 tags |
|---|---|---|---|
| FM0 @ 640 kHz (fast) | 0.21 ms | ~1.6 ms | **~64 ms** |
| Miller-2 @ 320 kHz | 0.86 ms | ~2.4 ms | ~95 ms |
| Miller-4 @ 250 kHz | 2.21 ms | ~4.0 ms | ~159 ms |
| Miller-8 @ 256 kHz (robust) | 4.31 ms | ~6.5 ms | ~259 ms |

Collisions add on top — a loaded round typically runs 1.5–2× the collision-free figure.

So across the full range the *pure airtime* difference for one box is roughly 200 ms. Against a
5-second budget that is 4%, which leads to the non-obvious conclusion:

> **The fastest RF mode is not always the fastest box read.** If a robust mode finds all 40 tags at
> 1.2 s and a fast mode finds 38 at 0.9 s and then runs to `maxDurationMs` waiting for the last two,
> the "slow" mode is four times faster in wall-clock and the "fast" mode does not even return a
> correct answer. Airtime per tag is a small term; *whether you have to wait for stragglers* is a
> large one.

Which means: pick the fastest mode **that still finds every tag every time**, and verify that with
the discovery curve, not with a spec sheet. A tunnel is a short-range, RF-controlled, high-tag-count
environment, which argues for the fast end — but the box's far corner, tag orientation, and liquid
or metal content in the articles all push back, and only measurement settles it.

**What the SDK actually exposes.** `MTR_PARAM_POTL_GEN2_TAGENCODING` takes values from the
`Reader.RFMODE` enum, and the low four are exactly the Gen2 encodings: `FM0`=0, `M2`=1, `M4`=2,
`M8`=3. Above those sit R2000 profiles (0x10–0x15) and a long list of E-series RF-mode profiles
(`RFM_1_EX_SFM`=101, `RFM_3_EX_SFM`=103, `RFM_11_EX_SFM`=111, `RFM_103_EX`=203, `RFM_120_EX`=220 and
others). The docs list 203, 111, 220, 101, 45, 115, 112, 103, 105, 107, 113 as the valid E-series
set — so on the E710 you are picking a *profile*, and FM0/M2/M4/M8 are the portable way to think
about what those profiles are doing.

**One hard constraint, straight from the vendor docs** (`MTR_PARAM_POTL_GEN2_BLF`): BLF 640 kHz is
valid *only* with FM0; Miller encodings are restricted to BLF 250. Encoding and link frequency are
not independent knobs, which is why the §7.6 table pairs them the way it does. (`_BLF` itself is
marked Deprecated/Reserved, so the pairing is enforced by the module, not by you.)

**Ex10 fast mode is configured through `Reader/Ex10fastmode`** — a 22-byte payload: mode (1 = Ex
fast, 0 = normal), a fixed `20`, then a **scenario** byte 0–5. Scenarios 0/2/4 are documented as
*dense* tag scenarios and 1/3/5 as *sparse*; each selects a different set of RFMODEs that the module
then **auto-switches between internally** (e.g. "103/…/103/…", or the 4124/…/4323/… set, or all of
them at scenario 4/5). Forty tags in a box is unambiguously dense → start at scenario 0, and try 4
to let the module range over every set.

This matters for the section above: **in Ex10 fast mode you do not pick an RF mode at all — the
module cycles them for you.** So the FM0-vs-Miller decision only bites when `fastMode: NONE`. The
real bench question is narrower than it looked: Ex10 scenario 0 vs scenario 4 vs Impinj fast mode vs
a hand-picked static encoding, judged on "finds all 40, every time, fastest".

The Impinj path is separate — `IMPINJ_FASTPARMS` via `gen2op/cc_33_cmd` (CC33 function 4), with
`CMD` selecting AUTOSET mode (`0x11`), an Impinj inventory mode ID (`0x12`), or mode+fast-mode
(`0x13`), and `0x00` to disable. Per the project notes the two are **mutually exclusive and sticky**:
the code must explicitly clear the other whenever `fastMode` changes — and the vendor adds a
specific warning that when disabling CC33 you must first set `MODUSPARMS`/`IMPINJ_FASTPARMS` `CMD`
to 0 before resetting the parameter, or the module is left in an inconsistent state.

One more Impinj feature worth sweeping while you are in here: **TagFocus**
(`tagcustomcmd/tagfocus`, 1 byte enable/disable). TagFocus makes an Impinj tag hold its S1 flag in
B rather than letting it self-decay — S1 with the drain behaviour of S2, without S2's inter-box
carryover. Given the vendor recommends S1 around this tag count (§7.1) and we recommend S2, TagFocus
is precisely the third option that might beat both. It needs Impinj silicon, same as FastID.

### 7.7 Initial Q

`initialQ: 6` — 2^6 = 64 slots, sized for ~40 tags. Too low and the first rounds are all collisions;
too high and they are all empty slots. The E710 adjusts Q dynamically, but the **initial** value sets
how bad the first rounds are, and with only a few hundred milliseconds of window the first rounds
*are* most of the window.

### 7.8 Antenna dwell

Two antennas, `dwellMs: 60` recommended. Short dwells and many cycles beat long dwells: while you
are parked on antenna 1, the tag only antenna 2 can hear is not being read at all. With 60 ms dwells
a 1.2 s read gives each antenna ten separate looks at the box as it moves through — which matters,
because the box's position changes and a tag hidden at one moment may be visible 200 ms later.
Below about 30 ms the switching overhead starts to eat the gain.

**Serious caveat found in the SDK docs: this may not be settable on RG_IN.** The parameter exists —
`MTR_PARAM_RF_HOPANTTIME`, "the antenna dwell time during inventory … the maximum working time per
antenna, in milliseconds" — but the note attached to it reads: *"When initialized to the China
region, the default is 0, internally using 4000 (i.e. 4 seconds), modifiable but not permanently
savable. When initialized to other regions, the default is 0, internally using 4 seconds, not
modifiable."* The documented alternative — CC33 / `MODUSPARMS` `CMD=0x02`, "configure work time for
each antenna; jump to next antenna when work time expires" — carries the same restriction: *"Only
available in China certification region."* Per-antenna Q (`CMD=0x03`) is China-only too.

Read carefully, 4000 ms is a **ceiling**, not a fixed dwell — the main description says "by default
the switching time between multiple antennas is not fixed", which implies the module switches
dynamically, probably per inventory round. So the practical dwell may already be short. But we would
not control it, and a 4-second ceiling on a 5-second budget is not something to discover in
production.

**This is now the highest-priority hardware test in the document**, ahead of the filter question.
It is also easy to answer: enable the discovery curve, log the antenna that produced each first
sighting, and look at how the two antennas interleave. Tight alternation means the module is
switching fast and the config value is moot; long single-antenna blocks mean dwell is a real problem
and the mitigations are physical (antenna placement and overlap) rather than configured.

### 7.9 Select mask — and what SKU-scope filtering would actually save

Set `MTR_PARAM_TAG_FILTER` on bank `EPC`, start address **bit 32** (CRC16 at 0, PC16 at 16, EPC data
from 32). The vendor's own worked example uses exactly `bank = 1`, `startaddr = 32` — so the bit-32
offset asserted earlier in this document is confirmed by the SDK docs, not inferred.

| Scope | Length | Mask | Selects |
|---|---|---|---|
| **COMPANY (default)** | 38 bits | `30361F8CDC` (first 38 bits significant) | any SGTIN-96, filter 1, partition 5, prefix 8905527 |
| SKU 8905527164445 | 58 bits | `30361F8CDC100F00` | that SKU only |
| SKU 8905527168207 | 58 bits | `30361F8CDC106D00` | that SKU only |

**Asked directly: for a 40-tag box, what does SKU-scope filtering save over company-scope? In the
box itself, exactly nothing.** Both masks match all 40 target tags identically — filtering cannot
speed up reading tags that match the filter. The *only* difference between the two scopes is which
**other Reliance SKUs** in RF range get suppressed. Non-Reliance tags are already gone under either.

So the saving is:

```
saving  =  (number of OTHER-Reliance-SKU tags in RF range)  ×  (per-tag singulation time)
```

With per-tag time from the §7.6 table, that gives:

| Other-Reliance tags in range | Saving (fast mode) | Saving (robust mode) |
|---|---|---|
| 0 | 0 ms | 0 ms |
| 10 | ~16 ms | ~65 ms |
| 40 (a whole adjacent box) | ~64 ms | ~260 ms |
| 100 (racking behind the tunnel) | ~160 ms | ~650 ms |

The realistic figure for a tunnel is the middle of that: **tens to low hundreds of milliseconds, and
only when a substantial population of other Reliance stock sits in RF range.** Against a 5-second
budget, 2–5%. Compare that with §7.1 (session) and §7.2 (early exit), which are worth whole seconds.

And it is not free. SKU-scope filtering makes a wrong-SKU Reliance article in the box *physically
unable to reply* — not "reported as unexpected", but invisible, at the air interface, with no trace
anywhere. You would be trading a few percent of read time for the ability to detect picking errors.
In a warehouse that is the wrong trade, which is why `selectScope: COMPANY` is the default.

`selectScope: SKU` is exposed anyway, because you asked for the number and the honest answer is that
the number depends entirely on what else is in RF range at *that site* — which nobody can know from
here. Measure it: run 50 boxes each way, compare the `durationMs` distributions. If the site turns
out to have heavy adjacent-SKU RF load and the saving is real and large, it becomes a genuine
decision with a known cost rather than a guess.

The filter is **sticky module state — always clear it** (`ParamSet(MTR_PARAM_TAG_FILTER, null)`).
If `ean` is absent from the call, no Select is applied.

#### Two mechanisms exist in the SDK, and the distinction resolves the open question

| | `MTR_PARAM_TAG_FILTER` | `Gen2/selectcommandconfig` |
|---|---|---|
| Structure | `TagFilter_ST` {bank, startaddr (bits), flen, fdata, isInvert} | `CMDAA4DData` → `SELData[]` |
| Fields | match criteria only | match criteria **plus `seltarget` and `selaction`** |
| Rules | 1, or up to 16 via `MTR_PARAM_TAG_MULTISELECTORS` | up to 12 per struct, chainable |
| Cleared by | `ParamSet(…, null)` | set CMD to 0 |
| Docs call it | "single-rule filter for tags" | "**Select** flags to tag command configuration … writes Select marks to tags to implement tag search rules, such as filtering or **silencing** tags" |

The second is unambiguously the real Gen2 Select: it carries target and action fields, it pairs with
`Gen2/querysel` (search flag 0 = all tags, 2 = tags marked `~SL`, 3 = tags marked `SL`), and the docs
describe it as *writing marks to tags* rather than filtering results. `TagFilter_ST` has no target or
action field at all — consistent with a simpler match-only path, but the docs never say whether the
module turns it into an on-air Select or applies it after the fact.

So the honest status, much narrower than before: **for filtering, use `TAG_FILTER` and let the
measurement answer the question** — if it post-filters, the `durationMs` distribution will not move
when foreign tags are present, and that *is* the experiment. **For flag manipulation, use
`SELECT_COMMAND`**, which is definitively a Select and is what §7.1's retry path needs. The
`selectMechanism` config key exists so both can be tried without a rebuild.

Worth pairing with the RSSI floor (`Reader/rssifilter`, config `rssiFilterDbm`): racking and
adjacent-box tags are *further away* than the box in the tunnel, so an RSSI threshold suppresses them
regardless of EAN, inside the module, at no airtime cost. For the "foreign tags in range" problem
that is very likely a better tool than either Select path — and unlike SKU-scope filtering it does
not blind you to a wrong-SKU article sitting in the box you are actually reading.

### 7.10 The discovery curve

**How to get it: `diagnostics.discoveryCurve.enabled`, and the measurement itself is free.**

`firstSeenMs` is already tracked for every EPC — it is a `putIfAbsent` with a timestamp on the
dedupe map you need regardless. So the flag does not gate the *measurement*, only the **file I/O**.
That distinction matters: it means production always has the data in memory, and turning the flag on
never changes read timing in a way that would invalidate what you are measuring.

When enabled, each read window writes one JSONL file:

```
/var/log/intelli/curves/2026-08-22T14-03-11.284Z-box.jsonl
{"t":0,"event":"carrier_on"}
{"t":118,"event":"first_tag"}
{"t":118,"epc":"30361F8CDC100F0000000001","antenna":1,"rssi":-42}
{"t":141,"epc":"30361F8CDC100F0000000002","antenna":1,"rssi":-51}
...
{"t":1204,"epc":"30361F8CDC100F0000000028","antenna":2,"rssi":-63}
{"t":1204,"event":"stop","reason":"COUNT_REACHED","unique":40,"expected":40}
```

One line per **first** sighting, so the file is 40-odd lines per box, not thousands. `retainFiles`
caps the directory. Plot unique-EPC-count against `t` and the shape names the binding constraint:

| Curve shape | Diagnosis | Fix |
|---|---|---|
| Rises fast, then a long flat tail missing 2–3 tags | RF coverage / tag orientation — not protocol | antenna placement, power, `dwellMs` |
| Rises slowly and evenly throughout | collisions | `initialQ`, and confirm `session: S2` |
| Reaches 40 fast, response returns hundreds of ms later | paying the settle window | §7.2 — `stopOnCount` |
| Flat for 200–400 ms before the first tag | start-up cost in the critical path | §7.3, §7.4 |
| Tags cluster by antenna, one antenna contributing little | coverage or a cabling/VSWR fault | check VSWR per antenna |

Even with the flag off, always log `stopReason` and `durationMs` per read. Once boxes are flowing,
the distribution of those two fields is the honest answer to "can we do this in 5 seconds" — and it
is the number to quote to Reliance, not a bench figure.

Worth adding alongside: an in-memory rolling histogram of `durationMs` and a counter per
`stopReason`, exposed on the Spring Actuator endpoint. That gives you the production picture with no
file I/O at all, which is what you want running permanently.

---

## 8. Where the code lives

```java
public record Sgtin96(int filter, int partition, String companyPrefix,
                      String itemReference, long serial) {
    public String gtin14()  { ... }   // recompute check digit
    public String ean13()   { return gtin14().substring(1); }
    public String toEpcHex(){ ... }
    public String toPureIdentityUri() { ... }
    public static Sgtin96 fromEpcHex(String hex) { ... }        // throws on bad header
    public static Sgtin96 forEan(String ean, int cpLen, int filter, long serial) { ... }
    public static byte[] selectMask(String ean, int cpLen, int filter, SelectScope scope) { ... }
}
```

**intelli-rfid-core**, not the tunnel app — reader-test needs it to write a valid tag during bench
acceptance, and wayside will want it if rail assets ever get GS1 identities. Pure logic, no hardware
dependency, so it is fully unit-testable here:

- Round-trip every GTIN × boundary serial (1, 42, 2^38−1).
- Assert the §3 vectors and the §7.9 masks byte-for-byte.
- Assert `(reader.id << 30) | counter` lands in the §5.2 range for ids 0, 1, 255.
- Assert a partition-6 encode of the same EAN decodes to the same GTIN but a **different** EPC —
  that test documents why the prefix length is config and not a guess.
- Reject: bad check digit, wrong company prefix, serial 0, serial ≥ 2^30 for local allocation,
  non-`0x30` header, `accessPassword` present with `lock: false`, zero password with `lock: true`.

`SerialAllocator` is a separate small class — `allocate(count)`, fsync-before-return, reader-id
banding, crash-recovery test — deliberately *not* told about caller-supplied serials, per §5.1.

---

## 9. Still open with Reliance

1. **Serial authority per site** — WMS supplies ranges, or the reader allocates. Pick one.
2. **Lock policy** and who holds the access password.
3. **The box's own tag.** The WMS passes the EAN from the barcode, so the box's RFID tag is not
   needed for identification — but the tunnel will still *see* it. If it is an SSCC (header `0x31`)
   it lands in `undecodable` today, which is wrong; either decode SSCC too, or classify by header as
   "logistic unit tag, not counted". Note it will **not** match the SGTIN Select mask at either
   scope, so with `selectByEan: true` the box tag is suppressed entirely.
4. **The read-time target as a number and a percentile** — "5 seconds" for what fraction of boxes,
   and what happens on the tail: retry, alarm, manual check?

## 10. What the vendor SDK already answers

Reviewed `API-linux-java-v260721/` — `docs_en/doc_API_J_html` (generated API reference) and the demo
sources. Findings below are from the vendor's documentation and example code; **nothing here has
been run against a module.**

| # | Question from the previous draft | Status | What the SDK says |
|---|---|---|---|
| 1 | Is `MTR_PARAM_TAG_FILTER` a true Gen2 Select or a firmware post-filter? | **Partly answered** | Two separate mechanisms exist. `Gen2/selectcommandconfig` (`CMDAA4DData`/`SELData`) is definitively a Gen2 Select — it has `seltarget`/`selaction` and the docs speak of "writing Select marks to tags … filtering or silencing". `TagFilter_ST` is described only as a "single-rule filter" with no target/action; whether the module renders it on air is still not stated. See §7.9. |
| 2 | Does the SDK expose Select *action* control (set inventoried → A)? | **ANSWERED — YES** | `SelCmd_Target` includes `SelC_Inventoried_S0/S1/S2/S3` and `SL`; `SelCmd_Action.Mat_SLorA_NMat_no` = "Match: Set SL or A; No Match: No Action". Same-box retry drops from ~2 s to one Select. Code sketch in §7.1. |
| 3 | Carrier-on → first-tag latency; is `TRIGGERED` viable? | **Design confirmed, number still unmeasured** | `BackReadOption.IsGPITrigger`/`GpiTrigger` run start/stop **inside the module** with no host round-trip, and `demos/JniMoudleAPItest/src/demo/trigger/maintest_trigger.java` is a working example using `GPITRIGGER_TRI1START_TRI2STOP` — literally the tunnel pattern. A carrier-wave test primitive (custom param, name `"0"`, first byte `0x01`) exists for timing carrier-up in isolation. §7.3. |
| 4 | Ex10 vs Impinj fast mode; which RF mode finds all 40? | **Question reshaped** | `Reader/Ex10fastmode` takes a **scenario** byte, 0–5, where 0/2/4 are *dense* and 1/3/5 *sparse*, and the module then **auto-switches RFMODE internally**. So in Ex10 mode you do not pick an encoding at all. `MTR_PARAM_POTL_GEN2_TAGENCODING` (`RFMODE`: FM0=0, M2=1, M4=2, M8=3, plus E-series profiles) only applies with `fastMode: NONE`. Hard constraint: BLF 640 kHz is FM0-only; Miller forces 250. §7.6. |
| 5 | `RG_IN` regulatory duty/dwell limits? | **ANSWERED — nothing for us to do** | `Region_Conf.RG_IN = 0x04` exists. Set once via `Ex/initregion`; for a non-China certification region the band "is the certification region and cannot be changed". Hop time is 500 ms for non-FCC and "determined by the module itself and cannot be modified". `MTR_PARAM_RF_LBT_ENABLE` is marked **Deprecated, no longer in use**. Compliance is the module's job and we cannot break it. |

### 10.1 Things found that were not on the list — and one is a problem

**A new top-priority risk: antenna dwell may not be settable on RG_IN.** `MTR_PARAM_RF_HOPANTTIME`
is documented as modifiable "only … China region"; for other regions it is "internally using 4
seconds, **not modifiable**". The CC33 per-antenna work-time route (`MODUSPARMS CMD=0x02`) and
per-antenna Q (`CMD=0x03`) are both China-region only as well. 4000 ms is a ceiling rather than a
fixed dwell, so the real switching cadence may be fine — but on a 5-second budget this is not
something to find out in production. **This now outranks question 1 as the first thing to test.**
§7.8 has the test: enable the discovery curve, attribute each first sighting to an antenna, and look
at how the two interleave.

**Genuinely useful things the SDK offers that the design should now use:**

- **FastID** (`tagcustomcmd/fastid`) — TID returned *with* the EPC in one operation, no per-tag
  second transaction. This changes the cost of `tid: true` from "the most expensive thing the caller
  can do" to nearly free, on Impinj silicon. §6.1 is rewritten around it.
- **Module telemetry via CC33** (`MODUSPARMS CMD=0x01`) — antenna connection status, per-antenna
  VSWR **and module temperature**, uploaded every time the power amplifier is enabled. The thermal
  question in §7.3 becomes a measurement instead of an argument. `MTR_PARAM_RF_TEMPERATURE` reads it
  on demand too.
- **`Reader/rssifilter`** — a module-internal RSSI floor. Probably a better foreign-tag suppressor
  than any Select, since racking and adjacent-box tags are simply further away, and it costs no
  airtime. Added to config as `rssiFilterDbm`. §7.9.
- **TagFocus** (`tagcustomcmd/tagfocus`) — Impinj's "hold S1 in B" feature: the drain behaviour of S2
  without S2's inter-box carryover. Given the vendor recommends S1 at this tag count and we recommend
  S2, this is the third option that may beat both. §7.6.
- **`Reader/isWriteReadFlag`** — makes `WriteTagEpcEx` read back automatically after writing, which
  is exactly `write.verifyAfterWrite`. Needs an oversized buffer and must be disabled afterwards.
- **Duty-cycle and power controls** — `BackReadOption.FastReadDutyRation`, `Reader/dutycycle`,
  `Reader/powermode`, `MTR_PARAM_POWERSAVE_MODE`. Keep the in-window duty ratio at 0 and manage heat
  with the trigger instead; use the power modes only between boxes. §7.3.
- **Q encoding gotcha** — `ParamSet(MTR_PARAM_POTL_GEN2_Q, {6})` sets a **static** Q. Dynamic Q with
  an initial value of 6 is `{6 | -256}`; `{-1}` is fully automatic. Easy to get silently wrong.
- **Power units** — `MTR_PARAM_RF_ANTPOWER` and friends are in **centi-dBm**: 30 dBm is `3000`.
- **`Reader/inv_fixed_rounds`** — fixed inventory rounds, or rounds × cycle time as a total timeout.
  A module-side alternative to `maxDurationMs`, worth comparing.
- Do **not** build against `MTR_PARAM_TRANSMIT_MODE` (m5e only) or `MTR_PARAM_TAG_SEARCH_MODE`
  (m6e only) — neither applies to the E710.
- A note that will matter during commissioning: `Reader/usermode` `0x81` is documented as requiring
  **a single antenna**. This installation has two, so that mode is unavailable to the tunnel.

### 10.2 Revised test order for the CM4

1. **Antenna dwell behaviour on RG_IN** — is switching actually fast, or are we stuck near 4 s?
2. `TagFilter_ST`: on-air Select or post-filter — answered by whether `durationMs` moves when
   foreign tags are present.
3. Carrier-on → first-tag latency, and the FULL↔power-save transition cost.
4. Session sweep S0 / S1 / S2 (+ TagFocus, + target `A->B`) at Q = 6 | -256, judged on the discovery
   curve rather than on throughput.
5. Ex10 scenario 0 vs 4 vs Impinj fast mode vs a static encoding — "finds all 40, every time,
   fastest".
6. Module temperature across a full shift in the real enclosure, from the CC33 telemetry.
