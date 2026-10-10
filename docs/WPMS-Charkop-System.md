# WPMS at Charkop, Mumbai: the installed system and the IntelliRFID retrofit

The **Wheel Profile Measurement System (WPMS)** at Charkop depot is a trackside station that
measures the wheels of passing trains. Today an **Omron NX1P2** controller runs it. The
**IntelliRFID wayside reader** (`intelli-wayside-reader`, design in `Wayside-Reader-Design.md`) is
added alongside it, with two physical changes:

1. **Wheel sensors.** The reader takes the Frauscher wheel-sensor current loops **in series with the
   Omron's analog input card**. Both controllers measure the same loop current.
2. **Pneumatics.** The reader **replaces the Omron's digital outputs** to the WPMS valve manifold,
   through the interposer.

This is the record of that design. Written 2026-10-10 from a cloud session, from the operator's
description, Omron's published data and what the repos already hold. **Nothing here has been
measured at Charkop.** Everything marked *to confirm* must be checked against the panel before
anything is rewired.

Related documents:

| Document | What it covers |
|---|---|
| `Wayside-Reader-Design.md` §2.0 | Wheel 1/Wheel 2 naming, direction, layout distances, the J26 map |
| `WPMS-Pneumatics-SMC.md` | The SMC manifold and valves, coil electrics, the flap-valve rules |
| `intelli-pcb-interposer/INTERPOSER-DESIGN.md` | The interposer's output envelope (≤ 80 mA, ≤ 30 V, OUT ≥ FIELD_COM) |
| `intelli-pcb-rfid-v2/WHEEL-SENSOR-JIG.md` | J22/J23 pinout and the 330 Ω front end, verified from the PCB |
| `intelli-train-simulator/REQUIREMENTS.md` | The series-loop case the simulator is built to prove |

---

## 1. The site

```
   Wheel 1 (J23) ──13 m── [ WPMS 3.5 m ] ──18.5 m── Wheel 2 (J22)      UP ──►
```

Starting values from the operator (2026-10-09), to be measured on site. They are in the wayside
app's packaged `application.yml` as `wheel1-to-wpms-m`, `wpms-length-m` and `wpms-to-wheel2-m`.
Wheel 1 first is `UP`, Wheel 2 first is `DOWN`.

The WPMS has six measuring modules: Left External, Left Internal, Right Internal, Right External,
Right Diameter and Left Diameter. Each one needs an air blow, and flaps open over the whole
station. The pneumatics are one SMC manifold (§4).

## 2. The installed controller (Omron) — as found

| Item | Part | What it is (Omron's published data) |
|---|---|---|
| CPU | **NX1P2-9024DT1** | NX1P2 machine controller with built-in I/O: **14 DC inputs** (PNP or NPN wiring) and **10 transistor outputs**. The `DT1` suffix is the **PNP (sourcing)** output variant; `DT` is NPN. Supply 20.4–28.8 V DC, 1.5 MB program memory |
| Analog input | **NX-AD4204** | NX-bus analog input unit: **8 channels, 4–20 mA, differential**, resolution 1/8000, 250 µs per channel. Input impedance **85 Ω**, as already recorded for the series-sharing scheme (`intelli-train-simulator/REQUIREMENTS.md`, from the WPMS retrofit wiring) |

**To confirm on the unit's datasheet:** the NX-AD4204's input impedance (85 Ω), its common-mode
range (§3.3) and what it reports below 4 mA (§3.4). Also the NX1P2-9024DT1's output rating per
point and per common. Distributor listings disagree, so take it from Omron's datasheet or the panel
drawing. The output *type* matters most here, because it decides how the manifold is wired today
(§4.2).

**What the Omron does today, inferred from the parts:**
- The NX-AD4204 reads the wheel-sensor loops. Each Frauscher RSR110d is two loops, so two sensors
  use 4 of its 8 channels.
- The NX1P2's PNP outputs energise the valve coils: flaps and air.
- Its program decides the valve sequence: when the flaps open, which modules blow, for how long.
  **That sequence is exactly what the wayside app does not yet know** (`Wayside-Reader-Design.md`,
  "Not decided yet").

**A record that may disagree:** `intelli-train-simulator/REQUIREMENTS.md` describes a legacy
"WheelPro-26" panel with **6 loops**, which would be three RSR110d. The reader has **4 loop inputs**
(J22, J23). If Charkop has a third sensor, it stays on the Omron only. *To confirm:* how many wheel
sensors are on the track, where they are, and which NX-AD4204 channel each loop uses.

## 3. Wheel sensors: the reader in series with the Omron

### 3.1 Why series works

The RSR110d is a **2-wire, loop-powered, constant-current** sensor: 5 mA free, dropping to about
3 mA when a wheel damps it (operator; confirm with Frauscher's documentation). It holds its current
whatever resistance is in the loop, within its supply window (8–33 V across the sensor). So two
measuring resistors in series, the Omron's 85 Ω and the reader's 330 Ω, **both see the same current
and neither disturbs the other.** Neither controller needs to know the other exists.

### 3.2 Loop wiring, per loop (×4)

The reader's burden is referenced to its own ground, so **the reader must sit at the bottom (0 V)
end of the loop**. The Omron's differential input goes in the middle.

```
   +24 V (ONE loop supply, see 3.3)
     │
     ├──► RSR110d system n  (+)
     │                       (−) ──► NX-AD4204  CHn+      (85 Ω, differential)
     │                                          CHn− ──► Reader J23/J22 pin 2 or 4
     │                                                        │
     │                                                  330 Ω burden (R45–R48)
     │                                                        │
     └─────────────────────────────── 0 V ◄──────────── Reader GND (pin 5)
```

Retrofit as a wiring change: today each loop most likely returns from `CHn−` straight to the panel
0 V. **The retrofit breaks that one link and routes it through the reader** (`CHn−` → reader sense
pin, reader GND → panel 0 V). *To confirm:* the actual loop wiring in the panel drawing.

Reader connector map (verified from the PCB, `WHEEL-SENSOR-JIG.md`):

| Sensor | Reader connector | Pin 2 | Pin 4 | Pins 1, 3 | Pin 5 |
|---|---|---|---|---|---|
| **Wheel 1** | **J23** | element 1 (`WSB1`) | element 2, the one on the Wheel 1 side (`WSB2`) | `V_SENB` +24 V via PTC F3 | GND |
| **Wheel 2** | **J22** | element 1 (`WSA1`) | element 2 (`WSA2`) | `V_SENA` +24 V via PTC F2 | GND |

The element on pin 4 must be the one on the Wheel 1 side, or every pass reports `UNKNOWN`
(`Wayside-Reader-Design.md` §2.0).

### 3.3 One loop supply, and one 0 V

Each loop must have **exactly one** source of current. There are two options:

| | **A. Panel supplies the loop (recommended)** | B. Reader supplies the loop |
|---|---|---|
| +24 V into the sensor | The panel's existing feed, unchanged | Reader `V_SEN` (J2x pins 1/3), through the board's PTC and TVS |
| Reader pins 1/3 | **Left unconnected** | Wired to the sensor |
| Reader powered off | Omron still reads correctly: the 330 Ω is passive and the current is unchanged | **The Omron loses all its wheel sensors** |
| Reader unplugged | Loop open, so the Omron loses that loop (see 3.5) | Same |
| Needs | Reader GND bonded to panel 0 V | Reader GND bonded to panel 0 V; panel feed to the sensor removed |

**Recommendation: A.** The Omron keeps working with the reader dead, which is what a retrofit beside
a working system should guarantee. Under either option, the reader's ground and the panel 0 V must
be one point. The board's wheel front end is not isolated, and the burden returns to board ground.
Simplest is to power the reader from the panel's own 24 V supply. That also satisfies the interposer
rule that all J26 field devices share one 24 V source.

The Omron's input then sits ~1.7 V above panel 0 V (5 mA in 330 Ω), up to ~3.3 V at the reader's
~10 mA full scale. A differential input should accept that. *To confirm* against the NX-AD4204's
common-mode range.

### 3.4 Loop budget

At the reader's ~10 mA full scale, worst case:

| Drop | Value |
|---|---|
| Reader burden 330 Ω | 3.3 V |
| Omron NX-AD4204 85 Ω | 0.85 V |
| Cable, terminals, PTC (if option B) | ≲ 0.5 V for a few hundred metres of 0.75 mm² |
| **Left across the sensor at 20.4 V supply** | **~15.8 V**, against the sensor's 8 V minimum ✅ |

**The tighter limit is loop resistance.** Frauscher's converter documents (WSC001/WSC003) are quoted
second-hand as allowing **≤ 500 Ω** of loop resistance (`WHEEL-SENSOR-JIG.md`). 330 + 85 = **415 Ω
before any cable**, which leaves ~85 Ω for cable, terminals and anything else in the loop. *To
confirm:* the real limit from Frauscher's documentation, and the cable length to each sensor.

**The Omron's view of the dip.** 3 mA is below the 4–20 mA span. Whatever the Omron does with it
today, under-range reading or a fault flag its program handles, **the retrofit does not change it**,
because the loop current does not change. Worth knowing when reading the Omron's diagnostics during
commissioning.

The reader's own scale: SAMD21 firmware `f80b0a3` uses 2441 µA/LSB for the 330 Ω burden, ~10.0 mA
full scale. It is not yet verified against a known current (`BOARD_FRONTEND_VERIFIED 0`); the train
simulator's 5.000 mA is the check.

### 3.5 Removing the reader must not blind the Omron

In series, **unplugging J22 or J23 opens those loops**, and the Omron loses the sensor. So fit a
**bypass for each loop at the panel terminals**: a link or shorting terminal from the Omron's `CHn−`
straight to 0 V. Close it before the reader's connector is removed, and open it after the connector
is back. Label it. This is the one new failure mode the retrofit adds to a system that worked
without the reader.

## 4. Pneumatics: the reader replaces the Omron's outputs

### 4.1 The new output map (operator, 2026-10-09)

The reader's J26 drives the valves through the interposer. The full electrical detail is in
`WPMS-Pneumatics-SMC.md`.

| J26 | Function | Coils | Current |
|---|---|---|---|
| OUT1 | Flaps **open** | SY7300 SOL.a | 16.7 mA |
| OUT2 | Flaps **close** | SY7300 SOL.b | 16.7 mA |
| OUT3 | Air, Left External | 1 × SY7100 | 16.7 mA |
| OUT4 | Air, Left Internal + Right Internal | 2 × SY7100 | 33 mA |
| OUT5 | Air, Right Diameter + Left Diameter | 2 × SY7100 | 33 mA |
| OUT6 | Air, Right External | 1 × SY7100 | 16.7 mA |
| OUT7 | Spare | — | — |
| IN3 | Held 5 s: shuts the CM4 down | | |
| IN1, IN2, IN4 | Spare | | |

Manifold: **SMC SS5Y7-10F1-07B-C8D0**, 7 stations, 25-pin D-sub, double wiring. Valves: 6 ×
SY7100-5U1 (air) and 1 × SY7300-5U1 (flaps, 3-position closed centre).

*To record at site:* which Omron output drives which coil today, and on which manifold station each
valve sits. The new map should keep the same coil-to-module assignment the Omron used.

### 4.2 Common polarity: keep what the Omron wired

The NX1P2-9024DT1's outputs are **PNP (sourcing)**. So the manifold is most likely wired
**negative common**: D-sub pin 13 = 0 V, and the Omron sources +24 V into each SOL pin.
`WPMS-Pneumatics-SMC.md` recommends positive common with the interposer's JP1 in SINK, written
before the Omron was known. **If the panel is negative common, set the interposer's JP1 to SOURCE
(2-3) and keep the manifold wiring as it is.** Only the output wires move, from the Omron's output
terminals to the interposer's.

| As found | Interposer JP1 | Manifold change |
|---|---|---|
| Negative common (expected with PNP outputs) | **SOURCE (2-3)** | None |
| Positive common | SINK (1-2, as shipped) | None |

Both modes keep OUT positive with respect to FIELD_COM in steady state, as the interposer requires.
One difference, INFERRED: in SOURCE mode the coil's switch-off current freewheels through the
interposer's TVS in its forward direction, so the valve may release a little more slowly than in
SINK mode. It is a few milliseconds against a 47–53 ms valve response; check it on a scope during
bring-up.

### 4.3 Disconnect the Omron's outputs, physically

**Every Omron output that drove a valve coil must be disconnected from that coil, not just left
idle.** The Omron's program keeps running after the retrofit and will go on switching its outputs on
every train. If an Omron output and an interposer output share a coil:
- Either controller can energise it, so the reader cannot guarantee "off".
- On the SY7300, the Omron could drive SOL.a while the reader drives SOL.b. **Both coils on is not
  allowed on that valve.**

Park the disconnected Omron output wires on labelled spare terminals so the change can be reversed.

### 4.4 Rules the wayside app must keep (from `WPMS-Pneumatics-SMC.md`)

- **OUT1 and OUT2 are never on together.** Keep ≥ 20 ms with both off when switching between them.
- **Both off holds the flaps where they are.** A dead JVM, a 24 V loss or an IN3 shutdown leaves them
  in their last position. Closing them is an explicit step on every stop path the app survives.
- The valve sequence is still not decided. See §5 for where it can come from.

## 5. Learning the valve sequence from the Omron before cutting over

The Omron's program already knows when to open the flaps, which air pairs to blow, and for how long.
That is the sequence the wayside app needs. Two ways to get it:

1. **From the program.** Ask the WPMS supplier for the Sysmac Studio project, or an export of the
   output logic and timers. That gives the intent, including edge cases (aborted passes, faults).
2. **By watching it.** Before the outputs are moved, wire some Omron outputs to the reader's spare
   inputs (IN1, IN2, IN4). An Omron PNP output applies +24 V, which is what a J26 input expects.
   Then log their timing against the wheel events the reader is already seeing in series. Three
   inputs cover three outputs per run, for example flaps-open, flaps-close and one air pair, so
   several runs cover all six. It gives the real timings at real train speeds. *To check first:*
   that the Omron output's common and the reader's FIELD_COM are the same 0 V.

Do both if possible: the program for intent, the capture for the numbers.

## 6. Cut-over order (proposed)

1. **Survey** the panel: loop wiring, sensor count, the NX-AD4204 channel map, the Omron output →
   coil map, manifold common polarity, cable lengths, the panel 24 V supply. Photograph and label.
2. **Wheel loops in series** (§3), bypass links fitted (§3.5), outputs untouched. The Omron must keep
   working unchanged. Check its readings before and after on the same train.
3. **Shadow run.** The reader logs passes, axles, direction and speed, and optionally the Omron's
   outputs (§5). No valve is driven by the reader.
4. **Outputs moved** (§4): Omron outputs disconnected and parked, interposer wired, JP1 set to match
   the common (§4.2), valve sequence implemented and bench-tested with the train simulator first.
5. **Live**, with the parked Omron wires as the way back.

## 7. Open items

| # | Item | Where it is answered |
|---|---|---|
| 1 | Number of wheel sensors and which NX-AD4204 channel each loop uses (2 or 3 sensors?) | Panel survey |
| 2 | The loop wiring today: who supplies it, where `CHn−` returns | Panel drawing / survey |
| 3 | NX-AD4204 input impedance, common-mode range, below-4 mA behaviour | Omron datasheet |
| 4 | Frauscher loop-resistance limit (≤ 500 Ω second-hand) and the cable lengths | Frauscher docs, survey |
| 5 | Omron output → coil map, and manifold station order | Survey |
| 6 | Manifold common polarity, which decides JP1 | Survey (§4.2) |
| 7 | The valve sequence | Omron program and/or shadow capture (§5) |
| 8 | What else the Omron does with its other outputs and inputs (lasers, cameras, interlocks), so nothing it still needs is removed | Survey / supplier |
| 9 | Whether the Omron program reacts to its outputs being disconnected (output feedback, short-circuit diagnostics on the DT1's protected outputs) | Supplier / commissioning |
