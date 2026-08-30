# IntelliRFIDv2 ⇄ Delta DVP-12SA2 — I/O integration

**Written 2026-08-29.** Device facts and their provenance live in
`ExternalSystems/Delta-DVP-SA2/DVP-SA2-SUMMARY.md` (digested from Delta doc
**DVP-0180030-01**, 2020-12-16, which is saved beside it). This file is only the
*interface*: what connects to what, whether it actually works, and with how much
margin.

Board side: `V2-DESIGN.md` §Connector (J26 pinout), `IO-BLOCK-SIZING.md` (the
TLP291-4 arithmetic), `INSTALLATION-SPEC.md` §5 (single field supply).

---

## 0. The four answers, up front

| Question | Answer |
|---|---|
| Which variant? | 🔴 **DVP12SA211R (relay).** The **T (NPN) variant cannot drive our inputs at all** — see §3. |
| Do our outputs drive its inputs directly? | **Yes, on guaranteed numbers, with 1.3–1.7× current margin** — and by a mechanism that did *not* work for the Omron that motivated the interposer. See §2. The deciding variable is the **rfid-v2 enclosure temperature**, not the PLC's. |
| Does it fit? | 7 OUT → 8 X (1 spare). 4 IN ← 4 Y (**zero spare**). Signal-by-signal map in §4. |
| What are the channels *for*? | Warehouse tunnel management — a 3-bit conveyor speed code, direction, a read result, plus one spare out and two spare in. §4.0–4.2. **The board drives PLC inputs only; the PLC talks to the VFD.** |
| Anything that breaks the system? | 🔴 The PLC is rated **0–55 °C, non-condensing, open-type**. IntelliRFIDv2 is an EN50155 −40…+85 °C design. See §6. |

> ★ **Decided 2026-08-29 (user): DVP12SA211R bought, wired DIRECT — no
> interposer.** The wiring list the panel builder needs is at the end of §4. Two
> items are now load-bearing rather than advisory, because nothing downstream
> boosts the signal: the **V_CE measurement at commissioning** (§2) and the
> **earthing of the 24 V negative rail** (§5) — the latter answered the same day,
> **0 V floating**, which is the outcome the isolation needs.

---

## 1. The two sides

**IntelliRFIDv2, connector J26 (Kangnex C35591 header + C18980 screw plug):**

| Pin | 1–7 | 8 | 9–12 |
|---|---|---|---|
| | OUT1…OUT7 | **FIELD_COM** | IN1…IN4 |

- **OUT1–7** — TLP291-4 phototransistor, **open-collector NPN sink**. Collector on
  OUTn, emitter on FIELD_COM. Drive is I_F ≈ 8.3 mA from a CM4 GPIO through 220 Ω.
- **IN1–4** — TLP291-4 LED anode on INn through **6.8 kΩ**, cathode on FIELD_COM.
  **Requires +24 V applied to INn.** Active-low at the GPIO (24 V present ⇒ GPIO LOW).
- **FIELD_COM** is the field supply **0 V**, shared by all 11 channels.
- All 11 lines carry an **SMAJ33A** TVS, cathode on the line, **anode on FIELD_COM**.

**DVP12SA2:** X0–X7 in (24 V, 4.7 kΩ, ON > 15 V, OFF < 5 V), Y0–Y3 out,
one S/S input common, one output common (C0 on the relay model).

---

## 2. OUT1–7 → X0–X7 — the direct-drive case, and why it works here

### Wiring

> **S/S strapped to +24 V. OUTn wired to Xn. FIELD_COM wired to the supply 0 V
> (the PLC's 24G).** Delta calls this **SINK mode** (instruction sheet Figure 5).

Never write only "sink mode" on a drawing — write the physical statement. The
word is used both ways round in the field, and reversing S/S produces a system in
which nothing ever turns on and nothing reports a fault.

### The key number: the ON threshold costs 2.94 mA, at whatever V_CE you like

The PLC input is +24 V → 4.7 kΩ → internal LED (≈1.2 V) → X. Turn-on is specified
as a **voltage across the input point**, U_in > 15 V, so the current at the
threshold is:

> I_threshold = (15 − 1.2) / 4.7 kΩ = **2.94 mA**, **independent of supply voltage** —
> a higher supply raises the demand current *and* the allowed V_CE by the same amount.

What changes with supply is the **V_CE headroom** the opto is allowed to sit at:

| Field supply | V_CE allowed while still reading ON |
|---|---|
| 20.4 V (min legal) | **≤ 5.4 V** |
| 24.0 V (nominal) | ≤ 9.0 V |
| 28.8 V (max legal) | ≤ 13.8 V |

### 🔴 This is the difference from the Omron case

`../intelli-interposer/INTERPOSER-DESIGN.md` §1 records the bind: an Omron input's
**U_low = 5 V** means the closed output must sit *well below* 5 V, i.e. inside the
0.4 V–5 V band where the TLP291 datasheet **guarantees nothing**. Only the deep-
saturation ratio (30 %, → 1.9 mA at +85 °C) was usable, and it was not enough.

Delta's input does not ask for that. **ON is granted at any V_CE up to 5.4 V even
at the minimum legal supply** — which is the exact point where the rank-GB CTR
guarantee *does* apply. The unguaranteed band is no longer in the way.

### The margin, from guaranteed numbers only

| Step | Value | Source |
|---|---|---|
| I_F | (3.0 − 1.18)/220 = **8.27 mA** | `IO-BLOCK-SIZING.md` |
| Rank GB: CTR ≥ 100 % at I_F = 5 mA, V_CE = 5 V | I_C ≥ 5 mA @ 25 °C | **GUARANTEED**, and I_C is monotone in I_F, so 8.27 mA cannot give less |
| ×0.76 (+85 °C) | I_C ≥ **3.8 mA** | traced Fig. 11.13, *not* guaranteed |
| ×0.86 (+60 °C, the real enclosure corner) | I_C ≥ **4.3 mA** | ditto |
| Required | **2.94 mA** | above |

| Corner | Margin |
|---|---|
| +25 °C | **1.70×** — fully guaranteed |
| +60 °C (50 °C ambient + 10 °C enclosure rise) | **1.46×** |
| +85 °C | **1.29×** |

### Where it stops being comfortable — state this honestly

LED light output degrades **10–30 % over life**. Applying that to the hot corner:

| | +60 °C | +85 °C |
|---|---|---|
| Fresh | 1.46× | 1.29× |
| −10 % aged | 1.31× | 1.16× |
| **−30 % aged** | **1.02×** | **0.90× — fails** |

So: **direct drive is sound for a benign installation and it is genuinely better
than the Omron case, but it is not sound at end-of-life at +85 °C.** The
`intelli-interposer` remains justified for exactly the reason it was built —
margin insurance in a stop path — not because the DVP cannot be driven.

🔴 **Corrected 2026-08-29.** An earlier version of this file said the +85 °C row
was pessimistic "because the PLC is only rated to 55 °C, so a cabinet that keeps
the PLC legal keeps the opto near +60 °C." **That is only true if the two share
one enclosure — which is the arrangement §6 recommends against.** The opto is on
*our* board. In the preferred split arrangement (PLC in a controlled panel,
IntelliRFIDv2 trackside) the board is free to reach +85 °C internal while the PLC
sits at 25 °C. **Which temperature row applies is set by the rfid-v2 enclosure,
never by the PLC's.**

### 🔴 No board change improves the *guaranteed* figure

Worth knowing before anyone proposes dropping R61–R67 to buy margin: Toshiba
specifies CTR only at **I_F = 1 mA and 5 mA**. The strict guarantee is therefore
**I_C ≥ 5 mA at 25 °C however hard the LED is driven** — raising I_F above 5 mA
buys *typical* margin and aging headroom, but not one milliamp of guaranteed
margin. (It would also need a `config.txt` GPIO drive-strength change; 220 Ω
already sits at the 8 mA pad default.) The 1.29× is what it is.

### The one measurement that retires the whole question

**Measure V_CE across a closed output at commissioning** (OUTn to FIELD_COM, PLC
wired and powered). The §2 margin is a bound, not a prediction — if V_CE comes
back near **0.5 V** the transistor is in deep saturation, nowhere near its current
limit, and the aging derate has enormous room to eat. If it comes back near
**5 V** the load line really is sitting at the guarantee anchor and the aged rows
above are live. One reading, and the argument is over.

### OFF state — no issue

Dark current is **GUARANTEED ≤ 50 µA at +85 °C**. Through 4.7 kΩ that is 0.24 V,
so U_in sits under 1 V against a 5 V OFF limit. It would take **> 1 mA** of
leakage to threaten a false ON, i.e. 20× the guaranteed maximum.

### Supply extremes vs the TVS

SMAJ33A standoff is 33 V against the PLC's maximum legal 28.8 V — clear, and the
TVS never conducts in normal operation.

---

## 3. Y0–Y3 → IN1–IN4 — 🔴 this is what fixes the variant choice

Our input needs **+24 V applied to INn**, returning through FIELD_COM. Nothing
else energises it: the LED's cathode is hard-wired to pin 8.

| PLC variant | Output | Can it apply +24 V to INn? |
|---|---|---|
| **DVP12SA211R** | relay dry contact | ✅ **Yes** — wire **C0 to +24 V**, Y0–Y3 to IN1–IN4 |
| **DVP12SA211T** | transistor **NPN, sinking** | ❌ **No.** An NPN output can only pull its terminal down to 0 V. It cannot source. |
| DVP28SA211S | transistor **PNP, sourcing** | ✅ Yes (16 IN / 12 OUT, if the bigger unit is wanted) |

> **There is no PNP transistor variant in the 12-point size.** For a DVP-**12**SA2
> the choice is **relay or nothing**. Choosing 12SA211T would need four external
> interposing relays to invert each output — more parts, more panel space and more
> failure modes than simply buying the R.

### The relay case checks out

| Check | Number | Verdict |
|---|---|---|
| Our load current | 24 V / 6.8 kΩ ≈ **3.36 mA** (2.30 mA at 16.8 V, 4.24 mA at 30 V) | |
| Relay **minimum load** | **1 mA / 5 V** | ✅ 3.4× above it — enough wetting current that contact oxide is not a concern |
| Relay maximum load | 1.5 A/point, 4 A/common | ✅ irrelevant, we are 450× under |
| Working voltage | 5–30 VDC | ✅ 24 V |
| Response | ≈ 10 ms | ✅ fine — these are permissive/status signals, and our own firmware debounces ≥ 10 ms anyway |
| Common | **all four Y share C0 on the 12-point relay model** | ✅ matches our single shared FIELD_COM exactly — one wire from C0 to +24 V serves all four |

The single-C0 arrangement and our single-FIELD_COM arrangement are the same
topology, so nothing is lost. Note this is a **12-point-specific** convenience;
the 28-point relay model splits its commons.

---

## 4. Channel budget and the recommended map

| | Board | PLC | Spare |
|---|---|---|---|
| Board → PLC | 7 outputs | 8 inputs (X0–X7) | **1** |
| PLC → board | 4 inputs | 4 outputs (Y0–Y3) | **0** |

⚠️ **Zero spare on the PLC→board direction.** Any later PLC-driven signal to the
board — an inhibit, a lamp-test, a mode select — needs an expansion module. If
that is at all likely, size up to a 28-point unit now (**DVP28SA211R** or
**DVP28SA211S**), not later.

**Recommended input map — keep X0 free.** X0–X2 are the 100 kHz high-speed
counter inputs; X3–X7 are 10 kHz. Our outputs are millisecond-class and waste a
fast input entirely. Seven channels cannot avoid all three, so:

| J26 | BCM | Function | PLC |
|---|---|---|---|
| OUT1 (pin 1) | 26 | `SPEED0` | X1 |
| OUT2 (pin 2) | 20 | `SPEED1` | X2 |
| OUT3 (pin 3) | 16 | `SPEED2` | X3 |
| OUT4 (pin 4) | 19 | `DIRECTION` | X4 |
| OUT5 (pin 5) | 21 | `RESULT_OK` | X5 |
| OUT6 (pin 6) | 12 | `RESULT_FAIL` | X6 |
| OUT7 (pin 7) | 13 | **`SPARE_OUT`** | X7 |
| FIELD_COM (pin 8) | — | shared return | 24G / 0 V, **and** the S/S return path |
| IN1 (pin 9) | 23 | `ZONE_ARRIVE` | Y0 |
| IN2 (pin 10) | 24 | **`ZONE_EXIT`** | Y1 |
| IN3 (pin 11) | 18 | **`SPARE_IN`** | Y2 |
| IN4 (pin 12) | 25 | **`SPARE_IN`** | Y3 |

*Revised 2026-08-29 (user). Previously: OUT7 = `HEARTBEAT`, IN2 = `ZONE_OCCUPIED`,
IN3 = `READER_ENABLE`, IN4 = `SPARE_IN`/`RESCAN_REQUEST`.*

⚠️ **Two channels now share the label `SPARE_IN`.** Firmware and wiring drawings
must key off the **channel name (`IN3`, `IN4`)**, which is unique, not off the
role label, which is not. Do not introduce a second numbering scheme
(`SPARE_IN1`/`SPARE_IN2`) — it will not survive contact with the J26 pin numbers.

### 4.0 What the revision gave up — two capabilities, both worth knowing

Neither is a defect. Both are things the interface *could* do yesterday and cannot
today, and each has a consequence that only shows up in service.

**1. 🔴 There is no longer a `HEARTBEAT`, so a dead board is SILENT.**
`000` = stop is fail-safe (§4.2) — but that cuts both ways: **a dead board, a
broken cable and a commanded stop are now indistinguishable to the PLC.** All
three present as `SPEED = 000` with every other output off. The heartbeat was the
only signal that separated "healthy and holding stop" from "gone".

> ✅ **Recommended first use of `SPARE_OUT` (OUT7): put `HEARTBEAT` back on it.**
> The channel is already built, wired and routed to X7 — restoring it costs one
> line of firmware and one rung. A PLC watchdog on a toggling input turns a silent
> failure into an alarm. Until then, board liveness must be inferred some other
> way (the Ethernet/API path), or not at all.

**2. `READER_ENABLE` is gone — the PLC can no longer gate the reader in hardware.**
The reader is still fully controlled by the CM4 (`RFID_EN` on BCM22, `RFID_NRST`
on BCM10); what disappeared is the PLC's ability to assert that over a wire,
independent of software. Enable/disable is now a host-side or API function only.
Fine if that is the intent — but if the panel ever needs to force the reader off
without the host cooperating, that path no longer exists and `SPARE_IN` (IN3, the
channel it used to occupy) is where it would come back.
| — | | | **X0 reserved** — the fastest counter input, left for a future encoder or wheel sensor |

### 4.1 Architecture — the board talks only to the PLC

✅ **Confirmed by the user 2026-08-29. All seven outputs land on DVP X inputs; the
PLC integrates with the VFD or whatever runs the conveyor.**

This retires a warning that would otherwise have overturned §2. An earlier design
note (`Downloads\Hardware-IntelliRFIDv2.md` §5) flagged that `SPEED0..2` and
`DIRECTION` "most likely land on a **VFD** or motion controller", whose inputs
commonly draw **5–10 mA** — far outside what a TLP291 open collector can
guarantee, and grounds for a MOSFET stage on four channels. **That condition does
not hold.** Nothing on our side ever faces a VFD input; every output sees the
DVP's 4.7 kΩ / 2.94 mA, which §2 covers with margin.

⚠️ **This is an architectural constraint, not an observation.** If anyone later
"simplifies" the panel by taking `SPEED0..2` or `DIRECTION` straight to a VFD — or
wires a stack light or relay directly to `RESULT_OK` / `RESULT_FAIL` — it will not
work, and it will fail **intermittently and hot** rather than cleanly. The board
drives PLC inputs and nothing else.

### 4.2 `SPEED0..2` is a 3-bit binary code — and it is fail-safe by construction

`SPEED0` (LSB) … `SPEED2` (MSB) carry a binary value **0–7**: **000 = stop**, plus
seven speed levels. Two properties of this encoding are worth stating explicitly,
because both are easy to destroy in a later revision:

**✅ Loss of signal commands STOP.** The chain is: GPIO HIGH → opto LED conducts →
phototransistor sinks X to 0 V → PLC reads ON = bit `1`. So every way the system
can fail *de-asserts* the bits:

| Failure | Bits | Result |
|---|---|---|
| Field cable broken or unplugged | 000 | **STOP** |
| Board unpowered | 000 | **STOP** |
| CM4 crashed or halted | 000 | **STOP** |
| **Before the CM4's code runs** | 000 | **STOP** |

The boot case is not luck: OUT1–7 sit on BCM 26, 20, 16, 19, 21, 12, 13 — **all
≥ GPIO9, hence in the BCM2711's power-on pull-DOWN group**, which the GPIO re-map
chose deliberately (`RESUME.md`). The outputs are off before any software exists,
so the conveyor is commanded stopped from the instant the board is powered.

🔴 **Do not let a future revision assign a moving speed to `000`, invert the output
logic sense, or move an output onto BCM 0–8** (which power on pulled *up*). Any of
those silently converts loss-of-signal from "stop" into "run".

**⚠️ The code is not atomic — three bits do not change together.** Optocoupler
turn-on and turn-off times differ, so on a multi-bit transition the PLC can
briefly latch an intermediate value: 3→4 (`011`→`100`) can read as `111` = full
speed if the falling bits lag the rising one. The DVP's 10 ms input filter (§5)
absorbs the skew itself, but the three channels' filters expire independently, so
a scan boundary can still fall between them.

Physically this is minor — one scan of a wrong speed against a VFD ramp measured
in seconds. But the fix is free and belongs in the ladder: **require the 3-bit
code to be stable for 2–3 consecutive scans before acting on it.** Do not solve
it on our side; nothing in copper can.

### ✅ SETTLED 2026-08-29 (user): `000` is a CONTROL stop, not a safety stop

The right answer, and it is the one the mechanism supports. An encoded value
carried on three non-atomic channels is a control signal; it could not have been a
safety function whatever the intent. Three consequences, all of which now hold:

1. **This board is not in the safety chain.** The conveyor's safety stop is
   provided by its own rated architecture — E-stop, safety relay, whatever the
   machine builder fitted — and does **not** pass through J26, the PLC's X inputs,
   or any part of IntelliRFIDv2. ⚠️ The one thing to confirm with the integrator is
   the negative: **that nothing in the safety function depends on our `000`.**
2. **No PL / SIL claim attaches to this board, and none may be made** in any
   customer-facing document, quotation or manual. The fail-safe behaviour above is
   a real and useful property — it is not a safety rating, and the two must never
   be conflated in writing.
3. **The one-scan skew glitch of §4.2 is now definitively benign.** Nothing
   safety-related rests on it. It stays worth fixing in the ladder for control
   correctness — a conveyor that briefly takes a wrong speed is still a real
   process problem — but it carries no safety argument.

⚠️ **"Control stop" is not "unimportant".** Failing to stop on command still means
pile-up, jams and product damage. It sets the *class* of the requirement, not its
priority. The 2–3 stable scan rule and the loss-of-signal behaviour both remain
requirements; they are simply availability and correctness requirements rather
than safety ones.

*(This also settles the framing carried in `../intelli-interposer/`'s memory, which
described the interposer as insurance "in a conveyor stop path" — accurate as to
the signal, but that path is control, not safety. It makes the direct-drive
decision of §0 more comfortable, not less.)*

### The complete wiring list — this is what goes to the panel builder

| From | To |
|---|---|
| Field supply **+24 V** | PLC `24V`, PLC **`S/S`**, PLC **`C0`** — jumper S/S to C0 |
| Field supply **0 V** | PLC `0V`, **J26 pin 8 (`FIELD_COM`)** |
| J26 pins 1–7 (`OUT1`…`OUT7`) | PLC `X1` … `X7` |
| J26 pins 9–12 (`IN1`…`IN4`) | PLC `Y0` … `Y3` |

**Exactly 12 cores to the board** — the 12-way plug is full, nothing spare.

Three things this table is quietly saying, each of which has been got wrong before:

1. 🔴 **`C0` is the +24 V side, not a ground.** It is the dry relay common that
   lets Y0–Y3 push +24 V into IN1–4. Feeding it does **not** establish the
   reference between board and PLC. The common is the separate
   **`FIELD_COM` → supply 0 V** wire, and without it the relay outputs have no
   return path and nothing works.
2. 🔴 **`S/S` must go to +24 V too**, or the seven outputs do nothing at all.
   S/S and C0 are internally isolated from one another, so one +24 V wire landing
   on both terminals is correct and normal.
3. ✅ **The board takes no +24 V feed.** J26 has no `FIELD_24V` pin — the outputs
   are open-collector sinks and the inputs are fed by the PLC's own contacts. Only
   the 0 V return reaches the board. (The interposer needed a separate 2-pin
   24 V feed because it powered its own photorelay LEDs. Direct-wired, that
   requirement disappears — do not carry it over from the interposer drawings.)

`FIELD_COM` carries the return for all eleven channels: ~35 mA from seven
outputs plus ~13 mA from four inputs, so ~48 mA steady state — nothing. Its real
duty is the surge case already judged in `SURGE-EMC-REVIEW.md`: a bundled field
cable can sum eleven clamp currents into that single contact, ≈22 A for tens of
µs. That is why the trace is 0.50 mm and why the return to pin 8 must be short.

---

## 5. Field supply — one supply, and the PLC sets its floor

🔴 `INSTALLATION-SPEC.md` §5 already forbids split field supplies: every J26 device
shares **one 24 V source and one return**. The PLC is now one of those devices, so
its 24V/0V terminals, its S/S strap and its C0 common all come off **that same
supply**.

⚠️ **The PLC, not the board, sets the low-voltage limit.** IntelliRFIDv2's field
I/O is sized to work down to **16.8 V** (EN50155 minimum). The DVP-SA2 **stops
below 17.5 V** and drops every output. Spec and protect the shared supply to the
**PLC's** floor.

Two more consequences of the shared supply:

- A power dip **< 10 ms is ridden through**; anything longer stops the PLC, drops
  all outputs, and then auto-restarts — **with latched relays and registers
  retaining their values.** The PLC program must handle resuming mid-state.
- The PLC's own EFT rating on digital I/O is **1 kV**, which is well under what a
  trackside field cable can present. Our side is clamped by D20–D30; the PLC side
  is not. Surge protection on the shared supply is the installer's job.

### ✅ ANSWERED 2026-08-29 — the 0 V will be left FLOATING, not earthed

The question below was put to the panel side and came back **floating**. The opto
barrier therefore does its full job: the eleven field channels are a genuinely
isolated island, and no ground loop is created between panel earth and trackside
earth. **The rule at the end of this section is satisfied as designed** — the rest
of the section is retained because it is what makes the answer load-bearing, and
because an as-built can drift from an intention.

One consequence of a floating supply, stated so nobody is surprised by it later:
a **first** earth fault anywhere on the 24 V system is silent and harmless — it
merely references the island, which is the ordinary IT-system property and the
price of the isolation. It is the **second** fault, at a different point, that
puts current through earth. If the site ever wants that first fault to be visible,
the tool is an insulation monitor on the 24 V supply, not a bond. Nothing to do
now; worth knowing before someone "fixes" a floating rail by earthing it.

### Why it matters — the mechanism the answer above avoids

`FIELD_COM` tied to the PLC's 0 V is correct and required — that is the shared
reference. It must **not** extend to the rfid-v2 board's own `GND`. That
separation *is* the 2500 Vrms opto barrier the entire field-IO block was built
around, and it is why even the TVS anodes return to `FIELD_COM` and never to
`GND` (`V2-DESIGN.md` §214 — bonding them to GND would be eleven parallel shorts
across the barrier that neither ERC nor DRC can see).

The way it gets bypassed is **through earth, with every individual wire correct:**

- **Board side is already earthed.** §4 of this spec bonds the coaxial GDT
  arrester to the enclosure earth stud, and the SMA shell is board `GND`. So
  rfid-v2's `GND` reaches trackside earth through the feeder screen.
- **Panel side often is too.** Earthing the 24 V negative rail is common panel
  practice, and Delta requires the PLC chassis itself be grounded directly
  (`ExternalSystems/Delta-DVP-SA2/DVP-SA2-SUMMARY.md` §3).

If both are true, `FIELD_COM` meets board `GND` through the earth path and the
barrier is decorative. **Nothing is damaged — both nodes sit near 0 V in a 24 V
system — but it re-creates precisely the ground loop the optocouplers were bought
to break**, and it does so over a long field cable running near traction cable,
which is the worst place to have one.

> **Rule: keep the shared 24 V supply's 0 V FLOATING (unearthed).** If the site's
> earthing standard forbids that, bond it *knowingly*, record it, and accept that
> the field-IO isolation no longer provides loop-breaking — only the surge
> clamping of D20–D30 remains.

This is an installation decision, not a board one. It cannot be enforced in copper,
which is why it had to be asked of the panel builder explicitly — and was.

⚠️ **The PLC chassis stays earthed while its 24 V rail floats.** That is the
intended arrangement, not a contradiction: Delta requires the chassis be grounded,
and the PLC's supply-to-chassis insulation is rated **> 5 MΩ at 500 VDC**, which
is ample to hold off whatever common-mode potential a floating 24 V island reaches
in this system.

---

## 6. 🔴 The environmental mismatch — the real integration risk

| | IntelliRFIDv2 | DVP-12SA2 |
|---|---|---|
| Operating temperature | EN50155 target, −40 … +85 °C | **0 … 55 °C** |
| Storage | — | −25 … 70 °C |
| Condensation | — | **non-condensing only** |
| Enclosure | designed for a trackside enclosure | **OPEN TYPE — control cabinet mandatory** |

**The PLC cannot go where the RFID board goes.** In an Indian trackside cabinet a
0–55 °C non-condensing part is out of its rating on a summer afternoon and again
on a monsoon morning. Two workable arrangements:

1. **PLC in a controlled panel, board trackside**, with the 12-core field harness
   between them. Preferred. It also puts the shared 24 V supply in the panel.
2. Both in one enclosure — then the enclosure must hold 0–55 °C non-condensing,
   which means heating, ventilation or both, and that becomes a system
   requirement, not an afterthought.

⚠️ This is not something either board can fix in copper. It belongs in the
installation documentation before a quotation is written against it.

---

## 7. If the interposer is in the path instead

`../intelli-interposer/` boosts OUT1–7 to a photorelay contact and passes IN1–4
through as bare copper. Checked against the DVP-12SA2:

| Interposer published envelope | DVP-12SA2 demand | Verdict |
|---|---|---|
| 0–30 V | 24 V (28.8 V max) | ✅ |
| **OUT positive w.r.t. FIELD_COM** | ✅ in SINK mode — X sits at +24 V through 4.7 kΩ when open | ✅ |
| ≤ 80 mA | ≈ 5 mA | ✅ 16× |
| ≤ 16 Ω contact | 5 mA × 16 Ω = **0.08 V** against a 5 V OFF limit | ✅ |
| **JP1 strap** | default **1-2 = SINK**, which is what Delta SINK mode needs | ✅ **leave JP1 at its default** |

So the interposer is compatible and needs no change. It buys back the
end-of-life/hot-corner margin identified in §2 — it is not required to make the
DVP work.

⚠️ The interposer connects to J26 by a **short 12-core harness with a screw plug
at each end** — it does not stack. Budget the panel space.

---

### 4.3 Provenance — this table used to live only in Downloads

The channel→function assignment came from `C:\Users\piyus\Downloads\Hardware-IntelliRFIDv2.md`
§2.1 and existed **nowhere in this repository or in project memory** until
2026-08-29. The repo documented all eleven channels purely electrically
("field output", "field input") with no semantic meaning attached. **§4 above is
now the authoritative copy** — that is the point of moving it here.

⚠️ **The Downloads note is a working draft and is partly stale.** Known
divergences, so nobody re-imports them:

- It states the eleven field lines "currently carry no surge protection". **False
  now** — D20–D30 SMAJ33A are fitted, cathode on the line, anode on `FIELD_COM`.
- Its §5 VFD warning is retired by §4.1 above.
- It refers to a `PLC-Digital-IO-Interface.md` that is not present anywhere on
  this machine. If that document exists elsewhere, reconcile §4 against it.

Same failure mode as the interposer's origin note, which `INTERPOSER-DESIGN.md`
demotes to "history, not the spec". A design input that lives only in a downloads
folder is one cleanup away from being lost.

---

## 8. Open items

- [x] ✅ **Variant confirmed 2026-08-29: DVP12SA211R (relay) is bought.** §3 is
      closed — the NPN blocker was avoided.
- [x] ✅ **Decided 2026-08-29 (user): wire DIRECT, no interposer.** §2's margin is
      accepted. The two consequences that follow are the V_CE commissioning
      measurement below and the earthing question below — neither is optional now
      that there is no booster in the path.
- [x] ✅ **Earthing answered 2026-08-29: the 24 V 0 V will be left FLOATING.** The
      opto barrier does its full job and no panel↔trackside ground loop is created
      (§5). Verify it is still floating at commissioning — an as-built can drift.
- [ ] Confirm the panel builder straps **S/S to +24 V** and does not reverse it.
- [ ] Confirm D1020 is left at its **10 ms default** — do not set it to 0. It is
      the PLC-side half of the ≥10 ms debounce that `SURGE-EMC-REVIEW.md` requires
      for shared-FIELD_COM cross-channel disturbance.
- [x] ✅ **Architecture confirmed 2026-08-29: all 7 outputs go to the PLC; the PLC
      drives the VFD.** The VFD drive-capability warning is retired (§4.1).
- [ ] **Ladder: require the 3-bit `SPEED` code stable for 2–3 scans** before acting
      (§4.2). Cannot be fixed on the board side.
- [x] ✅ **Settled 2026-08-29: `000` is a CONTROL stop, not a safety stop** (§4.2).
      This board is not in the safety chain; **no PL/SIL claim may be made for it.**
- [ ] Confirm with the integrator the *negative*: that **nothing in the conveyor's
      safety function depends on our `000`** (§4.2). Cheap to ask, expensive to
      assume.
- [ ] Locate `PLC-Digital-IO-Interface.md` (referenced by the Downloads note,
      not present on this machine) and reconcile §4 against it (§4.3).
- [ ] Decide 12-point vs 28-point against the **zero spare outputs** in §4.
- [ ] Decide the enclosure arrangement in §6 and get it into the installation spec.
- [ ] Bench-confirm one channel end to end (OUT asserted, measure V_CE and the X
      indicator; Y asserted, confirm the GPIO reads LOW) before committing the
      wiring drawing. The §2 margin rests on a traced temperature curve, and one
      measurement retires that caveat.
