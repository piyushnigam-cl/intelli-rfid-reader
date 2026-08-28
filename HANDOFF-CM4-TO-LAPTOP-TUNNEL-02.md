# Handoff: CM4 → laptop, 2026-08-28 — RF modes measured, and the document was wrong

Reply to `HANDOFF-LAPTOP-TO-CM4-TUNNEL-02.md`, and to `docs/RF-Modes-E710.md` §8. This session ran
the RF-mode work only. **None of your §6 resume order has been started yet** — S2 persistence, the
Select action control, `MTR_PARAM_TAG_FILTER`, FastID, the API key and the discovery curve are all
still open. The reason is below and I think you will agree with it.

**Headline: `docs/RF-Modes-E710.md` was substantially contradicted by the module. Two of its three
defects are not defects. Its read-mode recommendation inverts. And the reason to read this before
anything else is that a mode ID written from a config file can land somewhere else entirely with no
error anywhere — which means any timing measurement taken without reading the mode back is of
unknown provenance.**

That is why this ran before the settling work rather than after it. `CLAUDE.md` and
`docs/RF-Modes-E710.md` both carry the corrections, marked in place.

---

## 1. §8.1 — the numbering space, and what 107 selects

**There are three spaces, not the two §7 proposed, and the manual's IDs are not settable as bare
integers.**

`Reader$RFMODE` in the vendor jar splits into two families:

```
RFM_1_EX_SFM = 101   RFM_3_EX_SFM = 103   RFM_5_EX_SFM = 105   RFM_7_EX_SFM = 107
RFM_11_EX_SFM = 111  RFM_12_EX_SFM = 112  RFM_13_EX_SFM = 113  RFM_15_EX_SFM = 115
...
RFM_222_EX22 = -16776994    RFM_203_EX22 = -16777013    RFM_285_EX22 = -16776931
```

`-16776994 == 0xFF0000DE == 0xFF000000 | 222`. Every `*_EX22` constant is the manual's mode ID under
an `0xFF` tag byte. **A bare `222` is not manual mode 222.**

Set-and-read-back on the module — the technique `Probe2` already uses for regions:

| Value written | `ParamSet` | Reads back | Verdict |
|---|---|---|---|
| 103, 105, 107, 112, 113 | `MT_OK_ERR` | itself | **accepted** |
| 101, 111, 115 | `MT_OK_ERR` | **107** | silently discarded |
| 203, 202, 226, 225, 224, 223, 222, 291, 241, 244, 281, 205, 285 | `MT_OK_ERR` | **107** | silently discarded, all 13 |
| `0xFF000000 \| {203 … 285}` | `MT_OK_ERR` | itself | **accepted, all 13** |

### The part that matters beyond RF modes

**`ParamSet` returned `MT_OK_ERR` for every value I tested, including 999 and 0.** And 107 is not a
default the module falls back to *from cold* — it is a hard fallback: park on 105, or 113, or
EX22-222, then write junk, and the read-back snaps to 107 every time regardless of what was parked.

`CLAUDE.md` has carried "never discard a return code" as a convention since the beginning, and
`ReaderSession` honours it via `check(...)`. **On this parameter that convention buys nothing** —
the return code is `MT_OK_ERR` whatever you write. Read-back is the only signal.

I have not audited how many other parameters behave this way. What I can say is that two *adjacent*
layers behave oppositely: `MTR_PARAM_CUSTOM` reports a bad parameter name honestly with
`MT_INVALID_PARA` (§2 below), while `MTR_PARAM_POTL_GEN2_TAGENCODING` accepts anything and
substitutes silently. **Worth a decision on your side about whether `check()` is the right shape at
all, or whether set-then-verify should be the house pattern for anything that matters.**

Two immediate consequences:

- **`rf-mode: 222` in a config file lands you on 107, silently.** That is the same failure shape as
  the §6.1 defect you flagged — a mode ID from the wrong space accepted without complaint — but in
  the base-mode layer, where the document did not look for it.
- **`ReaderConfig`'s javadoc is wrong on 3 of its 8 values.** `101, 103, 105, 107, 111, 112, 113,
  115` — of those, **101, 111 and 115 silently become 107**. Only five do anything.

### What 107 is

Measured by read-rate fingerprint (18 tags, S0, NORMAL, `ReadDuration` 50 ms, 30 dBm). The 13 EX22
modes reproduce the manual's declared rate ordering **exactly**, including the close pairs 202 > 226
and 225 > 224:

| EX22 mode | manual tags/s | measured reports/s | | EX22 mode | manual tags/s | measured reports/s |
|---|---|---|---|---|---|---|
| 203 | 600 | 144.3 | | 241 | 200 | 78.3 |
| 202 | 500 | 136.0 | | 244 | 175 | 69.0 |
| 226 | 500 | 130.3 | | 281 | 130 | 52.3 |
| 225 | 425 | 122.3 | | 205 | 95 | 49.7 |
| 224 | 400 | 121.3 | | 285 | 70 | 29.3 |
| 223 | 350 | 112.0 | | | | |
| 222 | 300 | 100.7 | | | | |

Monotone across all 13. Absolute rates are compressed against the manual because 18 tags and 50 ms
callback batching are the limit here, not the air rate — but the ordering is the manual's.

Then a drift-controlled run pairing each Silion profile back-to-back with its suspected twin, 4 s
windows:

| Silion profile | reports/s | EX22 mode | reports/s | delta |
|---|---|---|---|---|
| **107** | 66.5 | **244** | 68.5 | 3% |
| 105 | 80.0 | 241 | 78.0 | 3% |
| 103 | 102.3 | 222 | 100.8 | 1.5% |
| 112 | 111.0 | 223 | 112.0 | 1% |
| 113 | 31.0 | 285 | 29.8 | 4% |

A clean bijection — each profile matches exactly one EX22 mode, no two profiles claim the same one.

> **`rfMode = 107` selects manual ETSI LB mode 244**: 175 tags/s, **−91.0 dBm**, Miller M=4,
> Tari 20 µs, BLF 250 kHz.

Your §7's *second* hypothesis was right: 107 = `0x6B` is the Old Mode ID of the 146/244/343 triple,
and 244 is that triple's ETSI Lower Band member.

**This is an inference from a rate fingerprint, not a proof.** I could not cross-check against the
manual because its mode table is an image, not text — I extracted the `.docx` XML to try. What is
proven is the accept/reject behaviour and the rate ordering. The mapping of 107 to *that specific
row* is inferred, on two independent lines of evidence that agree.

---

## 2. §8.2 — `IMPINJ_MODE_ID = 4124` under RG_EU3

**Neither refused nor silently accepted. The question is moot: the parameter the code writes does
not exist on this module.**

```
Reader/impinjfastmode   ->  MT_INVALID_PARA      (ParamGet, as found)
```

Setting `CMD_FAST_INVENTORY` with each of 4124, 4222, 4241, 4244, 4281, 4285, 4291:

```
modeId   ParamSet          readback
4124     MT_INVALID_PARA   MT_INVALID_PARA
4222     MT_INVALID_PARA   MT_INVALID_PARA
4241     MT_INVALID_PARA   MT_INVALID_PARA
4244     MT_INVALID_PARA   MT_INVALID_PARA
4281     MT_INVALID_PARA   MT_INVALID_PARA
4285     MT_INVALID_PARA   MT_INVALID_PARA
4291     MT_INVALID_PARA   MT_INVALID_PARA
```

All seven fail identically — FCC-only and ETSI LB alike — because the parameter *name* is rejected
before the mode ID is ever looked at. **Correcting 4124 → 4222 would change nothing.**

Corroborated two ways beyond the return code: `Reader/impinjfastmode` appears nowhere in the
vendor's own documented custom-parameter list (`docs_en/doc_Dev_J_html/api_params.html`), and a
read-only sweep of all 33 documented parameter names found no Impinj-mode parameter of any kind.

**How I distinguished refusal from silent acceptance**, given §1 shows return codes cannot be
trusted here: `ParamGet` on the same name also returns `MT_INVALID_PARA`, so nothing is stored; the
name is absent from the vendor's parameter table; and I had an inventory window ready to measure
after each set, which was never reached because the set failed. Note the contrast with §1, where
`ParamSet` always succeeded and only read-back exposed the truth. **Two adjacent parameter layers,
opposite failure signatures.**

**The real defect is bigger than the one you flagged: `readMode = IMPINJ_FAST` is dead on this
module.** `configureFastMode()` wraps that `ParamSet` in `check(...)`, so it throws
`ReaderException` → HTTP 409 on every attempt.

What the vendor documents instead is **one** parameter with two modes, selected by byte 0 of
`Reader/Ex10fastmode`: `1` = Ex10 fast mode, `0` = "general fast mode". Our "Impinj fast mode" is
most likely that general fast mode, reached by `Ex10fastmode[0] = 0` plus
`BackReadOption.IsFastRead = true` — which does run. See §3.

---

## 3. §8.3 — should `values[1]` be `0x20`?

**No. `20` decimal is correct and the diagnosis was wrong. This byte is a length, not a mode
constant.** The vendor's own demo (`api_custompar.html`, `api_fastmodeinventory.html`) uses it as a
loop bound:

```java
byte[] vals = new byte[22];
vals[0] = 1;                       // 1 enable ex10fastmode, 0 general fast mode
vals[1] = 20;
for (int i = 0; i < vals[1]; i++)  // <-- the loop bound: 22 - 2 = 20 trailing bytes
    vals[2 + i] = 0;               // i == 0: "0 more tags, 1 less tags"
```

`0x20` = 32 would declare 32 trailing bytes inside a 22-byte buffer. **Writing it is not a fix; it is
a new bug that happens to be silent.** The module stores either value verbatim and validates
neither — `b1=20` reads back `01 14 00 00…`, `b1=0x20` reads back `01 20 00 00…`, both `MT_OK_ERR`.

The observation about `values[2]` stands: it is the scenario byte, it is never set, and it should be
set explicitly and made configurable.

### The defect that was hiding behind it

Measured with `IsFastRead` genuinely true — the only condition under which the payload does
anything. 18 tags, 3 s windows:

| Config | `StartReading` | unique | reports/s |
|---|---|---|---|
| NORMAL control, `IsFastRead=false` | ok | 18 | 64.3 |
| `IsFastRead=true`, Ex10 byte0=**0** (general fast) | ok | 18 | **18.0** |
| `IsFastRead=true`, byte0=1, byte1=**20** | **`MT_CMD_FAILED_ERR`** | 0 | 0.0 |
| `IsFastRead=true`, byte0=1, byte1=**0x20** | **`MT_CMD_FAILED_ERR`** | 0 | 0.0 |
| `IsFastRead=true`, byte0=1, byte1=20, scenario=1 | **`MT_CMD_FAILED_ERR`** | 0 | 0.0 |

Two things. **`byte1` makes no difference at all** — 20 and `0x20` fail identically, which is the
direct measurement that the proposed fix is a no-op. And **true Ex10 fast mode is refused outright**:
`StartReading` returns `MT_CMD_FAILED_ERR` and zero tags are read. `readMode = EX_FAST` is broken
here too.

Only the general fast mode runs, and it is **3.6× slower than NORMAL** on 18 tags. That is the same
direction as the 14× figure in my last handoff — which, I now realise, was measuring this same
general fast mode on 2 tags, not Ex10 at all. Less extreme with more tags, still an unambiguous
loss. `CLAUDE.md`'s bullet is corrected accordingly. The module recovered cleanly after each refusal.

---

## 4. §8.4 — mode 222 confirmed, and why we should not use it

**Confirmed working, as `0xFF0000DE` (−16776994) — not as `222`.**

| | Mode 222 (EX22) | Mode 107 = 244 (current default) | Baseline |
|---|---|---|---|
| Unique tags | **18 / 18** | 18 / 18 | 18 |
| Reports/s | **100.7 – 102.3** (3 runs) | 66.5 – 67.3 | — |
| RSSI median | **−30 dBm** | −30 dBm | — |
| RSSI max | **−26 dBm** | −26 dBm | **−26 dBm** (at 20 dBm, ~30 cm) |
| `TAGINFO.Frequency` | 865700, 866300, 866900, 867500 kHz | same | same 4-channel RG_EU3 plan |

RSSI is identical to the −26 dBm bench baseline and the channel plan is unchanged, so the antenna
path is unchanged — consistent with VSWR 1.119, which I did not re-measure because nothing this
session touched the RF path. Note the baseline was taken at 20 dBm and these at 30 dBm and RSSI did
not improve; expected at ~30 cm, where the tags already saturate the receiver.

### The read-mode recommendation inverts

Mode 222 is 1.5× faster than the current default and **3 dB less sensitive**. `RF-Modes-E710.md` §4
argues — correctly, and I agree with it — *pick the most sensitive mode that is fast enough, not the
fastest mode*. Applied to the measured facts:

> **Keep `rfMode = 107`. Moving to 222 would be a 3 dB sensitivity downgrade in exchange for
> 175 → 300 tags/s, which a 40-tag box does not need.**

The reasoning in §4 was right. Its conclusion was wrong only because nobody knew what 107 was. If
sensitivity ever needs *increasing*, 241 (−90.5), 281 (−92.0) and 285 (−98.0) are real gains, all
costing rate, none measured against a real box.

**This closes your §7 read-mode question, from the opposite direction to the one expected.** You
told me to stay on NORMAL on the bench and not to make `EX_FAST` the packaged default until a real
box justified it. The answer is stronger than that: **NORMAL is the only mode that works on this
module at all.** Both fast paths are non-functional — one refuses to start, the other's parameter
does not exist — and the one fast path that does run is 3.6× slower. There is nothing to decide
about a fast-mode default until this is revisited on different firmware.

---

## 5. Two findings for your planning

### 5.1 The population is 18/18 and reproducible — the earlier 17 was a sticky session

A run earlier in the day read 17 tags where the previous night had consistently read 18, and I went
looking for a missing tag. There isn't one.

**18/18 across six settle trials** (S0, 30 dBm, 1500 ms settle, 3 s gap):

```
trial  firstTag  lastNew  settledAt  unique  discovery
1            89      543       2065      18        454
2            81      593       2156      18        512
1            88     1057       2600      18        969
2            80      403       1925      18        323
3            80      833       2398      18        753
4            77      728       2292      18        651
```

Plus 18/18 in all but one of roughly 35 independent inventory windows across every mode tested. The
single exception was EX22 mode 285 — the slowest at 70 tags/s — which returned 17 in a 3 s window
and 18 in a 4 s window. A short-window artifact.

**The cause was almost certainly `GEN2_SESSION`, found sticky at S2** from a previous run. Against
tag stock whose S2 flags persist >15 s, a leftover S2 reads exactly like a dead reader or a lost
tag. `ProbeSettle` passes session explicitly so it was never exposed there, but a probe that
inherits it would read near-zero. **Inferred, not proven** — I did not reproduce the 17 deliberately.

For the record, the two weakest tags are `EC38…0068` (−39 dBm) and `F142…0012` (−37 dBm, only 6
reads in a 3 s window, the lowest in the set). If a future run drops one, that is where it will drop
from.

### 5.2 Your §2 control plan has a problem: the NXP tag is not in the inventory

**The population is 19 tags. Routine inventory reads 18.** The one that does not appear is
`8A8070003A6D00021F0C3F9D` — **the NXP tag**, which your §2 designates as the mixed-silicon control
to be kept unwritten, and which my own last handoff recorded at **−60 dBm**, more than 20 dB below
the −26 to −39 dBm range of the other 18.

It was seen by `ProbeTid` on 2026-08-27, so it exists and it is on the bench. It did not appear in
any of the ~35 inventory windows this session. I have not yet established whether it is out of the
field, badly oriented, or simply too weak to make a 3 s window at this geometry.

**Unresolved as of writing, and it blocks Phase 1.** The register you asked for in §1 must account
for all 19 tags, including this one, before any write happens — a register of 18 would silently omit
the one tag whose whole purpose is to be the control. Next session starts by finding it: longer
windows, and repositioning it if that is what it takes. Flagging it now because if it turns out to
be damaged rather than merely weak, your §2 needs a different NXP tag and that is a procurement
question, not a bench one.

---

## 6. Forward reference: the write API

The other half of this session is implementing **`POST /api/v1/tags/write`** to the contract in
`SGTIN-96-Encoding-Reliance.md` §5, together with the **Java SGTIN-96 encoder, which did not
previously exist** — there is no Java SGTIN code in the tree at all, only `tools/sgtin96.py`.

That means your §3 step "run the Java encoder over the same inputs and diff against the Python list"
is being satisfied as part of building it, rather than as a separate exercise. **I do not yet know
the outcome** and will report it separately. For what it is worth ahead of that: `sgtin96.py
--selftest` passes and reproduces both agreed vectors exactly.

Also confirming what you already suspected in §4: the batch commissioning API you specified does not
exist yet. Only single-tag `write-epc` with a pre-encoded EPC hex is implemented, and it takes no
filter. The `count` / "next unwritten tag" hole is real and is now being hit in practice.

---

## 7. State of the bench

Module left verified clean by read-back:

```
region         = RG_EU3
TAGENCODING    = 107          (as found at session start, restored)
GEN2_SESSION   = 0            <-- CHANGED from the as-found 2, deliberately
GEN2_TARGET    = 0
GEN2_Q         = -250         (dynamic, initial Q=6)
Ex10fastmode   = 00 14 00 00 ... (22 bytes)   byte0 = 0: DISABLED
impinjfastmode = MT_INVALID_PARA              (cannot be set on this module)
fastid         = 00
tagfocus       = 00
Select filter  = cleared
temperature    = 43 C
```

**One deliberate deviation: session is left at S0, not the S2 found at start.** `CLAUDE.md`'s own
measured guidance is S0 for continuous-carrier bench work, and the leftover S2 is my leading suspect
for §5.1. Flagged so it is not mistaken for drift — set it back to 2 when the tunnel's production
configuration is wanted on the bench.

Also confirmed along the way: **`MTR_PARAM_POTL_GEN2_BLF` and `MTR_PARAM_POTL_GEN2_TARI` return
`MT_OP_NOT_SUPPORTED`.** The deprecated BLF path §1 of the modes document warns about is not merely
deprecated, it is absent. §1's conclusion is right for a stronger reason than it gives.

New probe: `apps/intelli-rfid-reader-test/tools/bench-probe/ProbeMode.java`, subcommands `enums`,
`state`, `scan`, `fallback`, `measure`, `impinj`, `ex10`, `ex10fast`, `params`, `clean`. Read-only
against tags — nothing in this session wrote to tag memory.

---

## 8. What I need from you

1. **Is `check()` the right shape?** §1 shows a parameter where the return code is meaningless.
   Set-then-verify as the house pattern for anything that matters is a bigger change than I want to
   make unilaterally.
2. **`readMode`'s enum now has two dead values on this hardware.** `IMPINJ_FAST` throws 409 and
   `EX_FAST` fails at `StartReading`. Do they stay as documented-broken, get removed, or get
   remapped onto the general fast mode (`Ex10fastmode[0]=0` + `IsFastRead`)? I lean toward remapping
   `IMPINJ_FAST` and leaving `EX_FAST` to fail loudly, but it is a contract question.
3. **`rf-mode` needs a validated setter regardless of which mode we pick** — as it stands any typo
   silently becomes 107. Read-back-and-compare in `applyConfig()` is a few lines; say if you want it
   here or with `/api/v1`.
4. **The NXP control tag (§5.2)** — if it turns out to be damaged, do you want a replacement NXP tag
   sourced before commissioning, or is 18 Impinj + 2 non-GS1 controls an acceptable population to
   proceed on?

Same rule as before: where the module contradicted the document, the document is now corrected and
`CLAUDE.md` carries the facts.

---

*CM4 session, 2026-08-28. §1–§4 are measurements. §5.1 and the 107 = 244 identification are labelled
inferences. §5.2 is unresolved.*
