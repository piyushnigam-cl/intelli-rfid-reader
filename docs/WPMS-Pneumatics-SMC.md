# WPMS pneumatics: SMC SS5Y manifold, SY7100 and SY7300 valves

The wayside reader drives the WPMS pneumatics from J26 OUT1–OUT7, through the interposer
(`Wayside-Reader-Design.md` §2.0). This is the reference for the whole pneumatic set: the valve
manifold, the seven valves, how they wire to the interposer, and what that means for the app.

**Source:** SMC catalogue *SY3000/5000/7000 Series, plug-in* (327 pp., 2021), committed as
`intelli-pcb-interposer/TechDocs/23-Aug-26/components/SS5Y51.pdf`. That repo is on CodeCommit only:
the 74 MB PDF is deliberately not on GitHub. Page numbers below are the catalogue's own. Written
2026-10-09 from a cloud session, from the catalogue and the operator's part list. **Nothing here is
measured.**

## The set (operator, 2026-10-09)

| Qty | Part | What it is | Does |
|---|---|---|---|
| 1 | **SS5Y?-51…** (reported as "SS5Y51") | Plug-in **metal base manifold, type 51 (bottom ported)** | Carries the valves; common supply and exhaust; one electrical connector for all coils |
| 6 | **SY7100-5U1** | SY7000, 2-position single solenoid | Air blow, one per WPMS module (OUT2–OUT7) |
| 1 | **SY7300-5U1** | SY7000, 3-position closed centre, two solenoids | WPMS flaps open/close (OUT1) |

> ⚠ **Read the full manifold part number off its label.** "SS5Y51" is not a complete SMC part
> number, and the one digit that matters is missing:
> - **SS5Y5-51…** is the base for **SY5000** valves (1/4 ports).
> - **SS5Y7-51…** is the base for **SY7000** valves (3/8 ports).
>
> The valves are SY7000 (`SY7…`), so the base should be an **SS5Y7-51**. An SY7000 valve does not fit
> an SS5Y5 base. The rest of the label also says how it is wired (connector type and single/double
> wiring), which decides the pinout below. Full form (p. 223):
> `SS5Y` · series `3/5/7` · `-` · type `50/51` · connector `F/P/PG/PH` · entry `1/2` · wiring `Nil/S` ·
> `-` · stations `02…12` · P/E entry `U/D/B` · A/B port size · thread · mounting.

## Valve part numbers, decoded (catalogue p. 225)

`SY 7 1 0 0 - 5 U 1`

| Position | SY7100-5U1 | SY7300-5U1 | Meaning |
|---|---|---|---|
| Series | 7 | 7 | SY7000 |
| Actuation | **1** | **3** | 1 = 2-position single; 3 = **3-position closed centre** |
| Seal | 0 | 0 | Rubber seal |
| Pilot | — | — | Internal pilot |
| Back-pressure check valve | — | — | None (not offered on SY7000 or 3-position anyway) |
| Pilot valve option | — | — | Standard, 0.7 MPa |
| Coil type | — | — | **Standard. No power-saving circuit** (that would be `T`, and it only comes with `Z`/`NZ`) |
| Rated voltage | **5** | **5** | 24 VDC |
| Light/surge suppressor | **U** | **U** | **With indicator light and surge suppressor, non-polar (varistor)** |
| Manual override | — | — | Non-locking push |
| `1` | 1 | 1 | Fixed digit of the plug-in base-mounted code |
| Mounting screw | — | — | Round head combination screw |

So yesterday's open questions are settled: **standard coils, no power-saving circuit, non-locking
push override.**

## Valve specifications (pp. 15–16)

| | SY7100 (2-position single) | SY7300 (3-position closed centre) |
|---|---|---|
| Operating pressure (internal pilot) | **0.15–0.7 MPa** | **0.2–0.7 MPa** |
| Ambient and fluid temperature | −10 to 50 °C, no freezing | same |
| Max operating frequency | 5 Hz | 3 Hz |
| Response time at 0.5 MPa, `U` type | **≤ 53 ms** | **≤ 47 ms** |
| Coil voltage, tolerance | 24 VDC ±10 % (21.6–26.4 V) | same |
| Power, standard with indicator light | **0.4 W → 16.7 mA** at 24 V, per energised coil | same, per coil |
| Surge suppressor | Varistor (non-polar) | Varistor, one per coil |
| Indicator light | LED (SOL.a orange, SOL.b green on double coils) | |
| Mounting orientation | Unrestricted | Main valve horizontal |
| Enclosure | IP67 (valve); the metal-base manifold itself is **IP40** (p. 220) | |

Response is measured to JIS B 8419 with the coil at 20 °C and rated voltage. Add up to 10 ms for the
interposer's photorelay. The flaps and the air take longer than the valve, so measure open and close
times on site.

## Manifold: plug-in metal base, type 51 (pp. 220–224, 248–249)

| Item | SS5Y7-51 (for SY7000) |
|---|---|
| Ports | P (1), EA/EB (3/5) **3/8**, common to all stations; A/B **bottom ported** |
| Flow, rubber seal, 5 stations | P→A/B: C = 4.1 dm³/(s·bar), b = 0.34. A/B→E: C = 4.8, b = 0.20 |
| P/E entry | **D side only** for type 51 |
| Mounting | **Direct mounting only** for type 51 (no DIN rail) |
| Stations | 2–12 with a D-sub (F) or 26-pin ribbon (P) connector |
| Enclosure | IP40 |
| Internal wiring | **Positive common or negative common**, set by how COM is wired. Non-polar valves (`U`) work either way |
| Wiring type | `Nil` = all double wiring (any valve on any station). `S` = all single wiring, **only if every station is a 2-position single valve** |

**The SY7300 needs double wiring.** A manifold built "all single wiring" cannot drive its second coil
at all. With six single valves and one 3-position valve the base must be all double wiring
(`Nil`). The SY7100s then use only their SOL.a pin and leave SOL.b unused.

### D-sub (F, 25 pins) pinout: all double wiring (p. 248)

| Station | SOL.a pin | SOL.b pin |
|---|---|---|
| 1 | 1 | 14 |
| 2 | 2 | 15 |
| 3 | 3 | 16 |
| 4 | 4 | 17 |
| 5 | 5 | 18 |
| 6 | 6 | 19 |
| 7 | 7 | 20 |
| 8–12 | 8–12 | 21–25 |
| **COM** | **13** | |

Station 1 is the one nearest the **D side**. Polarity: in **positive common**, pin 13 is +24 V and
each SOL pin is the coil's (−) end. In **negative common**, pin 13 is 0 V and each SOL pin is (+).
The SMC cable is `AXT100-DS25-015/030/050` (1.5/3/5 m, 25 × 0.3 mm²). Its colour code per pin is on
p. 248. Ribbon-cable variants (P 26-pin, PG 20-pin, PH 10-pin) have their own tables on p. 249,
with COM on the last two pins.

## Wiring to the interposer

**Use positive common, with the interposer's JP1 in SINK (1-2, as shipped).**
- Manifold COM (D-sub pin 13) goes to the field +24 V.
- Each interposer output pulls its coil's SOL pin to FIELD_COM when energised.
- OUT then sits at +24 V when off and near 0 V when on. That keeps it positive with respect to
  FIELD_COM at all times, which the interposer's unidirectional TVS requires (`INTERPOSER-DESIGN.md`
  §2). Negative common with JP1 in SOURCE also works. Pick one and record it, because JP1 is
  board-global.

Proposed allocation, to be confirmed against the real station order:

| J26 | Interposer | Function | Manifold station / pin (positive common, all double wiring) |
|---|---|---|---|
| OUT1 | OUTB1 | Flaps, SY7300 **SOL.a** | Station of the SY7300, SOL.a |
| — | — | Flaps, SY7300 **SOL.b** | **No output left** (see below) |
| OUT2–OUT7 | OUTB2–7 | Air, six SY7100 SOL.a | Their stations' SOL.a pins |
| — | FIELD_24V | Manifold COM | Pin 13 |

### Electrical checks against the interposer

| Check | Value | Verdict |
|---|---|---|
| Current per output | 16.7 mA per coil (0.4 W standard with LED) | 21 % of the 80 mA envelope. **Passes** |
| Total from the field supply | 7 coils × 16.7 mA ≈ 0.12 A worst case | Negligible |
| Suppressor | Varistor in each valve (`U`) | Meets the interposer's "suppressed coils only" rule |
| Turn-off clamp | The `U` varistor clamps at **~47 V** across the coil (p. 292) | ⚠ See below |
| Polarity | Non-polar valve; the interposer still needs OUT ≥ FIELD_COM | Met by positive common + SINK |
| Pulse length | No power-saving circuit, so the 67 ms rule does not apply | Photorelay limit: ≥ 50 ms. Use ≥ 100 ms |

⚠ **Turn-off energy goes partly into the interposer's TVS. INFERRED, check on the bench.** In SINK
mode the coil's flyback lifts OUT to 24 V plus the coil's clamp voltage. The valve's varistor would
allow ~47 V across the coil, about 71 V at OUT. The interposer's SMAJ33A on OUT starts conducting at
~37 V, so it clamps first and takes the coil's stored energy on every turn-off. That is well inside
its rating: about a millijoule per event against a 400 W pulse rating. It also keeps OUT below the
photorelay's 60 V. Worth one scope shot of OUT at turn-off during bring-up.

## 🔴 The flap valve needs two outputs, and has one

The SY7300 has two coils:

| SOL.a | SOL.b | Valve | Flaps (assuming SOL.a = open) |
|---|---|---|---|
| on | off | Position a | Driven open |
| off | on | Position b | Driven closed |
| off | off | **Centre: all ports blocked** | **Held wherever they are** |
| on | on | Not allowed | — |

With OUT1 on SOL.a only:
- The reader can **open** the flaps but never **close** them. Dropping OUT1 returns the valve to
  centre and freezes the cylinder.
- On power loss, a dead JVM or an IN3 shutdown, **the flaps stay as they were**, open if a train was
  passing.

Options:
1. **Swap the flap valve for a seventh SY7100-5U1** (2-position single, spring return), plumbed so
   that de-energised = flaps closed. One output; power loss closes the flaps; all seven stations the
   same part. The manifold could then even be all single wiring. **Recommended**, if "closed on
   power loss" is what the WPMS wants.
2. **Keep the SY7300 and give SOL.b an output.** J26 is full, so an air valve would have to give way
   or share. The app then needs **≥ 20 ms with both coils off** between SOL.a and SOL.b, because
   the photorelays are only bounded at ≤ 10 ms and could otherwise overlap. There is no hardware
   interlock.
3. **Keep OUT1 on SOL.a only, deliberately**, if the WPMS vendor wants hold-on-failure and closes the
   flaps another way. The operator instructions must then say the reader cannot close them.

Ask the WPMS vendor which behaviour the flaps are meant to have on failure. A closed-centre valve is
usually chosen so that something does *not* move when power goes, which may be intentional here.

## Things the catalogue warns about that apply here

- **Continuous energising (p. 293).** A standard coil energised for long periods heats up, reducing
  life and performance. Take special care if **three or more adjacent stations** are on together.
  The six air valves on neighbouring stations, all blowing at once for a long time, is exactly that
  case. If the air stays on for minutes rather than seconds, power-saving valves (`…-5TZ1`, positive
  common, polar) are the catalogue's answer. Decide once the blowing sequence is known.
- **Surge intrusion on non-polar valves (p. 293).** When a breaker cuts the supply to large loads
  sharing the 24 V, the surge can switch a de-energised non-polar valve over for a moment. The
  remedy is polar valves (`Z`/`NZ`) or a diode between the load COM and the output COM. Relevant
  only if heavy loads share the field 24 V.
- **Operating pressure.** The 3-position valve needs **≥ 0.2 MPa** and the single ones ≥ 0.15 MPa,
  so the site supply must stay above 0.2 MPa while all six are blowing.
- **Temperature.** −10 to 50 °C at the valve. A trackside enclosure in Mumbai sun can exceed 50 °C.
- **IP40 manifold.** The metal base is IP40, not IP67, so it needs an enclosure against dust and rain.

## Open items

1. The full manifold label: series digit (5 or 7), connector type, wiring type, station count.
2. Which station each valve sits on, so the J26 → pin table can be completed.
3. The flap valve decision (above).
4. The valve sequence: what opens the flaps and starts the air, for how long, and what closes them.
   Duration also decides whether standard coils are acceptable.
5. Positive or negative common, recorded together with JP1's position on that interposer.
