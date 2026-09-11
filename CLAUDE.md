# Intelli RFID Reader — project instructions

Software for the Intelli RFID reader. Read this before changing anything; it captures decisions and
hardware behaviour that are not derivable from the code.

## Hardware

| Part | What it is |
|---|---|
| RFID module | Silion **SIM7500**, built on an Impinj **E710** Gen2 RF chip |
| Host | Raspberry Pi **Compute Module 4**, on board the reader — this runs the apps |
| Architecture | **aarch64**. Path moved with the SDK: v260721 has `libs/aarch64/`, **v260827 has `libs/linux/aarch64/`** |
| Antennas | **The SIM7500 has ONE mono-static port.** The two connectors are fed from it by the board's **PE42442A SP4T**, switched by **GPIO8 (V1) / GPIO9 (V2)** — see below |
| Serial port | **Confirmed `/dev/ttyAMA0`** on the CM4 bench rig (2026-08-27) **and on the production v2.x carrier** (2026-08-29, with `disable-bt` + `uart3`; UART3 takes `ttyAMA3`). A USB bridge gives `/dev/ttyUSB0` |
| Region | **`RG_IN` since 2026-09-11** (865–867 MHz Indian band, hops 865.1/865.7/866.3/866.9 MHz). It became possible only after the module firmware update below; on sw `20.26.03.30` it was refused even with the auth region unlocked. **If the firmware is ever rolled back, the site config must go back to `RG_EU3` in the same step** |
| Module version | Production module: hw **`31.00.0E.80`** since the 2026-09-07 auth-region write (**not** the `31.00.00.80` quoted everywhere else; the third octet is the region marker), and sw **`20.26.08.19`** since the 2026-09-11 firmware flash (was `20.26.03.30`) |

**The module cannot see the antenna switch, and that shapes every antenna test you will ever run
here.** `MODULE_ONE_ANT`, `antportnumbers=1`, and `antenna-count: 1` is the correct config. The two
fitted ports are selected only by GPIO8/9:

| V2 (GPIO9) | V1 (GPIO8) | Port |
|---|---|---|
| 0 | 1 | **RF1 → J20 (ANT1)** |
| 1 | 0 | **RF2 → J25 (ANT2)** |

Three consequences. **The SDK's antenna argument is not the port** — `ants = {1}` is right for both,
and changing it selects nothing. **Every `TAGINFO` reports the same antenna id**, so per-antenna
attribution has to come from our own latched switch state. And **testing "both ports" with one
antenna tests one port and a bare connector**, which is the mistake that cost 09-07; see the RF
section below. Nothing in the application drives GPIO8/9 — the systemd unit sets them once at
`ExecStartPre` and they never move, so there is no multiplexing and the second antenna is dead
weight until someone writes it.

**On the production v2.x carrier the module is off and held in reset at boot, and neither the app
nor Linux does anything about it.** `RFID_EN` = GPIO22 (HIGH = on) and `RFID_NRST` = GPIO10
(LOW = reset) both come up as inputs with the BCM2711's pull-down. Measured 2026-08-29: with GPIO10
released, `InitReader_Notype` returns **`MT_UNKNOWN_READER_TYPE`** — a wrong answer rather than
silence, which reads like a baud or SDK-version fault and is neither. Raise the antenna select
first, then EN, then NRST: `pinctrl set 8 op dh; pinctrl set 9 op dl; pinctrl set 22 op dh;
pinctrl set 10 op dh`. The bench dev board needs none of this, so it is a production-only failure
mode. See `CM4-PRODUCTION-BRINGUP.md` step 7.

**`systemctl stop intelli-rfid-tunnel` POWERS THE MODULE OFF, and this will cost you an evening.**
The unit's `ExecStopPost=+/usr/bin/pinctrl set 22 op dl` drops `RFID_EN` deliberately — "a stopped
service is a quiet radio" — while `ExecStartPre` is what raises 8/9/22/10 in the first place.
**Nothing else on this board raises them.** So the standard advice below, *stop the app to probe the
pins*, leaves you probing a module that is switched off, and `InitReader_Notype` answers
`MT_UNKNOWN_READER_TYPE` — which reads as a baud or SDK-version fault and is neither. Measured
2026-09-07. Any probe run against a stopped service must raise the four pins itself;
`/home/intelli-sbc/api/run/run.sh` does. NRST is deliberately *not* dropped on stop, so only EN
comes back low.

**Region does NOT survive a power cycle — the module reverts to `RG_NA`.** Measured 2026-09-07:
after EN was dropped and raised, the module came up on `RG_NA` with the full 50-channel
902–928 MHz hop table at 30 dBm, having been on `RG_EU3` before. The app hides this because
`applyConfig()` sets the region on every connect, so it has never been visible in normal operation.
**Consequence for probes: a probe that does not set the region explicitly is testing 902–928 MHz**,
which is the wrong band for our tags and reads as total deafness. `ProbeBasic` sets and reads back
region, power and session for exactly this reason; the vendor's `test_inventory10` does not.

The apps run **on the reader itself**, not on a PC talking to a remote reader.

### Thermal — the first real measurement, and what it does and does not settle

**MEASURED 2026-09-02 (operator): at 30 dBm the reported module temperature stays well below 40 °C.**
That is the first thermal data this project has ever had, and it is far better than the vendor's own
coupon (29×29 mm FR4, 28 °C ambient, **15 dBm**: baseplate 70 °C, E710 70 °C, PA surface 81 °C). The
v2.1 board's thermal path is evidently much better than that coupon — believe the measurement.

**It does not by itself license 30 dBm, and the reason is a number no board can improve.**
`Rth_PA = 25.6 °C/W is fixed inside the module`. Back-calculating the vendor coupon (11 °C of PA-to-
baseplate delta at 15 dBm) gives a PA dissipating ~0.43 W there; at 30 dBm with ~35 % drain
efficiency it dissipates ~1.9 W, so **the PA sits roughly 45–50 °C above whatever the reported
temperature is.** A reported 38 °C therefore implies a PA near 85–90 °C — at the module's 90 °C
cutout, at bench ambient. INFERRED, not measured: it rests on the assumed PA efficiency.

**Duty cycling protects the baseplate but not the PA**, because their thermal time constants differ
by orders of magnitude — the baseplate averages over minutes, the PA junction reaches most of its
rise within a 3 s carrier-on burst. So the tunnel's ~15 % duty makes the *case* figure comfortable
and leaves the *per-burst* PA rise unchanged.

**What is therefore still unanswered:** the ambient the test ran at, whether the board was in its
sealed enclosure, how long it ran (a metal enclosure takes 20–40 min to reach steady state), and
**which sensor the number comes from** — the E710 die reading is not the PA. Until those are on
record, `read-power-dbm10: 3000` stays but **enable the E710 E7 temperature-throttle** so the module
degrades read rate instead of hitting the cutout mid-carton, and log CC33 per PA-enable.
Radiated power is a **separate, still-open question** — 30 dBm conducted plus antenna gain against
the Indian 865–867 MHz limit has nothing to do with heat.

### Module firmware — Silion's 2026-08-19 package: FLASHED on production 2026-09-11, and RG_IN works

**Result first.** The production module (serial `30262503F5`, the only board in use) was flashed
from `20.26.03.30` to **`20.26.08.19`** on 2026-09-11. The procedure: flash dump byte-identical to the
03-30 MiniTP image, then the MCU write (79 s, checksum verified), then an `RFID_EN` power cycle. The hw
field stayed `31.00.0E.80` and the SDK still reads the auth region as `RG_IN`. **`RG_IN` is now
accepted and reads back**, with hop table `865100 865700 866300 866900` kHz. The region whitelist
opened generally, from 4 regions to **26**; only `RG_EU`, `RG_EU2`, `RG_PRC2`, `RG_CE_LOW_HIGH` and
`RG_LAOS` are still refused. Ask Silion whether that breadth is intended. The module still powers up
on `RG_NA`, so setting the region on every connect is still required. **The site config runs
`region: RG_IN` since 20:46 that day**, and the tunnel reads under it: `applyConfig()` read-back
clean, reads only on the four in-band channels (EU3's out-of-band 867.5 MHz is gone), and with the
same 40-tag layout 30 tags at best −32 dBm against 28 at −32 dBm on `RG_EU3` a minute earlier. Raw
outputs are in the kit: `probe-before/after-production-2026-09-11.txt`,
`authread-after-…`, `region-scan-after-…`.

**A stacked tag bundle reads like a broken reader. Do not use one to judge the firmware.** 40 tags in
a hand-held stack gave 9 steady answers at −51 to −65 dBm. The same tags "spread a bit" gave 28–30
at −32 dBm best, four minutes later, on the same firmware. Inlays touching each other detune and
shadow one another.

**Still open:** radiated power under the Indian limit, which `RG_IN` now makes a live question; a
like-for-like carton read against 09-07's 38/38; and the rest of handoff §3.7 (rfMode 107
substitution, acceptance run).

The pre-flash notes follow, kept because they are how the next flash should be run.

An update *within* the V2.2.2 MiniTP line our modules run (sw `20.26.03.30` is its 2026-03-30
build), flashed **from the CM4 over `/dev/ttyAMA0` at 115200** with Silion's own Python scripts:
`docs/CM4-Firmware-Update-Handoff.md`, kit `firmware/silion-sim7500-20260819/`. **It is the test the
`RG_IN` question is waiting for.** The production module's auth region is already `RG_IN` (see the
auth-region entry under Vendor SDK facts), so if the region scan changes after this flash, the module
application was the block. Two traps. First, the vendor script will probably warn "wrong family
(SIMx100/SMP)" for a module that names itself `SIM7500`; settle that with the flash dump in step 3.3
before accepting. Second, never leave its address prompt blank: it then probes every `/dev/tty*`,
`ttyAMA3` (the SAMD21) included. Third, found on the CM4 2026-09-11: **the port is not locked.**
pyserial on Linux takes no `flock` unless opened `exclusive=True`, which `ModuleAPI.py` never does,
and its "port occupied" message matches Windows error text only. So the scripts will happily write
flash through `/dev/ttyAMA0` while the tunnel JVM is still talking on it. `pgrep -x java` and
`fuser -v /dev/ttyAMA0` are the only guard. On production, raise the pins with **ANT2**
(`8 dl, 9 dh`) and run every `run.sh` re-measure with `ANT=2`, or the RSSI comparison measures J20.

**MEASURED 2026-09-11, production baseline before any flash:** fw `20260330`, hw `31.00.0E.80`
(auth `0x0E INDIA`), APP descriptor `31.70.00.20` naming itself `SIM7500`, serial `30262503F5`,
bootloader `22.02.18.00`, Impinj `2.02.02` (the kit's own, so no E710 flash), stored baud 115200.
**The module powers up in its BOOTLOADER, with the power-on → APP flag off (`00000000`), and that is
normal**: the Java SDK starts the application itself on connect, which is why the tunnel has come up
after every `RFID_EN` cycle. Any raw-protocol tool sees `layer 0x11` first; `fw_probe.py --to-app`
sends the `0x04`. Do not "fix" it by setting the autoboot flag. The vendor MCU script's family
warning appears only if it starts with the module in APP, where `SIM7500` → `SIMx500` misses its
`SIMx500新` list. Started from BOOT it reads the `…80` hardware field and classes the module MiniTP.

## Naming — the Reliance warehouse tunnel

From 2026-09-01 the Reliance tunnel **drives the conveyor itself; there is no PLC**. Use these names
in code, comments, documentation and drawings — they are what the customer and the panel drawings
say.

| Name | Short | What it is |
|---|---|---|
| **Intelli-RFID Reader** | reader | The enclosure holding the IntelliRFID v2.1 board (CM4 + SIM7500) |
| **Tunnel Manager** | TM | The interposer box: field-side drive conditioning for the reader's 7 outputs, pass-through for its 4 inputs |
| **Entry Conveyor** | EnC | EZY-S100 driver card + motorised roller, upstream of the read zone |
| **Reading Zone Conveyor** | RZC | EZY-S100 + roller inside the read zone — the only one with speed and reverse control |
| **Exit Conveyor** | ExC | EZY-S100 + roller, downstream of the read zone |
| **Entry Sensor** | EnS | SICK W26 photoelectric at the entry of the read zone |
| **Exit Sensor** | ExS | SICK W26 photoelectric at the exit of the read zone |
| **Discharge Sensor** | DsS | SICK W26 at the far edge of the ExC. **There is no end stop there**, so a carton that reaches the edge with the belt running goes on the floor |

"the reader" and "TM" are the user's shorthand and mean exactly those two boxes.
**The reader never drives a field device directly.** Every output goes through the TM, because a
reader opto output sinks 1.9 mA at +85 °C and an EZY-S100 control input needs several mA (the
closest published equivalent, Itoh Denki CBM-105, draws 7.3 mA). Wiring:
`docs/Tunnel-Interconnect.md`.

### J26 functions

`FieldChannel` is the authoritative map and this table mirrors it.

| J26 | Ch | BCM | Reliance tunnel function |
|---|---|---|---|
| 1 | OUT1 | 26 | `EnC_RUN` — Run A of EnC. **Normally asserted**, see below |
| 2 | OUT2 | 20 | `RZC_RUN_A` |
| 3 | OUT3 | 16 | `RZC_RUN_B` |
| 4 | OUT4 | 19 | `RZC_REVERSE` |
| 5 | OUT5 | 21 | `ExC_RUN` — Run A of ExC. **Was `LAMP_PASS` until 2026-09-05** |
| 6 | OUT6 | 12 | `LAMP_PASS` (green). **Was `LAMP_FAIL`** |
| 7 | OUT7 | 13 | `LAMP_FAIL` (red), and the shutdown lamp. **Was the parked spare** |
| 8 | — | — | `FIELD_COM` — the single field 0 V for all 11 channels |
| 9 | IN1 | 23 | `ENTRY_SENSOR` ← EnS |
| 10 | IN2 | 24 | `EXIT_SENSOR` ← ExS |
| 11 | IN3 | 18 | `SHUTDOWN_REQUEST` ← panel push button, 5 s press |
| 12 | IN4 | 25 | `EXIT_FULL` ← DsS. **Was spare** |

RZC speed is Run A and Run B **as a pair**: A only = 100 %, A+B = 75 %, B only = 50 %, neither =
stop. EnC and ExC have Run A only, so they are run/stop at 100 % and share one channel — which is
why O1 drove two card inputs in parallel until 2026-09-05.

**Rewired on site 2026-09-05, and J26 is now full.** Every output from O5 down moved so that the
Exit Conveyor could have a channel of its own. The reason is DsS: there is no end stop on the ExC,
so the ExC has to be stoppable *without* stopping the EnC, which a shared O1 made impossible. Two
things follow. The line is **no longer serialised** — the previous carton can discharge while the
next one is being read, so cycle time stops being read + discharge. And **there is no spare channel
left**: O7 was the last one, and it was the earmarked home for the 1 Hz liveness heartbeat, which
now has nowhere to go.

### The exit interlock — one package at a time

**Decided by the operator 2026-09-05, and the two halves are different kinds of thing.**

- **The ExC is a level, not a phase.** O5 is `running && !exitOccupied` at every instant, computed
  in one place by `ConveyorController.applyExc()`. It stops the moment IN4 asserts, whatever else is
  happening. That is the whole of the fall-off protection, and it is deliberately outside the carton
  state machine — **an interlock with modes is an interlock with a mode in which it does not
  interlock.**
- **A blocked exit never interrupts a read.** If IN4 asserts mid-carton the read runs to completion.
  Only when the read *closes* against a still-occupied edge does the whole line stop, holding the
  carton in the read zone; it resumes on its own the moment the edge clears. No operator action but
  the lift.

**The result is published either way.** A held discharge delays the carton, never the callback — the
read has closed and the verdict is known. That is the mirror of `CartonRelease`'s rule that a slow
WMS must not stall the conveyor, and both directions matter.

**A blocked line waits indefinitely, and that is specified rather than overlooked.** There is no
timeout, because a timeout could only resolve to discharging into an occupied edge.

**The wait is not `hold()`.** That is the bench hold, which latches and refuses every command until a
human releases it; this one resolves itself. Routing it through `hold()` would need someone at the
panel to restart a line that is behaving exactly as designed.

**IN4 is a sampled level on its own thread, not a `gpiomon` edge**, and all three reasons matter:
occupancy *is* a level; `gpiomon` claims a line exclusively and would break a diagnostic read of
line 25; and **an edge cannot tell you a carton was already at the edge when the app started** —
precisely the state that must not be discharged into. `ExitOccupancyMonitor.start()` reads the level
before it schedules anything. It is therefore also **independent of `tunnel.v1.gpio.active-low`**,
since `FieldIo.read()` already speaks field sense.

**The EnC still restarts at read close** rather than at the IN2 exit edge (operator, 2026-09-05:
"fine for now"). With the belts split that is now a choice rather than a constraint, and moving it to
the exit edge is a one-line change if a carton is ever fed in on top of one still in the zone.

**IN3 shutdown, and the restart that follows it.** A 5 s press starts the shutdown sequence; O7's
lamp says when the counter is closed and it is safe to remove 24 V. **Restart is a full power cycle
and there is no other way** — a shut-down CM4 does not come back on its own and nothing in this
system wakes it, so there is no remote recovery and a press means an engineer at the panel. The
SAMD21 could physically do it (it holds `CM4_EN` off its own 24 V) but **nothing implements that and
this system does not use it** — do not write code that assumes otherwise.

### The RZC runs continuously in Super Fast Mode — O2 is held HIGH

**Operator decision, 2026-09-09.** `tunnel.field.conveyor.rzc-always-run: true`: the Reading Zone
Conveyor joins the EnC and the ExC as a belt that simply turns while the tunnel is armed, instead of
starting on the EnS entry edge and stopping on the IN2 exit edge. Shipped in the packaged
`application.yml` and in this unit's site config; the `FieldProperties` default stays `false`.

**The gear moved 50 % → 100 % with it and that is the same decision, not a second one.** The
EZY-S100 ladder is not monotonic — Run B alone is 50 %, Run A alone is 100 %, both is 75 % — so "the
RZC is running" and "O2 is high" are different machines: at 50 % the belt turns with **O3** high and
O2 dark. Run A alone is the only gear that leaves O2 high by itself, matching O1 and O5.
`PackagedConfigTest` pins both values, because either one alone gives the wrong machine.

Two things it buys, and two it does not touch:

- **The transfer straddle stops being a timing problem** — the RZC is already pulling before EnS
  fires, which is stronger than ordering a spin-up against the EnC stop. And **a missed IN2 edge can
  no longer strand a box**, since there is no per-carton roller stop to miss; `discharge-max-ms` now
  only warns.
- **The exit interlock still wins**, and it is the reason this is not dangerous: a read that closes
  against an occupied IN4 stops O1, O2 and O5 and holds the carton in the read zone, resuming by
  itself when the package is lifted. **Every stop still stops** — disarm, module fault, bench hold.
  Always-run is a resting state, never an override.
- **The cost is real**: the roller runs all shift, and a carton can no longer be held still in the
  read field, so more dwell now means a slower gear rather than a pause. At 100 % a carton crosses
  the zone in half the time it did at 50 %, and reads per tag was already thin at 2–3 — **if a real
  carton starts reporting short, step down to 75 % (both bits high, so O2 stays high) before
  touching `settle-ms`.**

### The reverse nudge — O4 pulsed mid-carton, and what a millisecond is worth here

**Added 2026-09-09, off by default.** `tunnel.field.conveyor.reverse` (0, 1 or 2),
`reverse-after-ms` and `reverse-for-ms` pulse **O4** during a carton's read, to jog the box a few
millimetres backwards so its articles shift and a shadowed tag gets a second chance. It starts on
the **IN1 read-open edge** — `ConveyorController.cartonEntered()`, which is where the carton
actually begins — and `reverse-after-ms[i]` is the gap **before** pulse *i*, measured from the
trigger for the first and **from the end of the previous pulse** for the rest.

**It is not `reverse(RzcSpeed)`, and the difference is the whole design.** That stops the roller,
waits `direction-change-dwell-ms` (250), then flips O4. A nudge cannot: the dwell alone is fifty
times the pulse. So the nudge writes O4 **with the Run bits still high** — a direct reversal of a
loaded drum motor, which is the one unmeasured motion this application commands. That is why it
ships off and why `PackagedConfigTest` pins it off.

**MEASURED 2026-09-09 on this CM4: every edge lands ~4 ms late and every pulse comes out ~4 ms
wider than requested.** The real controller driven with `reverse: 2`, `[100, 101]` and `[3, 5]`,
four cartons, warm JVM:

| asked | delivered |
|---|---|
| rise at 100 ms | **108 ms** |
| high for 3 ms | **7–8 ms** |
| rise 101 ms after the fall | **+105 ms** |
| high for 5 ms | **9–9.5 ms** |

Repeatable to about 1 ms carton to carton. **A cold JVM costs the first pulse another ~25 ms**, on
the first carton after a restart and no others. The cause is `pinctrl`: every level change is a
fork, measured at **4.2 ms**, and the pin stays high across the fork that lowers it. **So nothing
here can ask for less than ~7 ms** — a `reverse-for-ms` of 1 and of 3 are the same pulse. The
controller logs the *achieved* width of every pulse at DEBUG; tune against that and never against
the configured number.

What the error costs is **how far the carton actually moves**, not correctness — nothing decodes
this width, unlike the verdict pulse this project deleted. It is the reason the nudge is a few
millimetres longer than the arithmetic says.

**The sequence is cancelled and O4 driven low by anything that ends the carton** — the read
closing, the IN2 edge, disarm, fault, bench hold — because it is folded into `cancelTimers()`.
**Cancelling needs a generation token and not just `ScheduledFuture.cancel()`**: the pulses chain,
so a falling edge already running when the cancel arrives has nothing left to cancel and would
schedule the next rise regardless — a carton discharging with O4 going high behind it.

### O1 is a state machine, not a level

**O1 is HIGH by default — EnC and ExC run whenever a carton is not being read.** It drops LOW when
EnS sees a package (RZC takes over the carton) and goes HIGH again the moment the read finishes,
**on any outcome** — SETTLED, COUNT_REACHED, PACKAGE_EXITED or TIMEOUT.

Four things follow, and three of them are not obvious:

- **The backstop is load-bearing.** "Any outcome" must include the ones that are not outcomes: a read
  that never closes, a reader fault, a supervisor reconnect. If no outcome arrives, O1 and O5 stay
  low and the line is stopped with a box in the tunnel. `tunnel.max-duration-ms` must release them
  too, and the fault path must define them explicitly rather than leaving them wherever they were.
- **At boot the line does not run.** Outputs reset low, so EnC and ExC are stopped until the app is up
  and armed. That is the correct failsafe — a dead reader stops the line, it does not run it — but
  someone will power the panel up, see a dead conveyor and think the drive is broken. Say so in the
  operator instruction.
- **EnC and ExC shared one channel until 2026-09-05, which serialised the line.** The previous
  carton could not discharge while the current one was being read, so cycle time was read +
  discharge rather than max(read, discharge) — a throughput ceiling bought with the channel budget.
  **The copper no longer imposes it**, since the ExC has O5 of its own; `setBelts()` still commands
  the two together, so the ceiling is now a software choice and removing it is free. RS-485 remains
  the way to address all three cards independently, but this is no longer the argument for it.
- **Stopping EnC the instant EnS fires drags the carton.** EnS is at the *entry* of the read zone, so
  at that moment the leading edge is on RZC and the trailing edge is still on EnC. Either delay the
  EnC stop by the transfer time, or place EnS far enough downstream that the carton is fully
  transferred when it fires. **Unresolved — decide from the real geometry.** Since 2026-09-09 this
  is only about the EnC: with `rzc-always-run` the RZC is already moving when EnS fires, so there is
  no spin-up to order against the stop.

**We supply the cards' control power**, which is the `+` / `-` pair on the left of the vendor's
"PNP IO Control Wiring Principle" drawing: its switches `S1`/`S2`/`S3` are the TM's outputs and its
`-` is our control 0 V on the card's `Com` pin. **The cards' `DC+`/`DC-` motor supply is a separate
supply, provided by others, and is out of scope** — it must never share a rail with the control 24 V.

## How this project is worked on

Two machines with two different roles. Know which one you are.

| Where | Reader attached | Role |
|---|---|---|
| **Cowork on the Windows laptop** | No | System design, architecture decisions, first drafts of code |
| **Claude Code on the CM4** | Yes | Implementation, running against the real module, testing |

**Nothing designed on the laptop has been tested against hardware.** Everything a draft asserts about
module behaviour is inference from the vendor documentation and the demo sources — not observation.
Draft code is a proposal to be verified, not working code, however confident its comments sound.

Consequences, both directions:

- **On the CM4**: prefer running the thing over reasoning about it. You have the one resource the
  design sessions lack. When the module contradicts a draft, the module is right — fix the code, then
  record the correction in this file so the next draft starts from the truth rather than repeating
  the mistake.
- **On the laptop**: mark anything hardware-dependent as unverified rather than asserting it. Where a
  value can only come from a real site or a real module — settle windows, RSSI thresholds, antenna
  geometry — write a sensible default *and* say in a comment how to derive the real one.

What is worth writing back into this file after a CM4 session: corrected API signatures, module
quirks, the actual serial port, tuned configuration values, and anything that surprised you.

### Closing a session — do this without being asked again

**When Piyush hints that the session is ending, that hint is the instruction.** "That's it for
today", "I'm heading off", "let's wrap up", "good night", "we'll continue tomorrow" — treat any of
them as the trigger and run the whole close-out before replying that you are done. Do not ask
whether to do it; ask only if something in it would destroy work.

1. **Write the findings into the markdown.** Corrected signatures, module quirks, measured values,
   anything that surprised you — into this file, and into the runbook or handoff the work belongs
   to. A fact learned at the module and left in the transcript is lost.
2. **Update `RESUME-NEXT-SESSION.md`** so the next session can start cold: what changed, what state
   the unit was left in, and the next actions in order.
3. **Update memory** — the durable, cross-session facts that are not derivable from the repo.
4. **Commit and push everything**, in every repository that changed. The workspace root and each
   app under `apps/` are separate repos with separate remotes, so walk them all rather than
   committing at the root and assuming it covered the apps. Push, do not just commit — an
   unpushed commit on this board is invisible to the laptop, and the laptop is where the next
   design session happens.

The failure this prevents is specific and has already happened: a CM4 session that measured real
hardware behaviour, wrote none of it down, and pushed nothing, leaving the laptop to design its next
draft against facts the module had already disproved.

### Handoffs travel through git, not as files

**A handoff document is not delivered by handing the operator a file. It is delivered by committing
it and pushing it, so the other session pulls it.** The two sessions share one repository and that is
the whole point of the split.

The rule, because the laptop cannot push:

1. Write the document into `docs/` — markdown is the artefact of record; a `.docx` alongside it is a
   convenience for reading, never the deliverable.
2. **Commit it.**
3. **Tell the operator to push, in the same breath.** The bridge VM has no AWS credentials, so the
   commit and the push are two halves of one action and the second half needs a human. Saying "the
   document is ready" without the push command leaves it stranded.
4. The other session pulls and reads it from `docs/`.

**A document that is committed but unpushed has not been handed over.** Neither has one that was only
attached to a chat message. If a session ends with either, the work did not arrive.

The same applies in reverse: when the CM4 records a correction, it goes into `CLAUDE.md` and is
pushed, not described in a chat reply that the laptop session will never see.

## Repository layout

Each app is its **own git repository**, remoted to AWS CodeCommit in `ap-south-1`. The project root
is a workspace, not a monorepo — the repo at this level tracks **documentation only** and explicitly
ignores `apps/`.

```
intelli-rfid-reader/            repo: intelli-rfid-reader — DOCS ONLY, ignores apps/
├── CLAUDE.md                       tracked here
├── CM4-BENCH-HANDOFF.md            tracked here
├── docs/                           tracked here
├── API-linux-java-v260721/     vendor SDK — NOT in git, copied separately
├── Hardware/                   datasheets — NOT in git
└── apps/                       ignored by the root repo; each app is its own repo
    ├── intelli-rfid-core/          shared library — repo: intelli-rfid-core
    ├── intelli-rfid-reader-test/   bench acceptance — repo: intelli-rfid-reader-test
    ├── intelli-rfid-tunnel/        warehouse portal — repo
    ├── intelli-rfid-admin/         laptop admin interface — repo: intelli-rfid-admin
    ├── intelli-wms-test/           WMS simulator — repo: intelli-wms-test
    └── intelli-rfid-wayside/       trackside railway — repo (NOT checked out on this CM4)
```

`git init` belongs inside each app directory. **Never create a repo spanning `apps/`** — the root
repo keeps that rule by ignoring `apps/` outright, so a stray `git add -A` at the root cannot
swallow an app. Nesting the app repos would need submodules and is not what this project does.

**That same ignore is why a new app can exist for hours with no repository at all and nothing
complain.** `intelli-wms-test` was written, built and left uncommitted across a board reboot on
2026-09-04 — the root `git status` stayed clean throughout, because the root repo does not look
inside `apps/`, and the app itself had no `.git` to report anything. **`git init` is part of
creating an app, not part of finishing one.** When walking the repos at close-out, walk `apps/*/`
by directory and check each one *has* a repo, rather than iterating over the repos that exist.

## The apps

Two of them run **on the reader**; two run **on the Windows laptop** and talk to a reader over the
LAN. The port is the giveaway and the distinction matters, because a laptop app has no reader, no
vendor jar and no core.

| App | Port | Runs on | Purpose |
|---|---|---|---|
| `intelli-rfid-reader-test` | 8080 | reader | A new reader arrives: is it good? Reads a few tags, writes a few tags, reports pass/fail |
| `intelli-rfid-tunnel` | 8081 | reader | Warehouse entry/exit tunnel. A box of ~40 tagged articles passes through; a third-party app asks what was in it. Also commissions warehouse tags |
| `intelli-rfid-wayside` | 8082 | reader | Trackside railway reader. A train passes; produce the consist |
| `intelli-wms-test` | 8083 | laptop | A WMS, reduced to arming Super Fast Mode and showing the carton that comes back |
| `intelli-rfid-admin` | 8090 | laptop | The whole surface: v1 contract, internal endpoints, commissioning, key issuance, bench harness, call log, contract checker |

`intelli-rfid-core` is the shared library underneath the three reader apps. **The two laptop apps
deliberately do not depend on it** — shared DTOs would serialise and deserialise with the reader's
own code, so a wire-format regression would cancel itself out on both sides and be invisible to the
one test built to catch it. Both parse the reader's JSON field by field on purpose.

**The tunnel app is retail/warehouse. Only the wayside app is rail.** Do not conflate them.

### `intelli-wms-test` and `intelli-rfid-admin` overlap, and the overlap is the point

Admin already contains a WMS simulator, so `intelli-wms-test` looks like a duplicate and is not. The
two ask different questions:

- **Admin asks *does the reader behave*.** It holds an ADMIN key, times and logs every call including
  the ones that never connected, and checks each response against `docs/Intelli-RFID-RestAPI.docx`.
- **`intelli-wms-test` asks *could a WMS integrator use it*.** The only honest way to answer that is
  to hold **nothing but the INVENTORY key** and the five documented endpoints — so the call log, the
  contract checker, commissioning and the key tooling are deliberately absent. Adding any of them
  back would destroy what the app is for.

It is **a temporary app, and the customer's own integration replaces it** (operator, 2026-09-04).
That is why its `application.yml` carries the live `site-wms` INVENTORY key in plaintext: the jar is
handed over and double-clicked with no setup, and the app is disabled by rotating that key on the
reader rather than by revoking anything. Do not "fix" the committed key without checking that
decision still stands.

Two rules it enforces on screen, both of which exist to stop it flattering the reader:

- **Found is `matched.count`, not the number of rows in the table.** The table lists everything that
  answered, labelled `matched` / `unexpected` / `undecodable`, because 16 of the 18 bench tags carry
  no GS1 header and "found 2" over an 18-row table is the correct answer.
- **The verdict pill is the reader's own `complete`, never re-derived.** The contract says stop
  reason and count are independent; a page computing *found ≥ expected* itself would quietly
  disagree with the reader on the one number the customer cares about.

`callback.url` blank means the app offers its own site-local IPv4 and labels it a guess — right on a
laptop sharing the reader's LAN, wrong behind NAT. **Never `localhost`**: the reader would POST to
itself, every carton would read perfectly, every result would die in a connection refused inside the
*reader's* log, and the page would sit empty looking exactly like a reader that had stopped working.

### Two API surfaces on the tunnel, and only one of them is the contract

| Surface | What it is |
|---|---|
| **`/api/v1/**`** | **The customer contract.** Transcribed from `docs/Intelli-RFID-RestAPI.docx`, which has been issued to Reliance. Five endpoints, one result object, one error body, a fixed set of error slugs. Change it only with the document. |
| `/api/inventory/**` | The diagnostic and bench surface. The reader-test client drives it and it is useful for exactly the debugging the v1 layer needs. **It is not the contract, must not appear in customer documentation, and must not be reshaped to match v1.** |

The internal `CloseReason` enum has four values; the contract's `stopReason` has three and they are
not the same three. **Map at the boundary** (`v1/ResultMapper`) rather than renaming the internal
enum: the bench needs to know a session was closed by its caller, and the WMS was never told that
such a thing exists.

## Stack

Java 21, Maven, Spring Boot 3.4.1. Spring Boot was chosen after confirming the CM4 has headroom —
Actuator health and metrics matter on a reader nobody can walk up to.

**The target moved 17 → 21 on 2026-08-29**, when the production CM4 came up on Debian 13 (Trixie),
whose archive carries no `openjdk-17-jdk` at all. Taking the platform's maintained default beat
pinning a JDK the distribution has dropped. **The bench rig is still Java 17 on Bookworm**, so the
two machines now differ on this axis: a failure on one that will not reproduce on the other is worth
suspecting here first.

The part that was a decision rather than a measurement is **the vendor JNI under 21**: there is no
bytecode to recompile in `libModuleAPIJni.so`, so a green build proves nothing about it. The risk
splits in two, and only the first half is closed:

- **Load and bind: verified 2026-08-29 on the production CM4.** `new Reader()` under Debian's
  OpenJDK 21.0.12.1 aarch64 triggers `JniModuleAPI`'s static initialiser and returns cleanly, with
  `java.library.path` pointing at the SDK's own `libs/aarch64`. Core and tunnel also build and pass
  their 74 tests on 21.
- **Call time against a real module: closed 2026-08-29 on the production CM4.** Step 8's probes
  drove a real SIM7500 through the JNI on OpenJDK 21 — identity, every region set and read back,
  hop tables, and five 1 s inventory sweeps returning **18 of 18 tags each**, with `TAGINFO` structs
  marshalled back intact (EPC, RSSI, frequency, read count). Nothing on this board needs Java 17.

So the JDK is cleared: if this unit misbehaves at the module, look elsewhere first. The bench rig
remains on 17 as a comparison point.

## Build order

The vendor jar is not on Maven Central and core is a local dependency, so order matters:

```bash
cd apps/intelli-rfid-core
./tools/install-vendor-jar.sh     # installs com.uhf:module-api-j:2.6.0721
mvn install
cd ../intelli-rfid-tunnel && mvn package
```

## The tag pipeline

Understand this before touching reader code.

```
vendor JNI thread            dispatcher thread          consumers
─────────────────            ─────────────────          ─────────
ReadListener.tagRead()
  copy TAGINFO → TagRead     ← structs are recycled
  RSSI filter
  dedup window
  queue.offer()        ───►  poll()
                             RecentTagBuffer
                             TagBroadcaster (SSE)
                             app subscribers  ───►  InventoryService / PassService
```

**The JNI callback thread must never block.** Anything slow there costs reads at the module. The
callback filters and offers; a single dispatcher thread does the fan-out. The queue is bounded
(8192) and drops oldest-first under overload, counting drops — surfaced on `/api/reader/status` and
`/actuator/health`.

## The RF path was NOT dead — it was one antenna branch, and the unit runs ANT2 now

**RESOLVED 2026-09-07. The section this replaces said the module or the board was faulty and that
only a bench-board swap could narrow it. That was wrong, and the reason it was wrong is worth
keeping: every "both ports tried" test up to that point was run with ONE antenna.**

The SIM7500 has **one** mono-static port. The two J26-side antenna connectors are fed from it by the
board's **PE42442A SP4T**, switched by **GPIO8 (V1) / GPIO9 (V2)** — the module cannot see the switch
and reports the same antenna id whichever port is live. So flipping `ANT=2` while the only antenna
stayed screwed to J20 did not test J25; it listened into a bare port. The 09-07 evidence table's
"both fitted ports tried" line was therefore not evidence of anything.

**With an antenna on BOTH ports and the tags unmoved, the two branches are 24 dB apart:**

| port | distinct EPCs | best RSSI | worst |
|---|---|---|---|
| ANT1 / J20 | 3 | **−49 dBm** | −59 |
| ANT2 / J25 | 8 | **−25 dBm** | −64 |

−25 dBm sits on this rig's recorded −26 dBm baseline, so **the module, the PA and the SP4T are all
healthy** and the loss is inside the J20 branch — its cable, its connector, or that arm of the
switch. J20 is the port the systemd unit had always selected, which is the whole of the failure:
the app spent 09-05 to 09-07 listening through the bad branch. Its last run before the change
managed **506 reads in 20 minutes** where this module does ~60/s when healthy — degraded, not
silent, which is why it read 2–5 tags at site rather than none.

**`deploy/intelli-rfid-tunnel.service` now selects ANT2** (`pinctrl set 8 op dl; set 9 op dh`).
`run.sh` still defaults to `ANT=1`, so **a probe run with no `ANT=` is testing the broken branch on
purpose.** Put the unit back to ANT1 once J20 is repaired.

**Still not established, and it needs no software:** whether the 24 dB is in the cable/antenna or in
the board. Swap the two cables at the board, leave the antennas and tags where they are, and re-run
both ports. If the weakness follows the cable it is the cable; if it stays on J20 it is the board.

**What this corrects about the two "instruments that lie".** Both notes below stand and neither was
the problem — the VSWR sweep still rails at 3.0095203 with an antenna fitted and with the port bare,
and `connectedAntennas` is still just the configured count. But note what they cost: with no working
antenna instrument on this board, a 24 dB branch loss is invisible to every diagnostic the reader
has, and the only way to find it was a second antenna.

### Confirmed working end to end, 2026-09-07

Nine Super Fast cartons on ANT2, on the v260827 SDK, on the deployed jar:

| seq | stopReason | tags | matched | lastNewTagMs | RSSI |
|---|---|---|---|---|---|
| 855 | SETTLED | 18 | 18 / 18 | 801 | −51…−29 |
| 856 | SETTLED | 29 | 29 / 38 | 801 | −51…−26 |
| 858 | SETTLED | 34 | 34 / 38 | 832 | −50…−31 |
| 859 | SETTLED | **38** | **38 / 38** | 806 | −49…−25 |

`complete: true, trustworthy: true` on 855 and 859. Carton time 2.09–2.98 s. **`lastNewTagMs` lands
at 801–883 ms against a `settle-ms` of 800** — the watchdog's ~100 ms tick, exactly as measured on
09-04. This is the first 38-article carton this project has read, and the largest population before
it was 18.


## Vendor SDK facts

### The unit runs SDK v260827 from 2026-09-07, and three things about the upgrade catch people

- **The drop name is a date, not a version.** `ModuleAPI_J-v260827.jar` self-reports
  `jarVersion:260730_v3.8.3.4r-soVersion:20260611`. There is no `260827` string inside it, so do not
  go looking for one to confirm the upgrade — check `com.uhf:module-api-j:2.6.0827` in the fat jar
  instead. Maven coordinates are `2.6.0827`; **2.6.0721 is still installed in `~/.m2`, so rolling
  back is one line of `core/pom.xml`.**
- **The native library moved.** v260721 had `libs/{32,64,aarch64}`; v260827 has
  `libs/linux/{x86,x64,aarch64}` plus `libs/windows`. A path carried over from the old tree resolves
  to nothing, and `deploy/install.sh` then falls through to "keep whatever is already installed" —
  which is the OLD `.so`, silently, against the new jar.
- **TWO `.so` files were being loaded and it had gone unnoticed for weeks.** `NativeLibraryLoader`
  loads `rfid.reader.native-lib-path` by absolute path AND the vendor's static initialiser loads
  from `-Djava.library.path`. The site config pointed the first into the SDK tree and the unit
  pointed the second at `/opt/intelli/lib`. They were byte-identical, so nothing complained — and
  they would have become two different *versions* on this upgrade. **Both must resolve to
  `/opt/intelli/lib`**, which is the one `install.sh` keeps matched to the jar. Corrected in the
  site config 2026-09-07.

The SDK upgrade changed **no** API signature: core and tunnel compiled unmodified and all tests
passed. It also **did not fix the deafness** — that was the antenna branch above.


- **The VSWR sweep is useless on this carrier: it rails at `3.0095203` with the antenna connected
  AND with the port bare.** That figure is *exactly* a 6.000 dB return loss to float precision
  (`VSWR = (1+10^-0.3)/(1-10^-0.3)`), four channels identical to seven significant figures — a rail,
  not a measurement. Measured both ways 2026-09-07. **`/api/diagnostics/antennas` therefore cannot
  detect a disconnected antenna on this board and must never be used as an antenna check here**,
  though its javadoc reasonably calls it "the first thing to check on a coverage complaint".
  Two further traps: `vswrLimit` defaults to exactly `3.0f`, so the rail always reports
  `healthy: false` by 0.0095 and tells you nothing about severity; and **the 1.119 baseline quoted
  in `CM4-BENCH-HANDOFF.md` and `HANDOFF-CM4-TO-LAPTOP.md` is the BENCH DEV BOARD**, not this
  production carrier, whose `CM4-PRODUCTION-BRINGUP.md` line still reads `VSWR <..>`. Comparing this
  board against 1.119 is comparing two different units. If a real VSWR figure is ever needed here it
  has to come from an external analyser.
- **`ReaderInfo.connectedAntennas` is NOT a detection — it is a copy of `activeAntennas`**, i.e. the
  configured `antenna-count`. Its javadoc said "antenna ports the module detected as physically
  connected", which is false and cost time on 2026-09-07; the javadoc is now corrected. The module's
  real answer is the start-up WARN `Module reported no connected antennas (MT_OK_ERR); falling back
  to all N ports`, which this module emits **on every connect even when healthy** — it appeared 29
  times on 09-04 while reading 18 of 18 tags. So neither the field nor the warning tells you whether
  an antenna is attached.

### The vendor's own demo sources — four traps, all met on 2026-09-07

`API-java-v260827/demos/doc_demos/*.java` are single-file, have `main()`, and are the fastest way to
test a module without any of our code. They are also written for the vendor's **networked** reader
at `192.168.1.160`. Copies patched for `/dev/ttyAMA0` live in `/home/intelli-sbc/api/run/`.

- **`antportnum` defaults to 16 and this module is `MODULE_ONE_ANT`.** `InitReader_Notype` then
  returns `MT_INVALID_PARA`. The argument is total ports on the module, not connected antennas — it
  is 1 here. `test_inventory10` already passes 1; `test_readerinfo` does not.
- **Every demo prints `init the reader successfully` even after printing the error**, because there
  is no `return` between the two. Trust the `init the reader err :` line and nothing else.
- **The network demos NPE on a serial module.** `test_readerinfo` asks for MAC and IP, gets
  `MT_CMD_FAILED_ERR` / `MT_OP_NOT_SUPPORTED`, then does `new String(rip.ip)` on the null.
- **`test_paramgetandset` and `test_defaultparmgetandset` both set the region to `RG_PRC`**, and the
  second writes it as a **saved-in-module default** that survives a power cycle. Do not run either
  on a unit you care about.


Confirmed from `API-linux-java-v260721/docs_en/doc_API_J_html/` — grep those files rather than
guessing at signatures.

> **A return code from this SDK is a lower bound on success, not a confirmation.**
>
> `MT_OK_ERR` means the command was accepted, not that the module did what you asked. The measured
> case is `MTR_PARAM_POTL_GEN2_TAGENCODING`, where RF modes 101, 111 and 115 are all accepted and
> all silently become 107 — but treat the rule as general, because the next parameter that behaves
> this way will not announce itself either. Where a silent failure would invalidate a measurement or
> a customer-visible read, set the parameter and then read it back.
>
> `ReaderSession.applyConfig()` now does exactly that for the six that matter — **rf-mode, session,
> target, Q, region and power** — and throws naming what was written and what came back. Those are
> pushed once at start-up and on a deliberate config change, never per box, so the extra round trip
> costs nothing. **Do not extend this to the per-read path**: carrier-on latency is 14 ms and a
> blanket read-back would double the module round trips in the one place they are expensive.
> Verified on the bench 2026-08-28: all six read back exactly what was written, including the
> easily-doubted ones (`Q = -250`, meaning dynamic with initial Q 6, and the antenna power table).

- **`TAGINFO` structs are recycled** between callbacks. Copy before the read leaves the callback.
- **The byte-array argument to `WriteTagEpc` / `WriteTagData` / `GetTagData` is the access password**,
  not an EPC filter. Target one tag among several with `MTR_PARAM_TAG_FILTER`.
- `GetTagData(ant, bank, address, blkcnt, data, accesspasswd, timeout)` — 1 block = 2 bytes.
- `WriteTagData(ant, bank, address, data, datalen, accesspasswd, timeout)`.
- `WriteTagEpcEx(ant, epc, epclen, accesspwd, timeout)` — `epclen` must be even.
- `LockTag(ant, lockobjects, locktypes, accesspasswd, timeout)` — OR the `Lock_Obj` / `Lock_Type`
  enum values. Permanent lock types are irreversible.
- **Select filters are sticky module state.** A filter left set makes the reader look broken.
  `TagOperations.clearFilter()` exists for this; call it in a `finally`.
- **A TID Select filter really does target one tag, and that is what makes batch commissioning
  possible.** Measured on the production module 2026-08-29 with the whole population in the field:
  `MTR_PARAM_TAG_FILTER` on bank TID, bit 0, 96-bit pattern, then `WriteTagEpcEx` — the write landed
  on exactly the targeted tag, the filtered read-back returned it, and **no other tag changed**.
  Verified independently afterwards by re-reading the field: 8 of 8 claimed writes were on the right
  tag, and every tag the API reported as failed still carried its old EPC. The order does not
  matter: filter-then-access works with or without an inventory round in between, and whether or not
  continuous inventory ran first.
- **But a filtered *inventory* leaks on the first round after the filter changes.** The first
  `TagInventory_Raw` after setting a filter returned 2 and 4 tags in two runs where exactly 1
  matched; every subsequent round returned only the match. Reproducible, and the extra tags were all
  from the preceding unfiltered round — a stale buffer, not a broken Select. **Single-tag access
  (`GetTagData` / `WriteTagEpcEx`) never leaked**, which is why commissioning uses it and does not
  trust a filtered inventory to singulate.
- **Writing needs more power than reading, and the failure is `MT_CMD_NO_TAG_ERR` rather than
  anything about power.** Measured 2026-08-29 on tags that were being read perfectly at the time:
  at `writePower = 2000` (20 dBm) **every** TID-filtered write returned `MT_CMD_NO_TAG_ERR`; at 2700
  the same writes on the same tags returned `MT_OK_ERR`. The access-password argument makes no
  difference (`null` and `new byte[4]` behave identically). Unfiltered writes hide this, because
  they land on whichever tag is strongest — so a commissioning bug that only appears once you target
  a *specific* tag is exactly the shape to expect. A weaker tag still fails at 27 dBm, but honestly:
  `MT_CMD_FAILED_ERR / 0x42b PROTOCOL INSUFFICIENT POWER`, naming one tag to reposition.

  **`MT_CMD_NO_TAG_ERR` has a second cause, and it is not power: a silenced Gen2 session.**
  2026-08-31, at `writePower = 2700` on tags that had been written successfully before, every
  TID-targeted write in three separate batches failed with it. The tags were under `session: 2` and
  had gone quiet — `totalReads` frozen, nothing heard for twelve minutes — so the module was
  telling the exact truth and the write path had nothing to talk to. **Before suspecting power,
  check the reader is currently hearing tags at all**: `totalReads` climbing and
  `secondsSinceLastRead` near zero on `/api/reader/status`. A write cannot reach a tag that is not
  answering, and the two failures are indistinguishable from the return code alone.
- **Plain inventory start/stop is NOT rate-limited, and the `MODULE_NEED_RESTART` rule below has
  been over-applied.** Measured on the production module 2026-08-31: **30 `StartReading` /
  `StopReading` cycles in 30 seconds** — 600 ms on, 400 ms off, 60 restarts a minute, 7.5× the
  figure the rule quotes — every cycle returning `MT_OK_ERR` and reading ~50 tags, 16 distinct EPCs,
  no alert of any kind. `StartReading` costs **0–3 ms** and `StopReading` **20–60 ms**.

  **So a triggered carrier is safe at any realistic carton rate**, which is what
  `tunnel.v1.triggered-carrier` depends on. What this does *not* establish is what caused the
  original failures: both recorded cases — toggling FastID per read, and commissioning's three
  restarts per tag — changed a **parameter** alongside each restart (a custom `tagcustomcmd`
  set, a Select filter). The reconfiguration is the remaining suspect and it has not been isolated,
  so keep the rule for anything that reconfigures per operation and stop applying it to bare
  start/stop. `ProbeRestartRate` in `intelli-rfid-reader-test/tools/bench-probe` is the measurement.
- **`ReaderService.whilePaused` nests, and commissioning relies on it.** It stops inventory only if
  the reader is currently reading, so an outer `whilePaused` around a whole batch makes the inner
  ones no-ops. That turns three inventory restarts per tag into one per batch — an 18-tag batch used
  to ask the module for 54 restarts, and four inside thirty seconds is what produces
  `MODULE_NEED_RESTART`.
- **Ex10 fast mode and Impinj fast mode are mutually exclusive and both sticky.** `ReaderSession`
  clears the other on every mode change; skipping that gives a reader whose behaviour depends on
  what ran before it. **Corrected 2026-08-28:** on the bench SIM7500 Impinj fast mode cannot be set
  at all and Ex10 fast mode is refused (both below), so neither is actually stateful here. The
  clearing logic is still right — the failure it guards against is simply not reachable on this
  module.
- **Single-tag operations cannot run during continuous inventory.** The `/api/tags/ops` endpoints
  stop and restart inventory around each call.
- **`new Reader()` triggers the JNI library load** via `JniModuleAPI`'s static initialiser. This is
  why `ReaderSession` creates its handle lazily inside `open()` — constructing it eagerly threw
  `UnsatisfiedLinkError` during Spring bean creation and killed the context before any retry logic
  could run, crash-looping a field unit instead of letting it report unhealthy. **Do not move it
  back into a field initialiser.**
- **The JNI library needs `-Djava.library.path`; `rfid.reader.native-lib-path` alone does not work.**
  `JniModuleAPI`'s static initialiser calls `System.loadLibrary("ModuleAPIJni")`, which searches only
  `java.library.path`. `NativeLibraryLoader`'s `System.load()` of the same `.so` by absolute path
  succeeds but does **not** satisfy it, so `new Reader()` still throws `UnsatisfiedLinkError` — 
  surfacing as an HTTP 500, not a 409. **Every launch command and systemd unit must pass
  `-Djava.library.path=/opt/intelli/lib`.** Verified on the CM4 2026-08-27.
- **THE AUTHENTICATION REGION IS WRITABLE, AND IT IS NOT THE SAME THING AS THE OPERATING-REGION
  WHITELIST. This module's auth region is now `RG_IN` and `RG_IN` is still refused.** Done on the
  production module 2026-09-07 with Silion's own procedure, on the v260827 jar:

  ```java
  SpecObject sval = rdr.new SpecObject(Region_Conf.RG_IN);
  rdr.SpecParamsForReader(0, true, sval);          // isset TRUE = write; type 0 = auth region
  CustomParam_ST cp = rdr.new CustomParam_ST();     // then EITHER method 1:
  cp.ParamName = "Reader/Savestandby"; cp.ParamVal = new byte[]{1};
  rdr.ParamSet(Mtr_Param.MTR_PARAM_CUSTOM, cp);
  rdr.CloseReader();                                // one call, enters boot
                                                    // OR method 2: re-power the module
  ```

  `SpecParamsForReader(0, false, sv)` **reads** it — do that first, it is the only way to know what
  to restore. This module read `RG_PRC` before the write, which is why its accepted set looks like
  a China SKU. `ProbeAuthRead` / `ProbeAuthWrite` in `intelli-rfid-reader-test/tools/bench-probe`
  are the two, and `ProbeAuthWrite` takes `-Dtarget=RG_PRC` to put it back.

  **What it changed:** auth region `RG_PRC` → `RG_IN`, persisting across a re-power, and the
  **hardware version string permanently changed `31.00.00.80` → `31.00.0E.80`** — the third octet
  is the region marker and is how you tell from the outside. **Every document quoting
  `31.00.00.80` for the production module is now stale**, and anyone diffing this module's version
  against the bench module's will see two different strings on identical hardware.

  **What it did NOT change:** `ParamSet(MTR_PARAM_FREQUENCY_REGION, RG_IN)` still returns
  `MT_CMD_FAILED_ERR`, and the accepted set is exactly as before — `RG_NA` (1), `RG_EU3` (8),
  `RG_PRC` (6), `RG_OPEN` (255), everything else refused. Tested twice: once in the full scan, and
  once as the very first operation after a fresh module boot, in case the scan's eight preceding
  region writes mattered. They did not. **So on sw `20.26.03.30` the two are independent, and the
  next question for Silion is whether the operating whitelist also needs new module firmware.**
  **ANSWERED 2026-09-11: it did.** After the flash to `20.26.08.19`, with the auth region still
  `RG_IN`, `RG_IN` is accepted and the unit runs it (see "Module firmware" near the top).
  PENDING: a re-test after a full 24 V removal rather than an `RFID_EN` cycle — the module clearly
  re-read NVM on the EN cycle (the version changed), but a cold start is a stronger reset.

  **This corrects a claim made earlier the same evening** that `RG_IN` was a firmware SKU limit no
  SDK could lift and that the scan should not be re-run on a new SDK drop. There *is* an unlock, it
  is in both jars, and a scan that only exercises `ParamSet` cannot see it. The `RG_EU3` +
  3-channel hop table workaround remains what this project runs: `865700 866300 866900`, set after
  the region and read back, re-verified in the same session.
- **SUPERSEDED for the production module on 2026-09-11.** On sw `20.26.08.19` it accepts 26 regions,
  `RG_IN` included. What follows describes sw `20.26.03.30`, and still describes the bench module.
  **Region is a firmware SKU limit, the two modules differ, and neither accepts `RG_IN`.** The
  production SIM7500 on the v2.x carrier accepts **`RG_NA` (1), `RG_EU3` (8), `RG_PRC` (6) and
  `RG_OPEN` (255)** and refuses everything else with `MT_CMD_FAILED_ERR` — and it **ships set to
  `RG_NA`**, 902–928 MHz, which is illegal to key up on in India. Region is therefore not a setting
  that can be left at its default on a production board. Same firmware as the bench module
  (hw `31.00.00.80`, sw `20.26.03.30`), so the SKU difference is not a version difference.
  Measured 2026-08-29.
- **The hop table is writable, and it is how this project reaches the Indian band without `RG_IN`.**
  `MTR_PARAM_FREQUENCY_HOPTABLE` takes a `HoptableData_ST { int[] htb; int lenhtb; }` in kHz.
  `RG_EU3`'s stock table is 865700/866300/866900/**867500**, and only the first three are inside
  India's 865–867 MHz allocation. Writing `{865700, 866300, 866900}` under `RG_EU3` is accepted and
  reads back as a 3-entry table. Two rules, both measured on the production module 2026-08-29:
  **the table must be a subset of the region's own grid** (the same channels under `RG_OPEN`, whose
  grid is a coarse 860–960 MHz 10 MHz ladder, are refused), and **`ParamSet` on the region rewrites
  the table**, so the hop table must be written *after* the region on every connect.
  `ReaderSession.applyConfig()` does not do this yet — it should, with the same read-back as the
  other six. **Less urgent since 2026-09-11:** under `RG_IN` the stock table is already all in-band.
  The unit had been hopping on 867.5 MHz under `RG_EU3` the whole time, because nothing narrowed the
  table. It only matters again if the unit ever goes back to `RG_EU3`.
- **The bench module is locked to `RG_EU3`.** Setting each
  `Region_Conf` and reading it back is the only way to find out: `MTR_PARAM_RF_SUPPORTEDREGIONS`
  returns `MT_INVALID_PARA`. On the bench SIM7500 every region except `RG_EU3` (8) — `RG_IN` (4) and
  plain `RG_EU` (2) included — is refused with `MT_CMD_FAILED_ERR / 0x10b FAULT_INVALID_REGION`.
  Under `RG_EU3` it hops 865.7/866.3/866.9/867.5 MHz, so the first three channels are inside the
  Indian band. `RG_IN` is region **4**, not 7 (7 is `RG_EU2`).
- **`ParamGet(MTR_PARAM_FREQUENCY_REGION, ...)` takes a `Region_Conf[]`, not an `int[]`** — the
  vendor doc says `int[1]` and is wrong; an `int[]` throws `ClassCastException` from inside
  `Reader.ParamGet`. `ParamSet` on the same parameter does accept a bare `Region_Conf`.
- **`TAGINFO.Frequency` is in kHz** (`865700` = 865.7 MHz). It is the practical way to discover a
  module's actual channel plan.
- **`GetHardwareDetails` reports `module=MODOULE_NONE`** (vendor's spelling) on a perfectly healthy
  module. Not an error.
- **`BackReadOption.ReadDuration` is the latency knob, because the module batches callbacks.** A
  tag is not reported when it is read — it is reported at the *end* of each read window. Measured on
  the SIM7500: carrier-on → first tag = **ReadDuration + ~14 ms**, linear across 50/100/200/400 ms
  (63.9 / 114.5 / 213.9 / 412.8 ms median). The irreducible floor is ~28 ms. **Below ~25 ms the
  window starts missing the tag** and latency becomes an erratic multiple of the window (at 5 ms:
  min 28 ms, max 284 ms). 50 ms is a good default: first tag ~64 ms, tightly grouped. Callback rate
  follows the same law — ~1000/ReadDuration per second (50 ms → 16/s measured).
- **FastID works, and it puts the TID inside `EpcId`, not in `EmbededData`.** Setting the custom
  parameter `tagcustomcmd/fastid` to 1 makes every tag backscatter its 12-byte factory TID with its
  EPC. The module does **not** use `TAGINFO.EmbededData` for it (that stays empty even with
  `TMFlags.IsEmdData` set): it appends the TID to `EpcId` and grows the PC word to match — a 96-bit
  EPC arrives as 24 bytes with PC going `0x3400` → `0x6400`. Split on the trailing 12 bytes
  beginning with the **0xE2** allocation class, never on a fixed length: a tag that does not answer
  FastID reports its EPC unchanged, and mixed stock is the normal case in a warehouse.
  Verified across the whole bench population 2026-08-28: **18 of 18 EPCs identical with FastID off
  and on**, including one tag whose EPC is genuinely 6 bytes (`PC=1D7A`, `Epclen=6`) rather than 12.
  **Cost: about 25% of the raw read rate** — 80.7 → 60.6 reads/s on 18 tags at 30 dBm in NORMAL —
  with unique-tag discovery unchanged at 18/18. Re-measure on a real box before assuming that holds
  at 40 tags.
- **FastID is a connect-time setting, not a per-request one, and this is a hard-won rule.**
  Toggling it per read costs two inventory restarts, and four restarts inside thirty seconds made
  the module raise `MT_HARDWARE_ALERT_ERR_BY_TOO_MANY_RESET (0xfefe: MODULE_NEED_RESTART)` and stop
  reading. Set it once in `rfid.reader.fast-id` and let the API decide only whether to *render* the
  TID. The same warning applies to anything else that wants to stop and start inventory per request.
- **A read exception used to leave the reader `FAULTED` forever. Fixed 2026-08-29 —
  `ReaderService`'s supervisor thread now reconnects.** `handleReadException` still only records the
  fault (it runs on the vendor's read thread, and reopening the reader from inside its own exception
  handler means re-entering the native library while it is unwinding); a separate `rfid-supervise`
  thread watches for it and does the work. It closes, reopens, and restarts inventory **if inventory
  had been running** — `ReaderSession.wasReadingWhenFaulted()`, captured at fault time because by
  recovery time the previous state is gone.

  Two things about it are load-bearing and neither is obvious:

  **The backoff does not reset on a successful reconnect, only after the reader has stayed up for
  `recover-stable-ms`.** Reconnecting costs a module re-init, and re-initialising repeatedly is
  itself a way to break this module — four inventory restarts inside thirty seconds produced
  `MODULE_NEED_RESTART`. A reader that faults, recovers and faults again must not be handed the
  short delay again. `FaultRecoveryPolicy` holds that rule and is unit-tested.

  **Recovery is a latch, not a state observation.** A *failed* attempt does not leave the session
  FAULTED: `open()` throws out of `InitReader` before the block that sets FAULTED, so the state is
  whatever the preceding `close()` left — **CLOSED**. Watching for FAULTED alone therefore gives up
  after exactly one attempt, and CLOSED is indistinguishable from an operator's deliberate
  disconnect. Measured on the bench with the reader's RX pin de-muxed. The supervisor raises a
  `recovering` flag on the fault and lowers it only when the reader is genuinely OPEN/READING, or
  when `connect()`/`disconnect()` says an operator has taken over.

  **Fault behaviour on the Reliance tunnel, decided 2026-09-02: the package exits forward and the red
  lamp comes on.** O4 released, RZC driven until the carton is clear, O1 and O5 high to discharge,
  **O7** asserted (the red lamp moved there on 2026-09-05). The carton is reported as `TIMEOUT` /
  `complete: false` and the callback still goes — a
  carton that leaves unread and produces no result is one the WMS thinks never existed. This applies
  to a *module* fault, where the JVM is alive to act; a dead JVM or lost 24 V drives every output low
  and the lamp is dark, which is the failsafe and is correct. **Consequence, which the rewiring made solvable rather
  than solved:** discharging still starts the EnC, so the next carton is fed into a failed tunnel.
  Until 2026-09-05 that was forced — EnC and ExC shared O1 and there was no way to run one without
  the other. They are separate channels now, so the fault path *can* raise O5 alone. Nothing does it
  yet, and `ConveyorController.setBelts()` is where it would go.

  Verified on hardware 2026-08-29 with a real `IO_RECV_TIMEOUT`: five failed attempts backing off
  5→10→20→40→60 s while the module was unreachable, recovery with inventory restarted the moment it
  was reachable again, and a second fault a minute later recovered in 5.5 s on the reset delay.
  `recoveries` and `lastRecoveryAt` are on `/api/reader/status` and `/actuator/health` — a count that
  climbs steadily is a reader that keeps breaking, which each recovery would otherwise hide.

  **Inject this fault without touching the wiring:** `pinctrl set 15 ip pd` de-muxes RXD0, so the
  module's replies stop reaching the Pi and the vendor library raises a genuine read exception within
  seconds. `pinctrl set 15 a0 pu` puts it back.
- **A subprocess that prints to a pipe block-buffers, and libgpiod's `gpiomon` is the case that
  will cost you an afternoon.** gpiomon writes through libc stdio, which line-buffers to a tty and
  **block-buffers at 4 KB to a pipe**. Every edge is detected by the kernel, printed by gpiomon, and
  then held in a buffer that on a conveyor will not fill for hours. Nothing reports an error; the
  symptom is a tunnel that never triggers. Measured on this bench: three confirmed rising edges
  through a plain pipe delivered **zero** bytes, and the same three under `stdbuf -oL` delivered
  three lines. It looks exactly like missed edges, which is the wrong diagnosis and leads somewhere
  expensive — polling instead of interrupts, which in a JVM with no GPIO binding means spawning a
  process per poll and losing the kernel's edge timestamp. **Wrap any long-running CLI you read
  incrementally in `stdbuf -oL`.** The one-shot form hides it: `--num-events=1` prints because the
  process exits, and exiting flushes.
- **`gpiomon` holds the lines exclusively.** A second one, or a `gpioget` on the same line, gets
  `Device or resource busy` — so a probe run while the tunnel app is up will fail, and that failure
  is a sign the app is working rather than a fault. Stop the app to probe the pins.
- **Toggling a pin's internal pull is a real edge, which makes the sensors testable with no
  wiring.** `pinctrl set 23 ip pu` lifts an unconnected input to 1 and `pinctrl set 23 ip pd`
  returns it, and the kernel reports both to an edge monitor holding the line. That is how the
  entry/exit sensors were exercised on a bench with nothing attached to GPIO23 or GPIO24.
- **Gen2 S2 plus a continuously-on carrier makes a static tag go silent after one read.** Measured:
  16.0 callbacks/s on S0 versus **0.1/s on S2**, same tag, same everything else. This is correct
  Gen2 behaviour — S2's inventoried flag persists while the tag is powered — but it means any
  bench test that leaves the carrier on and uses S2 looks like a broken reader. It is also the
  thing that makes the tunnel's carrier-off-between-boxes design necessary rather than merely
  thermally convenient. Use S0 for continuous-carrier bench work; S2 belongs with triggered RF.
- **We run `session: 1` and it is clean. MEASURED 2026-09-02: the same tags re-read a few seconds
  later with no problem.** S1's inventoried flag self-decays in 500 ms–5 s even while the tag is
  powered, which is what a carton-at-a-time tunnel wants. **`application.yml` still says `session: 2`
  — that is live config drift; the committed default is not what the rig runs.** The S2 note below
  stands as the reason S1 was chosen, and as what you will see if the session is ever left at 2.
  Caveat: S1 decay is a timing window, not a guarantee, so a read that closes fast and immediately
  reverses can start its return pass with some tags still in state B. The Select-to-A reset is
  therefore still worth building — for determinism now, not as a fix.
- **Gen2 S2 inventoried flags persist for more than 15 s on our tag stock — carrier-off does not
  clear them quickly.** Measured: with S2, a first read found all 18 tags; every subsequent read
  found **zero**, at carrier-off gaps of both 4 s and 15 s. An S0 control at a 3 s gap read 18/18
  every time, so it is S2 state and not the rig. The Gen2 spec's "≥2 s" is a *minimum*, and this
  silicon holds far longer. **Consequence: the tunnel's `session: 2` plus a carrier-off window
  between boxes is not sufficient on its own** — a second box arriving inside the persistence window
  reads as empty. Options not yet tested: S1 (self-decays 500 ms–5 s even while powered, and a box
  read is under a second so mid-box re-answering may not matter), or a Select forcing
  inventoried → A at the start of each box (`SelC_Inventoried_S2` +
  `SelCmd_Action.Mat_SLorA_NMat_no`). Bracket the real persistence before choosing.

  **Worse than that, measured 2026-08-31 with a continuously-on carrier: the silence is not 15 s,
  it is indefinite.** The population answered once — 94 reads — and then nothing for **twelve
  minutes** with the carrier up and `secondsSinceLastRead` climbing the whole time. That is correct
  Gen2 behaviour, because S2's flag is held for as long as the tag stays *powered*, and the ">15 s"
  figure above was measured across carrier-**off** gaps, which is a different and much gentler
  case. **Do not run `session: 2` without the carrier actually dropping between cartons**
  (`tunnel.v1.triggered-carrier`). The unit now runs **S1** by decision, which self-decays even
  while powered; that choice is unverified against this stock and wants watching for a tag
  re-answering mid-carton and inflating a count.
- **RF mode IDs come in three numbering spaces, and `MTR_PARAM_POTL_GEN2_TAGENCODING` accepts two
  of them.** Read `Reader$RFMODE` out of the vendor jar: `RFM_7_EX_SFM = 107` is the Silion E-series
  profile space (100 + profile number), while `RFM_222_EX22 = -16776994 = 0xFF000000 | 222` carries
  the hardware manual's own mode IDs under an `0xFF` tag byte. **A bare `222` is not manual mode
  222.** Measured on the bench SIM7500 2026-08-28: of the eight values in `ReaderConfig`'s javadoc
  only 103, 105, 107, 112 and 113 are accepted — **101, 111 and 115 are silently discarded**. All 13
  ETSI LB mode IDs work when written as `0xFF000000 | id`.
- **`ParamSet` on `MTR_PARAM_POTL_GEN2_TAGENCODING` returns `MT_OK_ERR` for every value, valid or
  not** — 999 and 0 included — and **any unrecognised value silently snaps the module to 107**. 107
  is a hard fallback, not the previously-set value: verified by parking on 105, 113 and EX22-222
  first and writing junk over each. So `rf-mode: 222` in a config file lands on 107 with no error
  anywhere. **Read the parameter back and compare — the return code carries no information.**
- **`rfMode = 107` is manual ETSI LB mode 244**: 175 tags/s, −91.0 dBm, Miller M=4, Tari 20 µs, BLF
  250 kHz. **Inferred from a read-rate fingerprint, not proven.** The 13 EX22 modes reproduced the
  manual's declared rate ordering monotonically, and pairing each Silion profile back-to-back with
  its suspected twin matched within 1–4% across five pairs (107↔244, 105↔241, 103↔222, 112↔223,
  113↔285). Consistent with 107 = `0x6B` being the manual's Old Mode ID for the 146/244/343 triple.
  The manual's mode table is an image, so it could not be cross-checked directly. **Consequence: 107
  is *more* sensitive than mode 222 (−88.0 dBm), so moving the default to 222 would be a 3 dB
  downgrade bought with speed a 40-tag box does not need.**
- **`Reader/impinjfastmode` does not exist on this module.** `ParamGet` and `ParamSet` both return
  `MT_INVALID_PARA` for every `IMPINJ_MODE_ID` — the FCC-only 4124 the code currently uses and the
  ETSI LB alternatives alike — because the parameter *name* is rejected before the mode ID is ever
  looked at. It appears nowhere in the vendor's documented custom-parameter list, and a read-only
  sweep of all 33 documented names found no Impinj-mode parameter of any kind. **`readMode =
  IMPINJ_FAST` therefore throws `ReaderException` → HTTP 409 on every call, and correcting the mode
  ID cannot fix it.** What the vendor documents instead is one parameter with two modes, selected by
  byte 0 of `Reader/Ex10fastmode`: `1` = Ex10 fast, `0` = "general fast mode" — the latter is most
  likely what this project has been calling Impinj fast mode.
- **`Reader/Ex10fastmode` byte 1 (= 20) is a payload length, not a mode constant.** The vendor demo
  uses it as a loop bound over the 20 bytes following the 2-byte header of the 22-byte buffer
  (`for (i = 0; i < vals[1]; i++) vals[2 + i] = ...`). **Do not "correct" it to `0x20`** — that
  declares 32 trailing bytes in a 22-byte buffer. Measured: the module stores either value verbatim,
  validates neither, and behaves identically for both. `values[2]` is the scenario byte ("0 more
  tags, 1 less tags").
- **Neither fast read mode works on this module — NORMAL is the only one worth shipping.** Measured
  2026-08-28, 18 tags, 3 s windows, with `BackReadOption.IsFastRead = true`, which is the only
  condition under which the Ex10 payload does anything:

  | Config | `StartReading` | unique | reports/s |
  |---|---|---|---|
  | NORMAL control, `IsFastRead=false` | ok | 18 | 64.3 |
  | `Ex10fastmode[0]=0` — "general fast mode" | ok | 18 | **18.0** |
  | `Ex10fastmode[0]=1` — true Ex10 fast | **`MT_CMD_FAILED_ERR`** | 0 | 0.0 |

  **True Ex10 fast mode is refused outright** — `StartReading` fails and zero tags are read, for byte
  1 = 20 and `0x20` alike. Only the general fast mode runs, and it is **3.6× slower than NORMAL**.
  The earlier "14× slower" figure (2 tags: NORMAL 16.0 callbacks/s vs 1.1/s) was this same general
  fast mode, not Ex10 — same direction, less extreme with more tags. Fast mode is built for dense
  populations so it could still invert on a real 40-article box, but on everything measured so far
  **fast mode must not be assumed faster.** The module recovered cleanly after each refusal.
- **`MTR_PARAM_POTL_GEN2_BLF` and `MTR_PARAM_POTL_GEN2_TARI` return `MT_OP_NOT_SUPPORTED`** — not
  merely deprecated, absent. BLF, Tari, PIE and both modulations come bundled into the mode ID and
  cannot be set independently.
- **The bench/product tags are Impinj.** 19 tags read: 18 are Impinj (MDID `0x001`, TMID `0x190`,
  TID prefix `E2801190`), 1 is NXP (`0x006`). So FastID and Impinj fast mode are available on the
  product stock. XTID is set on all of them, so each has a serialised factory TID — a unique per-tag
  identifier independent of the EPC we write.
- **Decoding a TID: the 12 bits after the `E2` allocation class are not all MDID.** Gen2v2 puts
  three indicator bits on top — XTID `0x800`, Security `0x400`, File `0x200` — leaving a **9-bit
  MDID**. Mask `0x1FF`, not `0x7FF`: a security-enabled NXP tag (raw `0xC06`) otherwise decodes as
  an unknown `0x406` rather than `0x006`. Impinj tags decode correctly under either mask, so the
  error hides in a small sample.
- **A lambda field initializer cannot read a blank final field** before the constructor assigns it —
  hence the method references (`this::handleTags`) for the vendor listeners.

## Domain rules that are easy to get wrong

**Tunnel — settle is measured from the last _new_ EPC, not the last read.** A box sitting in the
field re-reads its own tags forever, so "no reads for N ms" never fires while the box is present.
A minimum duration guards the other end so a session cannot close in the gap before the rest of the
box enters the field.

**Tunnel — `expectedTags` is what turns a tag count into a verifiable inventory.** Without it the
service can say the population settled, but not that nothing is missing. A `TIMED_OUT` session is
never trustworthy even if the count happens to match.

**Wayside — silence is measured from the last read**, unlike the tunnel. A train is a moving
population: each wagon enters and leaves the field, so silence genuinely means the train has gone.

**Wayside — `pass-gap-ms` must sit above the longest gap _within_ a train** (across a locomotive, a
brake van, or a rake of untagged wagons) **and below the shortest headway between trains.** Too low
splits one train into two consists; too high merges two trains.

**Wayside — wagons are keyed on decoded wagon id, not EPC**, so a wagon with a tag on each side
counts once. Ordering is by first sighting only; a later re-read must never move a wagon.

**Wayside — direction and speed refuse to guess.** `UNKNOWN` / `null` when the antenna geometry is
not configured or the evidence is split. A wrong direction on a consist is worse than an absent one.

**Decoding never fails a read.** If the wagon-id rule does not match an EPC, the raw EPC is used and
the sighting is marked `decoded: false`. Losing a wagon because its tag did not match a regex would
be far worse than showing a hex string.

**Tunnel v1 — what counts towards the expected quantity must agree exactly with what lands in
`matched`.** Two rules over one population, and if they disagree the reader contradicts itself. The
bug, and it shipped for an afternoon: with no `ean` requested, the count predicate accepted any EPC
while `matched` accepted only EPCs that decode as SGTIN-96. A read with `expectedCount: 2` closed on
count at 90 ms and reported `stopReason: COUNT_REACHED` with `matched.count: 0` — the reader saying
it had found everything it was looking for and then listing none of it. `V1Service.countsTowardsExpected`
and `ResultMapper` are now tested against the same population precisely so they cannot drift apart.

**Tunnel v1 — the reader works for whatever EAN it is armed with. The shipped SKU allowlist is
gone (2026-09-07).** `rfid.gs1.valid-eans` carried three specific SKUs in the *packaged*
`application.yml`, and `V1Service.validateEan` refuses any EAN outside a non-empty list — so
`POST /api/v1/mode` answered 400 `invalid_ean` for every other SKU, on every unit built from that
file, whatever site it went to. It ships `[]` now. An EAN is still validated (13/14 digits, GS1
mod-10 check digit), just not enumerated.

What is lost is only the typo check: a WMS arming for a SKU nobody stocks now gets a carton whose
every article lands in `unexpected` with `complete: false`, instead of a 400 at the tunnel. **A site
that wants an allowlist sets it in its own `/etc/intelli/<app>/application.yml`** — never in the
packaged file, and `PackagedConfigTest` now fails the build if one reappears there.

**`company-prefix` is a different thing and still restricts.** It gates COMMISSIONING only
(`CommissioningController.validateEan`), never reading or arming, so a carton of any EAN reads and
counts correctly regardless of it. Note the two reader apps disagree: the tunnel ships `8909478` and
**`intelli-rfid-reader-test` still ships `8905527`**, so the bench harness refuses to commission the
SKU the tunnel writes — a 400 `invalid_ean` that looks like a bad EAN and is a stale config in
another app.

**Tunnel v1 — once an EAN is armed, only that SKU's tags hold the settle window open, and this is
two-phase on purpose.** Settle asks "has the population stopped growing", and the population in
question is the armed SKU's. Before this, a tag that could never count still bought the carton
another full settle window — a neighbouring carton, the SSCC label, supplier stock — so with
`exitOnCount: false` (the Super Fast default, where settle is the ONLY thing that ends a read) a
foreign tag was the one thing a non-matching tag could still decide. `SessionSpec.resetsSettle`
carries the rule; foreign tags are still recorded, still reported as `unexpected`, and still open a
session under auto-trigger.

**The phase is load-bearing and the naive version is a trap.** Scoping from the first millisecond
looks right and is not: `lastNewTagNanos` starts at session open and would never advance, so "the
population has stopped growing" is vacuously true from t=0 for a population that has not started.
Two failures follow, and both reach the customer. A carton whose articles are shadowed past the
window closes `SETTLED` with `matched: 0` while the field is still answering — and on a 40-article
carton, shadowing is exactly what the settle window exists for. And `ResultMapper.stopReason`
re-derives SETTLED from `lastNewTagMs`, so a read that never heard the SKU at all reports **SETTLED
instead of TIMEOUT** — the one word the contract uses to tell a WMS its count is a lower bound.
**So until the first article of the armed SKU answers, any new EPC still holds the window open.** A
carton holding none of the armed SKU therefore behaves exactly as it always did: it settles on its
own traffic and publishes promptly rather than stalling the line to the ceiling.

**Consequence for tuning:** `durationMs − lastNewTagMs == the last tag's sighting`, which is how
`settle-ms` was derived from the spool on 09-04, now holds only for the requested SKU's tags. Do the
`firstSeen` diff over matched tags, not the whole tag list.

**Tunnel v1 — an undecodable tag never counts.** However many there are. On the bench population 16
of 18 tags carry no GS1 header at all, so a count that included them would close a carton on tags
that are not articles of the requested SKU and report a short carton as complete.

**Tunnel v1 — a spooled callback carries the URL it was spooled with, and is given up on after
7 days.** The URL is captured at spool time, so re-arming with a different callback address does not
redirect a backlog, and **disarming does not stop the replay** — the replay timer retries the spool
every 60 s independently of arm state, which is the whole point of a spool. Both are correct and
both look like a bug: on 2026-09-01 two results were retried all day against a WMS that had moved
address, and read at a glance as disarm not working. Check `callbacks.jsonl` before suspecting the
arm path. Past `tunnel.v1.callback.max-age-ms` an entry is appended to `callbacks-dead.jsonl` and
dropped — **abandoned, not discarded**, because the contract promises the WMS that results are
spooled and replayed. Non-zero depth shows on `/actuator/health` as `abandonedCallbacks`; it is
deliberately absent from `/api/v1/reader/status`, which cannot gain a field without the document
changing.

**Tunnel v1 — the carton is released before the callback is sent, never after.** The contract
promises the WMS that "a slow or unavailable WMS endpoint does not stall the conveyor". If the
release ever waits on the callback, the symptom at the customer's site is a stopped line — the most
expensive failure this product has and the least obviously ours. `CartonRelease` exists as a named
seam so the ordering is checkable in one line at the call site rather than being a thing that
quietly does not happen anywhere.

**Tunnel v1 — in Super Fast Mode a sensor opens the read, and settle or the exit edge closes it,
whichever comes first.** A rising edge on J26 IN1 (GPIO23) opens the session. From there **exactly
two things can close a carton**, and the one that happens first names the stop reason:

> **Trigger edge — DECIDED 2026-09-02, was "unresolved by decision".** The operator has chosen to
> change it: the read must open on the **field-active** edge, not the raw rising edge. With the
> Reliance wiring (SICK W26, PNP, 24 V present = carton present) the opto pulls the pin **down**, so
> as it stands the trigger fires on beam *clear* — every carton would open its session as it leaves.
> Use the fix already identified in the GPIO notes: **`gpiomon -l` / `--active-low`, on both libgpiod
> v1 and v2**, which makes "rising" mean *the channel became active* and matches `FieldIo`. Read
> "rising edge" throughout this section as *field-active edge* once that lands. **IN3 is
> unaffected** — it is sampled as a level and never reaches the edge monitor.

| what closed the window | `stopReason` |
|---|---|
| the population settled, IN2 not yet seen | `SETTLED` |
| IN2 rising edge (GPIO24), population had not settled | `PACKAGE_EXITED` |
| neither, and the read budget expired | `TIMEOUT` |

**The stop reason says what closed the window and nothing about the count.** `stopReason` and
`complete` are independent and neither softens the other: a carton that settles two articles short
is `SETTLED` with `complete: false`, and one that meets its count and then leaves before settling is
`PACKAGE_EXITED` with `complete: true`. There is no "matched >= expected" short-circuit anywhere —
inferring the reason from the count is exactly what this rule forbids.

**Reaching the count does not end a read by default.** It is recorded as `countReachedAt` and the
read continues; `COUNT_REACHED` therefore does not occur in Super Fast Mode unless the caller armed
with **`exitOnCount: true`**, which is a real optional flag on `POST /api/v1/mode`, absent meaning
false. Keep it a flag: false is the honest reading, true is right on a line that trusts its counts
absolutely, and that is a line-by-line judgement that should not need a rebuild.

Publish **once per carton** — the IN2 edge following a settle-closed carton is consumed and
discarded, and only an IN1 edge opens a window. `maxDurationMs` stays as the backstop. With no
sensors the mode falls back to opening on the first tag and closing on settle, which is not
equivalent and is reported as `degraded` in `/api/v1/reader/status`.

**That "once per carton" rule was only half implemented, and the WMS saw the other half. MEASURED
2026-09-09 on the production unit: 129 `SETTLED` results against 114 `PACKAGE_EXITED` in one
afternoon — very nearly one spurious carton for every real one, each box reported twice with two
different counts.** The mechanism is in the log in full:

```
20:53:21.119  IN1  -> session A opens
20:53:22.647  IN1  (ignored: a read is running)
20:53:23.827  IN1  (ignored: a read is running)
20:53:24.179  settle closes A          -> callback 1: SETTLED, 39 of 40
20:53:25.149  IN1  -> session B opens          <-- same box, still in the zone
20:53:27.130  IN2  closes B            -> callback 2: PACKAGE_EXITED, 37 of 40
```

**Settle closes a read while the carton is still physically in the zone and still crossing the
entry beam.** The stale IN2 edge was consumed; the stale IN1 edge opened a whole new carton. The
guard was one-sided, and the second result is always the worse one — it is the tail of the same
box, so it reports a *lower* count than the result the WMS already had.

**Debounce cannot close this and raising it makes things worse.** The extra entry edges are
**1.2–1.5 s apart** — real beam events, not contact bounce — and the second session opened **4.0 s**
after the first. A debounce wide enough to swallow that would swallow the next genuine carton.

**Fixed 2026-09-09 by `tunnel.v1.gpio.reopen-block-ms` (default 10000): a carton whose read has
closed holds the entry trigger shut until IN2 says it has left.** A carton closed *by* the exit edge
has already gone and blocks nothing. The timeout is a wedge-guard only — a dead exit sensor lifts
the block on its own with a WARN, because **a tunnel that stops taking cartons is a stopped line and
that is worse than one that occasionally publishes a box twice**. `0` restores the old behaviour.
`CartonPublishedOnceTest` pins all of it.

**This only became visible on 2026-09-09 because that is the day IN2 started firing at all** —
before it, the spool holds essentially no `PACKAGE_EXITED` (36 SETTLED and zero on 09-08). The
duplicate sessions may well have been opening for longer and closing as a second `SETTLED`.

**Still open, and it is a field question rather than a software one: why does the entry sensor emit
five rising edges for one carton?** The guard above makes the duplicates harmless but does not
explain them. The spacing is suspiciously regular across cartons, and the reverse nudge — 1 pulse
at 2000 ms for 1000 ms, live on this unit — can drag a box back across EnS and forward again, which
would manufacture a genuine extra edge. Check the EnS alignment and re-run with `reverse: 0` before
concluding it is the sensor.

**Corrected 2026-08-31.** It replaces an earlier rule in which the exit sensor owned the end
outright, the count and settle were both merely observed, and a count that was never met beat
everything.

**Tunnel v1 — a Super Fast carton is a fast read followed by a fixed wait, and the wait is the
larger half.** Measured on the production CM4 2026-08-31 across **8 consecutive cartons** (9 tags,
`session: 1`, 27 dBm, `RG_EU3`, settle 1500 ms): every carton found **all 9 tags by 1016–1306 ms**,
then spent the rest of its 2560–2866 ms proving nothing further was coming. `durationMs −
lastNewTagMs` equals the last tag's sighting to the millisecond, so **`settle-ms` is the only lever
on carton time — the reading is already finished.** Settle fires at **1513–1591 ms**, not 1500: the
watchdog runs on a ~100 ms tick and overshoots. `PACKAGE_EXITED` cartons in the same session came in
at ~1.4 s because the IN2 edge cut the wait short, which is exactly what a conveyor's exit sensor is
for.

**`settle-ms` is 800 on the production unit from 2026-09-04, down from the packaged 1500.** The
window only has to exceed the largest gap between consecutive *new* EPCs inside one carton, and that
is far smaller than the window was: measured over 20 cartons (sequences 733–752, 16–18 tags),
**median worst-gap 231 ms, worst 406 ms** — 1500 was 3.7× the worst case. 800 keeps 2× and takes the
carton from ~2.8 s to ~2.0 s, with the reading itself (last new EPC at 1098–1409 ms) untouched.
**Derive it that way rather than by feel**: from the spool, sort each result's tag `firstSeen`
values, diff consecutive ones, take the worst across many cartons, double it. The bench population
is 18 unshadowed tags, so a real 40-article carton will have longer gaps and this number must be
re-derived there — **too low reads a carton short and reports it complete, with no other symptom.**

> **But that derivation is CIRCULAR if you run it on cartons read at the window you are testing,
> and the 09-04 number above was derived exactly that way.** A gap longer than `settle-ms` cannot
> appear in the data: the window closes the carton, and the tags that had not yet answered are
> simply absent from the result. So the measured worst gap is **censored at the window** — the
> analysis can only ever report that the current setting is comfortable, whatever it is set to.
> The symptom it is blind to is the one that matters, because a carton cut short reports `SETTLED`
> and `complete: true` when the count happens to be met and logs nothing either way.
>
> **Only cartons read at a window WIDER than the candidate are evidence for that candidate.**
> Re-derived 2026-09-08 over the whole spool, 416 `SETTLED` cartons, worst `firstSeen` gap per
> carton:
>
> | day | window | n | median gap | p90 | worst | cartons > 800 ms |
> |---|---|---|---|---|---|---|
> | 08-29 | 1500 | 224 | 251 | 664 | **1445** | 13 |
> | 08-31 | 1500 | 85 | 234 | 716 | **1503** | 5 |
> | 09-01 | 1500 | 3 | 404 | 514 | 514 | 0 |
> | 09-02 | 1500 | 8 | 372 | 567 | 567 | 0 |
> | 09-03 | 1500 | 25 | 238 | 350 | 406 | 0 |
> | 09-04 | 1500 | 3 | 286 | 287 | 287 | 0 |
> | 09-04 | 800 | 61 | 236 | 348 | 573 | 0 |
> | 09-07 | 800 | 7 | 240 | 623 | 623 | 0 |
>
> **The uncensored evidence for 800 is the 39 cartons of 09-01…09-04 that ran at 1500**: a gap up
> to 1500 ms was free to appear there and the worst was **567 ms**. That is what justifies 800, and
> it is a 1.4× margin on the worst case rather than the 2× the paragraph above claims.
>
> **The 08-29/08-31 rows are not noise and they are not RF.** 18 of those 309 cartons had gaps
> between 800 and 1503 ms — including full 18-tag cartons — and their RSSI (median −44, worst −50)
> is no worse than 09-07's (median −43, worst −51), so the bad J20 branch does not explain them
> either. Gap does not correlate with per-tag read count. What changed at 09-01 was configuration,
> and `session: 2` is the prime suspect: an S2 tag still holding its inventoried flag from the
> previous carton answers late, which lands in the data as exactly this — a long delay before a
> tag's *first* sighting. **Anything that silences a tag temporarily shows up as gap, not as loss**,
> and a settle window is the thing that has to absorb it.
>
> **Bigger populations showed SHORTER gaps, not longer** (30+ tags: median 200 ms, worst 274 ms
> over the 09-07 cartons), which is the opposite of what the paragraph above predicts — more
> articles means more arrivals to fill the window. It is only 2 cartons and it does not settle
> anything, but do not assume a 40-article carton needs a wider window than an 18-article one.
>
> **So the open question is not answered and cannot be answered from the existing spool.** All
> seven 38-article cartons were read at 800. To learn whether a big shadowed population produces
> gaps in the 800–1500 band, **set `settle-ms: 1500`, run a batch of full 38-article cartons, and
> read the gap distribution off those** — then bring the window back down to twice the worst. Any
> other order measures the window rather than the carton.

**Detection on the bench population is total, and the RSSI filter is discarding nothing.** Same
measurement: **72 of 72 tag detections**, every carton `SETTLED` with 9 of 9. RSSI **−41.6 to
−50.9 dBm**, each tag varying only ~1 dB run to run — so every tag sits **20 dB or more above the
−72 dBm `rssi-threshold-dbm` floor**.

**That measurement used to end "tighten toward −55/−50". Do not — it was wrong, and a larger
sample disproves it.** MEASURED 2026-09-04 on the production unit, per-tag `bestRssi` over 20
consecutive cartons (sequences 733–752, 18 distinct EPCs): tag medians run **−29 to −46 dBm**, but
the **weakest single detection is −61 dBm**. One article (`…0138`) swings **−61 to −27 dBm** carton
to carton while every other tag varies by a few dB — it moves in the box, and it alone sets the
floor. **A −55 threshold would have dropped every read of that tag in its weak cartons**, reporting
an 18-article population as a complete 17. The `~1 dB run to run` figure above came from 9 tags
sitting still; it does not survive a population that is handled.

The rule that generalises: **the threshold must clear the weakest detection of the weakest article,
not the median of the population**, and the two are 17 dB apart here. `−72` leaves 11 dB below the
worst case and is what this unit runs. **A too-tight threshold is silent** — it does not log, it
shortens cartons and reports them complete. Tighten only with evidence of a neighbouring carton
bleeding in; there is none on this rig, where all 18 EPCs appear in 13–20 of the 20 cartons and
every one is a genuine member of the population.

**Singulation order is random and carries no meaning.** One tag was first at 57 ms in one carton and
nearly last at 1219 ms in another, at unchanged signal strength. Nothing should read meaning into
arrival order.

**Reads per tag is only 2–3 per carton, which is a thin confidence signal.** Enough for detection,
but a single dropped read takes a tag to 1 — and the read count is what the contract offers a WMS as
evidence that a count is trustworthy. Re-measure on a real 40-article carton, where tags shadow each
other, before relying on it.

**Tunnel v1 — `endedAt` is simply when the read window closed.** Nothing mode-specific. It used to
be substituted with the moment the count was met, because a sensor-driven carton went on sitting in
the field until the conveyor moved it and reporting the exit moment inflated every duration by the
dwell — measured on the bench, a carton read in 600 ms and left the zone 4 s later. **Settle now
closes a carton, so that dwell is no longer inside the window and there is nothing to correct for.**
The count-met moment has its own field, `countReachedAt`, because it no longer ends anything and so
can no longer ride on `endedAt`.

**Tunnel v1 — completeness is judged on the requested SKU, not on everything in the field.**
`InventoryResult.matchingCount` is the number that matters; `tagCount` is everything that answered.
Comparing the total logged a perfect carton as *"18 of 2 articles, NOT trustworthy"*, because 16 of
the 18 bench tags are not GS1 at all.

**Tunnel v1 — `timed: true` runs the whole of `durationMs` even when the count was reached.** It
looks like a missed optimisation and it is not: the customer may be holding the carton for a
deterministic period, and a read that finishes early leaves it in the field. Verified on the bench:
count met at 189 ms, response returned at 3082 ms.

## The field interface (connector J26)

The reader drives the tunnel over eleven opto-isolated field channels, all of them through the
**Tunnel Manager**. There is no machine between this application and the drive cards, so every
channel is a decision this app makes and holds.

- **`com.intelli.rfid.tunnel.field.FieldChannel` is the authoritative channel map** — OUT1–7 on BCM
  26/20/16/19/21/12/13, IN1–4 on BCM 23/24/18/25. It is a hard-coded enum on purpose: a channel that
  could be moved from a config file is a channel that can silently disagree with the copper.
  `FieldChannelTest` pins every committed function individually, so a change of meaning has to be
  made deliberately rather than arriving as a diff to a table of numbers.
- **`IN1`/`IN2` are ambiguous and it will cost someone a day.** The J26 field channels and the
  SIM7500 module's own GPI pins are both called IN1/IN2 in their own documentation and are different
  silicon. Everything in this project means the J26 channels. **The module's GPI is deliberately
  unused** for the inventory trigger: it can start a read faster than we can but cannot take part in
  the verdict, the shutdown handshake or the zone state machine.
- **Field sense is inverted on inputs and not on outputs, and that asymmetry is the day-one bug.**
  An output asserted at J26 is GPIO **high**; an input asserted at J26 (24 V present) reads GPIO
  **low**, because the 24 V lights the opto's LED and pulls the pin down. `FieldIo` does the
  inversion and nothing above it sees a raw level. Get it backwards and the screen, the vendor's
  drawing and the multimeter all disagree — and the person holding the multimeter is right.
- **`pinctrl`, not `gpioset`, and the reason is process lifetime.** A level set by `pinctrl` survives
  the process exiting, because it writes the pad registers directly; `gpioset` *requests* the line
  and releases it on exit, so holding a level would mean one live process per channel. Register-level
  writes also do not contend with the `gpiomon` that holds lines 23/24 exclusively.
- **`pinctrl get` has two output shapes and a parser must take both.** Measured on the production
  CM4: an input is `12: ip    pd | lo // GPIO12 = input`, a configured output is
  `12: op -- pd | hi // GPIO12 = output` — note the extra column. Match leniently up to the `|`.
- **It runs unprivileged.** `/dev/gpiomem` is group `gpio` and the service user is in it, so no part
  of this needs root. A service user outside that group fails every write.
- **Measured 2026-08-31, boot state of the eleven channels on the production carrier:** every output
  (BCM 12/13/16/19/20/21/26) comes up `ip pd | lo` — which is the hardware failsafe that holds
  `SPEED = 000` from power-on until software drives it, so **do not add anything at start-up that
  disturbs it**. Every input (BCM 18/23/24/25) comes up `ip pd | hi`: reading high through the
  carrier's external 10 kΩ pull-up *against* the BCM2711's internal pull-down, which leaves only
  0.44 V of margin instead of 1.0 V. `PinctrlFieldIo` turns those internal pulls off at start-up.
  **That is right on the carrier and wrong on a bare bench** — with nothing wired to J26 there is no
  external pull-up to take over and the pins float, which on IN1 manufactures cartons. Hence
  `tunnel.field.disable-input-pulls`.
- **The verdict is two lamps, one lit for `lamps.hold-ms` (5 s) and then dark.** O6 green, O7 red;
  **both moved up a channel on 2026-09-05**, when the ExC took O5.
  The other lamp goes out at once, so exactly one is ever lit and both dark is the resting state.
  A new verdict cancels the previous dwell rather than waiting it out, so back-to-back cartons each
  get their full 5 s. `hold-ms: 0` latches instead, for a line that reads one carton an hour.

  **The dwell is not a payload, and that distinction is the whole reason a timer is allowed here.**
  The predecessor on the pass lamp encoded the verdict *in the width* — 100 ms FAIL, 500 ms PASS,
  decoded in 60–200 and 400–600 ms bands — which made scheduler latency a correctness problem: a
  500 ms pulse delivered at 380 ms was a silent **fail** on a carton that was fine. Here the
  *channel* carries the meaning and the duration carries none, so a hold that runs long or short is
  a lamp lit a moment longer, not a wrong answer. **Never encode a second meaning in the dwell**,
  and never shorten it to something an operator can miss.
- **PASS is exactly `complete == true`** — the carton held what was expected. A carton whose count
  could not be judged at all is *not* a pass: there are two lamps, two states, and **no "no
  verdict"** — reaching the end of a carton undecided lights FAIL explicitly, because that is the
  difference between an outcome and a guess that happened to match.
- **The verdict is signalled on the thread that closed the session, not on the result executor.**
  Same reason the carton release is: both are physical signals at the tunnel and neither may wait
  on the WMS. `results` is single-threaded and `callbacks.send()` blocks for up to five attempts
  with backoff, so a verdict queued behind it would light minutes late — a dead WMS would have
  turned every carton's lamp into a lie. Setting two pin levels costs microseconds; only the send is
  handed off.
- **The carton trigger watches GPIO *rising* edges, but a field-asserted input is GPIO *low*.**
  24 V on an input lights the opto and pulls the pin down, so as it stands the read window opens on
  beam *clear* rather than on the carton arriving. Confirmed on this board 2026-08-31 by driving
  line 18: a field-assert produced 0 events, the de-assert produced 1. **Decided 2026-09-02: fix it
  in software** with `gpiomon -l / --active-low` — on both v1 and v2 — which flips edge sense so
  "rising" means *the channel became active*, matching `FieldIo`. IN3 is unaffected: it is sampled
  as a level and never reaches the edge monitor. Note the inconsistency until that lands:
  `/api/v1/diagnostics/io` reports field sense while the edge monitor triggers on raw GPIO, so the
  screen can show IN1 asserted at a moment the trigger has not fired.
- **libgpiod v1 and v2 need different `gpiomon` arguments, and the two machines disagree.** The
  bench rig on Bookworm has **v1.6.3**; the production CM4 on Trixie has **v2.2.1**. v2 renamed all
  three things the monitor uses: `--rising-edge` → `--edges=rising`, the chip became `-c <chip>`
  instead of positional, and `%s.%n` became `%S`. Both print `<offset> <seconds>.<nanos>`, so the
  parse is unchanged and only the arguments differ. `GpioEdgeMonitor` detects the version from
  `gpiomon --version`; `tunnel.v1.gpio.libgpiod-major` overrides it.

  **Getting it wrong on v2 is not a clean failure, and that is the part worth remembering: an
  unrecognised format specifier is printed literally.** Every edge arrives as the text
  `18 %s.%n`, every parse fails, and the monitor declares itself broken and falls back to degraded
  — while `gpiomon` is detecting edges perfectly. Measured on the production CM4 2026-08-31, while
  this unit's site config still had `gpio.enabled: false` and so had never exercised it. **That
  config is now `gpio.enabled: true`, watching lines 23/24/18**, which is exactly the moment this
  would have bitten — and it looks like bad wiring rather than a format string. `libgpiod-major: 0`
  auto-detects and is the right setting here; only override it if the probe cannot answer.
- **The internal-pull trick for faking an edge does not work on the production carrier.** On the
  bench, `pinctrl set 23 ip pu` / `ip pd` lifts and drops an unconnected input and the kernel
  reports both as edges. On the v2.x carrier the **external 10 kΩ pull-up dominates the internal
  pull**, so an input reads high in both states and no edge is produced. Drive the pin instead —
  `pinctrl set 18 op dl` then `op dh` — which does produce real edges, verified on this board
  2026-08-31. Put it back to `ip pd` afterwards.
- **IN3 is a push button held for 5 seconds — a level, sampled, never a counted pattern.**
  Implemented 2026-09-02 in `field/ShutdownRequestMonitor`, which polls `FieldIo.read(IN3)` every
  `sample-ms` (250) on its own thread. It is deliberately **not** on `GpioEdgeMonitor`: a level is
  the thing being measured, and reading it through `pinctrl` also stays clear of the exclusive claim
  `gpiomon` takes on every line it watches. IN3 is therefore no longer on that command line at all.

  **Releasing abandons the hold outright — nothing is banked.** Two four-second presses are not an
  eight-second hold, so a line chattering asserted/released, which is what noise looks like, can
  never accumulate its way to a request.

  **Why a hold and not an edge, measured.** A single edge fired twice unprompted on this board on
  2026-09-01, at 13:48:50 and 19:41:35, with nothing driving GPIO18 either time. Each ran the full
  controlled shutdown correctly in ~130 ms and left the reader stopped and `CLOSED` — which from
  outside looks exactly like a dead reader: `/actuator/health` shows `OUT_OF_SERVICE`,
  `secondsSinceLastRead` climbs, and nothing reads. **Check for `SHUTDOWN REQUESTED` in the log
  before diagnosing a reader that has stopped for no reason.** A continuous 5 s assert cannot be
  produced by an EFT burst or a floating input, and the button now sits behind 24 V and the field
  opto through the Tunnel Manager rather than on a bare pin.

  **Two start-up guards, and both are needed**, because a stuck button or a shorted line reads
  asserted forever and would otherwise shut the unit down on every boot — an unbootable reader with
  no fault anywhere to explain it, on a line where restart is a full power cycle with an engineer at
  the panel.
  1. **`require-release-first`** is the one that holds: a hold may only begin from an observed
     released→asserted transition, so a line never seen released can never start one. The verdict is
     latched at the *start* of the assert, so a later release cannot retroactively bless it.
  2. **`startup-grace-ms` (30 s)** is the weaker second guard — on its own it only *delays* the
     shutdown of a stuck line.

  **`hold-ms` is 5000 and a non-default is warned about at start-up**; so is turning
  `require-release-first` off. The monitor measures uptime from its **first sample**, not from
  construction, so the grace and the samples share one clock and cannot be defeated by the two
  disagreeing.

  **Debugging needs TRACE.** At INFO you get the start-up `Watching IN3 (BCM 18)…` line and the WARN
  when a hold is accepted, and nothing else; DEBUG adds only the assert and the abandon. Every
  sample's running hold time is at TRACE — set
  `logging.level.com.intelli.rfid.tunnel.field: TRACE` for bench test 5.

- **Shutdown step 3 fails on an idle reader, and the sequence is right to carry on.** Step 1 stops
  inventory and drops the carrier, which leaves the session `CLOSED`; step 3, "finish any in-flight
  tag write", then throws `ReaderException: Reader is not connected (state=CLOSED)` even when there
  was no write to finish. Observed on both of 2026-09-01's shutdowns. It is logged at ERROR and
  stepped over — "not reaching step 6 is the worse failure" — so it costs nothing but a misleading
  line in the log of every clean shutdown. Worth making step 3 a no-op when no write is outstanding,
  so that an ERROR there means something.

- **The IN3 shutdown is a real ordered `systemctl poweroff`, and the risk was never the shutdown —
  it was the lamp saying "safe" one phase too early. Fixed 2026-09-04.** From this board's own
  `man bootup`, a systemd shutdown has two phases: units run up to `final.target`, and *then*
  `systemd-poweroff.service` replaces PID 1 with `systemd-shutdown`, which is what unmounts the
  remaining filesystems, **remounts root read-only and syncs**. `umount.target` covers everything
  except root, and root is the one that matters.

  `intelli-shutdown-lamp.service` was `After=umount.target Before=final.target`, so it drove the lamp dark
  in phase one — while `/` was still mounted rw with dirty pages waiting on the final sync. Its own
  comment claimed dark "cannot be reached before the filesystems are quiesced"; it could. An
  operator quick with the panel switch was cutting power during that sync, which is exactly the
  corruption the whole sequence exists to prevent, reached by a different route.

  **The fix is that the lamp is no longer a unit.** `deploy/intelli-lamp.shutdown` installs to
  `/usr/lib/systemd/system-shutdown/`, which `systemd-shutdown` runs *after* the root remount-ro and
  immediately before power is cut (`man systemd-halt.service`). `/usr/bin/pinctrl` and
  `/dev/gpiomem` are both still available there. **It must be 0755** — systemd-shutdown silently
  skips a file it cannot execute, and the symptom is a lamp that never goes dark on a board that is
  off, which reads as a hung shutdown and appears in no log. It puts the lamp out for `poweroff` and
  `halt` only: on `reboot` the board is coming back, so dark would be a lie for the few seconds
  until it does, and the app clears both lamps at start-up anyway.

- **Step 5 now actually syncs, and until 2026-09-04 it did not.** It was called "flush every
  outstanding write; leave storage safe to interrupt" while only awaiting `CallbackSender.awaitQuiet()`
  — which is *network* quiescence. `JsonlSpool.append` is a plain appending `Files.writeString` with
  **no fsync**, and this board's `dirty_expire_centisecs` is 3000, so up to **30 seconds** of carton
  results could be sitting in page cache when the button was pressed. `ShutdownSequence.systemSync()`
  forks `/bin/sync` after the callback flush; it is injected like `exit` so tests can pin the order
  without forking anything. This is what makes the *blink* phase survivable if 24 V is pulled early;
  it is the other half of the lamp fix, not a substitute for it. A failing sync is logged and step 6
  is still reached.

- **What is genuinely NOT a corruption risk here, so nobody re-derives it.** `sudo systemctl poweroff`
  is the same call `sudo poweroff` makes — no `--force`, no direct `reboot(2)`. The 120 ms an
  operator perceives as "instant" is the app's five steps only; the OS phase runs at full length
  after it. What it is *not* like is bare `sudo shutdown`, which is `shutdown -h +1` and waits a
  full minute before doing anything — that is the comparison that makes IN3 feel abrupt. Root is
  `ext4 rw,noatime` with the default `data=ordered`, so metadata is journalled and even a hard cut
  gives a journal replay, not a broken filesystem: what a cut costs is recent *data*, which shows up
  as NUL-filled tails in whatever was being appended. It is eMMC, not an SD card.

- **A NUL run inside a text file is the fingerprint of a hard power cut, and it dates the cut.**
  Found 2026-09-04: 3377 NUL bytes in `intelli-rfid-tunnel.log` immediately before a boot line, and
  1689 at the tail of `spool/inventory-2026-09-04.jsonl`. ext4 had journalled the inode's new size
  but the data blocks never reached the card. **Both read paths in `JsonlSpool` catch a bad line and
  skip it at DEBUG**, so the app starts and runs normally over the damage and nothing ever complains
  — check for it explicitly rather than waiting to be told. Trim with `truncate -s <last good byte>`.
  Related trap: **the CM4 has no RTC that survives an unclean cut**, so the boot after one restores a
  stale timestamp and the log appears to go *backwards*. Two files whose contents say 15:17 can sit
  after a boot line stamped 15:15. Do not reconstruct a timeline from the clock alone — PIDs are the
  reliable ordering (a low PID means a fresh boot).

- **journald on this board is volatile: `/var/log/journal` exists but is empty**, so
  `journalctl --list-boots` shows only the current boot and the entire transcript of a shutdown is
  gone at the next start. That is why a question like "did that poweroff unmount cleanly?" has to be
  answered from `/opt/intelli/logs/` and the kernel ring buffer instead. Make it persistent with
  `sudo systemd-tmpfiles --create --prefix /var/log/journal && sudo systemctl restart systemd-journald`.

- **The serial counter needs no flushing at shutdown, by construction.** `SequenceCounter.next()`
  calls `channel.force(true)` before returning each number, so the high-water mark is durable at
  every instant rather than at exit. Step 4 of the shutdown sequence therefore *confirms* — it reads
  the file back independently of the in-memory counter, which is the only check that would catch the
  two having drifted — rather than committing anything.
- **There is no liveness heartbeat, there is no longer anywhere to put one, and that is a real loss
  to be aware of.** OUT6 used to toggle
  at 1 Hz so a watchdog could stop the line after 3 s of silence — a *hardware* liveness signal that
  survived a hung JVM. OUT6 became the red lamp, O7 was earmarked to take the heartbeat back, and
  the site rewiring of 2026-09-05 spent O7 on the red lamp instead — so **J26 is full and nothing
  replaces that signal**: a wedged
  application leaves every output wherever it last set it. What limits the damage is that O1 is
  released by the read budget rather than held by a running loop, so a carton cannot be stranded
  indefinitely by a stall alone. **If a liveness signal is ever wanted back it needs a channel this
  connector does not have** — RS-485 to the drive cards is the way out, and it would free O1–O5 at
  the same time. It also needs its own thread, and nothing else may ever go on that thread, because a callback retrying
  against a dead WMS would sit in front of the next toggle.

## Conventions

- Framework-free code goes in `com.intelli.rfid.core`; anything Spring goes in
  `com.intelli.rfid.spring`. Core must stay usable from a plain CLI, so its Spring dependencies are
  `<optional>`.
- **Core's pom must keep `<parameters>true</parameters>` on the compiler plugin.** Core has no parent
  pom by design, so it does not inherit the flag from `spring-boot-starter-parent` the way the apps
  do. Without it, any `@RequestParam` / `@PathVariable` in core that omits an explicit name fails at
  *request* time with HTTP 400 ("parameter name information not available via reflection") — code
  that compiles and starts cleanly, then 400s on first use. Removing that config silently breaks
  four endpoints across all three apps.
- Every vendor `READER_ERR` is checked and wrapped in a `ReaderException` carrying the module's own
  detail string. Never discard a return code.
- `ReaderException` maps to HTTP **409**, not 500 — almost every one means "the reader is not in a
  state where it can do that", which is a state conflict, not a server bug.
- Config values that depend on a site (settle windows, RSSI thresholds, antenna geometry) get a
  comment saying how to tune them from real data, not just a default.

## Deploying to this unit

**The division of labour, agreed 2026-09-01: Claude edits and commits, Piyush deploys.** Claude
cannot `sudo` here (no tty) and cannot hold a long-running JVM across tool calls, so the deploy is
one command in the operator's own terminal:

```bash
cd ~/rfid/intelli-rfid-reader/apps/intelli-rfid-tunnel && deploy/redeploy.sh
#   --core     rebuild intelli-rfid-core first, if core changed
#   --no-pull  deploy what is already checked out
```

**Run it as `intelli-sbc`, not under `sudo`** — it sudoes for the three privileged steps itself.
Running the whole thing as root runs Maven as root, which writes `/root/.m2` and leaves `target/`
root-owned, and the next ordinary build then fails on permissions in a way that looks like a broken
checkout. The script refuses if it finds itself running as root.

**It waits for the JVM to actually exit after the stop, and stops if one survives.** The serial port
and the JNI library are single-owner: a JVM that outlived `systemctl stop` still holds
`/dev/ttyAMA0`, and the restarted service then fails to open the module — which reads as a hardware
fault and is not one. It reports the survivor rather than killing it, since it may be a probe or
another app in use. `pgrep -x java`, never `pkill -f`, which matches the shell running the script.

**Stop first, deliberately.** Until this migration the unit launched straight out of `target/`, so
a build overwrote the jar under the live JVM — and a `mvn clean` deleted it outright, which is
invisible until the next restart and then crash-loops on `Unable to access jarfile`. That happened
twice on 2026-08-31. `install.sh` now copies the jar and the aarch64 `.so` to `/opt/intelli`,
installs the unit file and reloads systemd, so the build tree is no longer a runtime dependency.

**A log level no longer needs any of this.** `loggers` is exposed on actuator, behind the ADMIN key:

```bash
curl -X POST -H "X-API-Key: <admin key>" -H 'Content-Type: application/json' \
     -d '{"configuredLevel":"TRACE"}' \
     localhost:8081/actuator/loggers/com.intelli.rfid.tunnel.field
```

Prefer that over a config edit — a restart re-inits the module and loses the state being
investigated, which for an intermittent shutdown request on IN3 is the whole point.

**Logs go to `/opt/intelli/logs/intelli-rfid-tunnel.log` as well as journald** (decision
2026-09-01 — `/opt` keeps the runtime under one prefix, and `/var/log/intelli` has never existed on
this board). `journalctl -u intelli-rfid-tunnel -f` stays the fast look at a running unit; the file
is what survives a journald rotation and can be copied off the board. Rolls at 20 MB, 14 files,
500 MB total. **The directory must be owned by `intelli-sbc`** — `install.sh` does that, and it is
load-bearing: `/opt` is root-owned and the app is unprivileged, so a root-owned log directory means
logback cannot open the file and the app **silently** logs only to journald, with nothing looking
wrong because journald keeps working. Check `ls -l /opt/intelli/logs/` after a deploy.

## Gotchas

- **`systemctl stop` leaves the unit in `failed` state, and it is cosmetic.** The JVM exits 143 on
  SIGTERM and the unit declares no `SuccessExitStatus=143`, so a perfectly clean stop reports
  `failed` and `systemctl is-active` says `failed` rather than `inactive`. `Restart=on-failure` does
  not fire on a deliberate stop, so nothing misbehaves — but do not read `failed` after a stop as
  evidence of a crash. The same SIGTERM produces `gpiomon exited with 143; the sensors are not being
  watched` in the log at every shutdown, which is shutdown noise and not a sensor fault.
- **A probe needs the module powered, and stopping the app is what switches it off.** See the
  Hardware section: `ExecStopPost` drops `RFID_EN`, and nothing but the systemd unit ever raises
  the four bring-up pins. Raise them yourself (`pinctrl set 8 op dh; pinctrl set 9 op dl;
  pinctrl set 22 op dh; pinctrl set 10 op dh`) or use `/home/intelli-sbc/api/run/run.sh`, which
  does it, refuses to start if a JVM still holds `/dev/ttyAMA0`, and takes `ANT=2` for J25.
  Then set the region explicitly — a power cycle reverts the module to `RG_NA`.
- **Ask the operator to start and stop the apps.** Claude Code on the CM4 cannot reliably manage a
  long-running process: a backgrounded JVM gets killed at tool-call boundaries, and
  `pkill -f '<app-name>'` matches Claude's own wrapper shell and kills that instead (exit 144). Use
  `pgrep -x java` or the listening port to identify it. For diagnostics prefer a **one-shot Java
  program** compiled against the vendor jar — open, do the work, exit, all inside one tool call. That
  is how the first tag read was obtained. If a server really is needed, start it and drive it within
  a single command, or ask the operator to run it in their own terminal.
- **The tunnel app hard-fails startup if its spool directory is not writable.**
  `JsonlSpool.initialise()` throws `UncheckedIOException` out of the `InventoryService` constructor,
  which kills the Spring context — `AccessDeniedException: /var/lib/intelli` on a dev box. Create it
  first (`deploy/install.sh` does, as user `intelli`). Worth questioning against this project's own
  rule that a field unit should come up and report unhealthy rather than refuse to start: a spool
  that cannot be written is a degraded reader, not an unusable one.
- **Maven incremental compile goes stale.** After editing a core source file, `mvn install` can
  report success while apps still bundle the old class. Use `mvn clean install` on core after
  editing it. Verify with `javap -c -p -cp target/classes <Class>` when behaviour contradicts source.
- Site config lives in `/etc/intelli/<app>/application.yml` and overrides the packaged defaults.
- The service user must be in the `dialout` group or the app starts and then fails to open the
  serial port — which looks exactly like a reader fault.
- **Never conclude a setting took effect from its return code — read it back.** Two adjacent
  parameter layers on this module have opposite failure signatures: `MTR_PARAM_CUSTOM` reports a bad
  parameter name honestly (`MT_INVALID_PARA`), while `MTR_PARAM_POTL_GEN2_TAGENCODING` returns
  `MT_OK_ERR` for anything at all and silently substitutes 107. `Probe2` does the read-back for
  regions and `ProbeMode` for modes — copy that pattern.
- **Check `GEN2_SESSION` before believing a low tag count.** A leftover `session = 2` from a previous
  run, against tag stock whose S2 inventoried flags persist >15 s, reads exactly like a broken reader
  or a missing tag. Found sticky at S2 on 2026-08-28 and briefly mistaken for a lost tag. Probes
  should set session explicitly rather than inheriting whatever the last run left.
