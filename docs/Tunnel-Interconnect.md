# Reliance Tunnel — Interconnect and Wiring Schedule

**Status: DRAFT for review. Nothing here has been built or measured.** Written on the laptop, so
every hardware-dependent figure is inference from datasheets, not observation — see the two-machine
rule in `CLAUDE.md`. Figures marked **UNVERIFIED** need a vendor answer or a bench measurement before
anyone cuts a cable.

Version 0.6 · 2026-09-04 — **O7 is withdrawn: the shutdown indication is ONE lamp on O6, and no
lamp is to be fitted to O7** (§11.6); control power is ours; motor supply out of scope; restart
after shutdown is a full power cycle; power budget added (§4.1); 30 dBm thermal measurement

---

## 1. Scope

The Reliance warehouse tunnel drives its own conveyor. There is no PLC. This document defines the
electrical interconnect between seven items of equipment: the Intelli-RFID Reader, the Tunnel
Manager, three EZY-S100 conveyor driver cards and two SICK W26 sensors, plus the two lamps, the
shutdown push button and the power supplies.

It does **not** cover: the **motor power supply to the three EZY-S100 cards** — their `DC+` / `DC-`
comes from a separate supply provided by others and is out of scope here; the safety chain (see §11);
mechanical layout; antenna cabling; or the Ethernet link to the WMS.

**What we supply is the control power** — the `+` / `-` pair drawn on the left of the vendor's
"PNP IO Control Wiring Principle" diagram. See §7.1: the switches `S1` / `S2` / `S3` in that diagram
are literally the Tunnel Manager's outputs.

## 2. Names

| Name | Short | What it is |
|---|---|---|
| Intelli-RFID Reader | reader | Enclosure holding the IntelliRFID v2.1 board (CM4 + SIM7500). Connector **J26**, 12-way |
| Tunnel Manager | TM | Interposer box. Conditions the reader's 7 outputs to industrial drive levels; passes its 4 inputs through unmodified |
| Entry Conveyor | EnC | EZY-S100 card + motorised roller, upstream of the read zone |
| Reading Zone Conveyor | RZC | EZY-S100 card + roller inside the read zone. The only one with speed and reverse control |
| Exit Conveyor | ExC | EZY-S100 card + roller, downstream of the read zone |
| Entry Sensor | EnS | SICK W26 photoelectric, entry of the read zone |
| Exit Sensor | ExS | SICK W26 photoelectric, exit of the read zone |

## 3. Block diagram

```
        PSU-A   24 V CONTROL  (ours, ~60 W)
          |
          +--------- TB1 ---------+-------------------+
          |            |          |                   |
      [ reader ]    [  TM  ]      |                   |
          | J26        |          |                   |
          +--W1--------+          |                   |
           12 core     |          |                   |
                       |     TB3 (inputs) <---- EnS, ExS, shutdown button
                       |
                  TB2 (TM outputs)
                       |
     +-----------------+-------------------+----------------+
     |         |               |           |                |
  [ EnC ]   [ RZC ]         [ ExC ]     PASS / FAIL      SAFE TO
  Run A     Run A,B,Rev     Run A        lamps           POWER OFF lamp
  + COM     + COM           + COM

  DC+ / DC- of EnC, RZC, ExC  <---- SEPARATE MOTOR SUPPLY, out of scope
```

## 4. Power architecture

**One supply is in scope: the 24 V control rail, and we provide it.** It is the `+` / `-` pair on
the left of the vendor's PNP wiring diagram, and it powers everything on the signal side of the
system.

| Supply | Feeds | Sizing |
|---|---|---|
| **PSU-A — control 24 V (ours)** | reader, TM, EnS, ExS, shutdown button, all three lamps, and the `COM` / signal side of EnC, RZC and ExC | **0.61 A continuous / 0.36 A average / 0.90 A peak** with LED beacons — see the budget below. **60 W / 2.5 A.** Regulation matters as much as size — see §10 |
| Motor 24/48 V — **out of scope** | `DC+` / `DC-` of the three cards only | Provided by others. Recorded here only so nobody assumes PSU-A carries it: each card is rated **5 A peak**, so the three together are ~15 A of stepped load. **It must never be the same rail as PSU-A** — that load will brown out the CM4 and inject motor noise into the sensor and lamp lines |

Because we supply the control power outright, there is no bonding arrangement to design between two
rails of ours. There is one thing to confirm on the other side of the boundary:

> **UNVERIFIED — the one vendor question that touches the panel.** The EZY-S100 catalogue says `COM`
> connects to "the common end of the optocoupler", which implies the signal terminal is galvanically
> isolated from `DC-`. **If it is not isolated, then wiring `COM` to our control 0 V silently bonds
> our 0 V to the motor supply's 0 V through all three cards** — a bond we did not design, on a rail
> we do not control, carrying 15 A of stepped motor current past our sensor returns. Ask EzyRolls to
> confirm the isolation before the panel is built.

### 4.1 Power budget — where the 60 W comes from

**Nothing here is measured.** Every figure is a datasheet value or a reasoned estimate; one clamp
reading on the bench rig would replace most of them.

| Load | Continuous worst | Average | Peak |
|---|---|---|---|
| Reader at 24 V — CM4 ~4 W + SIM7500 + ~0.3 W other, over an 85 % buck. **At 27 dBm** (module 3.3 W) | 9.2 W (0.38 A) | 5.2 W (0.22 A) | **16 W (0.67 A)** |
| — same, **at 30 dBm** (module 4.5 W); see the thermal note below | 10.6 W (0.44 A) | 5.4 W (0.23 A) | **16 W (0.67 A)** — unchanged, the peak is the PA-enable transient |
| Reader field inputs, 3.35 mA each through 6.8 kΩ | 0.32 W | 0.07 W | 0.32 W |
| EnS + ExS, ≤ 30 mA each | 1.44 W | 1.44 W | 1.44 W |
| **Tunnel Manager** — 7 × 47 kΩ input pull-ups (0.36 mA per *asserted* channel) + 2 mA indicator LEDs. No logic, no regulator | **0.42 W** (allow 1.0 W) | 0.17 W | 0.42 W |
| EZY-S100 control inputs, 7.3 mA each (**UNVERIFIED**, Itoh CBM-105 proxy) | 0.88 W | 0.53 W | 0.88 W |
| Lamps, **LED beacon case**, max two lit | 2.4 W | ~1.2 W | 2.4 W |
| **Total** | **14.7 W, 0.61 A** | **8.6 W, 0.36 A** | **21.5 W, 0.90 A** |

**The figure that sizes the supply is the reader's coincident peak**, not the steady load: the
SIM7500's PA-enable transient (1.35 A at 5 V) landing on top of a busy CM4 (1.3 A at 5 V) is ~0.67 A
at 24 V, and it repeats **once per carton**. Specify constant-current, not hiccup, overload
behaviour. 60 W gives 4.1× on continuous and 2.8× on peak, and survives the 20–50 % derating most
DIN supplies apply by +55 °C.

> **If tower lamps, filament lamps or a sounder are chosen instead of LED beacons, go to 100 W /
> 4.2 A.** Two 500 mA lamps take the peak to ~43 W, and 60 W is then only 1.4× before derating.

**RF power barely moves this budget, and that is the point.** Between 23 and 30 dBm the reader's
*average* draw changes by about ±0.15 W, because at ~15 % duty the module sits in 0.76 W carrier-off
standby most of the time and the CM4 dominates. **60 W covers 30 dBm without argument.** The RF level
is a *thermal* decision, not a supply-sizing one — see the note in `CLAUDE.md` on the 2026-09-02
measurement and on why the PA sits ~45–50 °C above the reported module temperature.

The TM is **under 3 % of this budget in every case**. Its input stage draws current only while a
channel is asserted, and the design as chosen (§7, sourcing/PNP) needs no logic, no regulator and no
bias supply beyond the pull-up path itself. What does need sizing in the TM is not its own draw but
the load current transiting its +24 V feed: **fuse and track for ≥ 1.5 A** if tower lamps are used,
~0.3 A otherwise.

## 5. Cable schedule

| Ref | From | To | Cores | Notes |
|---|---|---|---|---|
| **W1** | reader **J26** | TM field inputs | **12** | The whole reader field interface. Screened, 0.5 mm². Screen earthed at the **reader end only** |
| W2 | PSU-A | TB1 | 2 | +24 V control, 0 V control |
| W3 | TB1 | reader 24 V input | 2 | |
| W4 | TB1 | TM 24 V input | 2 | |
| W5 | TB2 | EnC signal terminal | 4 | 2 used, 2 spare |
| W6 | TB2 | RZC signal terminal | 6 | 4 used, 2 spare |
| W7 | TB2 | ExC signal terminal | 4 | 2 used, 2 spare |
| W8 | TB3 | EnS | M12 4-pin cordset | Sensor needs 3 conductors: +24 V, 0 V, signal |
| W9 | TB3 | ExS | M12 4-pin cordset | |
| W10 | TB2 | PASS lamp (green) | 2 | |
| W11 | TB2 | FAIL lamp (red) | 2 | |
| W12 | TB2 | SAFE TO POWER OFF lamp | 2 | Mounted beside the shutdown button. See §11.6 |
| W13 | TB3 | shutdown push button | 2 | |
| **W14** | TB2 | daisy-chain `485A`/`485B` across all three cards | screened twisted pair | **Fit now even though it is unused.** See §12 |

The motor feed to each card's `DC+` / `DC-` is not listed: it comes from the separate supply and is
out of scope. Keep it physically separated from this schedule's cables where the routing allows.

## 6. W1 — reader to Tunnel Manager, 12 core

Direct pin-for-pin. No cross-overs, no conditioning in the cable.

| J26 pin | Reader channel | BCM | TM terminal | Function |
|---|---|---|---|---|
| 1 | OUT1 | 26 | TM-O1 in | `EnC_ExC_RUN` |
| 2 | OUT2 | 20 | TM-O2 in | `RZC_RUN_A` |
| 3 | OUT3 | 16 | TM-O3 in | `RZC_RUN_B` |
| 4 | OUT4 | 19 | TM-O4 in | `RZC_REVERSE` |
| 5 | OUT5 | 21 | TM-O5 in | `LAMP_PASS` |
| 6 | OUT6 | 12 | TM-O6 in | `LAMP_FAIL` |
| 7 | OUT7 | 13 | TM-O7 in | **spare** — parked, see §11.6 |
| 8 | FIELD_COM | — | TM FIELD_COM | **The single field 0 V for all 11 channels** |
| 9 | IN1 | 23 | TM-I1 (bare pass-through) | `ENTRY_SENSOR` |
| 10 | IN2 | 24 | TM-I2 (bare pass-through) | `EXIT_SENSOR` |
| 11 | IN3 | 18 | TM-I3 (bare pass-through) | `SHUTDOWN_REQUEST` |
| 12 | IN4 | 25 | TM-I4 (bare pass-through) | spare |

The four inputs are **routed through the TM as bare copper** — no components in the path. The reader's
input chain already has 2.3× margin at 24 V and does not want conditioning; the only added risk is
two more connector contacts, which is the price of keeping one connector and one field common.

## 7. TM outputs

TM output stage configured **sourcing (PNP)**: an asserted output puts +24 V control on the terminal;
the load returns to 0 V control. This makes 24 V = active everywhere in the panel — outputs, sensors
and button all read the same way.

| TM out | Terminal | Goes to | Notes |
|---|---|---|---|
| **O1** | TB2-1 (+ common TB2-C) | **Run A of EnC and Run A of ExC** | **Two card inputs in parallel on one channel** (~14.6 mA if the class figure holds), and **normally asserted** — see §7.2 |
| **O2** | TB2-2 | **Run A of RZC** | |
| **O3** | TB2-3 | **Run B of RZC** | With O2, gives 100 / 75 / 50 % / stop |
| **O4** | TB2-4 | **Reverse of RZC** | Runs opposite to the default direction |
| **O5** | TB2-5 | **PASS lamp, green** | See §9 for the current question |
| **O6** | TB2-6 | **FAIL lamp, red** | |
| **O7** | TB2-7 | **nothing — spare** | Terminate the core and leave it. **Do not fit a lamp here**; the shutdown indication is O6 alone. See §11.6 |

### 7.1 How this maps onto the vendor's own PNP diagram

The EZY-S100 manual's "PNP IO Control Wiring Principle" drawing shows a control power `+` / `-` pair
on the left, three switches `S1` / `S2` / `S3` feeding pins 4, 5 and 6, and the `-` going to pin 7
`Com`. **We supply that control power pair, and the switches are the Tunnel Manager's outputs.**

| In the vendor drawing | Card pin | On RZC | On EnC and ExC |
|---|---|---|---|
| control power `+` | — | +24 V control, into the TM output stage | same |
| `S1` | 4 `Reverse` | **O4** | not fitted |
| `S2` | 5 `Run A` | **O2** | **O1** (both cards on this one channel) |
| `S3` | 6 `Run B` | **O3** | not fitted |
| control power `-` | 7 `Com` | 0 V control | 0 V control |

EnC and ExC still need `Com`, even though only one switch is fitted on each.

### 7.2 O1 is a state machine, not a level

**O1 is HIGH by default — EnC and ExC run whenever a carton is not being read.** It drops LOW when
EnS sees a package and RZC takes over, and returns HIGH the moment the read finishes on **any**
outcome (SETTLED, COUNT_REACHED, PACKAGE_EXITED, TIMEOUT).

| Phase | O1 | O2/O3 (RZC) | O4 |
|---|---|---|---|
| Idle, no carton | **HIGH** — EnC and ExC running | low — RZC stopped | low |
| EnS fires, carton in the read zone | **LOW** | asserted per the selected speed | low, or asserted on a reverse pass |
| Read finished, any outcome | **HIGH** | released | low |
| Boot, reader dead, or 24 V removed | **LOW** — everything stopped | low | low |

Four consequences, and three are not obvious:

- **The backstop is load-bearing.** "Any outcome" has to include the non-outcomes: a read that never
  closes, a reader fault, a supervisor reconnect. If none arrives, O1 stays low and the line is
  stopped with a carton in the tunnel. `tunnel.max-duration-ms` must release O1, and the fault path
  must set O1 explicitly rather than leaving it where it was.
- **At boot the line does not run.** Outputs reset low, so EnC and ExC are stopped until the app is up
  and armed. Correct failsafe — a dead reader stops the line rather than running it — but someone
  will power the panel up, see a dead conveyor and call it a drive fault. Put it in the operator
  instruction.
- **EnC and ExC share one channel, so the line is serialised.** The previous carton cannot discharge
  while the current one is read; cycle time is read **plus** discharge, not the larger of the two.
  That is a throughput ceiling bought with the channel budget, and RS-485 (§12) is the way out —
  it addresses all three cards independently and needs no extra channels.
- **Stopping EnC the instant EnS fires drags the carton.** EnS is at the *entry* of the read zone, so
  at that moment the carton's leading edge is on RZC and its trailing edge is still on EnC — half on
  a stopped belt, half on a moving one. Either delay the EnC stop by the transfer time, or place EnS
  far enough downstream that the carton is fully transferred when it fires. **Open — decide from the
  real geometry.**

**RZC speed truth table** (from the EZY-S100 manual):

| Run A | Run B | Result |
|---|---|---|
| ON | OFF | 100 % |
| ON | ON | 75 % |
| OFF | ON | 50 % |
| OFF | OFF | stopped |

EnC and ExC have Run A only, so each is run/stop at 100 %.

## 8. TM inputs

| TM in | Terminal | Source | Wiring |
|---|---|---|---|
| **IN1** | TB3-2 | **EnS** | +24 V control out on TB3-1 to the sensor; sensor's switching output returns to TB3-2 |
| **IN2** | TB3-4 | **ExS** | +24 V control out on TB3-3; output returns to TB3-4 |
| **IN3** | TB3-6 | **shutdown push button** | +24 V control out on TB3-5; button returns to TB3-6. **5 second press** initiates CM4 shutdown |
| **IN4** | TB3-7 | spare | terminated only |

**Edge polarity.** Field 24 V present makes the reader's opto conduct, so the GPIO reads **LOW**. A
carton arriving at EnS is therefore a **falling** edge at GPIO 23, not a rising one. Outputs are
active-high at the GPIO and inputs are active-low — one `activeHigh` flag cannot serve both, so the
inversion is hidden inside `FieldIo` and no caller ever sees a raw edge constant.

Sensor 0 V returns to the control 0 V group on TB3. Reader-side software must **disable the internal
pull on GPIO 18, 23, 24 and 25** — the BCM2711 pull-down opposes the external 10 k pull-up and leaves
only ~0.44 V of margin. Debounce ≥ 10 ms on IN1/IN2; IN3 needs a long filter, require ≥ 3 s
continuous before acting on the 5 s press.

## 9. Why the Tunnel Manager exists, in numbers

| | Current |
|---|---|
| Reader opto output, guaranteed sink @ +25 °C | 2.5 mA |
| Reader opto output, guaranteed sink @ **+85 °C** | **1.9 mA** |
| One EZY-S100 control input — **UNVERIFIED**, taken from Itoh Denki CBM-105, the closest published card of the same class | **7.3 mA** |
| O1, driving EnC **and** ExC in parallel | **~14.6 mA** |
| EZY-S100 input threshold (from the EzyRolls MDR leaflet) | ON ≥ 13 V, OFF ≤ 2 V |

The reader alone is **3.8× short for one card and 7.7× short for the parallel pair**, and it also has
to hold the node at or below 2 V while carrying that current, which a 1.9 mA source cannot do. This
is the whole reason for the TM.

**TM channel ratings to specify:**

| Channel | Minimum rating | Reason |
|---|---|---|
| O2, O3, O4 | ≥ 50 mA | one card input, 7× margin on the class figure |
| **O1** | **≥ 100 mA** | two card inputs in parallel |
| **O5, O6** | **≥ 500 mA, or drive the lamps through an interposing relay** | see below |
| **O7** | none — spare | drives nothing; terminate the core only |

> **Lamp current is an open question, and it covers two channels.** A 24 V LED beacon element is
> typically 20–50 mA and is trivial. A filament lamp, a multi-tier tower, or a tower with a sounder
> can be 200–500 mA with a cold-inrush multiple on top, and inrush into a photorelay is how they
> die. **Specify the lamp part numbers and their steady and inrush currents before fixing the TM
> output stage**, or put interposing relays on O5 and O6 and stop worrying about it.
>
> **O6 carries a second duty and it changes the choice of lamp.** It is the FAIL lamp during
> running *and* the shutdown indicator, where it **blinks at roughly 2 Hz** for the length of the
> shutdown. Pick a lamp and a TM output stage that can actually blink at that rate: a filament lamp
> is too slow to give a convincing blink and an interposing relay switching 2 Hz continuously for
> the duration of a shutdown is being asked to do something a photorelay would do better.

## 10. Equipment settings that must be made before installation

**EZY-S100, all three cards:**

1. **PNP jumper.** The card ships with the signal mode set by an internal jumper; the third jumper
   from the top on the left selects `COM` behaviour and PNP/NPN. Set all three cards to **PNP**, and
   wire `COM` to control 0 V. **This requires opening the card's outer shell** — a bench task, not a
   ladder task, and ESD-sensitive. Do it before the cards go in the frame.
2. **DIP `CONFIG-2`** sets default direction (CCW/CW). Set it so that the **default** direction is
   forward and O4 `Reverse` genuinely reverses.
3. **DIP `CONFIG-3`** open/closed loop, **`CONFIG-4`** automatic/manual error recovery,
   **`CONFIG-5`** current limit — decide and record per card.
4. **SPEED DIP** sets the 100 % speed. RZC's three steps are percentages of it, so it sets the whole
   speed ladder.
5. **Address DIP** — set unique 485 addresses (EnC=1, RZC=2, ExC=3) **even though 485 is unused
   today.** It costs nothing now and needs the shell open again later.

> **Speed range is stated three different ways** by the vendor: 600–6900 rpm on the website,
> 500–3485 rpm in the catalogue's DIP table, 100–1000 rpm in the Modbus register map. Resolve before
> committing to a belt speed.

**SICK W26, both sensors:**

- Supply 10–30 V DC, ≤ 30 mA unloaded. Output ≤ 100 mA, short-circuit and reverse-polarity
  protected. Response ≤ 500 µs.
- Use the **PNP** output. On a push-pull variant that is pin 4 (black, light switching) or pin 2
  (white, dark switching) on the M12 — **pick whichever makes "carton present" = 24 V at the reader
  input**, which depends on whether the chosen variant is a proximity or a retro-reflective type.
- PNP HIGH is approximately **UB − 2.5 V**, so the reader sees ~21.5 V, not 24 V. Re-deriving the
  board's input table at that voltage gives a sink of 0.68 mA at +85 °C against the 0.33 mA needed —
  **~2.1× margin**. Use that row rather than the 24 V one.
  **Do not read it as clearing the board's 1.6× worst case**, because that figure is the 16.8 V
  corner and this one is 24 V nominal minus the sensor drop. If the control rail itself sags to
  16.8 V the sensor delivers ~14.3 V and the margin falls *below* 1.6×. **Hold the control rail at
  24 V ±10 %** — that is a PSU-A specification, not a nicety.
- **The exact ordering code is not yet chosen.** The document we hold is a family overview with no
  electrical table; the figures above come from `WTB26P-24161120A00` as a representative part.
  Confirm against the datasheet of whatever is actually bought.

## 11. Rules that must not be broken

1. **The reader never drives a field device directly.** Every output goes through the TM.
2. **One field common.** All 11 J26 channels share pin 8. Sensors, button, lamps and card signal
   commons all sit on the same control 0 V. No split supplies on the field side.
3. **Never bridge FIELD_COM to the reader's board ground.**
4. **Failsafe rests on polarity and it is load-bearing.** All seven outputs are on GPIO ≥ 9, which
   the BCM2711 resets pull-**down**, so outputs are off at boot: Run A and Run B de-asserted, all
   three conveyors stopped. **The TM must not invert this.** A sourcing TM output stage that is
   closed when its input is open would mean reader death = everything runs. **Verify physically** by
   killing reader power with the conveyor running, at commissioning, before the line is accepted.
5. **Do not move a field output onto GPIO 2–8.** Those reset pull-up.
6. **Shutdown is a hazard, not a convenience.** Cutting 24 V from a running CM4 risks corrupting the
   serial-number high-water file, the one file whose corruption silently duplicates serials. The IN3
   press must trigger: stop inventory → all conveyors stopped → finish or abort the in-flight write →
   fsync and close the counter → sync, remount read-only → then it is safe to cut power.
   **ONE LAMP, ON O6 — changed 2026-09-04. Version 0.5 of this document specified a second lamp on
   O7; it is withdrawn, and no lamp is to be fitted to O7.** The shutdown indication is O6, the same
   red lamp that shows a failed carton, and it carries three states rather than two channels
   carrying one each:

   | O6 | meaning |
   |---|---|
   | **blinking** (~2 Hz) | the shutdown sequence is running |
   | **solid lit** | the application has stopped; the OS is still coming down |
   | **dark** | **the board is down. 24 V may be removed.** |

   Three states on one channel say everything two channels said, and they say one thing two could
   not: *how far along it is*. The operator's instruction is still one line — *press and hold for
   five seconds, wait for the lamp to go out, then cut power* — but a blink that has stopped
   blinking now tells them the wait is nearly over rather than leaving them staring at an unlit lamp
   wondering whether anything happened.

   **Dark is produced in exactly one place**, and that is what makes it trustworthy: a script at
   `/usr/lib/systemd/system-shutdown/`, which `systemd-shutdown` runs *after* it has remounted the
   root filesystem read-only. It is deliberately not a systemd unit — a unit, however late it is
   ordered, still runs in the first phase of the shutdown, before that remount, and would light
   "safe to remove power" while the filesystem was still being flushed. That was a real defect on
   this build, found and fixed on 2026-09-04.

   **The failure direction is still the safe one, and it is now safe in both directions.** A
   pinctrl level outlives the process that set it, so the lamp stays lit through the halt until
   24 V is actually removed. A reader that is unpowered or crashed shows the lamp dark — but a
   crashed reader has not been asked to shut down, and an operator only reads this lamp after
   pressing the button. A shutdown that *fails* (a missing sudoers grant, say) leaves it **lit**,
   never dark: lit says "not yet" and the operator falls back to the documented worst-case wait.

   **What O7 is now: a terminated spare.** Wire the core, land it on TB2-7, fit nothing. It is
   parked in the reader's own channel map, so the application refuses to drive it and only the
   wiring screen can, which is how its continuity gets proven at commissioning like every other
   channel. It is the only free output on J26, and it is **earmarked** — if the 1 Hz liveness
   heartbeat is ever wanted back (a hardware signal that survives a hung JVM and lets a watchdog
   stop the line), it belongs here. Do not spend it on anything smaller without settling that.
   - **Restart is a full power cycle. Decided 2026-09-02, and it is the only way.** A CM4 that has
     been shut down does not come back on its own, and nothing in this system wakes it. So the
     complete procedure is: **hold the button 5 s → wait for the SAFE TO POWER OFF lamp → remove
     24 V → re-apply 24 V.** Whoever removes the power is the only person who can restore it.
   - **Two consequences of that, and they change where the button goes.** There is **no remote
     recovery**: once someone presses it, the tunnel is down until a person is physically at the
     panel. And a press is therefore a *maintenance* action, not an operator convenience — **the
     button belongs inside the panel or behind a key, not on the operator face.** A shift operator
     who presses it to "reset a jam" has stopped the line until an engineer arrives.
   - The board's SAMD21 supervisor runs independently off 24 V and holds `CM4_EN`, so a
     software-driven restart is *physically* possible on this hardware. **Nothing implements it, and
     this system does not use it.** If remote recovery is ever wanted, that is where it would live —
     as a deliberate piece of work, not an assumption.
7. **The J26 lines carry no surge protection on the v2.1 board.** A conveyor and three motor cards on
   a shared panel are a far worse transient source than the trackside analysis assumed. **The TVS
   belongs in the TM** on all 11 lines.
8. **Safety is outside this document.** The EZY-S100 has no Safe Torque Off. Driving a conveyor
   brings ISO 13849-1 / IEC 62061 obligations and a competent safety assessment is required before
   layout. The E-stop chain must never route through reader software, and reader outputs must be
   physically incapable of producing motion when the safety chain is open.

## 12. Fit the RS-485 pair now

The EZY-S100 supports Modbus RTU (38400 8N1, addresses 1–255) with a continuous speed setpoint
(100–1000 rpm), acceleration and deceleration, actual-speed and bus-current readback, and eight fault
bits including stall and over-current. That is a strictly better interface than three digital
channels and three speeds, and bus current reveals a jam before a sensor does.

We are not using it today because the v2.1 board has no RS-485 port — UART0 is the reader and UART3
is the SAMD21 supervisor — so it needs an isolated transceiver in the TM or an isolated USB-RS485.
**But pulling W14 and setting the card addresses costs nothing now and costs a shutdown and three
opened enclosures later.** Do it during the first install.

If it is ever adopted: `BDAT0.3` selects 485 mode versus I/O mode and **defaults to I/O**, so
confirm with EzyRolls whether that selection survives a power cycle before designing anything that
depends on it. And keep stop on a hardwired output regardless — stopping must never depend on a
serial transaction completing.

## 13. Open items

| # | Item | Blocks |
|---|---|---|
| 1 | EZY-S100 control-input current and thresholds at 24 V, over temperature | Final TM output-stage rating |
| 2 | Is the EZY-S100 signal terminal isolated from `DC-`? | The 0 V bond plan, §4 |
| 3 | Lamp part numbers, steady current and inrush — **and whether O6's can blink at 2 Hz** | O5/O6 rating, §9 |
| 4 | Exact SICK W26 ordering codes, and light- vs dark-switching | §10 |
| 5 | Where the shutdown button is mounted — panel interior or keyswitch, **not** the operator face | §11.6 |
| 6 | Which speed-range figure is real | Belt speed, §10 |
| 7 | Safety assessment and the E-stop / STO architecture | Everything mechanical |
| 8 | Is the reader permitted to reverse the conveyor at all? | Whether O4 is used |

Closed since 0.1: **the shutdown indication is one lamp on O6 and O7 is spare** (§11.6, changed in
0.6 — 0.5 had O7 as `SAFE_TO_POWER_OFF`); **restart after shutdown is a full power cycle and there is
no other way** (§11.6); and the two-supply bonding question is gone now that the motor supply is out
of scope (§4) — what remains of it is the card isolation question, item 2.

## 14. Commissioning checks

1. **Loop-test all 11 channels** before trusting any of them. Protection resistors fail open
   silently, and the reader has no way to know.
2. Assert each output one at a time and confirm exactly one card input or lamp responds.
3. Confirm the RZC speed ladder end to end: measure belt speed at 100 / 75 / 50 %.
4. **Kill reader power with the conveyor running.** Everything must stop. If anything runs, the TM
   polarity is inverted and the line is not safe to accept.
5. Break each beam by hand and confirm the correct reader input asserts, and only that one.
6. Hold the shutdown button for 5 s and confirm the full sequence: conveyors stop, then the SAFE TO
   POWER OFF lamp lights, and **only then** is power cut. Confirm the lamp is dark with the reader
   unpowered. Then re-apply 24 V and time the full cold start to a reader that answers
   `/api/v1/reader/status` — **that figure is the site's downtime cost for one press**, and it needs
   to be written into the operator instruction rather than discovered during a shift.
7. Record the measured current on one card input — that number closes open item 1 permanently.
