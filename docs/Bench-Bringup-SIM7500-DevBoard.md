# Bench bring-up — SIM7500 "Develop Component A" board on a CM4

Goal: connect the CM4 to the **SIM7500 Develop Component A** evaluation board over UART and read
one tag. This is the vendor's module carrier — **not** the IntelliRFID v2.1 board. Nothing here has
been run against hardware; every timing and voltage below is from the vendor documents named at the
bottom, not from observation.

---

## 0. Read this first — the board is not what our docs describe

`docs/Hardware-IntelliRFIDv2.md` describes our **v2.1 carrier**. Almost none of it applies here.

| | v2.1 carrier | Develop Component A |
|---|---|---|
| Antennas | SP4T switch, 2 ports, GPIO8/9 | **One MMCX port, no switch** |
| Field I/O | 7 out + 4 in, opto, 24 V, J26 | **None** |
| Module GPIO | on a separate 3.3 V Degson terminal | **On the 12-pin connector, directly usable** |
| EN / NRST | GPIO22 / GPIO10 | 12-pin pins 5 / 11 |
| Baud | fixed 115200 by board design | **9600–921600 free to test** |
| Supervisor | SAMD21 | none |

Two consequences worth naming now: `antenna-count` must be **1**, and the module's own
2 GPI / 2 GPO — which are unreachable from J26 on v2.1 — **are reachable here**, so
`BackReadOption.IsGPITrigger` can finally be tested for real.

---

## 1. ⚠️ Which CM4 is this?

**If the CM4 is seated in the IntelliRFID v2.1 carrier, do not wire this board to GPIO14/15.**
Those pins already go to the on-board U20 SIM7500. Two modules driving one RX line is at best
garbage on the wire. Options, in order of preference:

1. **Use a bare CM4 IO board.** Clean, and what the rest of this document assumes.
2. **Use a USB–UART bridge** (3.3 V TTL) into the CM4's USB, dev board on `/dev/ttyUSB0`.
3. **A second UART** — e.g. `dtoverlay=uart2` (GPIO0/1) — *and* hold the on-board module off
   (`RFID_EN`/GPIO22 low). Last resort: it depends on U20 releasing TXD when disabled, which is
   unverified.

---

## 2. Wiring — 12-pin connector on the dev board

Pin map from `SIM7500 Develop Component A.pdf`. Pin 1 is marked on the silkscreen next to the
connector — **confirm the pin-1 end physically before applying power**; the datasheet gives no
connector part number, pitch, or cable keying, so the supplied cable's orientation is the only
authority.

| Dev board | Signal | Connect to | Note |
|---|---|---|---|
| 1 | VCC | **+5 V** | 3.6–5.25 V. **Not** 3.3 V. |
| 2 | VCC | **+5 V** | tie both — 1.35 A peak |
| 3 | GND | GND | must be common with CM4 GND |
| 4 | GND | GND | |
| 5 | EN | **leave unconnected** | internal 100 k pull-up to VCC ⇒ floating = ON. Low = powered off. |
| 6 | OUT2 | n/c | module GPO, 3.3 V push-pull |
| 7 | IN1 | n/c | module GPI, internal 30 k pull-up, idles high |
| 8 | IN2 | n/c | module GPI |
| 9 | **RXD** | **CM4 GPIO14 / TXD** (header pin 8) | crossover |
| 10 | **TXD** | **CM4 GPIO15 / RXD** (header pin 10) | crossover |
| 11 | RST | n/c *(optional: a spare CM4 GPIO)* | internal 10 k pull-up, **low = reset** |
| 12 | OUT1 | n/c | module GPO |

Both sides are 3.3 V TTL — no level shifting needed.

**Power, from the manual's own warnings:** the module pulls up to ~0.6 A on its own and the
assembly peaks at 1.35 A @ 5 V. Use **short, thick** VCC/GND wires — the manual is explicit that a
thin wire drops enough voltage to stop the module working (it needs >3.3 V at its own pin) and
radiates interference. Put **100 µF bulk + 0.1 µF + 100 pF** across VCC/GND at the board end.
Powering from the CM4 IO board's 5 V rail is acceptable for a first read; a separate bench supply
with common ground is better, and if the supply is a switcher prefer one running above 1.5 MHz —
its ripple lands in the tag return band otherwise.

**Antenna: fit it before anything else.** MMCX, 50 Ω. Recommended VSWR < 1.5; absolute max 8. The
manual says an open antenna port survived a week at full power, so an accident is unlikely to
destroy it — but a mismatch costs the E710 **4–5 dB of sensitivity at VSWR 2.0**, far more than the
E510/E310, so a bad connector will look like a dead reader.

---

## 3. CM4 setup

```ini
# /boot/firmware/config.txt
enable_uart=1
dtoverlay=disable-bt        # frees the PL011 for GPIO14/15
```

```bash
sudo raspi-config nonint do_serial_hw 0     # UART hardware on
sudo raspi-config nonint do_serial_cons 1   # login console OFF  <-- the usual day-one trap
grep -o 'console=serial0' /boot/firmware/cmdline.txt   # must print NOTHING
sudo reboot
```

After reboot:

```bash
ls -l /dev/ttyAMA0 /dev/serial0
systemctl status serial-getty@ttyAMA0    # must be inactive/dead
sudo usermod -aG dialout $USER           # log out and back in
```

---

## 4. Bring-up order — cheapest check first

**Step A — prove the CM4's UART before the module is involved.** Power off, jumper GPIO14 to
GPIO15 directly (header pins 8↔10), then:

```bash
python3 - <<'PY'
import serial, time
s = serial.Serial('/dev/ttyAMA0', 115200, timeout=1)
s.write(b'loopback\n'); time.sleep(0.2)
print(repr(s.read(64)))     # expect b'loopback\n'
PY
```

Nothing back means the console is still attached or Bluetooth still owns the PL011 — fix that here,
not later with the module in the loop. **Remove the jumper.**

**Step B — power the dev board alone.** Antenna fitted, UART not yet connected. Confirm it draws
roughly 0.15 A @ 5 V idle and does not get hot. Module TXD should idle **high** at 3.3 V.

**Step C — connect the UART and talk to it.** Power-on init is **100 ms** — do not send anything or
pull RST low inside that window. (If RST is wired: hold low > 2 ms, then wait > 110 ms.)

```bash
ls /opt/intelli/lib          # libModuleAPIJni.so, aarch64 build, from API-linux-java-v260721
```

**Step D — run the acceptance app** with the dev-board overrides:

```bash
cd ~/intelli-rfid-reader/apps/intelli-rfid-reader-test
mvn -q package
java -jar target/intelli-rfid-reader-test-1.0.0-SNAPSHOT.jar \
  --rfid.reader.address=/dev/ttyAMA0 \
  --rfid.reader.antenna-count=1 \
  --rfid.reader.read-power-dbm10=2000
```

Then, with **one** tag about 30 cm from the antenna:

```bash
curl -s -X POST localhost:8080/api/acceptance/run -H 'Content-Type: application/json' \
  -d '{"serialNumber":"SIM7500-DEV-A","operator":"pn","minTagsExpected":1,"writeTest":false}' | jq
```

`writeTest:false` for the first run — get a read before risking a write.

Checks run in order: connection → module identity → VSWR → tag read → tag write. A failure at
*connection* is the serial device, power, or `dialout` group; at *identity* it is baud or wiring
crossover; at *VSWR* it is the MMCX cable or antenna.

---

## 5. Region — the one setting most likely to make a good module read nothing

The manual's ordering table says **the module ships initialised to the CHINA region (920–925 MHz)**
unless the factory frequency range was specified at order time. Our `application.yml` asks for
`RG_IN` (865–867). Check the part number on the label:

| PN | Bands |
|---|---|
| `10.75000000.21` | FCC & CE & OPEN |
| `12.75000000.21` | SRRC & OPEN |

Either part covers 860–960 MHz in OPEN mode, so `RG_IN` should be settable — but region is applied
once via `Ex/initregion`, so **confirm what the module reports before concluding the antenna or the
tags are at fault.** A CN-region module reading IN-band tags at 20 dBm on a bench may well still
read; it is at range and at rate that it falls apart.

---

## 6. Bench limits worth respecting

- **Do not run 30 dBm on this board without heatsinking.** The datasheet's heat-dissipation line is
  "external heat sink air cooling", and the module force-stops inventory at **90 °C**, requiring the
  inventory command to be re-sent. 20 dBm is plenty for a tag at 30 cm and keeps the write test
  honest (at 30 dBm a tag two metres away that shouldn't be in the field will be).
- **I/O port ESD rating is only ±2 kV** and the antenna port ±1 kV. A degraded module often still
  works — the tell is receive sensitivity down ~7 dB. Baseline it now: note the RSSI of a fixed tag
  at a fixed distance, so a later ±3 dB shift is measurable rather than a hunch.
- Operating range −20…+65 °C; RSSI, phase and module temperature are all readable — log temperature
  from the first run.

## 7. What this test does NOT tell us

Nothing about the v2.1 carrier: not the opto field I/O drive margin, not the SP4T switching
overhead, not the 570 kHz buck ripple interaction, not the pi4j/libgpiod bias question. Those need
the v2.1 board. What it *does* give us is a known-good reference module — which is exactly what you
want on the bench when the carrier board later reads badly and the question is "module or board?".

---

### Sources
- `Hardware/SIM7500 Develop Component A.pdf` — 12-pin map, power, RF and environment figures
- `Hardware/SIMx500 Hardware User Manual 251217 (1).docx` (v1.6, 2025-12-17) — EN/NRST behaviour,
  100 ms init, >2 ms reset / >110 ms recovery, decoupling, VSWR and sensitivity, thermal, ordering
- `docs/Hardware-IntelliRFIDv2.md` — for contrast only
