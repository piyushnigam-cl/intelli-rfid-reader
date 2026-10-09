# intelli-wayside-reader — design

**Status: DRAFT for review, 2026-09-24. Written on the CM4, with no wheel sensor, no SAMD21 firmware
and no site data.** Everything below about train behaviour, sensor signals and site geometry is
proposal or inference. Anything marked **UNVERIFIED** has a default that must be replaced by a
measured value, and the way to measure it is given next to it.

---

## 1. What it is for

A reader beside the track at **Charkop** identifies each train that passes and makes **one REST
call per train** to a cloud endpoint. Each call carries:

- **Identity**: the two RFID tags each train carries, one at each end.
- **Wheel data**: axle count, direction and speed, from two wheel sensors read by the board's SAMD21
  through its analog front end.

It runs on the same hardware as the tunnel: an IntelliRFID v2.x carrier with a CM4 and a SIM7500.
It is built the same way: Java 21, Spring Boot 3.4, `intelli-rfid-core` underneath, and a systemd
unit that raises the module pins.

**It supersedes `intelli-rfid-wayside`**, the laptop draft that was never pushed to CodeCommit. That
draft took its direction and speed from two antennas and built a consist of many wagons. Charkop has
one antenna, two tags per train, and wheel sensors for direction and speed, so the draft's core
(`PassBuilder`, antenna-order direction inference) does not apply. **Its rules carry over. Its code
does not:**

- Close on silence since the last event, not since the last new one. A moving population that goes
  quiet has left.
- Never lose a tag to a decode rule. If an EPC does not decode, report it raw with `decoded: false`.
- Direction and speed refuse to guess. When the evidence is missing or conflicting, report
  `UNKNOWN` / `null`, because a wrong direction is worse than none.
- Every upstream call is spooled and replayed.

---

## 2. Hardware, as far as it is known

| Part | What | Status |
|---|---|---|
| RFID | SIM7500 (Impinj E710), one mono-static port, **one antenna** | Known. Runs `RG_IN` on sw `20.26.08.19`. See `CLAUDE.md` |
| Antenna port | J25 (ANT2) or J20 (ANT1), selected by GPIO8/9 at `ExecStartPre` | Per board. **Sweep both with `/api/diagnostics/antennas` before choosing** (J20 is bad on `intellisbc`) |
| Wheel sensors | Two Frauscher wheel sensors, **4 analog current-loop channels** on J22/J23 into SAMD21 ADC **PA02–PA05** | From the schematic. **Sensor model UNVERIFIED** |
| Supervisor MCU | ATSAMD21G18A, runs off 24 V independently of the CM4 | Known. **No firmware exists** |
| CM4 ↔ SAMD21 | **UART3, GPIO4/5 → `/dev/ttyAMA3`**, CTS/RTS on GPIO6/7 | Known. Needs `dtoverlay=uart3`, which the production bring-up already sets |
| SAMD21 programming | SWD from CM4 GPIO: 2 = RESET, 3 = SWCLK, 11 = SWDIO | Known. The CM4 can flash it with OpenOCD's `bcm2835gpio` driver, so no probe is needed on site |

**The sensor is the Frauscher RSR110d (operator, 2026-09-29).** Its public datasheet (2020-09)
gives two sensor systems, an open analogue interface, a **constant 5 mA with "a change in current"
when damped**, 0–450 km/h, 300–2100 mm wheels and an 8–33 V supply. **It does not give the size or
the direction of the change, the fault currents, or the spacing between the two systems.** So the
firmware detects on `|I − baseline|`, and `covered-ua`/`uncovered-ua` are deviations, not levels.
Frauscher's technical documentation, or a capture, has to supply the rest. **Operator,
2026-09-29: the current DIPS below 3 mA when a wheel damps it** (from the default 5 mA). That is
the first statement of its direction, given as the spec for a bench emulator; confirm it against
Frauscher's documentation. The detector works either way.

**Four channels means two double sensors.** A Frauscher counting head (the RSR180 family) contains
two systems a few centimetres apart along the rail. The order in which they are covered gives
direction from a single head. The time between them gives a coarse speed. Two heads, mounted a known
distance apart, give a better speed and a second, independent axle count to check against. **Confirm
the model and read its datasheet before firmware is written.** The quiescent current, the
wheel-present current and the fault bands (open loop, short) all come from there, and none of this
document's defaults can be trusted until they do.

**This app and the tunnel cannot run on the same board.** Both own `/dev/ttyAMA0` and the JNI
library, which allow a single owner. The Charkop unit is its own board.

### 2.0 Operator decisions, 2026-10-09

**Naming: Wheel 1 and Wheel 2, by the board's silk.** **J23 is Wheel 1** (silk "Wheel Sensor 1") and
**J22 is Wheel 2** (silk "Wheel Sensor 2"). That is the terminology from now on, in code, config, UI
and documents. The PCB swapped the nets: J22 carries the `WSA*` nets and J23 the `WSB*` nets
(`WHEEL-SENSOR-JIG.md`). That is a design-phase typo, and the project keeps the silk names.

| Name | Connector | Board nets | SAMD21 | Protocol channels | App today |
|---|---|---|---|---|---|
| **Wheel 1** | **J23** | `WSB1`, `WSB2` | PA04 (AIN4), PA05 (AIN5) | **2, 3** | "head B" |
| **Wheel 2** | **J22** | `WSA1`, `WSA2` | PA02 (AIN0), PA03 (AIN1) | **0, 1** | "head A" |

**Direction: Wheel 1 first = `UP`, Wheel 2 first = `DOWN`.** Always in capitals.

> **Done in the app 2026-10-09** (`intelli-wayside-reader`): the direction rule is fixed in code
> and not configurable, so `up-is-a-to-b` is gone, and a site file that still sets it is ignored.
> Internally the sensors are Wheel 1 and Wheel 2. The pass JSON keeps its schema-1 names, in which
> `headA`/`atA` are Wheel 2 and `headB`/`atB` are Wheel 1. Renaming them is a schema-2 change for the
> cloud owner. The GPIO stand-in is unaffected: J26 IN1 first is still `UP`.
>
> **Installation rule that follows from the channel order:** in each RSR110d, the sensing element on
> pin 4 (element 2) is the one on the Wheel 1 side, and the element on pin 2 the one on the Wheel 2
> side. Direction is named only when the sensor order and the element order at both sensors agree.
> A sensor wired with its elements swapped gives `UNKNOWN` on every pass, with the note "the two
> sensors disagree on element order". That is the commissioning symptom to look for.

**Loop currents are to be measured, not assumed.** The no-wheel current is expected near **5 mA** and
the damped (wheel-present) current near **3 mA**. Both are to be **measured on each loop at site**, on
the real RSR110d, and the detection thresholds derived from them. **The admin app needs a
wheel-sensor test page for this** (see the commissioning tools below).

**Speed at each wheel sensor.** Each RSR110d has two sensing elements a known distance apart along the
rail. The time between the two elements seeing the same wheel gives a speed **at that sensor**,
independent of the other one. That is now a first-class output, not just the single-head fallback
in §5.3. Measured on site and written to `application.yml`:

| Setting (`wayside.wheel.`) | What | Starting value (operator, 2026-10-09) |
|---|---|---|
| `element-spacing-m` | Between the two sensing elements of an RSR110d, **one value for both sensors**. Gives the speed at each sensor | **0.06** (6 cm) |
| `wheel1-to-wpms-m` | Wheel 1 to the WPMS | **13.0** |
| `wpms-length-m` | Length of the WPMS | **3.5** |
| `wpms-to-wheel2-m` | The WPMS to Wheel 2 | **18.5** |
| `sensor-spacing-m` | Wheel 1 to Wheel 2. **0 = the three above added up** (35 m); non-zero overrides the sum | 0 |

```
   Wheel 1 (J23) ──13 m── [ WPMS 3.5 m ] ──18.5 m── Wheel 2 (J22)      UP ──►
```

These are **in the packaged `application.yml`** as starting values; the team fine-tunes them on site
in the site config. A layout with any part at 0 gives no sensor-to-sensor speed rather than a short
sum. The old names `system-spacing-m` and `head-spacing-m` still bind to `element-spacing-m` and
`sensor-spacing-m`.

**What 6 cm costs in resolution (INFERRED).** The SAMD21 samples each loop at 5 kHz, so an edge is
placed to within about 200 µs. Over 6 cm that is ±2.4 % of the element-to-element time at 20 km/h,
±5 % at 45 km/h and ±10 % at 90 km/h, per axle. The train's min/mean/max over ~50 axles averages
much of it out. The 35 m sensor-to-sensor speed is far finer and is the figure to trust when both
sensors saw the train.

**Commissioning tools in the admin app (to build).** The admin app should help discover these values
and write them into the site `application.yml`:
- **Loop currents.** A live view per channel (current, baseline, deviation) and a capture of a wheel
  passing, giving the no-wheel and dip currents per loop and proposing `wayside.wheel.detect.*` from them.
- **Geometry.** Enter the measured distances, or derive the element spacing from a pass at a known
  speed, and check them against passes (speed at Wheel 1 vs Wheel 2 vs head-to-head).
- **Output.** The YAML block for the site config, as the key tool already does for key hashes.

**Development board.** Wayside development moves to **`intellisbc`**, the board on the test bench
that will later be deployed to the Reliance tunnel. `intellisbc2` pulls from git later, is tested,
and then ships to Charkop. **The tunnel and wayside apps cannot run at once** (both own
`/dev/ttyAMA0`). So on `intellisbc`, only one of the two units may be enabled at a time, and the
tunnel must be re-enabled before that board goes to Reliance.

### 2.1 Site geometry (proposed layout, UNVERIFIED)

```
   direction UP  ────────────────────────────────────────────►

   ══╪═══════════════╪═══════════════════════╪═══════════════╪══  rail
     │               │                       │               │
   [J23]           ◄ d_1 ►   [ANT]    ◄ d_2 ►               [J22]
  Wheel 1                  antenna (WPMS)              Wheel 2
```

- **Put one wheel-sensor head on each side of the antenna.** Then whichever way a train comes, it
  crosses a head before its leading tag reaches the antenna. That first axle is what switches the
  carrier on (§5.2).
- `d_1` and `d_2` (each wheel sensor to the WPMS, measured on site, §2.0) must be large enough for the carrier to come up before the leading tag reaches the
  antenna. That depends on how far the front tag sits ahead of the first axle and on the maximum
  line speed. **Both are site questions (§10).**
- **Wheel 1 → Wheel 2 is `UP`** (operator, 2026-10-09; see §2.0 for the code mismatch). If it is
  wired the other way round, every direction is confidently wrong. So the commissioning test is a
  train of known direction, not a config review.

---

## 3. Architecture

```
 SAMD21 (firmware, new)                    CM4: intelli-wayside-reader (Spring Boot, :8082)
 ──────────────────────                    ───────────────────────────────────────────────
 ADC PA02–05, sampled ──► detect wheel     WheelLink ──► WheelEventDecoder ──┐
   per channel            on/off per       (UART3,       (frames → events,   │
                          system, µs tick   COBS+CRC)     tick → CM4 clock)   ▼
       │                                                               PassTracker ◄── ReaderService
       └── UART3 frames ───────────────────────────────►               (opens/closes     (core tag
                                                                        a train;          pipeline)
                                                                        carrier on/off)
                                                                              │
                                                                              ▼
                                                                        PassResult
                                                                    ┌─────────┼──────────┐
                                                                    ▼         ▼          ▼
                                                               JsonlSpool  CloudSender  /api/v1/**
                                                               (history)   (spool+retry)  + SSE
```

**Split of work: the SAMD21 detects and timestamps. The CM4 decides.** The SAMD21 turns samples
into "system 2 of Wheel 2 covered at tick t, uncovered at t′, peak 9.8 mA", because that needs
sub-millisecond timing a JVM cannot promise. Everything above that happens in Java: axle pairing,
direction, speed, train boundaries, completeness. Java is where the logic can be unit-tested, and it
can be changed without reflashing a board on a railway.

### 3.1 Packages (mirroring the tunnel)

| Package | Contents |
|---|---|
| `com.intelli.rfid.wayside` | `WaysideApplication`, `WaysideProperties`, health indicator |
| `…wayside.wheel` | `WheelLink` (serial), `FrameCodec` (COBS + CRC), `WheelEvent` model, `TickClock` (SAMD21 tick → CM4 time), `WheelSource` interface, `SimulatedWheelSource` |
| `…wayside.pass` | `PassTracker` (the state machine), `AxleBuilder` (pairs system events into axles, derives direction and speed), `PassResult`, `TrainIdDecoder` |
| `…wayside.cloud` | `CloudSender`: spool, retry and dead-letter, copied from the tunnel's `CallbackSender` and adapted |
| `…wayside.v1` | The local REST API and its error handling |
| `…wayside.bench` | Train injection and the simulator controls, ADMIN-gated and off by default |

`WheelSource` is the seam. `SerialWheelSource` talks to the real SAMD21, and `SimulatedWheelSource`
generates axle trains from a JSON spec. **All of the pass logic is built and tested against the
simulator before any firmware exists.**

---

## 4. SAMD21 ↔ CM4 protocol, v1 (proposed)

### 4.1 Link

- `/dev/ttyAMA3`, **115200 8N1** to start, no flow control. That is ~11 kB/s, and the event traffic
  is a few hundred bytes per axle, so it is plenty. Raw waveform capture (§4.5) is the only heavy
  traffic, and it is on demand. Raise the rate with RTS/CTS later if capture needs it.
- **Binary frames, COBS-encoded, `0x00`-delimited**, each ending in a **CRC-16/CCITT-FALSE**. A
  frame that fails CRC is counted and dropped, never parsed. COBS resynchronises at the next zero
  byte, so a torn frame loses one message and not the stream.
- Little-endian throughout.

```
 frame (before COBS) = ver:u8 | type:u8 | seq:u16 | len:u16 | payload[len] | crc16:u16
```

`ver` = 1. `seq` increments per frame in each direction, so the receiver can count gaps. The
CM4 reports gaps as `wheelLink.framesLost` and never tries to recover them.

### 4.2 Time

The SAMD21 stamps everything with a **free-running 32-bit µs tick** (a TC in 32-bit mode at
1 MHz), which wraps every 71.6 min. Each `HEARTBEAT` carries the tick. The CM4 records its own
monotonic time on receipt and keeps a **linear fit of tick → CM4 nanos** over the last ~60
heartbeats, unwrapping as it goes (`TickClock`). UART latency jitter is well under 1 ms, which is
far finer than the RFID side's ~50 ms read-window batching. So "which tags belong to which axles"
never needs anything better. **Axle-to-axle timing (speed) uses raw ticks and never goes through the
fit.**

### 4.3 SAMD21 → CM4

| type | name | payload | when |
|---|---|---|---|
| `0x01` | `HELLO` | protocol ver, fw ver (u32 date), channel count, sample rate Hz, tick Hz, reset cause (`PM->RCAUSE`) | at boot and on `GET_INFO` |
| `0x02` | `HEARTBEAT` | tick u32, uptime s u32, status flags u16, per-channel mean µA ×4 (u16 each) | 1 Hz |
| `0x10` | `SYSTEM_EDGE` | tick u32, channel u8 (0–3), edge u8 (1 = covered, 0 = uncovered), level µA u16 | every detection edge |
| `0x11` | `SYSTEM_PULSE` | channel u8, tick_on u32, tick_off u32, peak µA u16, area u32 | on each uncover. The summary the CM4 actually uses |
| `0x20` | `CHANNEL_FAULT` | channel u8, fault u8 (open / short / stuck-covered / out-of-band), level µA u16 | on change |
| `0x30` | `CAPTURE_CHUNK` | capture id u16, chunk u16 of u16, samples… | in response to `CAPTURE` |
| `0x7F` | `ACK` / `NAK` | acked seq u16, result u8 | each command |

`SYSTEM_EDGE` and `SYSTEM_PULSE` overlap on purpose. The edge arrives the moment a wheel covers a
system, so the CM4 can switch the carrier on without waiting for the wheel to leave. The pulse is the
authoritative record for axle building. **If the two ever disagree, the pulse wins.**

### 4.4 CM4 → SAMD21

| type | name | payload |
|---|---|---|
| `0x81` | `GET_INFO` | — |
| `0x82` | `SET_DETECT` | per channel: covered threshold µA, uncovered threshold µA (hysteresis), min pulse µs |
| `0x83` | `CAPTURE` | channel mask, pre-trigger ms, post-trigger ms, arm-on-next-edge flag |
| `0x84` | `HOST_ALIVE` | CM4 uptime. **Reserved for the supervisor watchdog**, and ignored by v1 firmware (§4.6) |

Detection thresholds are **set by the CM4 at connect** from `wayside.wheel.detect.*`, and read back
through `HELLO`. The same rule as the RFID module applies: never trust the return code, read it back.
Firmware ships with conservative defaults so that a SAMD21 with no host still detects.

### 4.5 Analog data

Two levels, because "the analog data" can mean two different things:

1. **Per-wheel summaries, always**: peak current, pulse width and area in `SYSTEM_PULSE`. These go
   into the cloud payload per axle. They are enough to see a weak sensor or a flange-wear trend over
   months.
2. **Raw waveform, on demand**: `CAPTURE` arms a ring buffer. The next wheel event on the chosen
   channels triggers it, and it is sent afterwards as `CAPTURE_CHUNK`s. That is for commissioning and
   for tuning thresholds, and it is never streamed continuously. 4 channels × 12 bit at even 2 kHz is
   16 kB/s, which is more than the link carries.

**Sample rate, UNVERIFIED: 5 kHz per channel proposed.** A wheel covers one system for roughly
`flange footprint / speed`. At an assumed 100 km/h and ~50 mm that is ~1.8 ms, or 9 samples at
5 kHz, which is enough to detect a wheel and time its centre. Re-derive it from the sensor datasheet
and the line's real maximum speed.

### 4.6 What the SAMD21 also has to do, and v1 does not

The board doc (`Hardware-IntelliRFIDv2.md` §10) makes the SAMD21 the CM4's **only restart path**
after a `poweroff` on live 24 V, and a candidate hardware watchdog. The wayside firmware is the first
firmware this chip will run, so it has to be shaped for both jobs. **v1 implements only wheel
sensing**, leaves `CM4_EN_DRV` Hi-Z, and never holds the CM4 off. `HOST_ALIVE` and the message
number space from `0x40` up are reserved for the supervisor so a later version can add it without a
protocol break. **Restart-by-SAMD21 must gate on `PM->RCAUSE`**, or every SWD flash hard-cuts a
running CM4 (board doc §10).

---

## 5. The pass — one train, one result

### 5.1 States

```
IDLE ──first SYSTEM_EDGE on any channel──► OCCUPIED ──no wheel event for axle-gap-ms
  ▲                                        (carrier on,          AND no channel covered──► TAIL
  │                                         axles accumulate)                              (carrier on
  │                                                                                         rfid-tail-ms)
  └──────────────── publish PassResult, carrier off ◄─────────────────────────────────────────┘
```

- **Open**: the first `SYSTEM_EDGE` (covered) on any channel. The carrier comes on at once
  (`startReading`, 0–3 ms measured). Tags are attributed to the pass from `open − rfid-lead-ms`
  onwards, which covers the module's read-window batching.
- **Close**: no wheel event for `axle-gap-ms` **and** every channel reads uncovered. Then the
  carrier stays up for `rfid-tail-ms` for the trailing tag, and the pass is published.
  `axle-gap-ms` must exceed the longest axle-to-axle gap at the slowest speed a train crosses at.
  That is `max axle spacing / min speed`: for example 15 m at 5 km/h is 10.8 s. **UNVERIFIED: default
  15000**, re-derived from the rolling stock and the depot's slowest move.
- **Backstop**: `max-pass-ms` (default 600000). A train that stops over the sensors, or a sensor
  stuck covered, closes the pass with `stopReason: TIMEOUT` and raises a channel fault. It does not
  hold the carrier up forever.
- **Degraded, wheel link down**: the pass opens on the first tag and closes after `tag-gap-ms` of
  silence since the last read (the old wayside rule). Axles, direction and speed are `null`, and the
  result carries `wheelLink: DOWN`. Identity is still delivered, because it is what the cloud needs
  most.

### 5.2 Carrier

Triggered carrier is the default: on at open, off after the tail. Two reasons:

- **Thermal.** `CLAUDE.md` §Thermal: at 30 dBm the PA sits ~45–50 °C above the reported
  temperature (INFERRED), and a trackside box in Mumbai sun has no bench ambient. A carrier that is
  on only while a train crosses has a duty cycle of a few percent.
- **Emissions.** Nothing radiates while no train is there.

The price is that the leading tag must not reach the antenna before the first axle has crossed a
head (§2.1). `wayside.rfid.carrier: ALWAYS` is available for commissioning and for a site where the
geometry cannot be made to work.

**Gen2 session: S1 proposed, UNVERIFIED.** Two tags pass at speed, and they are each read a few
times and then leave for good. S1 decays in 0.5–5 s, so a tag is not silenced across the train's
length the way S2 silences it (see the S2 findings in `CLAUDE.md`). S0 is the alternative if read
counts come out thin. Measure both on a moving tag.

### 5.3 Axles, direction, speed

`AxleBuilder` pairs the two systems' pulses on each head into axles. The system order gives the
direction at that head, and the head-to-head order gives it again, independently.

- **Direction** is `UP` / `DOWN` only if **both heads agree for every axle**. `MIXED` means the train
  reversed over the sensors, which is ordinary in a depot. `UNKNOWN` means only one head saw it, or
  the evidence is split. **Never a majority vote.**
- **Speed** per axle is head spacing `L_AB` divided by the tick difference of the same axle at A and
  B. It is reported as min / mean / max over the train. If `L_AB` is not configured (0), speed is
  `null`. **Built 2026-10-09: speed at each wheel sensor as well**, from `element-spacing-m` and the
  time between that sensor's two elements seeing the same wheel. Each axle carries
  `speedAtWheel1Kmh` and `speedAtWheel2Kmh`. Its `speedKmh` is the sensor-to-sensor figure when that
  can be had (both sensors saw it, counts agree, direction known), otherwise the mean of the
  per-sensor figures. The train's min/mean/max are over `speedKmh`. Pairing a sensor's two pulses
  is mutual-nearest, so a missed pulse leaves an orphan rather than pairing a wheel with the next
  axle and producing a false speed.
- **Axle count** is reported per head. `axleCountConsistent: false` when the heads disagree. That is
  the classic axle-counter integrity check, and it is surfaced rather than resolved.

### 5.4 Train identity

The train is identified by its **two tags, one at each end**. `complete` = two tags read that both
decode to the same train. **The EPC encoding is a site question (§10).** Until it is answered,
`TrainIdDecoder` has a `RAW` mode (the train ID is null and both EPCs are reported), plus a
configurable rule that the old draft's `WagonDecoder` modes will be rebuilt into. The rule that
carries over unchanged: **a tag that does not decode is still reported, raw.**

If the tag encodes which end it is, then which end was read first is a second, independent direction
signal that needs no wheel sensor at all. Worth asking for when the tags are specified.

---

## 6. The cloud call (proposed)

One `POST` per train to `wayside.cloud.url`. Authentication is **`Authorization: Bearer <token>`**,
with the token in the site config (`/etc/intelli/intelli-wayside-reader/application.yml`, mode 640),
never in the packaged file.

```json
{
  "id": "0f6c1e0a-6b1e-4c5e-9a53-2f1d1d3f9b21",
  "readerId": "charkop-01",
  "sequence": 1287,
  "startedAt": "2026-10-02T09:14:03.118Z",
  "endedAt":   "2026-10-02T09:14:21.904Z",
  "stopReason": "CLEARED",
  "clockSynced": true,

  "train": {
    "id": "EMU-4321",
    "decoded": true,
    "tagsExpected": 2,
    "tagsFound": 2,
    "complete": true
  },
  "tags": [
    { "epc": "E28011…", "decoded": true, "firstSeen": "…03.402Z", "lastSeen": "…03.611Z",
      "reads": 6, "bestRssiDbm": -41.5 },
    { "epc": "E28011…", "decoded": true, "firstSeen": "…21.377Z", "lastSeen": "…21.560Z",
      "reads": 4, "bestRssiDbm": -47.0 }
  ],

  "wheels": {
    "link": "OK",
    "direction": "UP",
    "axleCount": { "headA": 48, "headB": 48, "consistent": true },
    "speedKmh": { "min": 21.4, "mean": 23.9, "max": 25.2 },
    "axles": [
      { "n": 1, "atA": "…03.301Z", "atB": "…03.527Z", "speedKmh": 21.4,
        "peakUa": [9820, 9790, 9805, 9811] }
    ],
    "faults": []
  },

  "reader": { "app": "1.0.0", "moduleFw": "20.26.08.19", "region": "RG_IN" }
}
```

- `stopReason`: `CLEARED` (the sensors cleared normally), `TIMEOUT` (the `max-pass-ms` backstop) or
  `TAG_GAP` (degraded mode, closed on tag silence).
- `complete` and `stopReason` are **independent** and neither softens the other. That is the same
  rule as the tunnel, for the same reason.
- `clockSynced` is false when NTP has not synchronised since boot. **The CM4 has no RTC that survives
  a hard cut**, so a result stamped before sync can be minutes or days off. The flag is there so the
  cloud never trusts such a timestamp silently.
- `axles[]` is ~50 entries for a 12-car train, which is small. `peakUa` is the per-system summary
  from §4.5, and raw waveforms never go in this call.

**Delivery, copied from the tunnel's `CallbackSender` and proven there:**

- It is handed to a single sender thread, so nothing in the pass path ever waits on the network.
- The client timeout is **5 s**, not the tunnel's 2 s, because a trackside uplink is probably
  cellular.
- **Retry 5xx and timeouts with backoff. Never retry 4xx. 401/403 raise an alarm.**
- **At-least-once, with the same `id` on every attempt.** The cloud deduplicates on `id`, and
  `sequence` lets it see gaps.
- If the endpoint stays unreachable, the result is spooled to disk, replayed every 60 s, and after
  7 days moved to `cloud-dead.jsonl`, which counts as abandoned, not discarded. Spool depth is on
  `/api/v1/status` and `/actuator/health`.

**This payload is a proposal for whoever builds the cloud side.** Once it is agreed it becomes a
contract document, the same way `Intelli-RFID-RestAPI.docx` is for the tunnel, and after that it
changes only with the document.

---

## 7. Local REST API (on the reader, :8082)

| Endpoint | Scope | What |
|---|---|---|
| `GET /api/v1/status` | READ | reader state, wheel link (`UP/DOWN`, framesLost, crcErrors, per-channel level and fault), cloud backlog, `clockSynced` |
| `GET /api/v1/passes/latest` | READ | the most recent `PassResult`, same shape as the cloud payload |
| `GET /api/v1/passes?since=<seq>` | READ | durable catch-up from the local spool |
| `GET /api/v1/passes/{id}` | READ | one pass |
| `GET /api/v1/wheel/levels` | READ | live per-channel current, for commissioning with a multimeter alongside |
| `POST /api/v1/wheel/capture` | ADMIN | arm a raw capture, then fetch it as JSON |
| `GET /api/v1/events` | READ | SSE: pass open/close, axles, tags, as they happen |
| `POST /api/bench/train` | ADMIN, `wayside.bench.enabled` | inject a simulated train. **Off in the packaged config** |

Plus everything `intelli-rfid-core` already serves: reader status, the tag stream, the VSWR sweep,
tag ops and actuator. API keys use core's existing `ApiKeyAuthFilter` and scopes.

---

## 8. Configuration (packaged defaults, all to be re-derived on site)

```yaml
server.port: 8082
rfid.reader:
  address: /dev/ttyAMA0
  region: RG_IN            # only if fw 20260819 AND auth INDIA; otherwise RG_EU3 (CLAUDE.md)
  antenna-count: 1
  read-power-dbm10: 3000   # radiated-power question still open (CLAUDE.md)
  session: 1
wayside:
  reader-id: ""            # per unit, must be set
  wheel:
    port: /dev/ttyAMA3
    baud: 115200
    # Direction is fixed: Wheel 1 (J23) first = UP (§2.0). No setting.
    wheel1-to-wpms-m: 13.0   # starting values (operator, 2026-10-09), fine-tuned on site
    wpms-length-m: 3.5
    wpms-to-wheel2-m: 18.5
    sensor-spacing-m: 0      # 0 = the three above added up (35 m); non-zero overrides
    element-spacing-m: 0.06  # between an RSR110d's two elements. 0 = no per-sensor speed
    detect:                # UNVERIFIED, from the sensor datasheet then a capture
      covered-ua: 0
      uncovered-ua: 0
      min-pulse-us: 0
  pass:
    axle-gap-ms: 15000     # max axle spacing / slowest crossing speed
    max-pass-ms: 600000
    rfid-lead-ms: 200
    rfid-tail-ms: 3000
    tag-gap-ms: 5000       # degraded mode only
  rfid:
    carrier: TRIGGERED     # or ALWAYS for commissioning
  train:
    decode: RAW
  cloud:
    url: ""                # empty = results spool locally and nothing is sent
    token: ""              # site config only
    timeout-ms: 5000
    max-age-ms: 604800000
  bench:
    enabled: false
```

Detection thresholds of 0 **refuse to start the wheel link** with a clear message, rather than
detecting against a guess. Every other value above is a working default.

---

## 9. Build plan

| Phase | What | Needs hardware? |
|---|---|---|
| **1** | Scaffold the app (`git init` first, CodeCommit remote). Core integration, systemd unit, deploy scripts copied from the tunnel. RFID-only pass (degraded mode), `CloudSender` with spool, local API | This board and tags only |
| **2** | Protocol codec and `TickClock`, `SimulatedWheelSource`, `AxleBuilder`, `PassTracker`, with unit tests for direction and `MIXED`, axle-count mismatch, timeout, link-down fallback, tick wrap | None |
| **3** | SAMD21 firmware (**its own repo, `intelli-wayside-reader-mcu`**), flashed from the CM4 over SWD. First target: `HELLO`/`HEARTBEAT`, then real ADC levels on the four channels with the sensors on the bench | The board, plus a sensor or a current source |
| **4** | Threshold tuning from raw captures, wheel link against real hardware, a mock cloud endpoint | Sensors |
| **5** | Charkop: geometry, `sensor-spacing-m` and `element-spacing-m`, direction proof, `axle-gap-ms` from real trains, radiated power check | Site |

**Phases 1 and 2 are DONE (2026-09-29)**, in `apps/intelli-wayside-reader` (CodeCommit
`intelli-wayside-reader`): 29 tests, plus an end-to-end run on `intellisbc` against the simulated
SAMD21 and a mock cloud. They have not yet run against the module or real sensors. Deviations from
the text above: every local `/api/v1` path is ADMIN (core's default-deny; a READ scope needs a core
rule), `wheel/capture` is not built (it needs firmware), `system-pair-max-ms` and
`system-spacing-m` were added to the config, and the HELLO payload does not echo the thresholds
back yet, so sec.4.4's read-back is still to be added to the protocol.

**Phase 3 STARTED 2026-09-29**: `apps/intelli-wayside-reader-mcu` (CodeCommit
`intelli-wayside-reader-mcu`). **The same day it was flashed on `intellisbc2` and runs.** It sends
HELLO, 1 Hz heartbeats and OPEN faults on all four loops (none connected). The UART is on PA12/PA15
(SERCOM2), and the clock runs −3000 ppm. It has not yet seen a wheel or a live RSR110 loop, and it
**talks to the Java app**: link UP, thresholds ACKed, 0 frames lost, and the
four OPEN faults visible in `/api/v1/wheel/levels` and `/actuator/health`. **Protocol clarification
from that test:** a `CHANNEL_FAULT` is sent on change *and* after every HELLO that answers
`GET_INFO`, because a host that connects late must still learn about a loop that broke earlier.

Phases 1 and 2 are all Java and could start at once. Phase 3 is the long pole, because nobody has written
firmware for this chip yet.

---

## 10. Open questions — none of these can be answered from the desk

**The line and the trains**
1. What runs past Charkop: suburban EMUs, Metro stock into the depot, or both? This sets axle
   spacing, the number of axles per train, and the speed range.
2. What are the maximum and minimum speeds over the sensors, and do trains stop, reverse or shunt
   there?
3. Is there one track in the antenna's field, or adjacent tracks (tags that must be rejected by
   RSSI)?

**The tags**
4. Who writes the two tags, and with what encoding? Does the EPC carry a train ID, and does it say
   which end it is?
5. Where exactly on the train is each tag: height, side, and distance ahead of the first axle? This
   fixes `d_1`/`d_2` and the antenna mounting.

**The wheel sensors**
6. ~~The exact Frauscher model~~ **RSR110d** (2026-09-29). Still open: the damped current (size
   and direction), the fault bands, and the system spacing. None of these is in the public datasheet.
   **2026-10-09:** the no-wheel (~5 mA) and dip (~3 mA) currents will be measured per loop at site,
   and the element spacing in each RSR110d measured there too (§2.0).
7. The planned distance between the two heads, and the distance from each head to the antenna.
   **2026-10-09:** to be measured at site and written to the site config (§2.0).

**The cloud**
8. Who owns the endpoint? Is the auth a bearer token or something else, and does the payload in §6
   suit them?
9. What uplink does the site have (wired, 4G router, VPN)? Is NTP reachable?

**The board**
10. Who writes the SAMD21 firmware, and in what toolchain (Arduino core, ASF4 or bare CMSIS)? The
    proposal is CMSIS plus a small HAL in its own repo, flashed over SWD from the CM4.
