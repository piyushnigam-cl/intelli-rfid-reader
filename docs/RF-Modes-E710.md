# E710 air-interface modes — which ones we can use, how they are set, and what is wrong today

**Status: derived, not measured.** The mode table is transcribed from the hardware user manual
(p.6). The code findings are read from source. Nothing here has run against a module. Where the
module disagrees, the module is right — fix the code, then correct this document.

**Transcription caveat:** the table below was read from the manual's mode-table image. Before
relying on a *specific* ID for a production setting, check it against the manual PDF. The structure
and the conclusions are safe; an individual hex value may not be.

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

**Suggested starting point: mode 222.** Middle of the range, −88.0 dBm, 300 tags/s — eight times
more headroom than a 40-tag box needs. If tags are missed, move *down* the table to 241 (−90.5) or
281 (−92.0), not up.

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

All three are read from source and **unverified on hardware**. Confirm before and after fixing.

### 6.1 The Impinj fast mode uses an FCC-only mode ID

`ReaderSession.configureFastMode()`:

```java
fast.IMPINJ_MODE_ID = IMPINJ_FASTPARMS.IMPINJ_INVENTORY_MODE_ID_4124;
```

**4124 is FCC mode 124, which has no ETSI Lower Band variant.** Under `RG_IN` or `RG_EU3` this is
either rejected or silently wrong. It should be one of the ETSI LB inventory IDs:
**4222, 4241, 4244, 4281, 4285, 4291** — 4222 to match the suggested base mode.

Worth checking whether the module *reports* an error here or accepts it and does something else.
A silent acceptance is the dangerous case and would explain a fast mode that reads poorly for no
visible reason.

### 6.2 A decimal-for-hex slip in the Ex10 payload

`ReaderSession.setEx10FastMode()`:

```java
byte[] values = new byte[22];
values[0] = (byte) (enabled ? 1 : 0);
values[1] = 20;                        // <-- SDK notes say this byte is 0x20
```

`20` decimal is `0x14`. The SDK notes describe the 22-byte payload as
`mode(1=Ex fast) + 0x20 + scenario(0-5)`. This looks like a textbook decimal-for-hex slip.

Also **`values[2]` — the scenario byte — is never set**, so it defaults to 0. Scenario 0 is "dense",
which is what a 40-tag box wants, so the current behaviour is probably right *by accident*. Set it
explicitly and make it configurable; dense is 0/2/4 and sparse is 1/3/5.

### 6.3 POLLED never clears a sticky fast mode

`configureFastMode()` is called only from `startReading()`, and `startReading()` throws for POLLED.
So:

```
readMode = EX_FAST   ->  start  ->  Ex10 enabled on the module
readMode = POLLED    ->  inventoryOnce()  ->  Ex10 still enabled
```

`inventoryOnce()` then runs in a mode nobody selected. This is exactly the failure the method's own
javadoc warns about, with POLLED as the hole in it. Fix: clear both fast modes when entering POLLED,
or call `configureFastMode()` from `applyConfig()` rather than from `startReading()`.

This matters immediately for bench work, because the acceptance suite and most diagnostics run in
POLLED — so a POLLED measurement taken after a fast-mode run may not be a POLLED measurement.

---

## 7. The `rfMode = 107` ambiguity — probe before trusting it

`ReaderConfig.java`:

```java
/** Gen2 RF mode (101, 103, 105, 107, 111, 112, 113, 115). 107 is a good general default. */
private int rfMode = 107;
```

Those numbers are **Silion E-series profile IDs from the vendor SDK docs — a different numbering
space from this manual's mode IDs.** The two collide: 103 exists in both and means different things.
And 107 is also `0x6B`, which is the manual's Old Mode ID for mode 146/244/343.

So `rf-mode: 107` could plausibly mean at least two different modes, and nobody has checked which.

**Probe it the same way the region question was settled** — set and read back, which is what
`Probe2.java` already does for regions:

1. Set `MTR_PARAM_POTL_GEN2_TAGENCODING` to each candidate and read it back.
2. Candidates: the Silion profile list (101, 103, 105, 107, 111, 112, 113, 115), then the ETSI LB
   mode IDs from §3 (203, 202, 226, 225, 224, 223, 222, 291, 241, 244, 281, 205, 285).
3. Record which are accepted, which are refused, and what each reads back as.
4. If a mode is accepted, inventory a tag and read `TAGINFO.Frequency` and the observed rate — that
   is the only way to tell which physical mode was actually applied.

If the module accepts values from both spaces, the numbering is ambiguous at the API and every
`rf-mode` value in every config file needs a comment saying which space it is in.

---

## 8. What to report back

1. Which numbering space `MTR_PARAM_POTL_GEN2_TAGENCODING` accepts, and what 107 actually selects.
2. Whether `IMPINJ_MODE_ID = 4124` is refused or silently accepted under RG_EU3.
3. Whether `values[1]` should be `0x20`, with the observed difference either way.
4. Confirmation that mode 222 works, and its measured read rate and RSSI against the
   −26 dBm / VSWR 1.119 bench baseline.
5. Anything above that the module contradicts — into `CLAUDE.md` before replying, as last time.

---

*Laptop design session, 2026-08-27. Derived from the manual and from source. Not measured.*
