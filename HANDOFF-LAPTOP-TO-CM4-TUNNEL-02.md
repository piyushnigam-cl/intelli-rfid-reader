# Handoff: laptop → CM4, 2026-08-27 — commission the bench tags, then resume

Reply to `HANDOFF-CM4-TO-LAPTOP-TUNNEL-01.md`. Excellent session — the `ReadDuration` law and the
S2 persistence result are both the kind of finding that only comes from hardware, and catching the
"213 ms" coincidence before reporting it is the reason the number is trustworthy.

**This document covers one thing: the operator will write Reliance EPCs onto the bench tags, which
unblocks most of what is currently untestable.** Your four §7 questions are still owed from the
laptop and are coming separately — §7 below says which ones must be answered before which tests.

**Also in this push:** `docs/RF-Modes-E710.md`, the air-interface mode table worked through against
our code. Read it before any read-mode tuning — it contains three more defects, one of which
(§6.3, POLLED not clearing a sticky fast mode) may affect measurements you have already taken.

---

## 1. Before writing anything: register the population

**This is not optional and it is not reversible if skipped.** The current EPCs are the only sample
we have of real mixed stock, and §9 of your report showed 17 of 19 tags carry no valid GS1 header at
all. That population is *evidence*, and writing over it destroys it.

Every tag is XTID-serialised, so each has a permanent factory TID independent of whatever we write
into EPC. Use it as the identity.

Produce `apps/intelli-rfid-tunnel/tools/bench-tag-register.jsonl`, one line per tag, **before** any
write:

```json
{"tid":"E28011...","mdid":"0x001","tmid":"0x190","originalEpc":"...","role":"","newEpc":"","writtenAt":""}
```

Commit it. It is the bench population register from here on, and every later run should be
interpretable against it.

---

## 2. Do not write all of them — keep three controls

Write **16**. Leave **3** untouched:

| Keep | Which | Why it is worth more unwritten |
|---|---|---|
| 2 Impinj | any two of the non-GS1 EPCs (`0x8A`, `0xF1`, …) | The only way to test that a Select does **not** blind us to a non-SGTIN article, and that `decoded: false` is handled routinely. Your §9 finding is the reason this matters. |
| 1 NXP | `8A8070003A6D00021F0C3F9D` | Non-Impinj silicon. When FastID is switched on, this tag is the control that shows what happens to mixed stock — whether it returns no TID, errors, or disturbs the inventory. |

Real warehouse stock is mixed. A bench population that is uniformly correct will pass tests that a
real box fails.

---

## 3. What to write

SGTIN-96, company prefix **8905527** (7 digits → **partition 5**), filter **1**, indicator **0**.

| Batch | EAN | Tags | Serials |
|---|---|---|---|
| A | `8905527164445` | 12 | 1–12 |
| B | `8905527168207` | 4 | 1–4 |

Two EANs so that `ean` filtering can be tested **functionally** — right tags selected, wrong ones
excluded. It is **not** a timing test: with 4 tags in the other SKU any Select-scope saving is far
below noise, and `SGTIN-96-Encoding-Reliance.md` §7.9 already puts the real saving at 2–5% of budget
with 40–100 foreign tags. Do not report a timing conclusion from this split.

**Explicit low serials, not the allocator.** `startSerial > 0` bypasses the local counter by design,
which is what we want here: human-readable serials that are easy to verify by eye. Say so in the
register — **this exercise does not validate the `(reader.id << 30) | counter` scheme**, and nobody
should later think it did.

### The self-check that makes this worth doing

Generate the full list with `tools/sgtin96.py` first and write it down. Then:

> **Serial 1 of batch A must encode to exactly `30361F8CDC100F0000000001`.**
> **Serial 1 of batch B must encode to exactly `30361F8CDC106D0000000001`.**

Those are the vectors from the first handoff. **Write serial 1 of batch A, read it back, and compare
before writing the other 15.** If it does not match, stop — the encoder is wrong and 16 tags are
about to be wrong the same way.

Then run the **Java** encoder over the same inputs and diff against the Python list. That is the
encoder validation that has been outstanding since §7.6, and it is free at this point.

### Safety

- **`lock: false`. Never permalock.** These tags will be rewritten many times.
- `accessPassword`: null, not all-zeros — all-zeros is rejected rather than treated as "no password".
- `verify: true` on every write, and re-inventory independently afterwards. The acceptance session
  already proved the write path on this module; what is unproven here is the *encoding*.

---

## 4. The singulation hazard — read this before the first write

`POST /api/tags/ops/write-epc` takes `{antenna, epc, accessPassword, verify, timeoutMs}` and
**no filter**. It writes whichever tag answers. With 19 tags in the field that is a lottery, and a
mis-targeted write is silent — you get a success response for the wrong tag.

**Present one tag at a time, physically.** Record its TID in the register as you go. Reducing power
until "only the near tag responds" is not a control; do not rely on it.

You read TID per tag via a Select filter on EPC, so Select works for a *read*. Whether it isolates a
*write* is a different question and the API does not expose it — do not assume it does.

### A design gap this exposes, worth recording

The commissioning API is specified as `{ean, count, startSerial, lock, accessPassword}`. **`count`
implies batch commissioning, but Gen2 gives no way to say "the next unwritten tag".** Writing 5 tags
in one call requires either physical singulation between each, or a Select on "does not yet match
our prefix" so each write targets a tag that has not been done. Neither is in the design.

Note it in `CLAUDE.md` when you hit it. It is a real hole in the customer-facing contract and better
found now than during a site commissioning.

---

## 5. Then re-run the two things that were measured on the old population

Both of your §10 numbers were taken on 18 tags whose EPCs were mostly not GS1. Re-run them on the
commissioned population so the discovery and settle figures are against realistic content:

- The 10-trial settling test (S0), for the discovery curve shape.
- One `expectedTags: 16` session, to confirm `complete: true` at 16/16.

Expect the *shape* to be unchanged — EPC content should not affect discovery timing. **If it does
change, that is a finding**, and probably means something in the pipeline is doing per-tag work that
depends on decodability.

---

## 6. Resume order

Ranked by what unblocks a decision, not by what is quickest.

1. **Bracket the S2 persistence.** 20 / 30 / 45 / 60 / 120 s carrier-off gaps, S0 control at each
   point. This is the top item because the tunnel's session design is currently undecided and
   waiting on it. Your `RESUME-NEXT-SESSION.md` §1 already has it queued.
2. **Select action control — does `SelC_Inventoried_S2` + `SelCmd_Action.Mat_SLorA_NMat_no` actually
   force inventoried → A?** This is the alternative fix to the S2 problem and it removes the
   dependency on persistence entirely. If it works, item 1 stops being load-bearing. Test: read the
   population under S2, issue the Select, read again — do the tags answer the second time?
3. **`MTR_PARAM_TAG_FILTER`: on-air Select or firmware post-filter?** Outstanding since §9.3 and
   **now properly testable for the first time** — you will have 16 SGTIN tags and 3 that are not.
   A COMPANY-scoped Select should return 16 and suppress 3. Then watch `durationMs`: if it drops
   with the 3 suppressed, the filter is on-air; if it does not, it is a post-filter and
   `SGTIN-96-Encoding-Reliance.md` §7.9 is worthless.
4. **FastID**, now that the silicon is confirmed Impinj. Two questions: does `tid: true` become
   effectively free as expected, and what does the **NXP control tag** do when FastID is on?
5. **The API-key package over the wire.** Still never exercised, and it is on by default for tunnel.
6. **Build the discovery curve** (`diagnostics.discoveryCurve`). Cheap now, and every later tuning
   run is worth more with it than without.

---

## 7. What is still owed from the laptop

Your §7 asked four questions. They need a design decision rather than a quick answer, and they are
coming in the next handoff. Which of the above they block:

| Your question | Blocks |
|---|---|
| Read-mode default after the 14× Ex10 result | Nothing above. Stay on **NORMAL** on the bench meanwhile — your reasoning is right, and a default that is slower on all measured evidence should not be the packaged one. |
| `COUNT_REACHED` and early exit on count | Nothing above, but it is the cheapest second in the budget and your settle measurement (60–75% of session time) is the argument. Do not build it yet — it interacts with the `/api/v1` layer. |
| Spool crash-vs-degrade | Nothing. Your instinct to degrade matches the project's own stated rule. |
| What to re-measure now `ReadDuration` sets both latency and callback rate | §5 above is the part that cannot wait. |

Same rule as before: where the module contradicts this document, the module is right — fix it,
record it in `CLAUDE.md`, then reply.

---

*Laptop design session, 2026-08-27. §1–§4 are procedure, not measurement. The encoding is specified;
whether our encoder produces it is exactly what §3 checks.*
