# Hardware handoff — IntelliRFID v2.1 board

**No handoff had reached this project.** Nothing in `intelli-rfid-reader` referenced the PCB — the
only hardware content was the vendor SIM7500/SIM3500 datasheets in `Hardware/`, plus the GPIO
assumptions I invented while drafting the field I/O interface. Several of those assumptions were
wrong. This document is the extract.

**Source of truth** (read 2026-08-22, hardware rev `0861de5`):
`…/Claude-Design/IntelliCAM-CardB/boards/intelli-rfid-v2/`

| Read | Why it matters here |
|---|---|
| `software/SOFTWARE-HANDOFF.md` | The authoritative GPIO map. Written for exactly this audience. |
| `software/bringup_test.py` | Runnable bring-up checks — use it before writing our own |
| `RFID-DESIGN.md` | Reader, antenna switch, UART and RF decisions |
| `IO-BLOCK-SIZING.md` | Opto sizing — where the field-IO drive limit comes from |
| `INSTALLATION-SPEC.md` | Feeder, antenna, earthing, field supply |
| `V2-DESIGN.md`, `SURGE-EMC-REVIEW.md`, `LEARNINGS.md` | Context |

> **If this document and the board's netlist disagree, the netlist wins.** Regenerate with
> `kicad-cli sch export netlist --format kicadsexpr -o v2.net IntelliRFIDv2.kicad_sch` then
> `python scripts/netlist_util.py v2.net --gpio`.

---

## 1. The board

| | |
|---|---|
| Host | Raspberry Pi **CM4** on DF40 (`Module1`) |
| Reader | **U20 = SILION SIM7500**, Impinj **E710**, 5–30 dBm, **one mono-static antenna port** |
| Antenna switch | **U22 = pSemi PE42442A-Z** absorptive SP4T — **2 of 4 ports populated** |
| Supervisor MCU | **U21 = ATSAMD21G18A**, runs off 24 V independently of the CM4 |
| Field I/O | **7 sinking outputs + 4 inputs, opto-isolated (TLP291-4), 24 V, connector J26** |
| Network | Ethernet, CM4's own MAC/PHY, HR911130A magjack |
| Power | 24 V in → buck → 5 V → CM4 + reader |

The field I/O block is **7 out + 4 in + 1 shared common on a 12-way connector**. J26 *is* the
tunnel's whole field interface; the authoritative channel map is
`com.intelli.rfid.tunnel.field.FieldChannel`.

---

## 2. GPIO map — authoritative

From the netlist at rev `0861de5`. **This map changed on 2026-08-04**; anything written against an
earlier revision is wrong (see §11).

| BCM | Dir | Function | Notes |
|---|---|---|---|
| 2 | out | SAMD21 SWD **RESET** | active low |
| 3 | out | SAMD21 **SWCLK** | |
| 4 / 5 | alt4 | **UART3** TX/RX ↔ SAMD21 | needs `dtoverlay=uart3` |
| 6 / 7 | — | UART3 CTS / RTS | wired, flow control optional |
| **8** | out | **Antenna switch V1** | boot = pull-**UP** → 1 |
| **9** | out | **Antenna switch V2** | boot = pull-**DOWN** → 0 |
| **10** | out | **RFID_NRST** | **LOW = reset** |
| 11 | i/o | SAMD21 **SWDIO** | |
| **12** | out | **OUT6** → J26 pin 6 | field output |
| **13** | out | **OUT7** → J26 pin 7 | field output |
| **14 / 15** | alt0 | **UART0** TX/RX ↔ SIM7500 | reader control, 115200 8N1 |
| **16** | out | **OUT3** → J26 pin 3 | field output |
| 17 | out | status LED | |
| **18** | in | **IN3** ← J26 pin 11 | field input |
| **19** | out | **OUT4** → J26 pin 4 | field output |
| **20** | out | **OUT2** → J26 pin 2 | field output |
| **21** | out | **OUT5** → J26 pin 5 | field output |
| **22** | out | **RFID_EN** | **HIGH or floating = reader ON**; 10 k pull-down R59 |
| **23** | in | **IN1** ← J26 pin 9 | field input |
| **24** | in | **IN2** ← J26 pin 10 | field input |
| **25** | in | **IN4** ← J26 pin 12 | field input |
| **26** | out | **OUT1** → J26 pin 1 | field output |
| 27 | out | status LED | |

**The output GPIOs are deliberately non-contiguous** — assigned by a crossing-minimising solver. You
cannot drive all seven with one masked `GPSET0`/`GPCLR0` write. Use the table.

### 2.1 J26 mapped onto the tunnel functions

Mirrors `FieldChannel`, which is authoritative. Pins and BCM numbers are a property of the board and
have never moved.

| J26 pin | Channel | BCM | Function |
|---|---|---|---|
| 1 | OUT1 | **26** | `EnC_ExC_RUN` — Run A of the Entry and Exit conveyors together |
| 2 | OUT2 | **20** | `RZC_RUN_A` |
| 3 | OUT3 | **16** | `RZC_RUN_B` |
| 4 | OUT4 | **19** | `RZC_REVERSE` |
| 5 | OUT5 | **21** | `LAMP_PASS` (green) |
| 6 | OUT6 | **12** | `LAMP_FAIL` (red) |
| 7 | OUT7 | **13** | `SAFE_TO_POWER_OFF` |
| 8 | FIELD_COM | — | shared return, all 11 channels |
| 9 | IN1 | **23** | `ENTRY_SENSOR` ← EnS |
| 10 | IN2 | **24** | `EXIT_SENSOR` ← ExS |
| 11 | IN3 | **18** | `SHUTDOWN_REQUEST` ← panel push button, held 5 s |
| 12 | IN4 | **25** | spare |

---

## 3. Logic sense — outputs and inputs are opposite, and that will bite someone

This asymmetry is the highest-probability source of a day-one bug.

**Outputs are active-HIGH at the GPIO.** GPIO high → 220 Ω → opto LED conducts → phototransistor
saturates → the field output **sinks** to `FIELD_COM`. So `gpio=1` means "output asserted".

**Inputs are active-LOW at the GPIO.** From `IO-BLOCK-SIZING.md`: *"field 24 V present ⇒ opto
conducts ⇒ GPIO reads LOW."* So `gpio=0` means "field signal present".

```
OUT: gpio HIGH  -> field output ON  (sinking)
IN : gpio LOW   -> field input  ON  (24 V present)
```

Consequence for our code: **one `activeHigh` config key cannot serve both.** Split it, or better,
put the inversion inside a `FieldIo` class so nothing above it ever sees raw GPIO levels.

Three more input requirements from the board docs:

- **Disable the internal pull on GPIO18/23/24/25.** All four sit in the BCM2711 pull-DOWN group,
  which *opposes* the external 10 k pull-up. 10 k against ~50 k gives 2.75 V — it reads high, but
  with ~0.44 V of margin instead of ~1.0 V. Set no-pull (or pull-up) explicitly at start-up.
- **Debounce ≥ 10 ms.** EFT bursts (IEC 61000-4-4) couple through the opto's barrier capacitance and
  register as false edges; the same debounce covers cross-channel coupling on the shared
  `FIELD_COM`. Our configured 15 ms is inside this. Keep a held input longer (100 ms) — a
  spurious low there costs a power cycle.
- **All 11 channels share one return.** Every field device on J26 must be on **one** 24 V source and
  return. Split field supplies are not supported, and this is repeated as an installation
  requirement in `INSTALLATION-SPEC.md` §5.

---

## 4. Boot state — the failsafe is real, and it was designed in

- **All seven field outputs are on GPIO ≥ 9**, which the BCM2711 resets **pull-DOWN**. So every
  output comes up **OFF**. The board doc calls this deliberate and load-bearing: *"a 24 V output
  energising at power-on, on a trackside device driving actuators, is the worst available failure.
  Do not ever move a field output onto GPIO2–8."*
- Therefore `SPEED = 000` at boot and on any CM4 failure ⇒ **conveyor stopped**. The failsafe assumed
  in §2.1 above is confirmed by the hardware, not merely hoped for. Still
  loop-test it at commissioning — see §10.
- **All four inputs read inactive at boot** — the 10 k external pull-up wins over the internal
  pull-down regardless of which reset group the pin is in. Chosen for exactly that reason.
- **RFID_EN is GPIO22 (pull-down) ⇒ the reader is disabled at boot.** No RF flows until software
  decides.
- **The antenna switch boots to RF1 / ANT1 (J20)** — a populated, live port (GPIO8 pulls up → V1=1,
  GPIO9 pulls down → V2=0). Harmless only because RFID_EN is low. Do not rely on "boot = unfitted
  port"; an older note claiming that was wrong and is corrected in `RFID-DESIGN.md`.

---

## 5. 🔴 The field outputs cannot drive a field device directly — this is why the TM exists

From `IO-BLOCK-SIZING.md`, and it is the most consequential thing in this document.

The outputs are opto sinks whose drive is set by the **guaranteed saturated** transfer ratio (30 %),
not the part's headline 100 % linear CTR:

| Corner | Guaranteed sink |
|---|---|
| −40 °C | 2.3 mA |
| +25 °C | 2.5 mA |
| **+85 °C** | **1.9 mA** |

(Counter-intuitively **hot is the bad corner**, not cold — 0.76× at +85 °C versus 0.94× at −40 °C.)

The board doc's own verdict: this drives *"a digital input of IEC 61131-2 **Type 1 or Type 3**
(≥ 2 mA at 15 V is the Type 1 threshold, so this is **marginal-to-adequate**), an SSR/opto input, or
a logic-level receiver."* And: *"It will **NOT** drive a coil relay, a lamp, a contactor, or an IEC
**Type 2** input (6 mA)."*

**This is settled, and the answer is the Tunnel Manager.** Every one of the seven outputs lands on
something that needs more than 1.9 mA: an EZY-S100 control input (the closest published equivalent,
Itoh Denki CBM-105, draws 7.3 mA) or a lamp. **The reader therefore never drives a field device
directly** — all seven go through the TM, which does the field-side conditioning. See
`Tunnel-Interconnect.md`.

Note what this means for O1 in particular: it drives **two** card inputs in parallel, because EnC
and ExC share the channel, so the TM has to be sized for the pair.

**The failure mode to watch for at site** is somebody "simplifying" this by wiring a stack-light or
a relay straight to pins 5/6. It will not work, and it will fail *intermittently and hot* rather
than cleanly.

Also noted: **the 11 field lines currently carry no surge protection** (deliberate, parked pending
placement — `IO-BLOCK-SIZING.md`). A conveyor and its VFD share the field ground and are a good
source of transients. Worth raising with the installer.

### 5.1 The inputs, by contrast, are fine — and the reason is structural

The four inputs have no equivalent problem. Re-deriving `IO-BLOCK-SIZING.md`'s figures
(6.8 kΩ series, ~1.2 V LED drop, 30 % saturated ratio, ×0.76 at +85 °C, 10 kΩ pull-up needing
0.33 mA to pull the GPIO down):

| Field volts | LED current | Sink @ +25 °C | Sink @ +85 °C | Margin @ +85 °C |
|---|---|---|---|---|
| **16.8 V** (EN50155 min) | 2.29 mA | 0.69 mA | **0.52 mA** | **1.6×** |
| 24 V nominal | 3.35 mA | 1.01 mA | 0.76 mA | 2.3× |
| 30 V max | 4.24 mA | 1.27 mA | 0.97 mA | 2.9× |

The tightest corner is the *low*-voltage end, and it holds with 1.6× in hand.

**Why one direction is a problem and the other is not**: on the input side the **field device**
supplies the drive — we are simply a 3.4 mA load, which any 24 V PNP sensor output sources without
noticing. On the output
side **we** supply the drive, through an opto that is a deliberately weak source. Whoever has to
provide the current owns the problem, and on this interface that is us, on outputs only.

Two things to watch rather than fix:

- **The 6.8 kΩ input resistors are the tightest thermal item on the board's field side.** At 30 V
  each dissipates 122 mW in a 1206. That is 49 % of the headline 250 mW rating, but thick-film 1206s
  derate above +70 °C: at +85 °C the part is rated ~206 mW, so 122 mW is **59 %, a 1.7× margin**, and
  at +100 °C it is 75 %. Fine, but note that a held input such as `SHUTDOWN_REQUEST` sits high while the
  reader runs and the sensors sit high for much of each cycle — these are steady-state conditions,
  not brief pulses. If the field supply runs at the high end of tolerance in a hot enclosure, this is
  the number to check.
- **The input source must be a real driver, not another weak solid-state output.** 3.4 mA at 24 V is
  nothing for a sensor output or a dry contact, but if any of the four inputs ends up driven by another
  opto-isolated output with the same 1.9 mA class of limit, the problem reappears on that channel.
  Worth one question to the integrator about what actually drives pins 9–12.

Practical consequence for the interposer: **leave the inputs alone.** They do not need boosting, and
routing them through an added board only puts more contacts in series with the read trigger.

---

## 6. Reader control

- **UART0 (PL011) on GPIO14/15, 115200 8N1.** Requires `enable_uart=1`, `dtoverlay=disable-bt`, and
  the Linux serial console **disabled** on GPIO14/15 or it fights the reader.
- **`RFID_EN` = GPIO22** — HIGH or floating = on; a 10 k pull-down means off unless driven.
- **`RFID_NRST` = GPIO10** — LOW = reset.
- Timings from `RFID-DESIGN.md`: **EN de-assert < 3 ms; hold NRST low > 2 ms to reset; wait > 110 ms
  after.**
- The module exposes its own 3.3 V output on its pin 12 — that is an **output**, ≤ 20 mA. Never feed it.

### 6.0 The module's own 2 GPI / 2 GPO — and why they are not a field port

The SIM7500's own `IN1`/`IN2`/`OUT1`/`OUT2` do **not** go to J26. They go to a **separate Degson 5-way
terminal** (4 signals + GND), each line through 33 Ω plus an ESD diode. It looks like a field port
because it lands on a terminal block, but it is **a 3.3 V logic port**, and it is not field-ready on
three independent counts:

| | Module GPIO | What a 24 V field interface needs |
|---|---|---|
| Output level | ~3.3 V (V_OL ≤ 0.3 V) | Omron ON threshold is **≥ 14.4 V** — 3.3 V registers as nothing |
| Input tolerance | V_IH ≥ 2.7–3.0 V, **absolute max −0.3 V to VCC** | 24 V applied here **destroys the pin** |
| Isolation | **none** — 33 Ω and an ESD diode, straight to module silicon | J26 has 2500 V optos and 2.0 mm spacing, and needs them |
| Drive | I_OH 10 mA typ, 15 mA max | cannot source a 24 V loop at all |

Worth noting the irony: at 10–15 mA the module's *unisolated logic* port has **5–8× more drive than
our isolated 24 V field outputs** (1.89 mA). It is the wrong voltage and unprotected, so it does not
help — but it does show where the current is being lost.

**Nothing was given up by not using them.** They are a local auxiliary port for logic inside the same
enclosure. Making them field-ready would need exactly the same treatment as every other field line —
isolation, level shift, drive, one channel at a time — so there is no shortcut hiding there.


### 6.1 This gives us a software reader power-cycle — and it changes the pin-11 design

An earlier draft treated "power cycle essential to restart the reader" as requiring
the 24 V to drop, which drags the CM4's filesystem — and the serial counter — into every restart.

**The board makes a reader-only power cycle available in software**: drop `RFID_EN`, or pulse
`RFID_NRST` low for > 2 ms and wait > 110 ms. If what the customer actually needs is *the reader
module* re-initialised, this achieves it **without touching the CM4 at all**, and the filesystem
hazard disappears.

Worth putting to the integrator: does pin 11 need to remove 24 V from the whole unit, or only to
guarantee the reader restarts clean? If the latter, the interlock becomes a software action with no
risk to the counter file, and only a genuine fault needs the full 24 V cycle.

### 6.2 ⚠️ Do not raise the UART baud rate casually — and it may still bite us

`RFID-DESIGN.md` fixes the link at 115200 with a stated rationale, and the rationale is **the wayside
case, not ours**:

> *"UART stays at 115200. The E710's fast modes want **921600 bps** (RF_MODE 103/11) or 460800
> (120/1) — but the intended trackside case is few tags, long range = RF_MODE 13, which needs only
> > 57600. So this board buys sensitivity, not read rate."*

**The tunnel is the opposite application**: many tags, short range, read rate is the whole
requirement. The board was optimised for wayside. Two consequences:

1. **The fast modes we discussed in `SGTIN-96…md` §7.6 are the ones the board doc says want
   921600.** At 115200 the host link is ~11.5 kB/s. The module is specified at **> 1000 tag/s** for
   96-bit EPCs; at ~30 bytes per tag report that is ~30 kB/s — comfortably over the link. So at full
   fast-mode rate **the UART, not the air interface, becomes the bottleneck.**
2. But the raise is not free: the datasheet warns **UART edges couple into the receiver and desense
   the module**, which is why the board doc says do not raise the baud without a measured need.

**Practical line to take.** We do not need 1000 tag/s — we need ~40 *unique* tags. So first, keep the
uplink small rather than making it faster: leave `Reader/inv_raw_tag_mode` **disabled** so the module
aggregates repeat sightings into `TAGINFO.ReadCnt` instead of streaming every read, and do not enable
`tid: true` on the throughput path unless FastID is available. If measurement then shows the uplink
is still the limit, raising the baud becomes a **deliberate, measured** change with a sensitivity
check — and `MTR_PARAM_SAVEINMODULE_BAUD` is how the SDK does it (its own example uses 921600).
Measure read rate *and* sensitivity before and after; do not change it blind.

---

## 7. Antennas — this is the biggest correction to our design

**The SIM7500 has ONE mono-static antenna port.** The two tunnel antennas are multiplexed by the
**PE42442A SP4T on the board**, controlled by **CM4 GPIO8 (V1) and GPIO9 (V2)**:

| V2 (GPIO9) | V1 (GPIO8) | Port | Fitted |
|---|---|---|---|
| 0 | 1 | **RF1 → J20 (ANT1)** | ✅ |
| 1 | 0 | **RF2 → J25 (ANT2)** | ✅ |
| 1 | 1 | RF3 | ❌ |
| 0 | 0 | RF4 | ❌ |

Absorptive part, so unfitted ports are safe unterminated. Max switching rate 25 kHz, insertion loss
~0.9–1.05 dB at 900 MHz, +33 dBm max CW against our ≤ 27 dBm design point.

**Three consequences, and the first one is good news:**

**7.1 The RG_IN antenna-dwell risk is gone.** `SGTIN-96…md` §7.8 flagged as top risk that
`MTR_PARAM_RF_HOPANTTIME` is documented as non-modifiable outside the China region, potentially
leaving a 4-second dwell ceiling. **That parameter is irrelevant on this board** — the module believes
it has one antenna and does no switching. **Dwell is entirely ours**, set by how often we toggle
GPIO8/9. Delete that risk from the test list.

**7.2 We must attribute the antenna ourselves.** `RFID-DESIGN.md`: *"the CM4 selects the port and
must tag reads with the antenna ID (the module doesn't know the switch exists)."* Every `TAGINFO`
will report the same module antenna port. The per-antenna attribution in the discovery curve
(`SGTIN-96…md` §7.10) has to come from **our own switch state at the moment of the read**, latched
alongside the timestamp. Also: `MTR_PARAM_TAGDATA_UNIQUEBYANT` is meaningless here — the module
cannot distinguish our two antennas.

**7.3 A new cost we did not have before: switching is not free.** Because the module is unaware, we
cannot switch on its round boundaries. Hot-switching mid-round is within the switch's ratings but
will corrupt the round in progress. The likely pattern is *stop inventory → switch GPIO8/9 → restart
inventory* per dwell, and **the stop/start overhead is now the thing that sets the minimum sensible
dwell.** If a stop/start costs 50 ms, the 60 ms dwell once proposed for this interface is
~50 % overhead and the right answer is a much longer dwell with fewer switches.

**This replaces the deleted risk as the antenna question to measure first:** time
stop → switch → start on the CM4, then pick the dwell from that number rather than from the
short-dwell reasoning, which assumed switching was free.

**Antenna status LEDs.** GPIO17 and GPIO27 are software-driven status LEDs. (`RFID-DESIGN.md`
assigns the antenna LEDs to GPIO12/13 — that is **stale**, those are now OUT6/OUT7. See §11.)

---

## 8. Power and thermal — our configured 30 dBm is wrong for this board

`INSTALLATION-SPEC.md` and `SOFTWARE-HANDOFF.md` agree:

> **Conducted power design point = 23–27 dBm (0.2–0.5 W).** *"The thermal path closes at the
> 23–27 dBm design point … It does **not** close at 30 dBm EU continuous at +55 °C — that would need
> 3.5 °C/W, unreachable through any gap pad."*

`SGTIN-96…md` §4 currently configures `powerDbm: 30`. **Change it to 27 and treat it as an
ambient-dependent ceiling, not a constant.** Three further requirements:

- **Enable the E710's E7 temperature-throttle mode** as the backstop, so the module degrades read
  rate rather than stopping mid-pallet at its 90 °C cutout.
- **Log the module temperature** — host-readable to ±4 °C, and available per-PA-enable through the
  CC33 telemetry we already planned. The board doc notes an enclosure in sun runs 15–25 °C above air
  temperature and that this is *not modelled anywhere*.
- Recommended operating range is **−20…+55 °C**. Rth_PA = 25.6 °C/W is fixed inside the module; the
  only reducible term is the board path, and it is already designed.

Supply: 5 V at roughly 0.9–1 A for the reader alone at full power, more on antenna mismatch.

**Band and radiated-power limit are an open item on the board.** `INSTALLATION-SPEC.md` §8 states the
deployment band and radiated-power limit are *not fixed in that document*, and the board is described
as EU-band (866 MHz). Our tunnel targets **`RG_IN` (865–867 MHz)** — overlapping in frequency, but the
certification region, the ERP cap and the front-end acceptance are a question, not an assumption.
**Confirm the deployment band and the Indian radiated-power limit before commissioning**, and note
that on this board the region is set once through `Ex/initregion` and then fixed.

---

## 9. Two RF facts that constrain software choices

**9.1 The 570 kHz buck ripple — this directly touches our encoding decision.** The buck runs at
570 kHz against SILION's request for > 1.5 MHz. The mechanism, from `SOFTWARE-HANDOFF.md` §8: supply
ripple places sidebands at **±570 kHz from the carrier, inside the Gen2 backscatter BLF band
(160–640 kHz)**, and *"the free mitigation is firmware — prefer RF_MODEs whose BLF avoids 570 kHz."*

`SGTIN-96…md` §7.6 leans toward the fast end, which on this module means **FM0 at BLF 640 kHz** —
sitting close to the 570 kHz sideband. **Miller at BLF 250 kHz is well clear of it.** So on *this*
board there is a concrete, physical reason the fast encoding may underperform its airtime arithmetic,
and it reinforces the conclusion already reached there: pick the fastest mode that finds every tag
every time, and prove it with the discovery curve rather than from the per-tag table.

**9.2 The E710 is unusually VSWR-sensitive.** Sensitivity degrades **4–5 dB at VSWR 2.0** (versus
under 1 dB on the E310 it replaced), and the RF path here is switch → SMA → coax → antenna with the
far end uncontrolled. The full sensitivity benefit only lands if **VSWR stays below 1.5 all the way
to the antenna**. Practical software consequences: read per-antenna VSWR at start-up and on a
schedule (`MTR_PARAM_RF_ANTPORTS_VSWR`, and per-PA-enable via CC33), fail commissioning on a bad
port, and treat a VSWR drift alarm as a first-class fault — on this reader it costs sensitivity, not
just heat. Also worth knowing at install: ~5 m of RG-58 costs about 5 dB round-trip at 866 MHz, so
the feeder can quietly consume more link budget than any setting we choose.

---

## 10. The SAMD21 supervisor — the recovery path we did not know we had

An **ATSAMD21G18A** runs off the 24 V rail **independently of the CM4** and supervises it:

- `CM4_EN_DRV` (SAMD21 PB11) can hold the CM4 off. **Wired-AND node — open-drain only.** Release =
  Hi-Z, hold off = drive LOW, **never drive push-pull HIGH**.
- `CM4_BOOTED` (SAMD21 PB10) senses `nEXTRST` — the SAMD21 knows when the CM4 is out of reset.
- Comms to the CM4 on **UART3 (GPIO4/5)**, needing `dtoverlay=uart3`.
- It also owns the two Frauscher wheel sensors — irrelevant to the tunnel, relevant to wayside.

⚠️ **"A CM4 that has been `shutdown` will not restart by itself. The SAMD21 is the recovery path."**
That matters for our pin-11 sequence, which ends in `poweroff`: if the 24 V does *not* actually drop,
nothing restarts the CM4 except the SAMD21. Two things to settle:

- If pin 11 → `poweroff` and 24 V is then genuinely removed, a fresh power-on boots normally.
- If 24 V is **not** removed (or is removed and the SAMD21's own rail is unaffected), the
  unit stays dark until the SAMD21 releases `CM4_EN`. **The SAMD21 firmware must therefore implement
  the restart**, and its startup hold-off must be gated on `PM->RCAUSE` (`POR|BOD12|BOD33` = real
  power cycle, hold; `EXT|WDT|SYST` = a debug or watchdog reset, leave the CM4 alone). Ungated, every
  firmware upload hard-cuts a running CM4.

There is also a design opportunity here: the 1 Hz liveness heartbeat this project used to emit on
J26 has a local analogue — the SAMD21 can watch the CM4 independently and recover it without anything
on J26 being
involved at all. Worth deciding which watchdog owns which failure before both try.

---

## 11. Stale-document traps

`RFID-DESIGN.md` predates the **2026-08-04 GPIO remap** and contains superseded pin numbers. The
`SOFTWARE-HANDOFF.md` map in §2 wins.

| Signal | `RFID-DESIGN.md` (stale) | **Correct (rev `0861de5`)** |
|---|---|---|
| `RFID_EN` | GPIO23 | **GPIO22** |
| `RFID_NRST` | GPIO24 | **GPIO10** |
| Antenna LEDs D18/D19 | GPIO12 / GPIO13 | **GPIO17 / GPIO27**; 12/13 are now **OUT6/OUT7** |

The danger is specific: **GPIO23 and GPIO24 are now field inputs IN1 and IN2** — our `ENTRY_SENSOR`
and `EXIT_SENSOR`. Code written from the stale document would drive two field inputs as outputs
while believing it was enabling the reader.

One naming collision to be aware of: older RF documents use `J26`/`J27` for the third and fourth
(unpopulated) **SMA antenna** ports, while the current build and `INSTALLATION-SPEC.md` §5 use **J26
for the 12-way field I/O connector**. In this project, **J26 = field I/O**.

---

## 12. OS setup and what it means for a Java application

From `SOFTWARE-HANDOFF.md` §6 — do this before any test:

```ini
# /boot/firmware/config.txt
enable_uart=1
dtoverlay=disable-bt          # frees PL011 for GPIO14/15 (the reader)
dtoverlay=uart3               # SAMD21 on GPIO4/5
```

```bash
sudo raspi-config nonint do_serial_hw 0     # enable UART hardware
sudo raspi-config nonint do_serial_cons 1   # DISABLE the login console on it
cat /boot/firmware/cmdline.txt              # 'console=serial0' must NOT appear
sudo apt install -y python3-libgpiod gpiod python3-serial ethtool
```

After reboot: `/dev/ttyAMA0` (reader) and `/dev/ttyAMA3` (SAMD21) — **confirm which is which**,
numbering varies by OS release.

Three notes specific to us:

- **`gpiochip0`** is the one to use (`pinctrl-bcm2711`, 58 lines). **libgpiod v2 changed the CLI**:
  `gpioinfo -c gpiochip0`, not `gpioinfo gpiochip0`.
- **Our application is Java**, and the board's tooling is Python. Decide the GPIO binding early —
  pi4j v2 over libgpiod is the obvious candidate, and it needs proving on this kernel before the
  field I/O layer is written. Do not discover at integration that the chosen library cannot set
  bias (no-pull) on GPIO18/23/24/25, which §3 requires.
- **`software/bringup_test.py` already exists** and exercises this hardware. Run it before writing
  anything of our own, and mine it for the correct sequences rather than re-deriving them.

**EEPROM write protect:** R89 is fitted but **inert until armed in software** —
`sudo rpi-eeprom-config --edit` → `WRITE_PROTECT=1`, then `sudo rpi-eeprom-update -a`. This belongs
in the production process document or the strap is decorative.

---

## 13. Safety — from the board's own handoff, §9

1. **Never enable the reader without an antenna or 50 Ω load on the selected port.** Select the port
   *first*, then enable. Our start-up sequence must order it that way.
2. **Asserting a field output switches real connected equipment.** On this installation that means
   the conveyor. Disconnect field wiring or confirm with site before any output test.
3. **The 24 V field side is galvanically isolated and can float at hazardous potential relative to
   board ground.** Never bridge `FIELD_COM` to board GND — that shorts the 2500 V opto barrier.
4. The product's isolation claim is **"basic insulation, 24 V field circuit, 2.5 kV impulse
   withstand"** — *not* 2500 Vrms, which is the opto's component rating, not the system's.
5. **Commissioning must loop-test all 11 channels.** The series protection resistors can fail *open*
   with no indication, so an untested channel may be silently dead.

---

## 14. What changes in our documents

The field I/O draft this section used to correct has been deleted — the corrections themselves are
the part worth keeping, so they are restated here as standalone findings.

| Finding | Detail |
|---|---|
| GPIO numbers | The early draft's numbers were invented placeholders. §2.1 above is the real map, and `FieldChannel` is authoritative in code. |
| J26 does **not** reach the module's GPI | The module's own 2 GPI / 2 GPO go to a separate 3.3 V Degson terminal. `BackReadOption.IsGPITrigger` is therefore **not** reachable from J26 without an extra interface, and the trigger is a CM4 GPIO interrupt instead. The cost is small: a host-side start is single-digit milliseconds against a multi-second budget. |
| Output topology | Outputs are **sinking**, `FIELD_COM` is the shared return, isolation is opto (TLP291-4). |
| Sense is not uniform | Outputs active-high at the GPIO, **inputs active-low**. `FieldIo` owns the inversion. |
| Boot failsafe | Confirmed by design — outputs on GPIO ≥ 9, pull-down at boot, so the line does not run until software drives it. |
| `SGTIN-96-Encoding-Reliance.md` §4 | `powerDbm: 30` → **27**, ambient-dependent; add E7 throttle. |
| " §7.6 | Add the 570 kHz BLF constraint — FM0 at 640 kHz sits near the buck sideband. |
| " §7.8 | **Delete the RG_IN dwell risk** — the module does not switch our antennas. Replace with measuring stop/switch/start overhead. |
| " §7.10 | Antenna attribution must come from our own switch state; the module cannot report it. |
| " §10.2 | Re-order: the `HOPANTTIME` test is void; the switching-overhead test replaces it. |

---

## 15. Open questions raised by the hardware

1. ~~**IEC 61131-2 input type and current.**~~ **Answered, and the answer is the Tunnel Manager.**
   The 1.9 mA guaranteed sink drives nothing on this line directly, so every output is conditioned
   field-side by the TM. (§5, `Tunnel-Interconnect.md`)
2. **Does pin 11 need to remove 24 V from the whole unit, or only guarantee the reader restarts?**
   A reader-only cycle is available in software and avoids the CM4 filesystem hazard entirely. (§6.1)
3. **Deployment band and radiated-power limit** — the board is EU-band; the tunnel is `RG_IN`. Open
   in `INSTALLATION-SPEC.md` §8 too. (§8)
4. **Antenna model, gain, polarisation and DC-ground**, plus feeder type and length. The feeder can
   consume more link budget than any software setting. (§9.2)
5. **Field-side surge protection on the 11 J26 lines** is currently absent by decision. With a
   conveyor and VFD on the same field ground, is that still the right call? (§5)
6. **Which watchdog owns CM4 recovery?** Nothing does today: the SAMD21 could (it holds `CM4_EN`
   off its own 24 V) but nothing implements it, and there is no PLC. Restart after a shutdown is a
   full power cycle with an engineer at the panel. (§10)
7. **Java GPIO binding** — pi4j v2 over libgpiod, proven on this kernel, with bias control. (§12)
