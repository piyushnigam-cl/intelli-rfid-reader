# WPMS pneumatics: SMC SS5Y manifold, SY7100 and SY7300 valves

The wayside reader drives the WPMS pneumatics from J26 OUT1–OUT6, through the interposer
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
| 1 | **SS5Y7-10F1-07B-C8D0** | Plug-in **connector connecting base, type 10 (side ported)**, 7 stations | Carries the valves; common supply and exhaust; one D-sub for all coils |
| 6 | **SY7100-5U1** | SY7000, 2-position single solenoid | Air blow, one per WPMS module: Externals on their own outputs (OUT3, OUT6), Internals and Diameters paired (OUT4, OUT5) |
| 1 | **SY7300-5U1** | SY7000, 3-position closed centre, two solenoids | WPMS flaps: SOL.a open (OUT1), SOL.b close (OUT2) |

**Corrected 2026-10-09:** the operator first reported the block as "SS5Y51". The full part number is
**SS5Y7-10F1-07B-C8D0**: a type-10 connector base, not a type-51 metal base. The valves fit it
(catalogue p. 41: the type-10 example lists `SY3100-5U1` / `SY3200-5U1` / `SY3300-5U1` on an
`SS5Y3-10F1` base). Decoded (pp. 41–42):

| Field | Value | Meaning |
|---|---|---|
| `SS5Y7` | 7 | SY7000 series, matching the valves |
| `-10` | 10 | Connector connecting base, **side ported** |
| `F` | F | **D-sub, 25 pins, IP40** (`FW` would be the IP67 D-sub) |
| `1` | 1 | Connector entry upward |
| `07` | 7 | **7 stations, double wiring**: every station has SOL.a and SOL.b, so the SY7300 works on any station |
| `B` | B | P/E ports on **both** sides |
| (nil) | — | SUP/EXH block: internal pilot, matching the valves' internal pilot |
| `C8` | C8 | A/B ports **ø8 one-touch** (P/E are ø12 one-touch on SY7000) |
| `D0` | D0 | **DIN rail mounting, rail not included** (brackets only): supply a 35 mm rail |

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

## Manifold: SS5Y7-10F1-07B-C8D0 (pp. 36–42, 55)

| Item | Value |
|---|---|
| Type | Plug-in connector connecting base, side ported, 7 stations |
| Ports | A/B ø8 one-touch per station; P and 3/5 (E) common, ø12 one-touch, both ends |
| Electrical | One **D-sub 25-pin (IP40)** for all 14 coil positions, double wiring |
| Internal wiring | **Positive common or negative common**, set by how COM is wired. Non-polar valves (`U`) work either way |
| Mounting | DIN rail (rail not supplied) |

Double wiring means each SY7100 uses only its SOL.a pin and leaves SOL.b unused, which the catalogue
calls "an unused control signal". That is harmless.

### D-sub (F, 25 pins) pinout: double wiring (p. 55; the metal base on p. 248 is identical)

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
The SMC cable is `AXT100-DS25-015/030/050` (1.5/3/5 m, 25 × 0.3 mm²), with its colour code per pin
in the catalogue.

## Wiring to the interposer

**Use positive common, with the interposer's JP1 in SINK (1-2, as shipped).**
- Manifold COM (D-sub pin 13) goes to the field +24 V.
- Each interposer output pulls its coil's SOL pin to FIELD_COM when energised.
- OUT then sits at +24 V when off and near 0 V when on. That keeps it positive with respect to
  FIELD_COM at all times, which the interposer's unidirectional TVS requires (`INTERPOSER-DESIGN.md`
  §2). Negative common with JP1 in SOURCE also works. Pick one and record it, because JP1 is
  board-global.

Allocation (operator, 2026-10-09, revised the same day to split the External pair). The stations are
still to be confirmed against the real manifold:

| J26 | Interposer | Function | Coils | Manifold pins (positive common, double wiring) |
|---|---|---|---|---|
| OUT1 | OUTB1 | Flaps **open** | SY7300 SOL.a | SY7300 station, SOL.a |
| OUT2 | OUTB2 | Flaps **close** | SY7300 SOL.b | SY7300 station, SOL.b |
| OUT3 | OUTB3 | Air, Left External | 1 × SY7100 SOL.a | Its station's SOL.a pin |
| OUT4 | OUTB4 | Air, Left Internal + Right Internal | 2 × SY7100 SOL.a | Both stations' SOL.a pins, joined |
| OUT5 | OUTB5 | Air, Right Diameter + Left Diameter | 2 × SY7100 SOL.a | Both stations' SOL.a pins, joined |
| OUT6 | OUTB6 | Air, Right External | 1 × SY7100 SOL.a | Its station's SOL.a pin |
| OUT7 | — | Spare | — | — |
| — | FIELD_24V | Manifold COM | — | Pin 13 |

Join each pair at the D-sub cable or a terminal block; the manifold itself needs no change. A pair
can only blow together, and splitting it later is a rewire. If the stations are free to choose, put
each pair on adjacent stations so the joins are short.

### Electrical checks against the interposer

| Check | Value | Verdict |
|---|---|---|
| Current per output | 16.7 mA on OUT1, OUT2, OUT3, OUT6 (one coil); **33.4 mA** on OUT4, OUT5 (two coils in parallel) | 21 % and 42 % of the 80 mA envelope. **Passes** |
| Total from the field supply | 6 air coils + 1 flap coil (never both flap coils) × 16.7 mA ≈ 0.12 A worst case | Negligible |
| Suppressor | Varistor in each valve (`U`) | Meets the interposer's "suppressed coils only" rule |
| Turn-off clamp | The `U` varistor clamps at **~47 V** across the coil (p. 292) | ⚠ See below |
| Polarity | Non-polar valve; the interposer still needs OUT ≥ FIELD_COM | Met by positive common + SINK |
| Pulse length | No power-saving circuit, so the 67 ms rule does not apply | Photorelay limit: ≥ 50 ms. Use ≥ 100 ms |

⚠ **Turn-off energy goes partly into the interposer's TVS. INFERRED, check on the bench.** In SINK
mode the coil's flyback lifts OUT to 24 V plus the coil's clamp voltage. The valve's varistor would
allow ~47 V across the coil, about 71 V at OUT. The interposer's SMAJ33A on OUT starts conducting at
~37 V, so it clamps first and takes the coil's stored energy on every turn-off. That is well inside
its rating: about a millijoule per coil per event (two on a paired output) against a 400 W pulse rating. It also keeps OUT below the
photorelay's 60 V. Worth one scope shot of OUT at turn-off during bring-up.

## The flap valve has two outputs (resolved 2026-10-09)

The SY7300 has two coils:

| OUT1 (SOL.a) | OUT2 (SOL.b) | Valve | Flaps |
|---|---|---|---|
| on | off | Position a | Driven **open** |
| off | on | Position b | Driven **closed** |
| off | off | **Centre: all ports blocked** | **Held wherever they are** |
| on | on | **Not allowed** | — |

The first allocation gave the flaps OUT1 only, so they could be opened and never closed. Pairing the
air valves freed OUT2 for SOL.b. Which coil opens and which closes depends on the plumbing to the
cylinder: confirm on site that OUT1 opens.

What the app has to do, because nothing in hardware does it:
- **Never energise OUT1 and OUT2 together**, and keep **≥ 20 ms with both off** between dropping
  one and raising the other. Each photorelay may take up to 10 ms to release, and there is no
  hardware interlock.
- **Drive the flaps closed explicitly** on every stop path the JVM survives: pass end, fault, disarm,
  IN3 shutdown. Dropping every output is not enough, because the closed centre holds the flaps.
- **Power loss, a dead JVM or a hung app leave the flaps where they were**, open if a train was
  passing. That is the valve's design; ask the WPMS vendor whether it is acceptable, since a
  spring-return SY7100 on the flaps would close them on power loss instead.
- **Pulse or hold.** The valve returns to centre when its coil drops, and the cylinder stops
  wherever it got to. A pulse must outlast the full travel, so measure open and close times on site;
  holding the coil for the whole movement is simpler. Max operating frequency is 3 Hz.

## Things the catalogue warns about that apply here

- **Continuous energising (p. 293).** A standard coil energised for long periods heats up, reducing
  life and performance. Take special care if **three or more adjacent stations** are on together.
  The six air valves on neighbouring stations, all blowing at once for a long time, is exactly that
  case, and pairing makes it more likely, since each pair energises two stations at once. If the air stays on for minutes rather than seconds, power-saving valves (`…-5TZ1`, positive
  common, polar) are the catalogue's answer. Decide once the blowing sequence is known.
- **Surge intrusion on non-polar valves (p. 293).** When a breaker cuts the supply to large loads
  sharing the 24 V, the surge can switch a de-energised non-polar valve over for a moment. The
  remedy is polar valves (`Z`/`NZ`) or a diode between the load COM and the output COM. Relevant
  only if heavy loads share the field 24 V.
- **Operating pressure.** The 3-position valve needs **≥ 0.2 MPa** and the single ones ≥ 0.15 MPa,
  so the site supply must stay above 0.2 MPa while all six are blowing.
- **Temperature.** −10 to 50 °C at the valve. A trackside enclosure in Mumbai sun can exceed 50 °C.
- **IP40 connector.** The `F` D-sub is IP40, not IP67, so the manifold needs an enclosure against dust and rain.

## Open items

1. ~~The full manifold label~~: **SS5Y7-10F1-07B-C8D0**, compatible with both valves.
2. Which station each valve sits on, so the J26 → pin table can be completed.
3. ~~The flap valve decision~~: both coils driven, OUT1 open and OUT2 close. Still open: pulse or
   hold, the travel times, and whether start-up drives the flaps closed.
4. The valve sequence: what opens the flaps and starts the air, for how long, and what closes them.
   Duration also decides whether standard coils are acceptable.
5. Positive or negative common, recorded together with JP1's position on that interposer.
