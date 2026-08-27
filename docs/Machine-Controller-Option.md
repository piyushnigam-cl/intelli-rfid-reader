# Replacing the PLC — what it would actually take

**2026-08-22 · options note, nothing designed or built.**
Companion to `Board-v3-Digital-IO-Change-Request.md` and `Board-Warehouse-Variant-Proposal.md`.

**The question:** instead of talking to a PLC, enhance our board so it *replaces* the PLC — driving
the conveyor and the lights itself. What additional board would that take?

**Short answer:** a companion **machine-control board with its own MCU and an isolated fieldbus link
to the VFD** — call it 100 × 80 mm, or a DIN-rail module. That part is not difficult. But the board
is the smallest of the three things this decision involves, and the other two need deciding first.

---

## 1. What this changes about the product

Today the reader is a **data-capture device**: it observes, reports over REST, and asks a PLC to act.
The proposal makes it a **machine controller**: it commands motion on a machine people work near.

That is not a feature increment, it is a different class of product, with a different set of
obligations — functional safety, machinery-directive scope, EMC for a controller rather than a
sensor, firmware lifecycle on something that moves loads, and a support model for when it stops.

None of that is a reason not to do it. It *is* a reason to decide it deliberately at the start rather
than discover it at commissioning.

---

## 2. What the PLC is actually doing — decomposed

Worth separating, because we would not be taking on all of it:

| Function | Take on? |
|---|---|
| Read zone sensors (photo-eyes) | ✅ already do |
| Command conveyor **speed and direction** | ✅ this is the ask |
| Drive **green / red beacon**, buzzer | ✅ easy |
| Release / divert the pallet | ✅ if it is a solenoid or a gate; ❓ if it is more machine |
| **Actually turn the motor** | ❌ **the VFD does this and stays.** Replacing the PLC does not mean replacing the drive |
| **E-stop, guard interlocks, safe torque off** | ❌ **and must not.** See §3 |
| Interlocks with upstream/downstream conveyors | ❓ depends how much line there is |

**The last row is the one to scope carefully.** A tunnel rarely stands alone. If the PLC also
coordinates the upstream accumulation conveyor, a diverter, or a downstream sorter, then "replace the
PLC" quietly means "become the line controller", which is a much bigger commitment than driving one
motor and two lamps. **Get a list of every I/O point on the existing PLC before agreeing to anything.**

---

## 3. 🔴 Safety — the non-negotiable part, and the clean way through it

A conveyor is machinery that people work near. It needs a safety function — emergency stop at
minimum, usually guard interlocking too — and that safety function is assessed to **ISO 13849-1**
(Performance Level) or **IEC 62061** (SIL). A competent safety assessment is required regardless of
who supplies the controller, and this note is not one.

**The good news is that the safety function is not the standard PLC's job today either.** In a
properly built panel the E-stop does not run through the PLC program — it runs through a **certified
safety relay** (or safety PLC), which independently removes the drive's ability to produce torque. So
replacing the *standard* PLC does not mean taking on the safety function.

**The architecture that keeps us out of the safety boundary:**

```
E-stop / guards ──▶ certified SAFETY RELAY ──▶ VFD  Safe Torque Off (STO)
                                  │                        ▲
                                  └── aux contact ──▶ us   │ (we never drive STO)
                                                           │
        us ──▶ speed / direction / start ───────────────────┘
```

- The safety relay drives the VFD's **STO** input (or a motor contactor) **directly**. We never sit
  in that path and never command it.
- We *read* an auxiliary contact so we know whether motion is currently permitted, and can show a
  sensible state instead of commanding into a dead drive.
- Our board therefore commands motion but **cannot prevent a stop**, which is exactly the split that
  keeps a non-safety-rated Linux-and-MCU controller legitimate.

Three rules that follow, and they are hard rules:

1. **Never route the E-stop through our software.** Not even as a convenience path.
2. **Our outputs must be physically incapable of producing motion when the safety chain is open** —
   the drive is disabled at STO, not by us declining to command it.
3. **The safety relay stays in the panel and is not ours.** Its certification is what the assessment
   rests on.

**Still requires a proper assessment**, because we become the controller of a machine even outside
the safety function. Budget for someone qualified to do it, and do it before the board is laid out —
the outcome can change the architecture.

---

## 4. The real argument for doing this

Not cost. A small PLC is a few hundred dollars and comes with certification, spares in every
distributor, and an installer base that already knows it. On price alone this loses.

**The argument is the recovery loop.** `PLC-Digital-IO-Interface.md` §6 proposes that when the tag
count is short as the pallet reaches the end of the zone, the reader slows the conveyor, stops it, or
reverses it for a re-scan — issuing a Gen2 Select to reset the inventoried flags before each reverse
pass so the tags answer again.

That behaviour is **tightly coupled to RFID read state**, at hundreds-of-milliseconds granularity.
Implemented across a PLC boundary, it means specifying a protocol, getting the customer's integrator
to implement it in ladder, and debugging it across two vendors on site. Implemented in one box, it
just works, and it works identically at every site.

**That is a genuine product argument**: the thing that makes the tunnel good — reading 40 of 40, every
time, by adapting the conveyor — is exactly the thing that is painful to deliver through someone
else's PLC. If a customer will not implement the recovery protocol, the reader degrades to
pass/fail and the differentiator is gone.

Secondary: one box to install, one thing to support, no argument about whose fault a missed read is.

---

## 5. Architecture — where the machine control should live

**Not on the CM4.** Linux is not a real-time system. A JVM garbage-collection pause of 200 ms while a
pallet is moving is a real event, and motion command timing should not depend on it. The CM4 should
own RFID, business logic, REST and reporting — the things it is good at.

Two candidates for what does own motion:

### Option A — promote the SAMD21

It is already on the board, already runs off 24 V **independently of the CM4**, already talks UART3,
and after the wheel-sense block goes it has ~30 free pins and nothing to do.

- ✅ No new silicon. Deterministic. Can hold a safe state when Linux is down — which it already does
  as CM4 supervisor.
- ❌ Its firmware becomes a machine controller rather than a supervisor, on a board that also has to
  stay valid for the wayside product. Two applications, one firmware image, one flash.

### Option B — a companion board with its own MCU (recommended)

All industrial I/O and motion control on a separate board with its own MCU (STM32G0/G4 class), linked
to the CM4 by one interface.

- ✅ **The RFID board stops churning.** It is the expensive part — RF-sensitive, thermally
  constrained, EMC-critical — and industrial I/O requirements are exactly the ones that keep changing.
- ✅ The machine controller becomes a separate, testable, separately-certifiable unit, and can be
  respun without retesting the RF path.
- ✅ The wayside product keeps the RFID board unchanged.
- ✅ The SAMD21 keeps its current, well-scoped supervisor job.
- ❌ One more MCU, one more firmware image, one more thing to update in the field.

**Recommendation: Option B.** The separation is worth more than the part saved, mainly because it
stops industrial-I/O churn from touching an RF board that took real work to get right.

---

## 6. Packaging — and a realisation that changes the shape

If we are replacing the PLC, **the natural home for this board is the control panel, not the reader
enclosure.** The panel is where the VFD, the safety relay, the 24 V supply and the field terminals
already are. The reader sits on the tunnel structure with its antennas.

So this is probably not a board that bolts next to the CM4 at all. It is a **DIN-rail module in the
panel**, cabled to the reader — which is also how every integrator expects to find it, and it
decouples reader mounting from panel layout entirely.

**Link between them:** the CM4 already has Ethernet, and a panel-mounted controller on Ethernet is
ordinary practice — likely there is a switch in the panel already. Failing that, RS-485 over the same
multicore as everything else. **Ethernet is the better answer** if the panel has a switch: no pin
budget consumed on the CM4, standard cabling, and the link is diagnosable with tools everyone owns.

---

## 7. What goes on the machine-control board

| Block | Notes |
|---|---|
| **MCU** | STM32G0/G4 class. Needs: 2× UART, SPI, timers, plenty of GPIO. Hardware watchdog **mandatory** |
| **Isolated RS-485** | For **Modbus RTU to the VFD** — see §8. An ADM2582E-class part is transceiver + isolated supply in one |
| **Ethernet** | If that is the CM4 link. Adds a PHY + magnetics, or use a module |
| **Isolated digital outputs ×12** | Photorelay or isolated driver, **≥ 0.5 A** — beacons, buzzer, gate solenoid, spares |
| **Isolated digital inputs ×12** | Photo-eyes, safety-relay aux contact, jam/pallet-present, mode select, E-stop *status* (not the E-stop itself) |
| **Analog output (fit/DNP)** | Isolated 0–10 V / 4–20 mA, in case the VFD is commanded by analog reference instead of fieldbus |
| **Hardware safe-state logic** | 🔴 A retriggerable monostable on an MCU heartbeat line that **de-energises every output in hardware** if the firmware stops toggling it. Not a software watchdog — hardware, provable by inspection |
| **24 V supply** | Its own, plus field 24 V pass-through and per-channel fusing for lamp loads |
| **Per-channel LEDs** | Same argument as CR-3 — commissioning and fault-finding without a laptop |
| **TVS on every field line** | A VFD on the shared field ground is a serious transient source |

Rough size: **~100 × 80 mm**, or whatever a 2–3 module DIN housing dictates. Bigger than the
interposer by a lot, but this is a different animal.

---

## 8. How to command the VFD — this is the decision that matters most

| Method | What you get | Verdict |
|---|---|---|
| **3 digital speed bits + direction** (today's design) | 8 preset speeds configured in the drive | Works, coarse. The recovery loop wants finer than 8 steps |
| **Analog 0–10 V / 4–20 mA** | Continuous speed | Better resolution, but still **open loop** — no readback, no fault visibility |
| **Modbus RTU over RS-485** | Speed setpoint at full resolution, direction, start/stop, **and readback: actual speed, motor current, drive status, fault codes** | ✅ **Recommended** |

Modbus RTU is standard on essentially every modern VFD, needs one isolated transceiver, and the
readback is what changes the character of the system. Motor current tells you a pallet is jammed
before a sensor does. Fault codes turn "the conveyor stopped" into an actionable message on the same
REST API that reports the tags. **Open-loop digital bits give none of that**, and we would be building
a machine controller with less insight into the machine than the PLC it replaces.

Two cautions: Modbus RTU is polled and not fast — budget 10–20 ms per transaction and do not put it
inside a tight control loop; and **keep start/stop on a hardwired digital output as well**, so
stopping never depends on a serial transaction completing.

---

## 9. What this costs, honestly

- **Functional safety assessment** — before layout, by someone qualified. Can change the architecture.
- **EMC as a controller**, not a sensor. A VFD in the same panel is a hostile neighbour and the
  emissions/immunity case is harder than the reader's.
- **Firmware lifecycle on something that moves loads** — versioning, rollback, field update, and a
  test rig that can exercise motion without a conveyor.
- **Support model.** When the line stops at 2 a.m., "the PLC" is currently someone else's problem
  with spares in every town. Afterwards it is ours.
- **The integrator relationship.** Some customers will not accept a third-party device commanding
  their conveyor, whatever the safety architecture. Worth testing with Reliance before building.

Set against: one box, one supplier, no integration protocol to negotiate, and **the recovery loop
that makes the product good actually gets delivered.**

---

## 10. A middle path worth considering first

There is an option between "talk to a PLC" and "replace the PLC", and it may capture most of the
value for a fraction of the commitment:

**Keep the customer's PLC for the line, but take direct control of the VFD for the measurement zone
only.** We command speed and direction over Modbus for the tunnel section; the PLC keeps the E-stop
chain, the upstream and downstream conveyors, and everything else. The recovery loop — the thing that
actually needs tight coupling — becomes ours, while line coordination and the safety story stay where
they are.

Hardware-wise that is the same companion board minus most of the I/O: **an MCU, an isolated RS-485
port, a handful of digital I/O, and the hardware safe-state logic.** Much smaller, much less exposure,
and it can grow into the full controller later if the customer wants it.

**I would price and scope both**, and let Reliance's answer to §11.1 decide.

---

## 11. Open questions

1. **Does the customer want us to replace the PLC, or are we proposing it?** Some sites mandate a
   specific PLC family as a standard. This should be tested before any design work.
2. **A full I/O list from the existing PLC.** Decides whether this is "one motor and two lamps" or
   "the line controller" (§2).
3. **VFD make, model, and whether it has STO and Modbus RTU.** Almost all modern drives do; confirm.
4. **What the safety architecture is today** — is there already a certified safety relay, and does
   the drive's STO get used?
5. **Is the beacon LED or filament**, and is a buzzer wanted?
6. **Where is the panel relative to the tunnel**, and is there a spare Ethernet port in it? Decides
   the link in §6.
7. **Would Reliance accept it?** — commercially, not technically. §9's last bullet.
