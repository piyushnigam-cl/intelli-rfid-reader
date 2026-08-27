# Change request — digital I/O, IntelliRFID v3

**To:** whoever draws the next revision of `intelli-rfid-v2`
**From:** the tunnel software side
**Date:** 2026-08-22 · against hardware rev `0861de5`
**Status:** requirement change, for the next lot. Nothing here has been built or measured.

Everything below traces to your own documents — `IO-BLOCK-SIZING.md`, `V2-DESIGN.md`,
`SOFTWARE-HANDOFF.md`, `RFID-DESIGN.md`. Where a number came from a vendor page instead, it says so.

---

## 1. Why this is coming now

v2 was designed for the **wayside** case and the docs say so explicitly: few tags, long range,
RF_MODE 13, sensitivity over read rate, `UART stays at 115200`. That was the right call for the
application in front of you.

The board is now also going into a **retail warehouse tunnel**: ~40 tags per box, short range, a
conveyor, a PLC and a VFD, and a hard requirement that a box is read in ~5 seconds rather than 10.
Two of v2's decisions land differently in that application, and one of them is a blocker.

Nothing here says v2 was wrong. It says the second application has different edges.

---

## 2. 🔴 CR-1 — Field output drive capability (blocker)

### The requirement

**Each of the field outputs shall sink or source at least 50 mA continuous at ≤ 1 V drop, on all
channels simultaneously, over the full −20…+55 °C ambient range, guaranteed by specification rather
than by typical figures.**

### Why

Per `IO-BLOCK-SIZING.md`, drive is set by the TLP291-4's **guaranteed saturated** transfer ratio
(30 %), giving **2.3 mA at −40 °C, 2.5 mA at +25 °C and 1.89 mA at +85 °C**.

### Measured against real PLC inputs, not just the standard

We went and read the Omron datasheets, because Omron is the likely PLC family here. **Every Omron DC
input family specifies the same ON threshold: 3 mA minimum.**

| Omron unit | Input current, typ | **ON: min current** | OFF: max current | Transistor output |
|---|---|---|---|---|
| CP1E built-in DC input | 7.5 mA | **3 mA at ≥ 17.0 V** | 1 mA at ≤ 5.0 V | 0.3 A/point, 0.9 A/common |
| CJ1W-ID211 (16-pt) | 7 mA | **3 mA at ≥ 14.4 V** | 1 mA | — |
| CJ1W-ID231/232/233/261/262 | 4.1 mA | **3 mA at ≥ 19.0 V** | 1 mA | — |
| NX-ID standard | 6 mA | **3 mA** | 1 mA | — |
| NX-ID fast-response | 3.5 mA | **3 mA** | 1 mA | — |
| NX-OD transistor output | — | — | — | 0.5 A/point, 1–8 A/unit |

**This is worse than the earlier IEC comparison suggested, and the conclusion has to be restated.**

Between Omron's OFF maximum (1 mA) and ON minimum (3 mA) lies a band in which the input is
**guaranteed neither on nor off** — the manufacturer simply does not define behaviour there.

**Our output sits inside that band at every temperature in the operating range:**

| | Board can sink | vs Omron 3 mA ON minimum |
|---|---|---|
| −40 °C | 2.3 mA | ✗ short |
| **+25 °C** | **2.5 mA** | **✗ short — at room temperature** |
| +85 °C | 1.89 mA | ✗ short |

So the earlier framing — "it works cold and fails hot" — was too generous. On guaranteed numbers,
**this board cannot turn on an Omron DC input at any temperature.** It will *appear* to work, because
typical parts beat their guaranteed minimums and a typical Omron input will trip below its specified
threshold, and that is precisely the trap: two typicals covering for each other, with nothing in the
specifications backing it up.

For completeness against the standard: IEC 61131-2 sink-input ON current is 2.0 mA (Type 1), 2.5 mA
(Type 3), 6.0 mA (Type 2). We fail all three at +85 °C, and Type 2 and 3 at every temperature.

Your own note already says this will not drive a relay coil, a lamp, a contactor or a Type 2 input.
The tunnel adds a case that note did not have to consider: **three outputs carry a 3-bit conveyor
speed command and one carries direction, most likely into a VFD digital input, and VFD inputs
commonly draw 5–10 mA.** A conveyor that ignores a speed command intermittently is the worst version
of this.

**For scale on the other side of the same interface:** an Omron transistor output drives **0.3 A**
(CP1E) to **0.5 A** (CJ/NX) per point. That is 160–265× what our output can do, and it is why nothing
in the industrial interface catalogue is designed to be driven at our level — the whole ecosystem
assumes a source like that one.

We also checked whether it could be solved outside the board and it cannot: **1.9 mA sits below the
floor of the industrial interface market**, which exists to be driven *by* PLC outputs. DIN relay
modules want 8–17 mA, DIN SSR modules ~10 mA, panel SSRs 5–20 mA. Even a PhotoMOS — the most
sensitive category there is — specifies a *maximum* operate current of 3.0 mA. There is nothing to
buy that works at this drive level.

### Recommended implementation — swap the output optocouplers for photorelays

This looks like the cleanest change available, and it is close to a footprint swap rather than a
redesign:

**Replace the three TLP291-4 quads on the seven output channels with one photorelay per channel
(MOSFET-output optocoupler), and keep one TLP291-4 for the four inputs unchanged.**

Worked against Panasonic **AQY212EH** as a representative part (vendor page, verified 2026-08-22):

| Parameter | AQY212EH | Consequence |
|---|---|---|
| LED operate current | typ 1.2 mA, **max 3.0 mA** | **The existing 220 Ω is unchanged.** GPIO at ~3.0 V gives 6.8–8.0 mA depending on V_F → **2.3–2.7× margin** on the guaranteed max, still inside the 8 mA BCM2711 default pad drive |
| LED max current | 30 mA | 8 mA is comfortable |
| Load | 60 V, **0.55 A**, R_on ≤ 2.5 Ω | 250 mV drop at 100 mA. Exceeds the 50 mA requirement by 10× |
| **I/O isolation** | **5000 Vrms** | **Better than the TLP291-4's 2500 Vrms — the isolation analysis improves rather than degrades** |
| Output | bidirectional MOSFET pair | **Sinking or sourcing purely by wiring** |
| Package | DIP4 (SMD variants exist) | ~7 × SOP-4 ≈ 130 mm² vs the 2 quads it replaces ≈ 150 mm² — **area-neutral** |

Four things fall out of this that are worth naming, because they are why this is the recommendation
rather than just an option:

1. **The isolation architecture is untouched, and improves.** No change to the 2.0 mm spacing, the
   basic-insulation claim, or anything in `SURGE-EMC-REVIEW.md`. A part with a *higher* component
   rating replaces a lower one.
2. **The existing 220 Ω LED resistors stay.** The drive-side circuit does not change at all.
3. **It settles the sinking/sourcing question for free.** A bidirectional MOSFET output can be wired
   either way, so the field convention stops being a decision that has to be right before layout.
   Given that whether `FIELD_COM` sits at 0 V or +24 V is *still* an open question with the
   integrator, this removes a schedule dependency.
4. **Cost is roughly +$10 per board** (7 photorelays at ~$1.50 against two extra quads). Negligible at
   this volume, and it retires an entire class of field fault.

**Must verify before committing:** the I_F(on) *temperature* curve. Our 2.3–2.7× margin is against
the +25 °C maximum; photorelay operate current rises at cold, and the spec must still hold at
−20 °C. If it does not, raise the LED drive — there is headroom to 30 mA, though the BCM2711's
8 mA default pad drive then becomes the constraint and would need a `config.txt` change.

**Fallback if photorelays do not suit:** keep the TLP291-4 and add a field-side MOSFET stage per
output channel — roughly 1 FET + 3 passives each. This is what an external interposer would have
done; folding it onto the board is strictly better. It is ~30 more parts than the photorelay route
and it does not solve the sinking/sourcing question, which is why it is the fallback.

**Whichever route:** boost **all seven channels uniformly.** A board where three channels behave
differently from the other four is a maintenance trap that outlives everyone who remembers why.

---

## 3. CR-2 — Field-side surge protection on all 11 lines

`IO-BLOCK-SIZING.md` records this as *"Not included — deliberate, revisit at placement"*, held back
purely for want of area next to three optos and fifteen resistors.

**Two things have changed.** The photorelay swap in CR-1 frees comparable area, and the tunnel puts a
**conveyor and its VFD on the shared field ground** — a considerably better transient source than the
original analysis assumed. A VFD is a switching converter with metres of motor cable acting as an
antenna, sharing `FIELD_COM` with our 11 signal lines.

**Ask:** TVS on all 11 field lines. The part is already in the BOM (SMAJ33A on the wheel-sensor
inputs), so no new line. If area is still tight, note that the 400 W SMA part was chosen for a
*trackside* environment with traction return currents; a warehouse conveyor is a milder case and an
SOD-123FL part (~200 W, 2.7 × 1.6 mm against 5.3 × 2.6 mm) may well be sufficient. **Your call — we
are flagging the environment change, not specifying the part.**

---

## 4. CR-3 — Per-channel status LEDs on the field I/O

`SOFTWARE-HANDOFF.md` §5 requires commissioning to loop-test all 11 channels because *"the series
protection resistors can fail open with no indication, so an untested channel may be silently dead."*

An LED per channel turns that from a procedure someone might skip into something visible from across
the panel, and makes a *post*-commissioning failure diagnosable without a meter or a laptop. For the
seven outputs the LED can sit on the field side in series with the load; for the four inputs, across
the opto LED.

Low priority against CR-1, but it is cheap and it directly serves a hazard your own documentation
already calls out.

---

## 5. CR-4 (conditional) — one more I/O channel, if the connector allows

The tunnel drives conveyor speed as **three parallel bits**, and GPIO bits do not change atomically:
stepping 4 → 3 can transiently present 7 (`100` → `111` → `011`) depending on write order. On a
conveyor that is a real hazard, and the clean fix is a **strobe line** the PLC latches on.

Checking whether it fits, using your own numbers (12-way courtyard 46.88 mm in a 55.47 mm south-edge
span):

| Ways | Courtyard | Slack | Plug exists? |
|---|---|---|---|
| 12 (current) | 46.88 mm | +8.59 mm | ✅ |
| **13** | **50.69 mm** | **+4.78 mm** | ✅ |
| 14 | 54.50 mm | +0.97 mm | ❌ **no 14-way plug** |
| 15 | 58.31 mm | −2.84 mm | ✅ but does not fit |

**13-way is the only step up that both fits and has a matching plug** — the Kangnex plug range runs
2–8 then jumps to 12, 13, 15, 17, 18, exactly the trap `V2-DESIGN.md` records for the 10-way.

**This is your call, not ours.** It halves the edge slack from 8.59 mm to 4.78 mm, and you have
already recorded that thin slack makes field wiring unpleasant to land. **Only take it if the strobe
turns out to be needed** — which depends on whether the PLC latches the speed bits or reads them
asynchronously, still an open question with the integrator. If they latch on their own strobe, or if
we constrain the software to single-step speed changes, 12-way stays.

---

## 6. CR-5 / CR-6 (secondary) — the two RF decisions that were wayside-shaped

Neither blocks anything. Both are worth reconsidering while the board is open, because they were
correct for wayside and are backwards for the tunnel.

**CR-5 — the 570 kHz buck.** `SOFTWARE-HANDOFF.md` §8 records that SILION asks for > 1.5 MHz, and
that ripple puts sidebands **±570 kHz from the carrier, inside the Gen2 backscatter BLF band
(160–640 kHz)**, with the stated mitigation being *"prefer RF_MODEs whose BLF avoids 570 kHz — the
long-range low-BLF modes the trackside case wants anyway."*

The tunnel wants the opposite end: high tag count, short range, read rate is the entire requirement,
which points at **FM0 at BLF 640 kHz** — the mode sitting closest to the 570 kHz sideband. So the
firmware mitigation that was free for wayside costs us the thing we most need. **If a > 1.5 MHz
switcher is feasible in the next spin, it removes a constraint that is otherwise permanent for this
application.**

**CR-6 — UART headroom.** `RFID-DESIGN.md` fixes the link at 115200 with an explicit rationale: the
E710's fast modes want 921600 (RF_MODE 103/11) or 460800 (120/1), *"but the intended trackside case
is few tags, long range = RF_MODE 13, which needs only > 57600."* The module is specified at
**> 1000 tag/s** for 96-bit EPCs; at ~30 bytes per report that is ~30 kB/s against 11.5 kB/s
available, so **at full fast-mode rate the host link, not the air interface, is the bottleneck.**

We can mitigate in software first — keeping the uplink small by letting the module aggregate repeat
sightings rather than streaming raw reads — and we will do that before asking for anything. But the
datasheet's warning that **UART edges couple into the receiver and desense it** is the reason we
cannot simply raise the baud ourselves. **If the next spin can improve that coupling (series
termination, slew limiting, routing, or guarding those two traces), it turns a hard limit into a
tuning knob.**

---

## 7. What must NOT change

These are load-bearing and several were hard-won. Please carry them forward explicitly.

| Keep | Why |
|---|---|
| **All field outputs on GPIO ≥ 9** | BCM2711 resets those pull-DOWN, so outputs come up **OFF**. On the tunnel this means `SPEED = 000` → conveyor stopped on any reader failure. Your note — *"do not ever move a field output onto GPIO2–8"* — now guards a moving conveyor. |
| **10 kΩ input pull-ups** | Beats the ~50 kΩ internal pull-down (2.75 V) so all four inputs read *inactive* at boot regardless of reset group, and keeps the 50 µA dark-current drop harmless. Both constraints in `IO-BLOCK-SIZING.md` still bind. |
| **The input chain exactly as it is** | 6.8 kΩ series, worst corner 16.8 V at +85 °C, **1.6× margin** — verified, adequate. Do not "improve" it. |
| **One connector, one FIELD_COM** | The single-connector decision, and the installation rule that all field devices share one 24 V source and return. |
| **RFID_EN pull-down (reader disabled at boot)** | No RF before software decides. |
| **Opto isolation, 2.0 mm spacing, basic insulation / 2.5 kV impulse** | CR-1 raises the component rating; it must not disturb the spacing that actually sets the system claim. |

One thing we considered asking for and are **not**: routing the field zone sensors to the module's
own IN1/IN2 so the SIM7500's hardware GPI trigger becomes usable from the PLC. We costed it — a
host-side GPIO interrupt instead is single-digit milliseconds against a 5-second budget, and the
start-up latency we actually cared about is solved by keeping the module configured and warm. **Not
worth board area.**

---

## 8. Acceptance criteria

CR-1 is done when, on a built board:

1. Every one of the seven outputs sinks (or sources) **≥ 50 mA at ≤ 1 V drop**, with all seven
   asserted simultaneously, at **+55 °C ambient**.
2. The same holds at **−20 °C** — this is the corner where photorelay operate current is worst, and
   the one a bench test at room temperature will miss.
3. **With the main board unpowered, every output is OFF.** Measured, not reasoned — this is the
   conveyor stop path.
4. The same is true through a **full power-cycle transient**: outputs must not glitch on during the
   rise or fall of the 24 V rail.
5. Isolation testing shows **no degradation** against the v2 result.
6. The four inputs behave exactly as v2 at 16.8 V / +85 °C.

Please also confirm (7) the **as-built GPIO map from the netlist**, not from a document. The
2026-08-04 remap is still catching people — `RFID-DESIGN.md` continues to show `RFID_EN` on GPIO23
and `RFID_NRST` on GPIO24, which are now field inputs IN1 and IN2. Code written from the stale map
drives two field inputs as outputs while believing it is enabling the reader.

---

## 9. Priority

| | Change | Status |
|---|---|---|
| 1 | **CR-1** field output drive | 🔴 Blocker for the tunnel application |
| 2 | **CR-2** field-side TVS | Strongly recommended — environment has changed |
| 3 | **CR-3** per-channel LEDs | Cheap, serves a hazard already documented |
| 4 | **CR-5** buck > 1.5 MHz | Worth it if feasible; otherwise a permanent RF-mode constraint |
| 5 | **CR-6** UART coupling | Worth it if cheap; software mitigates first |
| 6 | **CR-4** 13th channel | **Conditional** — only if the PLC needs a strobe |

## 10. Open questions that gate this

1. **Which PLC family, and the VFD's input specification.** Partly answered now: if it is Omron —
   CP1E, CJ or NX — the requirement is **≥ 3 mA guaranteed with ≥ 14.4 V at the terminal**, and the
   50 mA target in CR-1 clears it by 16×. The VFD is still unknown and is the more demanding of the
   two. **The 50 mA figure is our recommendation for a number that ends the argument permanently, not
   a customer specification.**
2. **Sinking or sourcing** — is `FIELD_COM` 0 V or +24 V? Open with the integrator. The photorelay
   route in CR-1 makes this a wiring choice rather than a layout decision, which is a good reason to
   prefer it.
3. **Does the PLC latch the speed bits on a strobe, or read them asynchronously?** Gates CR-4.
4. **Deployment band.** The board is described as EU-band 866 MHz; the tunnel targets **`RG_IN`
   865–867 MHz**, and `INSTALLATION-SPEC.md` §8 already lists the band and radiated-power limit as
   open. Please confirm the front end and certification path are right for India before this lot.
