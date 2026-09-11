# Proposal — a warehouse variant of IntelliRFID

> **Superseded in premise, 2026-09-01.** This note was written when the Reliance tunnel was expected
> to have a PLC. **It does not: the reader drives the conveyor itself**, through the Tunnel Manager.
> References to a PLC below are the *context this was argued in*, not a description of the system —
> the current field interface is `com.intelli.rfid.tunnel.field.FieldChannel` and
> `docs/Tunnel-Interconnect.md`. Kept because the electrical reasoning is still sound.

**To:** the board team · **From:** the tunnel software side · **2026-08-22**
**Companion to:** `Board-v3-Digital-IO-Change-Request.md`. Read that first — CR-1 applies here too.
Nothing below has been built or measured.

**The idea (user, 2026-08-22):** make a warehouse-specific version, strip the wheel-sensor block
because it is rail-only, and use the reclaimed space for more digital I/O that can drive lights and
PLC inputs directly.

**Verdict: the instinct is right and worth doing — but for a slightly different reason than the
framing suggests, and there is a constraint that has to be solved first.**

---

## 1. The constraint that shapes everything: the CM4 has no free GPIO

Reclaiming board area does not give you more CM4 GPIO. The CM4 exposes **GPIO0–27 — 28 pins,
full stop** — and the authoritative map in `SOFTWARE-HANDOFF.md` §2 already assigns **every one of
GPIO2 through GPIO27**. There is no pin bank waiting behind the wheel-sensor block.

So the useful framing is: **board area is not what is scarce. Two other things are.**

1. **Edge span for connectors.** J26 already fills its edge — 46.88 mm of courtyard in a 55.47 mm
   span, and `V2-DESIGN.md` records that only a 13-way would still fit. A second field connector has
   nowhere to go. **This is what removing the wheel sensors actually buys, and it is the real
   bottleneck.**
2. **A pin budget for the new channels.** Solved separately, in §3.

Both are solvable. The good news arrived while checking: **GPIO0/1 appear to be free.**

---

## 2. What removing the wheel-sensor block actually frees

From the schematic: **J22 and J23 are 5-way Degson 15EDGRC-3.81 terminals**, feeding four analog
current-loop channels into the SAMD21's ADC on **PA02–PA05**, with an SMAJ33A TVS per line and
VDDANA filtering (FB1). `WheelSense.kicad_sch` is a 200 KB sheet — comparable to the RFID sheet, so
this is a substantial block, not a corner.

**Edge span freed** (using the 4.97 mm end allowance implied by J26's 46.88 mm courtyard):

| | Courtyard | Plug exists? |
|---|---|---|
| J22 + J23 today (2 × 5-way) | **40.4 mm**, before any gap between them | — |
| Replace with **8-way** | 31.6 mm | ✅ **fits, +8.8 mm spare** |
| Replace with 12-way | 46.9 mm | ✅ but **6.5 mm short** |
| Replace with 13-way | 50.7 mm | ✅ but 10.3 mm short |

So an **8-way second field connector drops straight into the freed span** with margin. A 12-way
would need either the inter-connector gap that was already there, a small board growth, or a
different edge — worth checking against the real placement, because a 12-way has a strong advantage
(§4).

**Also freed:** SAMD21 PA02–PA05, four SMAJ33A, the analog front ends, and the VDDANA filtering.
**The SAMD21 itself stays** — it is also the CM4 supervisor (`CM4_EN_DRV`, `CM4_BOOTED`), which the
warehouse needs just as much. It simply loses its ADC job and gains ~30 idle pins.

---

## 3. Where the new I/O pins come from — three routes

### Route A (recommended) — I²C0 on GPIO0/1 + an I/O expander

Checking the netlist: `SDA0` / `SCL0` and `ID_SD` / `ID_SC` appear as hierarchical labels on
`CM4_GPIO.kicad_sch`, and **there is no I²C device anywhere on the board** — no MCP23xxx, no PCA95xx,
no EEPROM beyond the CM4's own. The GPIO map starts at GPIO2.

On a custom carrier (as opposed to a HAT), GPIO0/1 are ordinary GPIO / I²C0 and free to use. So
**a whole I²C bus is available without sacrificing a single assigned pin.** An MCP23017 gives 16 I/O
per device and up to 8 devices on the bus — far more than this will ever need.

> ⚠️ **Please confirm from the netlist what `SDA0`/`SCL0` currently land on** at the root sheet. If
> they go to a test point or nothing, this route is clear. This is the single fact the proposal rests
> on.

**One design requirement if you take this route:** tie the expander's `RESET` so that a CM4 reset
also resets the expander. MCP23017 outputs default to *inputs* (high-impedance) on reset, so with
external pull-downs on the field-driver gates that gives the same **outputs-off-at-boot** property
the BCM2711 pull-downs give today. Without that tie, an expander can hold stale outputs across a CM4
reboot — which is exactly the failure the current design engineered away.

### Route B — the SAMD21 as the expander, over the existing UART3

Zero new components. It is already there, already talks to the CM4 on UART3, and after losing wheel
sensing it has ~30 free pins.

Its real advantage is different and worth naming: **the SAMD21 runs off the 24 V rail independently
of the CM4**, so it can enforce a safe output state when the CM4 is down or hung — drive everything
low if it stops hearing from the CM4. That is a genuine watchdog, and `Hardware-IntelliRFIDv2.md`
§10 already flags "which watchdog owns CM4 recovery" as an open decision. This would settle it.

Against it: firmware in the output path, a second thing to update in the field, and **SAMD21 GPIOs
reset to floating inputs** rather than to a defined pull — so external pull-downs become mandatory
rather than merely wise.

### Route C — free up CM4 pins

`GPIO6/7` are UART3 CTS/RTS ("wired, flow control optional") and `GPIO17/27` are status LEDs. That is
**four pins**, at the cost of the LEDs. Not enough on its own, and not worth doing alone.

### Recommendation

**Route A for the new channels, and take Route B's watchdog anyway.** The expander carries the added
lights, status and aux inputs; the SAMD21 keeps supervising and can hold the whole field side safe
when the CM4 is not answering. Route C stays in the pocket if a couple of native pins turn out to be
needed.

---

## 4. The safety split — and why J26 must not change

**Keep the conveyor run and reverse lines on native CM4 GPIO ≥ 9. Do not move them to an expander or to the
SAMD21.** The conveyor-stops-on-any-failure property is a *hardware* property today: those pins are
in the BCM2711's pull-down reset group, so the outputs come up off with no software involved. An I²C
bus lockup leaves an expander's outputs in their last state, which for a speed command is the wrong
failure. The verdict lamps gate what an operator does with a pallet, so I would keep those native too.

Which leads to the cleanest thing about this proposal:

> **Leave J26 exactly as it is — 12-way, same pinout, same functions — and make everything new
> additive on a second connector.**

The existing PLC interface then needs no re-documentation, no re-wiring and no change to the PLC
program; a site running the current interface can take the new board unchanged. All the risk lives in
the new connector, which is the one nobody depends on yet.

**Strong suggestion: make the second connector structurally identical to J26** — 12-way, *7 outputs
+ FIELD_COM + 4 inputs*, same part, same convention, same documentation shape. It halves the
documentation, and an installer who has wired one has wired both. That is the argument for finding
47 mm rather than settling for the 8-way that fits today; if the span genuinely will not stretch, an
8-way as *4 outputs + COM + 3 inputs* is a reasonable fallback.

---

## 5. Proposed channel budget

Against what the tunnel actually wants:

| New channel | Why |
|---|---|
| Beacon: green / red / amber | Drive the stack light **directly** instead of asking the PLC to. This is the user's point and it removes the PLC from the visual-indication loop entirely. |
| Buzzer / audible | Same, if the site wants one |
| Status: reader healthy | Distinct from `HEARTBEAT`, which is a liveness toggle for the PLC |
| Status: over-temperature | The module reports temperature per PA enable via CC33; surfacing it as a contact is nearly free |
| Input: e-stop / permissive | Currently no way for the field to say "do not start a cycle" |
| Input: manual rescan | The `RESCAN_REQUEST` already proposed for J26 pin 12 |
| Input: mode select | Commissioning vs production, without a laptop |

That is 6 outputs and 3 inputs — comfortably inside a mirrored 12-way, with a spare each way.

**On driving lamps directly:** CR-1's photorelay recommendation already covers it (0.55 A against a
24 V LED beacon's 20–50 mA). Two things to confirm: that the beacons are **LED, not filament** —
filament lamps have a cold-inrush many times their running current — and that each lamp channel gets
its own protection, because driving a lamp means we now own its failure. **A shorted beacon should
take out a fuse or a PTC, not a channel.**

---

## 6. What else changes — and what does not

**Remove:** J22/J23, the four analog front ends, their four SMAJ33A, VDDANA filtering.
**Keep unchanged:** the SAMD21 and its supervisor role, the whole RF chain, power, J26.
**Fold in:** all of `Board-v3-Digital-IO-Change-Request.md` — CR-1 (photorelay outputs), CR-2 (field
TVS), CR-3 (per-channel LEDs) apply to the warehouse variant identically, and to the new connector's
channels as well.

**One thing not to relax.** A warehouse is a milder environment than trackside in most respects, so
some of the EN50155-driven margin can come off. **But not on the field side.** A conveyor's VFD
shares `FIELD_COM` with all our signal lines and is a *better* transient source than the original
analysis assumed — it is a switching converter with metres of motor cable acting as an antenna. Relax
the trackside-specific requirements; keep or increase the field-line protection.

**Band:** this variant is India-specific, so `RG_IN` (865–867 MHz) rather than the EU band the board
is currently described against. `INSTALLATION-SPEC.md` §8 already lists band and radiated-power limit
as open — this variant is the moment to close it.

---

## 7. Sequencing, and the honest cost

**Do CR-1 first, then fork the warehouse variant from it.** If the two run in parallel, the
photorelay output stage gets designed, reviewed and qualified twice. CR-1 is the expensive, risky
part; the warehouse changes on top are mostly subtraction plus one connector.

**The cost is variant management**, and it is real: two layouts, two BOMs, two build and test
procedures, two sets of documentation to keep synchronised — and this project has already been bitten
by documentation drift (the 2026-08-04 GPIO remap still has `RFID-DESIGN.md` showing `RFID_EN` on
GPIO23, which is now a field input). Two boards doubles that exposure.

Set against that: you already maintain a dozen board variants in this repo, so the machinery exists;
and the wheel-sensor block is genuinely dead weight in a warehouse — it is board area, four TVS, two
connectors and an ADC front end that can never do anything. **On balance the variant looks worth it**,
provided it is a fork of v3 rather than a parallel effort, and provided the GPIO map for both boards
is generated from the netlist rather than maintained by hand.

---

## 8. Open questions

1. 🔴 **What do `SDA0`/`SCL0` land on at the root sheet?** Route A rests on GPIO0/1 being free.
2. **Which edge are J22/J23 on**, and is the freed span contiguous with anything useful? Decides
   whether the second connector can be a mirrored 12-way or has to be an 8-way.
3. **Is the beacon LED or filament**, and what current per colour?
4. **Route A or B** for the added channels — or both, with the SAMD21 taking the watchdog either way.
5. Does the warehouse variant still need the **4 antenna ports** (2 populated today), or is 2 the
   permanent answer here? `RFID-DESIGN.md` records the revisit trigger as *field evidence of missed
   tags*, which the tunnel will produce quickly one way or the other.
6. Everything still open in `Board-v3-Digital-IO-Change-Request.md` §10 — above all the PLC and VFD
   input types, which set the real drive number behind CR-1.
