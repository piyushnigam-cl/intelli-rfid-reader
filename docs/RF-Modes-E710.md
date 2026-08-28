# E710 air-interface modes — which ones we can use, how they are set, and what is wrong today

**Status: originally derived, corrected against hardware on 2026-08-28.** The mode table is
transcribed from the hardware user manual (p.6); the code findings were read from source. The
document was written before anything had run against a module, and a bench pass on the SIM7500
contradicted a substantial part of it. Corrections are marked **Corrected 2026-08-28** in place, and
the superseded claim is left visible rather than deleted — what was assumed versus what was measured
is the useful record.

**What survived:** §1 (a mode ID is a bundle), §2's three-band structure, §3's mode table itself,
and §4's central argument that sensitivity matters more than rate. **What did not:** the way a mode
is actually selected (§2, §3), the recommendation to move to mode 222 (§4), and two of the three
defects in §6. §7's question is now answered, and its premise was wrong.

**Transcription caveat:** the table below was read from the manual's mode-table image. Before
relying on a *specific* ID for a production setting, check it against the manual PDF. The structure
and the conclusions are safe; an individual hex value may not be. The bench pass could not
cross-check the table directly for this reason — the manual's mode table is an image, not text.

---

## 1. A mode ID is a bundle, not a knob

Each row of the manual's table fixes **five** things together: forward-link modulation, Tari, PIE,
BLF, and reverse-link modulation. You do not choose BLF and encoding separately — you select one
mode ID and the module applies all five as a set.

This matters because our SDK notes carried a rule that reads like an independent constraint:

> ~~"BLF 640 kHz is FM0-only; Miller forces BLF 250."~~

**That is wrong as a general rule.** Modes 120, 124, 225, 291 and 189 all run BLF 640 with Miller
M=2 or M=8. The claim came from the deprecated `MTR_PARAM_POTL_GEN2_BLF` path and does not
constrain mode-ID selection. Do not design around it.

---

## 2. Three ID spaces for the same physical modes — region picks the column

The manual lists every mode three times:

| Space | Range | Band |
|---|---|---|
| FCC | 100-series | 902–928 MHz |
| **ETSI Lower Band** | **200-series** | **865–868 MHz — this is us** |
| ETSI Upper Band | 300-series | 915–921 MHz |

India's 865–867 MHz band is **ETSI Lower Band**, and so is the bench module's forced `RG_EU3`.
**Only the 200-series applies to this product.**

There is also an older 1-byte "Old Mode ID" column, and a "Corresponding Impinj Inventory Mode ID"
column used by the Impinj fast-inventory path, where the ID is `4000 + mode ID`.

> **Corrected 2026-08-28 — there is a fourth space, and it is the one you actually write.** The
> three columns above are how the *manual* lists modes. The SDK reaches the manual's IDs through a
> tag byte: `Reader$RFMODE` has `RFM_222_EX22 = -16776994`, and `-16776994 == 0xFF0000DE ==
> 0xFF000000 | 222`. Every `*_EX22` constant follows that rule. **Writing a bare `222` does not
> select manual mode 222** — see §7.
>
> The "Corresponding Impinj Inventory Mode ID" column is **not reachable on this module at all**:
> the custom parameter that carries it, `Reader/impinjfastmode`, returns `MT_INVALID_PARA` to both
> get and set. See §6.1.

### The cost: the fast end of the table is not available to us

The five fastest modes have **no ETSI Lower Band variant at all**:

| Mode | Rate | Available as |
|---|---|---|
| 103 | 1100 | FCC only |
| 102 | 950 | FCC + ETSI UB (302) |
| 120 | 800 | FCC only |
| 104 | 725 | FCC only |
| 124 | 700 | FCC + ETSI UB (323) |

**Our ceiling is mode 203 at 600 tags/s.** Any design or quotation assuming 1100 tags/s is assuming
an FCC deployment.

---

## 3. The modes we can actually use

ETSI Lower Band, fastest first. Sensitivity is the E710 chip spec from the manual.

| Mode | Impinj inv. ID | Rate (tags/s) | Sensitivity (dBm) | Reverse link | Tari (µs) | PIE | BLF (kHz) |
|---|---|---|---|---|---|---|---|
| 203 | — | 600 | −84.0 | FM0 | 12.5 | 1.5 | 426 |
| 202 | — | 500 | −85.5 | FM0 | 15 | 1.5 | 426 |
| 226 | — | 500 | −86.5 | Miller M=2 | 12.5 | 1.5 | 426 |
| 225 | — | 425 | −88.0 | Miller M=2 | 15 | 2 | 640 |
| 224 | — | 400 | −86.5 | Miller M=2 | 12.5 | 2 | 320 |
| 223 | — | 350 | −88.0 | Miller M=4 | 15 | 2 | 320 |
| **222** | **4222** | **300** | **−88.0** | **Miller M=4** | **20** | **2** | **320** |
| 291 | 4291 | 280 | −88.0 | Miller M=8 | 10 | 2 | 640 |
| 241 | 4241 | 200 | −90.5 | Miller M=8 | 20 | 2 | 320 |
| 244 | 4244 | 175 | −91.0 | Miller M=4 | 20 | 2 | 250 |
| 281 | 4281 | 130 | −92.0 | Miller M=8 | 20 | 2 | 320 |
| 205 | — | 95 | −77.5 | FM0 | 20 | 2 | 50 |
| 285 | 4285 | 70 | −98.0 | Miller M=8 | 20 | 2 | 160 |

Forward-link modulation is PR-ASK for every ETSI LB mode. (DSB-ASK appears only on FCC 103 and 104.)

> **Corrected 2026-08-28 — how to actually set one of these.** The "Mode" column above is the
> manual's ID, **not** a settable value. To select mode *N* from this table, write
> `0xFF000000 | N` to `MTR_PARAM_POTL_GEN2_TAGENCODING`:
>
> | Mode | Settable value | | Mode | Settable value |
> |---|---|---|---|---|
> | 203 | `0xFF0000CB` (−16777013) | | 241 | `0xFF0000F1` |
> | 202 | `0xFF0000CA` | | 244 | `0xFF0000F4` |
> | 226 | `0xFF0000E2` | | 281 | `0xFF000119` |
> | 225 | `0xFF0000E1` | | 205 | `0xFF0000CD` |
> | 224 | `0xFF0000E0` | | 285 | `0xFF00011D` (−16776931) |
> | 223 | `0xFF0000DF` | | 291 | `0xFF000123` |
> | 222 | `0xFF0000DE` (−16776994) | | | |
>
> All 13 were accepted and read back correctly on the bench SIM7500. Writing the bare integer
> instead is accepted with `MT_OK_ERR` and **silently lands on 107** — all 13 of them do. The
> "Impinj inv. ID" column is dead on this module (§6.1).

The manual also has an **"Impinj Inventory Mode Special Parameters"** block giving BPSK reverse-link
variants of certain inventory IDs — 4323, 4345, **4222**, **4241**, 4146, 4285 — at reduced rates.
Two of those are ETSI LB modes, so they are in scope, but treat them as a later experiment rather
than a starting point.

**Mode 205 is a trap.** It is the *worst* sensitivity in the table (−77.5 dBm) *and* nearly the
slowest, because BLF 50 kHz is a special-purpose dense-reader setting. It is never the answer to
"which mode should I use".

---

## 4. Rate is not the lever it looks like. Sensitivity is.

Do the arithmetic before tuning anything:

| Mode | Rate | Time for 40 tags |
|---|---|---|
| 203 (fastest available) | 600/s | **67 ms** |
| 222 (suggested start) | 300/s | 133 ms |
| 285 (slowest) | 70/s | **571 ms** |

**The entire span of the table is about half a second on a 5-second box budget — roughly 10%.**

Sensitivity spans **−84.0 to −98.0 dBm — 14 dB.** That is what determines whether the reader hears
the articles shadowed at the centre of a densely packed box, and a box that reports 38 of 40 has
failed regardless of how fast it did so.

This is the same conclusion `SGTIN-96-Encoding-Reliance.md` §7 reached from Gen2 timing arithmetic,
now with the manual's own numbers behind it:

> **Pick the most sensitive mode that is fast enough — not the fastest mode.**
> A robust mode finding all 40 in 1.2 s beats a fast mode finding 38 in 0.9 s and then running to
> timeout.

~~**Suggested starting point: mode 222.** Middle of the range, −88.0 dBm, 300 tags/s — eight times
more headroom than a 40-tag box needs. If tags are missed, move *down* the table to 241 (−90.5) or
281 (−92.0), not up.~~

> **Corrected 2026-08-28 — stay where we are. The default is already better than the suggestion.**
> The bench pass identified `rfMode = 107`, the current default, as **mode 244: 175 tags/s,
> −91.0 dBm**. Mode 222 is −88.0 dBm. Applying this section's own rule — *pick the most sensitive
> mode that is fast enough* — **moving 107 → 222 would be a 3 dB sensitivity downgrade in exchange
> for 175 → 300 tags/s, which a 40-tag box does not need.** The reasoning in this section is right;
> only its conclusion was, and it was wrong because nobody knew what 107 was.
>
> **This identification is an inference, not a proof.** It rests on a read-rate fingerprint: the 13
> EX22 modes reproduced the manual's declared rate ordering monotonically, and pairing each Silion
> profile back-to-back with its suspected twin matched within 1–4% across five pairs (107↔244,
> 105↔241, 103↔222, 112↔223, 113↔285). It is corroborated by 107 = `0x6B` being the manual's Old
> Mode ID for the 146/244/343 triple, of which 244 is the ETSI LB member. The manual's mode table is
> an image and could not be cross-checked directly. If sensitivity ever needs to be *increased*, 241
> (−90.5) is a step down and 281 (−92.0) or 285 (−98.0) are real gains — but all three cost rate,
> and none has been measured against a real box.

---

## 5. How a mode is selected in our code — three layers that interact

| Layer | Mechanism | Where |
|---|---|---|
| 1. Base RF mode | `MTR_PARAM_POTL_GEN2_TAGENCODING` ← `rfid.reader.rf-mode` | `ReaderSession.applyConfig()` |
| 2. Ex10 fast mode | `Reader/Ex10fastmode` custom param | `ReaderSession.setEx10FastMode()` |
| 3. Impinj fast mode | `Reader/impinjfastmode`, `IMPINJ_FASTPARMS` | `ReaderSession.configureFastMode()` |

**Layer 2 overrides layer 1.** In Ex10 fast mode the module auto-switches RFMODE internally, so
`rf-mode` stops applying. Layers 2 and 3 are **mutually exclusive and sticky on the module**, which
is why `configureFastMode()` explicitly clears the other one on every change. That clearing is
correct and must stay — a reader whose behaviour depends on what ran before it is the worst failure
mode this project has.

> **Corrected 2026-08-28 — on this module, only layer 1 works.** Layer 3 does not exist:
> `Reader/impinjfastmode` returns `MT_INVALID_PARA` to get and set alike (§6.1). Layer 2 exists as a
> parameter but the module **refuses to start reading** with true Ex10 fast mode enabled — `byte 0 =
> 1` gives `MT_CMD_FAILED_ERR` from `StartReading` and zero tags (§6.2). Only the "general fast
> mode" path (`byte 0 = 0`, with `BackReadOption.IsFastRead = true`) runs, and it measured **3.6×
> slower than NORMAL** on 18 tags.
>
> The clearing logic is still right and should stay; the interaction it guards against is simply not
> reachable here. **Practical consequence: `rf-mode` always applies, because nothing can override
> it, and NORMAL is the only read mode worth shipping.**

### Switching at runtime

```
POST /api/reader/config    {"rfMode": 222}
POST /api/reader/config    {"readMode": "NORMAL"}
```

`ReaderController.updateConfig()` stops reading, applies the setting, calls
`session.applyConfig()`, and restarts if it was reading. `configureFastMode()` runs from
`startReading()`. So both layers are re-pushed on a switch — this part is built correctly.

Runtime-settable keys: `readPowerDbm10`, `writePowerDbm10`, `session`, `target`, `q`, `rfMode`,
`readMode`, `rssiThresholdDbm`, `dedupWindowMs`. Anything else needs a restart.

Note: `ModuleConfigCache.applyIfChanged()`, referenced in the SGTIN document, **does not exist**.
`applyConfig()` re-pushes everything unconditionally. That is fine for a deliberate switch and
wrong for a per-call path — do not call it per box.

---

## 6. Three defects found against this table — work items

All three were read from source and unverified on hardware when written. **All three were tested on
the bench SIM7500 on 2026-08-28. One is real; one is real but unreachable; one was a misreading and
the existing code is correct.** Each is marked below.

### 6.1 The Impinj fast mode uses an FCC-only mode ID — ~~defect~~ **moot: the parameter does not exist**

`ReaderSession.configureFastMode()`:

```java
fast.IMPINJ_MODE_ID = IMPINJ_FASTPARMS.IMPINJ_INVENTORY_MODE_ID_4124;
```

~~**4124 is FCC mode 124, which has no ETSI Lower Band variant.** Under `RG_IN` or `RG_EU3` this is
either rejected or silently wrong. It should be one of the ETSI LB inventory IDs: **4222, 4241,
4244, 4281, 4285, 4291** — 4222 to match the suggested base mode.~~

> **Corrected 2026-08-28 — the mode ID is never reached. The parameter name is rejected first.**
>
> ```
> Reader/impinjfastmode  ->  MT_INVALID_PARA      (ParamGet, as found)
> ```
>
> Setting `CMD_FAST_INVENTORY` with each of 4124, 4222, 4241, 4244, 4281, 4285 and 4291 gave
> `MT_INVALID_PARA` on both set and read-back — **all seven identically**, FCC-only and ETSI LB
> alike. The name is rejected before the mode ID is looked at, so the proposed fix would change
> nothing.
>
> Corroborated two ways: `Reader/impinjfastmode` appears nowhere in the vendor's own documented
> custom-parameter list (`docs_en/doc_Dev_J_html/api_params.html`), and a read-only sweep of all 33
> documented parameter names found no Impinj-mode parameter of any kind.
>
> **The real defect is larger than the one described here: `readMode = IMPINJ_FAST` is dead on this
> module.** `configureFastMode()` wraps that `ParamSet` in `check(...)`, so it throws
> `ReaderException` → HTTP 409 on every attempt.
>
> What the vendor actually documents is **one** parameter with two modes, selected by byte 0 of
> `Reader/Ex10fastmode`: `1` = Ex10 fast mode, `0` = "general fast mode". Our "Impinj fast mode" is
> most likely that general fast mode, reached by `Ex10fastmode[0] = 0` plus
> `BackReadOption.IsFastRead = true` — which does run (see §6.2).
>
> Also worth knowing: `IMPINJ_FASTPARMS` exposes only FCC mode-ID constants
> (4123/4124/4141/4146/4148/4185), while `Reader$IMPINJ_MODE_ID` carries the full set including
> 4222/4241/4244/4281/4285/4291. The fix suggested above was **not directly expressible** through
> the constants the code uses. Moot given the above, but it would have been the next surprise.

### 6.2 A decimal-for-hex slip in the Ex10 payload — ~~defect~~ **not a defect: the existing code is correct**

`ReaderSession.setEx10FastMode()`:

```java
byte[] values = new byte[22];
values[0] = (byte) (enabled ? 1 : 0);
values[1] = 20;                        // <-- SDK notes say this byte is 0x20
```

~~`20` decimal is `0x14`. The SDK notes describe the 22-byte payload as
`mode(1=Ex fast) + 0x20 + scenario(0-5)`. This looks like a textbook decimal-for-hex slip.~~

> **Corrected 2026-08-28 — `values[1]` is a payload length, not a mode constant. Do not change it.**
>
> The vendor's own demo (`api_custompar.html`, `api_fastmodeinventory.html`) uses it as a loop
> bound:
>
> ```java
> byte[] vals = new byte[22];
> vals[0] = 1;                       // 1 enable ex10fastmode, 0 general fast mode
> vals[1] = 20;
> for (int i = 0; i < vals[1]; i++)  // <-- the loop bound: 22 - 2 = 20 trailing bytes
>     vals[2 + i] = 0;               // i == 0: "0 more tags, 1 less tags"
> ```
>
> `0x20` = 32 would declare 32 trailing bytes inside a 22-byte buffer. **Writing it is not a fix; it
> is a new bug that happens to be silent.** Measured: the module stores the byte verbatim and
> validates nothing — `set b1=20` reads back `01 14 00 00…`, `set b1=0x20` reads back `01 20 00 00…`,
> both `MT_OK_ERR`.
>
> The note about `values[2]` stands: it is the scenario byte, it is never set, and it should be set
> explicitly and made configurable.

**And a real defect this one was hiding: Ex10 fast mode is refused by this module.** Measured with
`IsFastRead` genuinely true, which is the only condition under which the payload does anything —
18 tags, 3 s windows:

| Config | `StartReading` | unique | reports/s |
|---|---|---|---|
| NORMAL control, `IsFastRead=false` | ok | 18 | 64.3 |
| `IsFastRead=true`, Ex10 byte0=**0** (general fast) | ok | 18 | **18.0** |
| `IsFastRead=true`, byte0=1, byte1=**20** | **`MT_CMD_FAILED_ERR`** | 0 | 0.0 |
| `IsFastRead=true`, byte0=1, byte1=**0x20** | **`MT_CMD_FAILED_ERR`** | 0 | 0.0 |
| `IsFastRead=true`, byte0=1, byte1=20, scenario=1 | **`MT_CMD_FAILED_ERR`** | 0 | 0.0 |

`byte1` makes no difference at all — 20 and `0x20` fail identically, which is the direct measurement
that §6.2's proposed fix is a no-op. **`readMode = EX_FAST` is broken on this module**, and the only
fast path that runs is 3.6× slower than NORMAL. The module recovered cleanly afterwards (the next
settle run read 18/18).

### 6.3 POLLED never clears a sticky fast mode — **real in the code, unreachable on this module**

`configureFastMode()` is called only from `startReading()`, and `startReading()` throws for POLLED.
So:

```
readMode = EX_FAST   ->  start  ->  Ex10 enabled on the module
readMode = POLLED    ->  inventoryOnce()  ->  Ex10 still enabled
```

`inventoryOnce()` then runs in a mode nobody selected. This is exactly the failure the method's own
javadoc warns about, with POLLED as the hole in it. Fix: clear both fast modes when entering POLLED,
or call `configureFastMode()` from `applyConfig()` rather than from `startReading()`.

> **Corrected 2026-08-28 — the code defect is real; the failure it enables cannot fire here.**
> Neither fast mode can be enabled on this module (§6.1, §6.2), so there is nothing to go sticky.
> The module state as found at the start of the bench session confirms it: `Ex10fastmode` byte 0 was
> `0` (disabled) and `impinjfastmode` was `MT_INVALID_PARA`.
>
> **Fix it anyway** — it is cheap, it is correct, and it stops being unreachable the moment the
> firmware changes or a different module ships. But it does **not** cast doubt on POLLED measurements
> taken on this module, which was the reason it was flagged as urgent.
>
> The thing that *was* found sticky, and that does invalidate measurements, is **`GEN2_SESSION`**: it
> was left at **S2** by a previous run. Against tag stock whose S2 inventoried flags persist >15 s,
> that reads as a dead reader. Probes must set session explicitly rather than inherit it.

---

## 7. The `rfMode = 107` ambiguity — **answered: 107 is mode 244**

`ReaderConfig.java`:

```java
/** Gen2 RF mode (101, 103, 105, 107, 111, 112, 113, 115). 107 is a good general default. */
private int rfMode = 107;
```

The original question: those numbers are Silion E-series profile IDs from the vendor SDK docs, a
different numbering space from this manual's mode IDs, and the two collide — 103 exists in both and
means different things. 107 is also `0x6B`, the manual's Old Mode ID for mode 146/244/343.

> **Corrected 2026-08-28 — the premise was wrong. There are three spaces, not two, and the manual's
> IDs are not settable as bare integers.**

**What `MTR_PARAM_POTL_GEN2_TAGENCODING` accepts**, by set-and-read-back (the technique `Probe2`
uses for regions):

| Value written | `ParamSet` | Reads back | Verdict |
|---|---|---|---|
| 103, 105, 107, 112, 113 | `MT_OK_ERR` | itself | **accepted** |
| 101, 111, 115 | `MT_OK_ERR` | **107** | silently discarded |
| 203, 202, 226, 225, 224, 223, 222, 291, 241, 244, 281, 205, 285 | `MT_OK_ERR` | **107** | silently discarded, all 13 |
| `0xFF000000 \| {203, 202, 226, 225, 224, 223, 222, 291, 241, 244, 281, 205, 285}` | `MT_OK_ERR` | itself | **accepted, all 13** |

Three findings, in order of how much trouble each can cause:

1. **`ParamSet` returned `MT_OK_ERR` for every value tested, including 999 and 0.** The return code
   carries no information. Read-back is the only truth.
2. **107 is a hard fallback.** Park on an accepted mode (105, 113 or EX22-222), then write 222 / 203
   / 999 / 0 — all four return `MT_OK_ERR` and the read-back snaps to 107 every time, regardless of
   what was parked. An unrecognised value does not leave the previous mode in place.
3. **So `rf-mode: 222` in a config file lands on 107, with no error anywhere.** That is defect 6.1's
   failure shape — a mode ID from the wrong space accepted silently — in the base-mode layer, where
   this document did not think to look for it.

**Also: `ReaderConfig`'s javadoc is wrong on 3 of its 8 values.** 101, 111 and 115 are silently
discarded. Only 103, 105, 107, 112 and 113 do anything.

### What 107 actually selects

Measured by read-rate fingerprint — 18 tags, S0, NORMAL, `ReadDuration` 50 ms, 30 dBm. The EX22
modes reproduce the manual's declared rate ordering **exactly**, including the close pairs 202 > 226
and 225 > 224:

| EX22 mode | manual tags/s | measured reports/s |
|---|---|---|
| 203 | 600 | 144.3 |
| 202 | 500 | 136.0 |
| 226 | 500 | 130.3 |
| 225 | 425 | 122.3 |
| 224 | 400 | 121.3 |
| 223 | 350 | 112.0 |
| 222 | 300 | 100.7 |
| 291 | 280 | 89.0 |
| 241 | 200 | 78.3 |
| 244 | 175 | 69.0 |
| 281 | 130 | 52.3 |
| 205 | 95 | 49.7 |
| 285 | 70 | 29.3 |

Monotone across all 13. The absolute rates are compressed against the manual because 18 tags and
50 ms callback batching are the limit here, not the air rate — but the *ordering* is the manual's.

Then a drift-controlled run pairing each Silion profile back-to-back with its suspected twin, 4 s
windows:

| Silion profile | reports/s | EX22 mode | reports/s | delta |
|---|---|---|---|---|
| **107** | 66.5 | **244** | 68.5 | 3% |
| 105 | 80.0 | 241 | 78.0 | 3% |
| 103 | 102.3 | 222 | 100.8 | 1.5% |
| 112 | 111.0 | 223 | 112.0 | 1% |
| 113 | 31.0 | 285 | 29.8 | 4% |

A clean bijection: each profile matches exactly one EX22 mode, and no two profiles claim the same
one.

> **`rfMode = 107` selects manual ETSI LB mode 244**: 175 tags/s, −91.0 dBm, Miller M=4, Tari 20 µs,
> BLF 250 kHz.

The second hypothesis above was right — 107 = `0x6B` is the Old Mode ID of the 146/244/343 triple,
and 244 is that triple's ETSI Lower Band member.

**This is inferred from a rate fingerprint, not proven.** The manual's mode table is an image rather
than text (extracting the `.docx` XML did not help), so it could not be cross-checked directly. What
is proven is the accept/reject behaviour and the rate ordering; the mapping of 107 to *that specific
row* is the inference.

**The consequence is benign and slightly lucky:** the current default is already more sensitive than
the mode §4 was going to recommend. See the correction in §4 — keep 107.

### Mode 222, confirmed working

As `0xFF0000DE` (−16776994), not as `222`:

| | Mode 222 (EX22) | Mode 107 = 244 (current default) | Bench baseline |
|---|---|---|---|
| Unique tags | **18 / 18** | 18 / 18 | 18 |
| Reports/s | **100.7 – 102.3** (3 runs) | 66.5 – 67.3 | — |
| RSSI median | **−30 dBm** | −30 dBm | — |
| RSSI max | **−26 dBm** | −26 dBm | **−26 dBm** (at 20 dBm, ~30 cm) |
| `TAGINFO.Frequency` | 865700, 866300, 866900, 867500 kHz | same | same 4-channel RG_EU3 plan |

RSSI is identical to the −26 dBm bench baseline and the channel plan is unchanged, so the antenna
path is unchanged — consistent with VSWR 1.119, which was not re-measured (nothing in that session
touched the RF path). Note the baseline was taken at 20 dBm and these at 30 dBm and RSSI did not
improve, which is expected at ~30 cm where the tags already saturate the receiver.

Mode 222 is 1.5× faster than the current default and 3 dB less sensitive. **On §4's own reasoning,
do not switch.**

### One more thing the module contradicted

**`MTR_PARAM_POTL_GEN2_BLF` and `MTR_PARAM_POTL_GEN2_TARI` return `MT_OP_NOT_SUPPORTED`.** The
deprecated BLF path §1 warns about is not merely deprecated, it is **absent**. §1's conclusion — that
BLF and Tari come bundled in the mode ID rather than being independent knobs — is right, for a
stronger reason than it gives.

---

## 8. What to report back

**All five answered on 2026-08-28** and sent to the laptop in `HANDOFF-CM4-TO-LAPTOP-TUNNEL-02.md`.
Kept here as the record of what was asked.

1. ~~Which numbering space `MTR_PARAM_POTL_GEN2_TAGENCODING` accepts, and what 107 actually
   selects.~~ → §7. Two spaces: bare Silion profiles (5 of 8 working) and `0xFF000000 | id` for the
   manual's IDs. 107 = mode 244, inferred.
2. ~~Whether `IMPINJ_MODE_ID = 4124` is refused or silently accepted under RG_EU3.~~ → §6.1. Neither:
   the parameter does not exist on this module.
3. ~~Whether `values[1]` should be `0x20`.~~ → §6.2. No. It is a payload length; the existing code is
   correct.
4. ~~Confirmation that mode 222 works, and its measured read rate and RSSI against the −26 dBm /
   VSWR 1.119 bench baseline.~~ → §7. Works as `0xFF0000DE`. 100.7–102.3 reports/s, RSSI max −26 dBm,
   identical to baseline. But do not switch to it.
5. ~~Anything above that the module contradicts.~~ → the eleven corrections marked in this document,
   and the `CLAUDE.md` "Vendor SDK facts" and "Gotchas" entries added the same day.

---

*Laptop design session, 2026-08-27. Derived from the manual and from source. Not measured.*
*Corrected against the bench SIM7500, CM4 session, 2026-08-28 — corrections marked in place.*
