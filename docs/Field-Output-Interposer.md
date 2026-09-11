# Field-output interposer — small board beside IntelliRFIDv2

> **Superseded in premise, 2026-09-01.** This note was written when the Reliance tunnel was expected
> to have a PLC. **It does not: the reader drives the conveyor itself**, through the Tunnel Manager.
> References to a PLC below are the *context this was argued in*, not a description of the system —
> the current field interface is `com.intelli.rfid.tunnel.field.FieldChannel` and
> `docs/Tunnel-Interconnect.md`. Kept because the electrical reasoning is still sound.

**Short answer: yes, and it is the right fix.** A small interposer that plugs into **J26** and sits
beside the main board solves the drive-current problem completely, needs no rework of the existing
PCB, and — critically — **does not touch the product's isolation claim**, because it lives entirely
on the field side of the barrier that is already there.

Context: `Hardware-IntelliRFIDv2.md` §5 and `Tunnel-Interconnect.md`.
Status: **design note, no hardware built or measured.** Component values below are worked from the
board team's own guaranteed figures and are illustrative — final selection belongs to whoever draws
the board.

---

## 1. The problem, in one line

The seven field outputs are opto sinks whose drive is set by the TLP291-4's **guaranteed saturated**
transfer ratio, and at the hot corner that is **1.89 mA**.

Against the IEC 61131-2 sink-input ON-state requirements:

| Input type | Required | Board alone @ +85 °C | Board alone @ +25 °C |
|---|---|---|---|
| Type 1 | 2.0 mA | **1.89 mA — 5 % short** | 2.5 mA — passes |
| Type 3 | 2.5 mA | **1.89 mA — 24 % short** | 2.5 mA — exactly at the line |
| Type 2 | 6.0 mA | **1.89 mA — 3.2× short** | 2.5 mA — 2.4× short |

**And against a real PLC it is worse than the standard suggests.** Every Omron DC input family —
CP1E built-in, CJ1W-ID, NX-ID — specifies **ON at 3 mA minimum** and **OFF at 1 mA maximum**. Between
those lies a band where the input is guaranteed neither state. The board sits inside that band at
**−40 °C (2.3 mA), +25 °C (2.5 mA) and +85 °C (1.89 mA)** — i.e. **it cannot guarantee turning an
Omron input on at any temperature**, not merely when hot.

It will *appear* to work, because typical parts beat their minimums on both sides. That is the trap:
two typicals covering for each other with nothing in the specifications behind it, which is the most
expensive category of field fault there is.

(These are guaranteed minimums; typical parts do better. For a field product you design to the
guaranteed number.)

---

## 2. Why an interposer rather than anything else

**It sits after the isolation barrier.** The existing optos already provide the 2.5 kV impulse
separation, and J26 is on the field side of them. An interposer plugged into J26 is therefore purely
field-side signal conditioning: it adds no barrier, crosses no barrier, and **the product's isolation
claim is unchanged**. No new qualification, no change to `SURGE-EMC-REVIEW.md`'s conclusions.

**It needs no rework.** J26 is a pluggable terminal. The interposer carries the mating plug, and
presents its own field terminals to the panel. Nothing on the main board is cut, lifted or
re-stuffed, and the change is reversible — pull the interposer, plug the field wiring back into J26,
and you are exactly where you started.

**Options considered and rejected:**

| Option | Why not |
|---|---|
| Swap the 220 Ω LED resistors for 150 Ω | Gains ~40 % (→ ~2.7 mA hot). Still **cannot reach Type 2**, exceeds the BCM2711's 8 mA default pad drive, and is rework on every board — most of the pain of a change for none of the certainty. |
| Off-the-shelf DIN-rail interposing relay module | Relay coils are precisely the load the board doc excludes. A solid-state module's opto input still wants more than 1.9 mA guaranteed. Unlikely to find one specified low enough to trust. |
| Re-isolate on the interposer, tapping CM4 GPIO pre-opto | The GPIOs are consumed on-board; there is no header. Would require rework, and creates a **second** isolation barrier to qualify. Strictly worse. |
| Do nothing, hope the PLC is high-impedance | Possible! See §6 — but it is a bet on a number nobody has asked for yet. |

---

## 3. What the interposer must do

Non-negotiable, in priority order:

1. **Boost the seven outputs** to comfortably exceed the actual PLC/VFD requirement — design for
   ≥ 50 mA/channel even if 6 mA is needed, since the parts cost nothing and it ends the argument.
2. **Preserve the failsafe.** De-energised or unpowered — main board off, interposer off, or
   both — every output must be **OFF**, so `SPEED = 000` and the conveyor stops. This is the whole
   reason the board team put all seven outputs on GPIO ≥ 9. An interposer that inverts this is worse
   than no interposer.
3. **Preserve the polarity convention** (or deliberately change it — §4, Option B).
4. **Not overload the opto.** The interposer's own bias current must sit well inside 1.89 mA, at
   30 V field and +85 °C, with margin.
5. **Pass the four inputs through unchanged.** They are fine as they are — 1.6× margin at the
   tightest corner (16.8 V, +85 °C) per `IO-BLOCK-SIZING.md`. Do not "improve" them.

---

## 4. Two topologies

Both hang a pull-up on each `OUTn` so the opto's state becomes a voltage the interposer can act on.

**Pull-up sizing** (this is the number that keeps the opto happy):

| R_pu | Draw @ 30 V | Margin vs 1.89 mA | Dark-current drop @ +85 °C |
|---|---|---|---|
| 22 k | 1.36 mA | 1.4× | 1.10 V |
| **33 k** | **0.91 mA** | **2.1×** | 1.65 V |
| 47 k | 0.64 mA | 3.0× | 2.35 V |
| 100 k | 0.30 mA | 6.3× | 5.00 V |

**33 k–47 k** is the sweet spot: ~2–3× margin on the sink, while the guaranteed 50 µA dark current
still leaves the node solidly high when the opto is off.

### Option A — keep sinking outputs (NPN convention, as specified)

The opto node is *inverted* relative to "asserted", so exactly one inversion is needed.

```
+24V ──[33k]──┬── OUTn (from J26)
              └──[22k]── G  Q1 (small N-FET, e.g. 2N7002)
                            S → FIELD_COM, 100k G-S pulldown, 12V zener clamp
                         D ──[47k]── +24V
                            └── G  Q2 (output N-FET)
                                   S → FIELD_COM, 100k G-S pulldown, 12V zener clamp
                                   D → OUTn'  (boosted field output)
```

- Opto ON → `OUTn` low → Q1 off → Q1 drain high → **Q2 on, output sinks**. Non-inverting overall. ✅
- Opto OFF, or main board unpowered → `OUTn` pulled high → Q1 on → Q1 drain low → **Q2 off**. ✅
- **Interposer unpowered** → both pull-ups dead, Q2 gate held down by its 100 k → **Q2 off**. ✅

~9 parts per channel, ~63 total. No logic rail, no IC, and the failsafe is provable by inspection —
which for something in the conveyor's stop path is worth more than the part count saved.

**IC variant** if assembly count matters more: divide each `OUTn` down to logic level, through an
**octal inverting buffer** (74HC540 class), into a **TBD62003A** 7-channel DMOS sink array. Two ICs
plus a small 24→5 V rail. Prefer the DMOS array over a ULN2003: the Darlington's ~1 V saturation
drop eats into a 24 V input's threshold margin, where DMOS drops ~0.1–0.3 V. **Add pull-downs on the
array inputs** so a dead 5 V rail leaves the outputs off.

### Option B — sourcing outputs (PNP convention) — much simpler, if the PLC accepts it

```
+24V ──┬──[47k]──┬── G  Q1 (P-FET, S → +24V)
       │         └── 12V zener G-S clamp
       │    [33k] from G ── OUTn (from J26)
       └── S
            D → OUTn'  (boosted field output, sources to load, load returns to COM)
```

- Opto ON → gate pulled toward COM, clamped to −12 V → **P-FET on, output sources**. ✅
- Opto OFF → gate pulled to source, Vgs = 0 → **off**. ✅ Unpowered → off. ✅
- Opto load with 47 k / 33 k: **0.61 mA, 3.1× margin.**

**One FET and three passives per channel** — roughly a third of Option A. The catch: it converts the
outputs from sinking (NPN) to sourcing (PNP), which changes the field convention.

**This may be free.** Whether `FIELD_COM` is 0 V or +24 V is still open question 1 in
Nobody had committed to sinking when this was written. If the field devices want
sourcing outputs, Option B is simultaneously the simpler board **and** the only way this hardware can
deliver them at all. Ask before choosing a topology.

---

## 5. What else to put on it while it exists

The interposer is a natural home for three things the main board deliberately left out or cannot do:

- **🔴 Field-side surge protection.** `IO-BLOCK-SIZING.md` records this as *"Not included —
  deliberate, revisit at placement"*: the 11 J26 lines carry no TVS, held back purely for want of
  board area. The interposer has area. A conveyor and its VFD share the field ground and are an
  excellent transient source, and the part (SMAJ33A class) is already in the BOM. **Put a TVS on all
  11 lines** — 7 boosted outputs and the 4 pass-through inputs.
- **Per-channel commissioning LEDs.** `SOFTWARE-HANDOFF.md` §5 requires a loop test of all 11
  channels because *"the series protection resistors can fail open with no indication."* An LED per
  channel turns that from a procedure someone might skip into something visible from across the
  panel — and it makes a fault after commissioning diagnosable without a meter.
- **Headroom for the loads we were told not to drive.** Sizing Q2 for ~500 mA means a stack-light or
  a small relay coil wired directly to pins 5/6 by a well-meaning installer just works, instead of
  failing intermittently and hot.

**What NOT to put on it:** no microcontroller and no firmware. This board sits in the conveyor's stop
path; its behaviour should be readable off the schematic, with no software state and nothing to
update in the field. Keep it combinational.

---

## 6. The decision gate — we still do not know we need this

Everything above is downstream of a number nobody has asked the integrator for yet: **the IEC
61131-2 input type and actual input current of the PLC *and* the VFD** (`Hardware-IntelliRFIDv2.md`
§15, question 1).

- If both are genuinely high-impedance voltage-sensing inputs, the board drives them as-is and the
  interposer is unnecessary.
- If either is Type 2, or a typical VFD digital input at 5–10 mA, **the interposer is mandatory.**
- If either is Type 1 or Type 3, the board is *at* the threshold cold and *under* it hot — which
  argues for the interposer anyway, because the alternative is an intermittent seasonal fault.

**Recommendation: design it now, hold fabrication until that answer lands.** The design is a day's
work and the lead time is the schedule risk, not the effort. And if the answer comes back needing it,
**boost all seven channels uniformly** rather than only the four going to the VFD — a mixed board
where three channels behave differently is a maintenance trap that will outlive everyone who
remembers why.

---

## 7. Why off-the-shelf does not work — including SSRs

Asked directly, and the answer is clean: **1.9 mA sits below the floor of the industrial interface
market.** That whole product category exists to be driven *by* a PLC output — hundreds of
milliamps — so every part in it assumes the opposite of our situation.

| Category | Typical control-input current at 24 V | Verdict |
|---|---|---|
| DIN-rail **relay** interface modules (Phoenix PLC-RSC, Weidmüller TERMSERIES, Wago 788) | ~8–17 mA coil | ❌ 5–9× short |
| DIN-rail **SSR / optocoupler** modules (Phoenix PLC-OSC, Weidmüller SSR) | ~10 mA class — input network sized for a PLC output | ❌ |
| Panel-mount industrial **SSRs** (Crydom, Omron G3NA class) | ~5–20 mA | ❌ |
| **PhotoMOS / MOSFET-output optocouplers** — the most sensitive category there is | **AQY212EH: I_F(on) typ 1.2 mA, max 3.0 mA** | ⚠️ **still short** |

That last row is the one that settles it. A PhotoMOS is the lowest-input-current solid-state relay
technology available, and the arrangement is tempting: put its LED in series with a resistor from
+24 V down to `OUTn`, and our opto's sinking action lights it — one part per channel, non-inverting,
failsafe intact.

**But its *guaranteed* operate current is 3.0 mA, and we have 1.89 mA guaranteed.** Typical parts
(1.2 mA) would work fine, which is exactly the trap: it would pass every bench test and then fail on
the hot channels of the hot units. You do not ship a field product on a typical figure. (Worth a
parametric search on Digi-Key/Mouser filtered by *maximum* trigger current before closing this off —
if a PhotoMOS with a guaranteed I_F(on) ≤ 1.2 mA exists, it becomes a one-part-per-channel solution
and the simplest board on the table. I did not find one.)

### The underlying reason, which is worth internalising

**Everything optically coupled needs milliamps, because it has to light an LED. A MOSFET gate needs
essentially zero.**

Our opto cannot *source* meaningful current — but it can perfectly well *swing a node* between
~0.2 V and 24 V through a high-value pull-up, because that only costs it 0.6–0.9 mA. That is a
**voltage** signal, and a MOSFET gate is a capacitor that asks for no steady current at all.

So the fix has to be voltage-driven, not current-driven. That is not a preference for a custom board
— it is the only class of solution that works at this drive level, and it is why §4's topologies both
start by converting the opto's state into a voltage.

### One off-the-shelf route that *is* worth checking first

Not on our side — on theirs. Before building anything, ask whether:

- the **PLC** has (or can take) a high-impedance / Type 1 input card, or spare inputs configurable as
  such; or
- the **VFD** has a selectable low-current or NPN/PNP input mode.

If either is true, the problem disappears with no new hardware in our enclosure and no BOM at all.
It costs one question and it is the cheapest possible outcome, so ask it before ordering a board.

---

## 8. Expected size

**The connectors set the size, not the electronics.** From `V2-DESIGN.md`, J26 is a **Kangnex C35591
header + C18980 plug, 12-way at 3.81 mm pitch, 46.88 mm courtyard** (pin-1-to-pin-12 span is
definitionally 3.81 × 11 = 41.91 mm; the ~4.6 mm end allowance is assumed — the board team flagged
that every datasheet fetch 403'd, so **pull the real PDF before cutting any aperture**).

| Driver | Dimension |
|---|---|
| Connector courtyard (each) | 46.88 mm |
| Board width floor | ~50–55 mm |
| Connector depth on-board (each) | ~8–9 mm |
| Per-channel component column | 3.81 mm wide × ~25–30 mm (one channel per connector pitch) |

Laying one channel per 3.81 mm column, directly in line with its connector pin, gives a clean short
layout and sets the depth:

- **Option B (P-FET, 6 parts/channel + TVS + LED): ~55 × 50 mm.**
- **Option A (two-FET discrete, ~11 parts/channel): ~65 × 60 mm.**
- **Option A IC variant** (74HC540 + TBD62003A + 5 V rail): similar to B, ~60 × 60 mm.

Call it a **60 × 60 mm 2-layer board** as a planning figure — roughly a coaster. Comfortable rather
than tight, and there is no reason to fight for smaller.

**Two levers that actually move the number:**

- **The TVS package.** SMAJ33A in SMA/DO-214AC is 5.3 × 2.6 mm; eleven of them is the single largest
  area consumer on the board. An SOD-123FL part (SMF33A class, ~200 W versus 400 W) is 2.7 × 1.6 mm
  and would shrink the board noticeably. The 400 W part was chosen for a *trackside* environment with
  traction return currents; a warehouse conveyor is a milder case, and the smaller part is probably
  adequate — worth asking the board team rather than defaulting.
- **Whether the four inputs pass through.** As bare copper they cost no area, but they decide whether
  the output-side connector is 12-way or 8-way.

**⚠️ The installed envelope is much larger than the PCB.** 3.81 mm pluggable terminals need wire-bend
and screwdriver space — budget **25–40 mm clear in front of each connector face**. A 60 × 60 mm board
with terminals on opposite edges wants roughly **60 × 130 mm of panel space**. That, not the PCB, is
what has to fit beside the main board.

**⚠️ A connector-availability trap, straight from `V2-DESIGN.md`.** The Kangnex plug range runs
2, 3, 4, 5, 6, 7, 8 and then jumps to **12, 13, 15, 17, 18** — there is **no 14-way plug**. So do not
design an output side of "12 signals + 24 V + 0 V" as a single 14-way terminal. Use a **12-way plus a
separate 2-way** for the supply feed. The board team already lost time to the same class of mistake
(a 10-way header exists with no matching 10-way plug), and their rule stands: **always confirm the
plug exists, not just the header.**

Also inherit their derating: LCSC lists Kangnex at 8 A / 300 V while the dimensionally identical
Degson 15EDGRC-3.81 is rated 7 A / 250 V. **Design to the lower.**

---

## 9. What it actually takes to build

### 9.1 Per-channel circuit and part count

**Option B (sourcing) — the smaller one**

| # | Part | Value / class |
|---|---|---|
| 1 | R_pu | 47 kΩ 0805 — +24 V to gate |
| 2 | R_s | 33 kΩ 0805 — gate to `OUTn` |
| 3 | D_z | 12 V zener SOD-323 — gate-source clamp (Vgs would otherwise exceed ±20 V) |
| 4 | Q1 | P-channel MOSFET, SOT-23, **≥ 60 V**, current class per §9.2 |
| 5–6 | LED + R | commissioning indicator (§5) |
| 7 | TVS | on the field output line |

**7 parts × 7 channels = 49**, plus 4 TVS on the pass-through inputs ≈ **53 components**.

**Option A (sinking) — one inversion stage, so roughly double**

Adds a second FET, a second gate pull-down, a second clamp and a second pull-up per channel:
**~11 parts × 7 = 77**, plus 4 ≈ **81 components**.

Both plus: 2 × 12-way connectors (in from J26, out to field), 1 × 2-way for the +24 V / 0 V feed.

### 9.2 The one part choice that needs an answer first

The output FET's current rating depends on what it will ever drive:

| If the outputs only ever drive… | FET class | Note |
|---|---|---|
| PLC inputs (Omron: 3 mA min, 7.5 mA typ) | 60 V, ~0.2 A SOT-23 | 20× margin, cheapest |
| PLC inputs + a VFD input (5–10 mA) | 60 V, ~0.2 A SOT-23 | still comfortable |
| **+ any chance of a lamp or relay coil** | 60 V, **≥ 0.5 A** | and **add a fuse or PTC per channel** — driving a lamp means we own its failure |

**Recommend the 0.5 A class regardless.** The price difference is cents, and it removes the failure
mode where a well-meaning installer wires a stack-light straight to pin 5 and it works for a month.

### 9.3 Cost and effort

| | |
|---|---|
| BOM | **~$8–15 per board** at low volume — **dominated by the three connectors**, not the silicon |
| PCB | 2-layer, ~60 × 60 mm — a few dollars each in small quantities |
| **Unit cost** | **~$20–25** all in, at the quantities this will be built in |
| Design effort | **1–2 days** schematic + layout for this team — it is ~53 parts on 2 layers with no high-speed anything |
| Lead time | fab + assembly, **~2–3 weeks** to hardware in hand |

**The lead time is the schedule risk, not the effort.** That is the whole argument for drawing it now
and holding fabrication until the input-spec answer lands (§6).

### 9.4 Acceptance — the same three that matter for CR-1

1. **≥ 50 mA at ≤ 1 V drop**, all seven asserted simultaneously, at **+55 °C**.
2. **With the main board unpowered, every output OFF — measured, not reasoned.** This is the conveyor
   stop path, and it is the one test that must not be skipped.
3. No output glitch during the rise or fall of the 24 V rail.

Plus a loop test of all 11 channels end to end, for the reason `SOFTWARE-HANDOFF.md` §5 gives: the
series protection resistors can fail open with no indication.

### 9.5 Interposer or v3 — they are not either/or

The interposer covers **boards that already exist**; CR-1 fixes it **at source** for the next lot.
Which you need depends on one number nobody has stated yet: **how many v2 boards are already built,
in stock, or committed to a build?**

- **Few or none, and the next lot is imminent** → skip the interposer, do CR-1, wait.
- **Boards in the field or in stock** → the interposer is the only option for those units, and it is
  worth building even if v3 also happens.
- **Both** → build the interposer for the existing fleet and CR-1 for everything after; they do not
  conflict, and the interposer's circuit is a rehearsal of the fallback topology in CR-1 anyway.

---

## 10. Open questions for the board designer

1. **Sinking or sourcing** (Option A vs B) — blocked on the same integrator question.
2. **Mechanical**: is there room beside the main board inside the enclosure, and does the field wiring
   still reach? Also, the interposer is at `FIELD_COM` potential, which *"can float at hazardous
   potential relative to board ground"* — it must be mounted so it creates no new path between the
   field domain and the chassis/board ground.
3. **Connector**: J26's exact part and mating plug from the 3.81 mm family in
   `CONNECTOR-FAMILY-DECISION.md` — and note that family had a stock scare, so second-source it.
4. **The four inputs — revised recommendation.** I previously said route them *past* the interposer
   so an interposer failure could not take out the read trigger. On reflection **route them
   *through*, as bare copper with no components on them.** Splitting the field wiring across two
   terminals undoes the single-connector decision the board team made deliberately (and fought a
   connector-availability trap to keep). With no parts in the input path, the only added risk is two
   more connector contacts per channel — the same risk any connector carries — rather than a
   component failure. That is the better trade.
5. **Field supply feed**: the interposer needs +24 V and 0 V from the *same single field supply* that
   `INSTALLATION-SPEC.md` §5 already mandates for all J26 devices. Two extra terminals.
6. Does this become a permanent part of the product, or a bridge until a v3 main board folds the
   MOSFETs in? That decides how much polish it earns.
