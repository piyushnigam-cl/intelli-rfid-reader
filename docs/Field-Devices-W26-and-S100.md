# Field devices — SICK W26 sensors and the conveyor driver card

What the two vendor documents in `docs/` actually say, and what they change.

| | |
|---|---|
| **Sensor** | `productoverview_W26_g433551_en.pdf` — SICK W26, 10 pages. Cited below as **W p.N** |
| **Driver card** | `winroller-dc-driver-s100.pdf` — 18 pages, Rev 3.0 (2022-08-09). Cited below as **S p.N** |

Both are the source of record for `EnS`/`ExS` and for the three conveyor cards. Read §3 first if you
only have a minute — it is the part that changes decisions.

> **Two warnings before any number below is used.**
>
> **The driver card document never says "EZY-S100".** The strings `EZY`, `S100` and `WinRoller` do
> not appear in it. It calls the product *"Vector variable frequency motor controller"*, type
> **`VECTOR-T100`** (S p.7), also written `VECTOR-100` (S p.8) and "the C type controller" (S p.4).
> It is plausibly the OEM manual for the card EzyRolls rebadges, but that link is **not established
> by this file**, and the project has been citing "the EZY-S100 manual" as a source. Confirm the
> part actually being bought is this card before relying on anything here.
>
> **The W26 document is a family overview, not a data sheet.** It carries **no** electrical or
> timing data of any kind. It points to `www.sick.com/W26` for the per-article data sheet (W p.5),
> and that is where the numbers live.

---

## 1. SICK W26 — the Entry and Exit sensors

### 1.1 What the document does not contain

Searched across all 10 pages, the following appear **nowhere**: supply voltage, current consumption,
output current, short-circuit or reverse-polarity protection, residual voltage, leakage current,
response time, switching frequency, jitter, on/off-delay, pin assignment, wire colours, light spot
size, minimum detectable object, ambient light immunity, MTTF, EMC, and any IO-Link revision, port
class, cycle time or parameter list.

The only technical table is "Technical data overview" (W p.4), which has six rows and one of those
is blank. Everything else is marketing prose and ordering tables.

**Consequence: every W26 electrical figure currently in `Tunnel-Interconnect.md` §10 is a proxy and
stays a proxy.** They were taken from `WTB26P-24161120A00`, which is a real part in these tables
(W p.7, art. 1218666) — but the overview gives no electricals for it or anything else.

### 1.2 Sensing modes and ranges (W p.5–9)

| Principle | Detail | Range | Page |
|---|---|---|---|
| Through-beam | — | 0–60 m | W p.5 |
| Through-beam | — | 5–120 m | W p.5 |
| Retro-reflective | with minimum reflector distance, dual lens | 0.25–19 m | W p.5 |
| Retro-reflective | with minimum reflector distance, dual lens | 0.25–3 m | W p.6 |
| Retro-reflective | **no** minimum distance, autocollimation | 0–18 m | W p.6 |
| Proximity | background suppression + TwinEye | 10–1000 mm | W p.6 |
| Proximity | background suppression + TwinEye | 10–500 mm | W p.6 |
| Proximity | background suppression | 30–1600 mm | W p.7 |
| Proximity | BGS + NarrowBeam | 30–1600 mm | W p.8 |
| Proximity | background suppression | 30–3000 mm | W p.8 |
| Proximity | background suppression | 30–2000 mm | W p.8 |
| Proximity | **foreground** suppression | 0–800 mm | W p.9 |
| Proximity | MultiMode: BGS + FGS + distance value | four ranges | W p.9 |

There is no plain diffuse/energetic variant in the family. For gating a carton across a conveyor the
candidates are the **through-beam `WSE26` group** (W p.5) or the autocollimation **`WLA26`** (W p.6)
if a single-sided mount with a reflector is wanted.

### 1.3 Output type and switching mode — the part that matters

**Switching mode is an ordering-table column. It is fixed by part number, and the family ships all
three kinds.**

Four switching-output values appear: **`push-pull: PNP/NPN`** (the family default, on nearly every
block), **`PNP`** (W p.7 ×2, p.8), **`NPN`** (exactly one part — `WTB26I-24G11420ZZZ`, art. 1124859,
W p.8), and push-pull as a per-row cell.

Four switching-mode values appear:

| Value | Meaning | Examples |
|---|---|---|
| **`Light/dark switching`** | selectable on the device | most of the catalogue |
| **`Light switching`** | fixed light-on | `WSE26P-24165100A00` (1118267), `WLA26P-24116100ZZZ` (1222792), `WTB26P-24113420ZZZ` (1140316) |
| **`Dark switching`** | fixed dark-on | `WLA26P-24114100ZZZ` (1222793), `WTB26P-24115420ZZZ` (1147510), `WTB26I-24115120ZZZ` (1222815) |
| **`–`** | not stated | `WTS26P-24161120A70` (1219799), `WTS26P-2416H120A71` (1219800) |

**The document never states the mechanism** by which a `Light/dark switching` part is toggled. The
nearest it comes is a teach-in button claim (W p.3) that is scoped to the **proximity** column — the
parallel column for through-beam and retro-reflective sensors claims only a blue LED alignment aid,
no teach button. "Teach-Turn adjustment" and IO-Link are listed as family features (W p.4).

**Do not infer polarity from the order-code digits.** The correlation is inconsistent across
families: in `WLA26`, `…24114100ZZZ` is Dark and `…24116100ZZZ` is Light; in `WTB26`,
`…24115420ZZZ` is Dark and `…24113420ZZZ` is Light. The code structure is never documented.

Push-pull, where fitted, **never floats** — it sources high and sinks low — so it will drive either a
sourcing or a sinking 24 V input and needs no bias resistor. That assumption breaks on the PNP-only
and NPN-only parts.

### 1.4 Connection (W p.5–9)

Connection type is given; pinout is not. The complete set: `Male connector M12, 4-pin`;
`Cable with plug, M12, 4-pin, 318 mm`; `Cable, 4-wire, 2 m`; `Cable, 4-wire, 10 m`;
`Cable with Q6 male connector, 6-pin, DC-coded, 298 mm`; `Cable with Q7 male connector, 7-pin,
DC-coded, 298 mm`. **M12 4-pin is the standard and every bare-cable variant is 4-wire.** No M8.

The 6-pin and 7-pin variants are the only hint that a second output or a teach input exists; the
document never confirms either.

### 1.5 Mechanical and environmental (W p.4)

| | |
|---|---|
| Dimensions (W×H×D) | `24.6 × 82.5 × 53.3 mm` / `20 × 55.7 × 42 mm` / `31.4 × 112.3 × 70.4 mm` |
| Sensing range max. | **blank in the source table** |
| Light source | PinPoint LED / LED / PinPoint Pro LED, depends on variant |
| Type of light | visible red / infrared, depends on variant |
| Enclosure rating | IP66 / IP67 / IP69 / IP65, depends on variant |
| Housing material | plastic (VISTAL, W p.3); metal variants exist for ATEX |
| Operating temperature | **−40 °C … +60 °C** |
| Housing shape | rectangular, every variant |

ATEX category 3D/3G variants exist for Zone 22 and Zone 2 (W p.3–4).

### 1.6 IO-Link (W p.2–4)

Named as a family feature with no protocol detail. Used for: MultiMode operating-mode selection,
Two Value Teach-in, two independent switching points, Window mode, distance value in millimetres,
remission value, and DustAlert contamination warning. **It is never said whether light/dark switching
itself is settable over IO-Link** — only operating mode, switching points and window mode are
enumerated, and only for the MultiMode `WTM` parts.

---

## 2. The conveyor driver card — EnC, RZC and ExC

### 2.1 Signal connector — 9 pins

The pin order is **not in the text**; it is recovered from the wiring diagrams (S p.13), which are
raster images. Both diagrams show the same connector:

```
1  0-10V      2  Speed     3  Error     4  Reverse    5  Run A
6  Run B      7  Com       8  485A      9  485B
```

Terminal descriptions, verbatim from the signal-terminal table (S p.6):

| Terminal | Description |
|---|---|
| `0~10V` | Analog speed regulation — external 0–10 V analog voltage input speed adjustment |
| `SPEED` | Speed pulse feedback; PNP and NPN optional (controller internal jumper) |
| `ERROR` | Error signal output; PNP and NPN optional (controller internal jumper) |
| `REVERSE` | The drum motor runs in the opposite direction of the default direction |
| `RUN A/B` | Effective level based on `COM` port status / specific function |
| `COM` | Connects to the common end of the optocoupler through an internal jumper. Port controls fixed NPN when suspended. **Connect 0 V for PNP** input/output; connect 24 V for NPN. *"Ensure that the jumper has been set with the corresponding signal input and output mode"* |
| `485A/B` | 485 communication interface |

There is **no `Enable` and no `Brake` input** — braking is a DIP setting, not a terminal. No `24V` or
`0V` control-supply pin is named in the table; the control pair appears only in the diagrams.

### 2.2 Speed encoding (S p.6) — confirmed

| Run A | Run B | Result |
|---|---|---|
| ON | OFF | fixed set speed **100 %** |
| ON | ON | fixed set speed **75 %** |
| OFF | ON | fixed set speed **50 %** |
| OFF | OFF | **drum motor stops** |

"100 %" is the gear chosen on the SPEED DIP (§2.5). Direction is independent, via `REVERSE` and
CONFIG-2.

**Not stated:** any minimum pulse width on the Run inputs, any debounce, and whether changing between
50/75/100 % while running uses the ACC/DEC ramp.

### 2.3 PNP wiring — we run everything PNP

From the "PNP IO Control Wiring Principle" drawing (S p.13):

- **control power `+`** → the three switches `S1`/`S2`/`S3` → pins **4 `Reverse`**, **5 `Run A`**,
  **6 `Run B`**
- **control power `−`** → pin **7 `Com`**
- `DC+` / `DC−` is a **separate connector on the opposite side of the card**

The NPN drawing on the same page is the mirror image: `−` feeds the switches, `+` goes to `Com`.

Polarity convention (S p.4): *"NPN means low level is active, that is, connected to `DC-` effective;
PNP means high level is effective, that is, it is effective when connected to `DC+`."* Note this
phrases activity in terms of the **motor** rails — see §3, open item 2.

**Three internal jumpers** (S p.17), top to bottom on the left:

1. Speed-feedback PNP/NPN — left short-circuit = NPN
2. Fault-feedback PNP/NPN — left short-circuit = NPN
3. `COM` mode — **left short-circuit brings `COM` out for external PNP/NPN selection; right
   short-circuit is fixed NPN**

For our PNP wiring, jumper 3 must be **left**. Right would make the card fixed-NPN and our wiring
inert. Setting them needs the outer shell open; the document warns it is ESD-sensitive and for
trained personnel only.

### 2.4 Control input electrical characteristics — **absent**

Searched across all 18 pages:

- **no input current figure** — the string `mA` does not occur once in the document
- **no input impedance** — `impedance`, `Ω`, `ohm` do not occur
- **no input voltage threshold, no V_IH/V_IL, no control-pin voltage range**
- **no opto-coupler part number, forward current or forward voltage**
- **no `ERROR`/`SPEED` output drive capability**

All that can be said is that the inputs are opto-coupled (`COM` is "the common end of the
optocoupler", S p.6) and that control signalling is nominally at the same 24 V level as the supply.

### 2.5 DIP switches, speed and ramps

**There are no potentiometers.** Three DIP banks: `SPEED` (4-way), `CONFIG` (8-way), `ACC/DEC`
(4-way), under a transparent shell openable from the lower end (S p.8–9). `ON = 1, OFF = 0`
(S p.12).

`CONFIG` (S p.9):

| # | Function | OFF | ON |
|---|---|---|---|
| **1** | **High/low speed band** | **low speed** | **high speed** |
| 2 | Forward/reverse default | CCW | CW |
| 3 | Open/closed loop | open | closed |
| 4 | Error recovery ("adjustable after 5 restarts") | manual | automatic |
| 5 | Current limit | small | large |
| 6, 7 | Brake mode | see below | |
| 8 | Analog input switch | *(states not stated)* | |

Neither "small"/"large" current limit is given in amps, and no factory default is stated for any DIP.

**Speed, low band, CONFIG-1 OFF** (S p.11), 16 gears:
500, 719, 902, 1102, 1410, 1500, 1705, 1902, 2086, 2290, 2487, 2691, 2889, 3093, 3297, **3485 rpm**

**Speed, high band, CONFIG-1 ON** (S p.12), 16 gears:
3678, 3878, 4086, 4303, 4474, 4671, 4871, 5066, 5270, 5460, 5665, 5869, 6066, 6257, 6440, **6600 rpm**

In the speed tables switch 1 is the **MSB**; in the ACC/DEC table switch 1 is the **LSB**. Both are
transcribed as printed. A remark "high speed = low speed *" is **truncated in the source** and the
multiplier is missing; the ratio is not constant across the tables, so the remark is unusable.

**ACC/DEC time** (S p.12), 16 gears: 3.90, 2.44, 1.77, 1.39, 1.15, 0.98, 0.85, 0.75, 0.67, 0.61,
0.56, 0.51, 0.48, 0.44, 0.41, 0.39 s.

**Brake mode** (S p.10): SW6/SW7 — OFF/OFF **Electronic**, ON/OFF **Free**, OFF/ON **Servo**
(ON/ON is also free, per the Modbus table). *Servo brake* holds rotor position using the Hall
sensors when the run signal disappears; *free* opens the motor circuit and coasts; *electronic*
applies DC to the stator.

### 2.6 Power (S p.7–8)

| | |
|---|---|
| Rated input | **24 V / 48 V** |
| Allowable range | **20–28 V** / **40–60 V** |
| Fluctuation | ±15 % |
| Peak input current | **5 A per card** — a *limit*, not a trip: "after reaching the limit current, it will continue to output at the limit current" |

PSU sizing table (S p.8): 40 W drum → 60–80 W supply; 80 W → 120–160 W; 100 W → 150–200 W. The
supply must be NEC Class II certified with short-circuit and overload protection.

**No separate control-supply rail is described.** The only power terminals are `DC+`/`DC−`.

### 2.7 Outputs, Modbus, faults

`ERROR` and `SPEED` are both PNP/NPN jumper-selectable outputs with **no stated electrical rating**
and no pulses-per-revolution figure. **There is no "running" output** — running status is the green
LED, plus Modbus.

**Modbus RTU** (S p.15): 38400, 8 data bits, no parity, 1 stop bit. Address by 8-way DIP, 1–255
(S p.14). Coils include run, direction, open/closed loop, **running mode (0 = 485, 1 = I/O, default
I/O)**, restart mode, brake mode, and read-only fault bits for over-current, rotation-clogging, hall
fault, motor fault, low/over voltage, motor overheat, controller overheat, controller fault.
Registers: `40001` speed **100–1000 rpm**, `40002`/`40003` accel/decel 5–50, `40004`/`40005` bus and
phase current.

**Red LED fault flash codes** (S p.14): 1 sensor fault · 2 overheat (75 ° start, 100 ° protection) ·
3 over-current · 4 rotation-clogging · 5 reserved · 6 low voltage · 7 high voltage · 8 reserved.
Yellow = power, green = running and follows motor speed.

### 2.8 Mechanical — absent

The dimension page (S p.16) contains one raster drawing and the sentence "The unit of all the
dimensions is mm". **No numeric dimensions, no mounting detail, no IP rating and no operating or
storage temperature appear in the text.** The only ingress statement is "do not allow any liquid to
penetrate the interior of the controller" (S p.8).

---

## 3. What this changes — reconciliation against `Tunnel-Interconnect.md`

| Project figure | Where | Verdict |
|---|---|---|
| RZC speed table: A 100 %, A+B 75 %, B 50 %, neither stop | §7.2 | ✅ **Confirmed** verbatim, S p.6 |
| `S1`→pin 4 `Reverse`, `S2`→pin 5 `Run A`, `S3`→pin 6 `Run B`, `−`→pin 7 `Com` | §7.1 | ✅ **Confirmed** from the PNP drawing, S p.13 |
| `COM` → 0 V for PNP; floating = fixed NPN; set by internal jumper | §10.1 | ✅ **Confirmed**, S p.6 and p.17. The jumper is the **third** of three and must be **left** |
| CONFIG-2 direction, CONFIG-3 loop, CONFIG-4 error recovery, CONFIG-5 current limit | §10.2–3 | ✅ **Confirmed**, S p.9 |
| SPEED DIP sets the 100 % reference; address DIP 1–255 | §10.4–5 | ✅ **Confirmed**, S p.9 and p.14 |
| Each card 5 A peak, motor supply out of scope | §4 | ✅ **Confirmed**, S p.7 |
| **Control input draws 7.3 mA** (Itoh CBM-105 proxy) | §9, §4.1 | ❌ **STILL OPEN.** The document contains no current figure at all — `mA` never occurs. The proxy stays a proxy |
| **Input threshold ON ≥ 13 V, OFF ≤ 2 V** (EzyRolls MDR leaflet) | §9 | ❌ **STILL OPEN.** No threshold is stated |
| **Signal terminal isolated from `DC−`?** | §13 item 2 | ❌ **STILL OPEN**, with evidence both ways — see below |
| **Speed range stated three ways** | §13 item 6 | ✅ **RESOLVED** — they are three different things |
| W26 electricals (10–30 V, ≤30 mA, ≤100 mA out, ≤500 µs, UB−2.5 V) | §10 | ❌ **STILL OPEN.** The overview has no electrical data |
| **W26 ordering code and light/dark switching** | §13 item 4 | ❌ **STILL OPEN — and it is a purchasing decision** |

### 3.1 The trigger-edge assumption is not settled, and the fix is broader than `gpiomon -l`

`CLAUDE.md` records the trigger edge as **decided on 2026-09-02** — open the read on the field-active
edge — resting on the stated assumption *"SICK W26, PNP, 24 V present = carton present"*.

**The datasheet neither confirms nor refutes that, because it is a property of the part number, and
the part number has not been chosen.** The family ships fixed light-switching, fixed dark-switching
and selectable parts, in PNP-only, NPN-only and push-pull. Whether "carton present" is 24 V or 0 V at
the reader input depends on which is bought *and*, for a retro-reflective or through-beam type, on
the fact that the idle state is beam-**made**, which inverts the sense again relative to a proximity
type.

**Recommendation, stronger than the current decision: make IN1/IN2 edge sense per-channel
configurable** rather than compiling in `--active-low`. It costs one config key, it is correct under
every variant in the table, and it converts a purchasing risk into a commissioning step. Then
commissioning check 5 — "break each beam by hand and confirm the correct reader input asserts" —
becomes the thing that sets it.

### 3.2 The TM output stage cannot be sized from this document

`7.3 mA` per input, and therefore **O2/O3/O4 ≥ 50 mA and O1 ≥ 100 mA** (§9), rest entirely on the
Itoh CBM-105 proxy. Nothing in 18 pages confirms or contradicts it.

Two ways to close it, and the second is already written down:

1. Ask the vendor for the control-input current at 24 V over temperature.
2. **Commissioning check 7** — "record the measured current on one card input" — which §14 already
   calls the thing that closes open item 1 permanently. That is now the *only* route on paper.

Until then the margins in §9 are unverified, and the ×7 headroom on the class figure is what is
carrying the design.

### 3.3 The isolation question, with new evidence pointing both ways

**For isolation:** `COM` is described as "the common end of the optocoupler" (S p.6), and `DC+`/`DC−`
sits on a **physically separate connector on the opposite side of the card** from the signal
terminal (S p.13).

**Against:** the polarity convention (S p.4) defines PNP as "effective when connected to `DC+`" and
NPN as "connected to `DC−` effective" — phrasing the control levels in terms of the **motor supply
rails**, which reads as an assumed shared rail. And there is **no separate control-supply rail
described anywhere** in the document.

**The document neither authorises nor forbids** running the control inputs from a different 24 V
supply than the motor rail. `Tunnel-Interconnect.md` §4's warning stands unchanged, and §13 item 2
stays open. Ask the vendor.

### 3.4 The speed-range contradiction resolves into three separate things

§10 flags "600–6900 rpm on the website, 500–3485 rpm in the catalogue DIP table, 100–1000 rpm in the
Modbus register map". The manual explains all three:

- **500–3485 rpm** is the **low** speed band, CONFIG-1 OFF (S p.11)
- **3678–6600 rpm** is the **high** speed band, CONFIG-1 ON (S p.12) — the website's "600–6900" is a
  loose rounding of the two bands end to end
- **100–1000 rpm** is the **Modbus `WDAT0` register range** (S p.15), which the document never
  reconciles with the DIP tables

So the belt speed is picked by choosing a band on CONFIG-1 and then a gear on the SPEED DIP. **The
Modbus/DIP discrepancy is real and unexplained** — do not assume a 485 setpoint can reach a DIP-table
speed.

### 3.5 Three things `Tunnel-Interconnect.md` §10 should gain

1. **CONFIG-1, the high/low speed band.** §10 lists CONFIG-2 through CONFIG-5 and omits this one,
   which selects the entire ladder the SPEED DIP indexes into. Setting the SPEED gear without first
   setting the band is meaningless.
2. **CONFIG-6/7, brake mode.** Not mentioned at all. **Servo brake** holds rotor position when the
   run signal drops, which is what a carton stopping inside the read zone wants; **free braking**
   coasts, which lets it drift. This is a per-card decision with a physical consequence.
3. **The `ERROR` output (pin 3).** Nothing in the channel map reads it, and it is the only way the
   reader could know a card has faulted rather than merely failing to move a carton. It is
   PNP/NPN jumper-selectable with no stated drive rating. Worth an input if one can be found — IN4
   is the only spare channel.

---

## 4. Still to be answered by someone other than these documents

| # | Question | Ask |
|---|---|---|
| 1 | Control-input current and threshold at 24 V over temperature | vendor, or commissioning check 7 |
| 2 | Is the signal terminal galvanically isolated from `DC−`? | vendor |
| 3 | Is the card actually the "EZY-S100"? | vendor / purchasing |
| 4 | W26 ordering code, switching mode and output stage | purchasing — then pull the per-article data sheet from `www.sick.com/W26` |
| 5 | W26 supply/output ratings, response time, M12 pinout | per-article data sheet |
| 6 | Card dimensions, mounting, IP rating, operating temperature | vendor (the drawing is a raster with no text) |
| 7 | Which speed band and gear give the wanted belt speed | site geometry, then CONFIG-1 + SPEED DIP |

---

## Appendix — recovering the figures from the PDFs

There is no `poppler-utils`, `mutool`, ImageMagick, PyMuPDF or PIL on this board, so the raster
figures cannot be rendered by the usual route. They can be pulled out directly: the image XObjects
are `DCTDecode`, i.e. ordinary JPEG, and the bytes between `stream` and `endstream` are a complete
file. The wiring diagrams are objects **143** (NPN) and **144** (PNP); the board layout is 111, the
signal connector 75, the jumper detail 168/170, the dimension drawing 164.

The W26 PDF is **RC4-128 encrypted with an empty user password** — it decrypts the way any viewer
does, which is worth knowing before concluding the file is corrupt.
