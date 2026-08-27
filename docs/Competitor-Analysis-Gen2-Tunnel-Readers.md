# Competitive analysis — UHF Gen2 readers for warehouse RFID tunnels

**Compiled 27 August 2026** by web research for the `intelli-rfid-tunnel` positioning. Every figure
is sourced inline. Vendor performance claims are flagged as such; where a vendor publishes nothing,
this says "not published" rather than estimating. Nothing here has been validated against our own
hardware.

---

## 1. Headline finding

Two of the three assumptions behind our positioning do not survive contact with the market.

1. **Expected-count / completeness reporting is not a differentiator. It is the definition of the
   product category.** Every turnkey tunnel product examined does expected-vs-found reconciliation,
   and a "stop when you have seen N tags" primitive has been in the LLRP standard since 2007 and
   ships in Zebra's SDK today. See §4.
2. **On-reader edge compute is not a differentiator either.** Impinj, Zebra, Kathrein, CAEN,
   ThingMagic, Turck, Nordic ID and Invengo all run Linux and all host customer applications.
   Impinj shipped an R700 refresh in **April 2026** specifically to triple embedded application
   memory. See §6.
3. **Read *rate* is not our constraint and never was.** 40 unique tags in 3–5 s is ~8–13 unique
   tags/s. Every reader here claims 750–1300 tags/s. The binding constraint is RF coverage of a
   sealed carton — which is exactly where a single mono-static port behind an SP4T is genuinely
   weaker than an 8-port reader. See §5 and §7.

What *is* defensible is narrower and more commercial than we assumed. See §9.

---

## 2. The field

**Tier 1 — reader hardware we would be displaced by**

| Vendor | Products | Notes |
|---|---|---|
| Impinj | R700, R720, xSpan, xArray | Also supplies the E710 chip *inside our own module* |
| Zebra | FX9600, FX7500, FXR90, ATR7000 | Widest Indian channel presence of any reader brand |
| Alien Technology | ALR-F800 / -X | Emissary edge workflow controller embedded |
| Kathrein Solutions | ARU 3500 (Gen3/Gen4), RRU | German, industrial, IP68 |
| FEIG Electronic | ID LRU4000, LRU500i, LRU3000/3500 | Industrial/automation channel |
| CAEN RFID | Quattro R4321P, Proton, Ion | Embedded Linux + Java |
| JADAK / Novanta (ThingMagic) | IZAR, Sargas | Now under Novanta "Precision Medicine" branding |
| Nordic ID | AR85, Sampo S2 | NUR-module based, on-reader apps |
| **Chainway** | UR4, URA4 | **E710-based, China pricing, same Indian channel — closest threat to our BOM story** |
| Invengo | XC-RF807 | Dual-CPU Linux, 840–960 MHz global |
| Turck | Q300, Q180 | CODESYS runtime, IP67 |

**Tier 2 — turnkey tunnel *systems*, i.e. who we actually meet on a Reliance tender**

| Vendor | Product | Built on |
|---|---|---|
| Clustag / Rielec (ES) | MOT Station | Impinj R700 — Impinj's own showcase tunnel |
| Checkpoint Systems | RFID Box Tunnel, Midi Tunnel | Proprietary "Wirama Radar" |
| CYBRA (US) | RFID Cage + Edgefinity IoT | 4-port reader + **separate EdgeBox controller + GPIO box** |
| Nedap | iD Cloud Supply Chain | Own + third-party readers |
| Detego | Factory-to-store shipment validation | Software layer |
| Vertical Systems | RAPID RFID Read Tunnel | "works with Zebra or Impinj readers" |
| Lyngsoe Systems | RFID Tunnel Reader | Logistics/postal |
| SATO | MSTRP-5050 | **PJM, not UHF Gen2** — different physics, not a like-for-like comparator |
| **India** | ID Tech Solutions, Bar Code India, Ecartes, RFID4U India | Our direct on-the-ground competition |

Worth noting as additions to the original list: **Clustag/Rielec** (closest analogue to what we are
building), **CYBRA**, **Vertical Systems**, **Lyngsoe**, **Turck**, and above all **Chainway**.

---

## 3. Comparison

### 3a. RF and physical

| Reader | Chip | Ports | Max power | Claimed rate | Sensitivity | IP | PoE | Op. temp |
|---|---|---|---|---|---|---|---|---|
| **Intelli-RFID (ours)** | E710 via SIM7500 | 1 → SP4T → 2 ant | 5–30 dBm | ≥900 tags/s *(Silion)* | not published | n/a | none | CM4 −20…+85 °C |
| Impinj R700 | E710-class | 4 | 10–33 dBm | "up to 1100 reads/s" | **−92 dBm** | IP50 | af/at | −20…+50 °C |
| Zebra FX9600 | not disclosed | 4 or 8 | 0…+33 dBm | **not published** | −86 dBm | IP53 | af/at | −20…+55 °C |
| Zebra FXR90 | not disclosed | 4 or 8 | — | **1300+ tags/s** | −92 dBm | **IP65/67** | af/at | **−40…+65 °C** |
| Alien ALR-F800 | not disclosed | 4 | 31.5 dBm | **not published** | **not published** | IP53 | yes | −20…+50 °C |
| Kathrein ARU 3500 Gen4 | "Impinj Ex10" | 3 + steerable | — | 1100 tags/s | "10× Gen3" *(mktg)* | **IP68** | — | — |
| FEIG ID LRU4000 | not disclosed | 4 (int. MUX) | 100 mW–2 W | not published | not published | IP65/67 | PoE+ | — |
| CAEN Quattro R4321P | ARM9 host | 4 | 31.5 dBm ETSI | not stated | −84 dBm @10 % PER | IP30 | af | — |
| ThingMagic IZAR | not disclosed | 4 | 0…+31.5 dBm | 750 tags/s | not published | — | — | — |
| **Chainway UR4** | **Impinj E710** | 4 SMA | 5–30 (opt. 33) | 900+ tags/s | < −84 dBm | not spec'd | — | — |
| Invengo XC-RF807 | dual CPU | 4 | 11–33 dBm | not stated | not published | IP54 | at | — |
| Turck Q300 | not disclosed | int. + 4 ext | 2 W ERP | not published | not published | **IP67** | PoE+ M12 | — |

### 3b. Compute, API, I/O

| Reader | On-reader compute | App hosting | API | Digital I/O | India 865–867 |
|---|---|---|---|---|---|
| **Intelli-RFID (ours)** | **CM4, Java 17 / Spring Boot** | Full Debian, 2–8 GB RAM | REST/JSON | **7 out + 4 in, 24 V opto** | Native design target |
| Impinj R700 | Dual-core A53, **Linux 6.6**; Apr 2026 refresh = 2× CPU, **3× app memory** | R700 Embedded Toolkit, C/C++ | REST (OpenAPI), MQTT, Kafka, webhooks, LLRP | 3 out / 2 in | ETSI + Global SKUs; **India not confirmed** |
| Impinj R720 | Qualcomm QCS404 quad-core | 256 MB app memory | as R700 | not published | as above |
| Zebra FX9600 | TI AM3505, 512 MB flash | .NET/C/Java EMDK + **IoT Connector user apps in Python and Node.js** | IoT Connector (MQTT/REST/HTTP POST/WebSocket/TCP) + LLRP | **4 in / 4 out** | 865–868 listed |
| Zebra FXR90 | NXP iMX8 Mini quad A53, **2 GB / 16 GB** | IoT Connector | same | 4 in / 4 out | **India not listed** |
| Alien ALR-F800 | embedded | **Emissary** visual workflow builder; drives 4 more readers | Java, .NET, Ruby | **4 in / 8 out** | 860–960 regional |
| Kathrein ARU 3500 Gen4 | Linux, no external controller | C++, C#, .NET; app store incl. **TagBlower** | web UI + apps | not published | not published |
| CAEN Quattro | **Embedded Linux + Java** | yes | easy2read | 2 in / 2 out | **865.6–867.6** |
| ThingMagic IZAR | Linux onboard | yes | Mercury API, LLRP | **12 GPIO** | not stated |
| Turck Q300 | **CODESYS + Linux + OPC-UA** | yes | CODESYS / OPC-UA | 4 configurable (2 A) | FCC/ETSI variants |
| Nordic ID AR8x | Linux, on-device MQTT broker | zip app packages | MQTT + WebSocket | — | — |
| Chainway UR4 | **not documented** | not documented | Win/Linux/Android SDK | 2 in, 1 relay, 1 opto out | 865–868 listed |

> **Our I/O count is the best in the field.** 7 outputs + 4 inputs at 24 V beats every reader here —
> Alien's 4/8 is nearest, everyone else is 2–4 each way, and the R700 gives only 3 out / 2 in. For a
> conveyor-coupled tunnel with diverters, stack lights and photo-eyes that removes a separate I/O box
> from the BOM. CYBRA ships a separate GPIO box in its tunnel kit for exactly this reason.

---

## 4. The "did I read everything?" question — the uncomfortable part

### 4a. The primitive has been standard since 2007

LLRP defines an `AISpecStopTrigger` whose types include **`Tag_Observation`**, parameterised by a
`TagObservationTrigger` — and among that trigger's enumerated types is literally
`Upon_Seeing_No_More_New_Tag_Observations_For_T_ms_Or_Timeout`. **Settle detection, standardised, in
the base protocol.**

Zebra ships it today. Their RFID SDK exposes:

- `STOP_TRIGGER_TYPE_TAG_OBSERVATION_WITH_TIMEOUT` — "stop inventory after reading 'n' tags", with timeout
- `STOP_TRIGGER_TYPE_N_ATTEMPTS_WITH_TIMEOUT`
- plus `DURATION` and `GPI_WITH_TIMEOUT`

So "read until you have found the expected number of tags, or until the timer expires" is an
off-the-shelf configuration parameter on a Zebra reader.

### 4b. What reader APIs genuinely do not do

They do not reconcile against a *business-level* expected set. Impinj's IoT Device Interface exposes
tag events, system events and GPI/GPO over REST/MQTT/Kafka/webhooks with a 300,000-event buffer —
and has **no** completeness, expected-count or settle concept in its API surface. The one thing that
sounds close is a red herring: R700 firmware v8.2 added "an Impinj tag population estimation
algorithm that improves read rate by up to 5%" — an internal Gen2 Q-algorithm optimisation, not an
exposed metric. Kathrein's **TagBlower** app (asynchronous entry/exit messaging) is the closest any
reader vendor comes to shipping zone-occupancy semantics as a product.

Nobody exposes *"here is the SGTIN list you expected, here is what I found, here are the 3 missing."*

### 4c. At the system level, everyone does it — because it is the product

- **Clustag/Rielec MOT Station**: validates "item contents against shipment orders"; variations reroute the carton
- **Nedap iD Cloud**: "checks RFID reads against packing lists before orders leave the DC"
- **Vertical Systems RAPID**: barcode imager queries the ERP for expected contents, compares against the tunnel read
- **CYBRA RFID Cage**: "Edgefinity IoT validation algorithms" for carton verification
- **Detego**: factory-to-store outbound carton shipment validation
- A 2018 patent application (US20180157873) on carton certification describes exactly this, and explicitly puts the logic in a "processing unit", not the reader

**Verdict: completeness reporting is table stakes.** A Reliance evaluator who has seen one other
tunnel demo will not experience "expected vs found" as novel. Reframe — see §9.

---

## 5. Read-rate reality

**Claims** cluster at 750–1300 tags/s (R700 1100, FXR90 1300+, Kathrein 1100, IZAR 750, Chainway
900+, Silion SIM7500 ≥900). **These are peak singulation rates, not unique-tag inventory rates.**

Two counterweights:

1. **The RAIN Alliance's own System Design Guidelines v2** uses, as its worked example for session-S0
   selection, "approximately **20 tags** in read zone, **100 tags per second** throughput" — an order
   of magnitude below the datasheet peaks. That document contains essentially no achievable-throughput
   benchmarks at all, which is itself telling.
2. **Our band is the slow one.** The EU lower band (865–868 MHz) has **4 transmit channels** at
   600 kHz spacing versus **50 channels** for FCC 902–928. Every headline tags/s figure is quoted
   under FCC conditions, and India's 865–867 is narrower still than ETSI's 865.6–867.6. This is a
   structural handicap that applies equally to us and to Impinj/Zebra — but it means nobody should be
   quoting 1100 tags/s in an Indian tender, and if a competitor does, that is our opening.

**Accuracy data, best available:**

| Source | Claim | Independence |
|---|---|---|
| Auburn RFID Lab / GS1 US | "item-level quantity audits in over **99.99%** of all cartons" | **Genuinely independent**, and retail-apparel — our use case |
| Checkpoint | 99.89% avg (Box Tunnel); up to 99.90% (Midi, 50 m/min, 50–100 tags/box) | Vendor-measured |
| Clustag | "up to 100% accuracy", 1400 boxes/hr ≈ **2.6 s/carton**, up to 400 tags/box, integrated RF shield | Marketing — "up to 100%" is not a measurement |
| CYBRA | ">99%" and "99.99%" on the same page | Marketing, and self-inconsistent |
| ID Tech Solutions (India) | "close to 99%+ **in controlled environments**" | The hedge is doing real work |

**Marketing-copy flags:** Indian reseller encstore states the R700 reads "1300+ tags/s" — Impinj's
own datasheet says 1100. Zebra publishes **no** read rate for the FX9600 at all. Alien publishes
neither rate nor sensitivity for the ALR-F800.

**Implication:** 40 tags in 3–5 s is ~8–13 unique tags/s — every reader here is 50–100× that on
paper. Our risk is not singulation throughput; it is the last one or two tags shadowed by a
metal-content SKU or stacked tag-on-tag. That reframes the engineering *and* the sales story around
**antenna diversity and dwell**, not speed.

---

## 6. Edge compute — the weakest of the three claimed differentiators

Almost every competitor hosts customer applications on the reader: Impinj (R700 Embedded Toolkit,
C/C++), Zebra (**Python and Node.js** user apps via IoT Connector), Alien (Emissary, no-code
workflows), Kathrein (C++/C#/.NET), CAEN (**Linux + Java**), ThingMagic (Linux onboard), Turck
(**CODESYS**), Nordic ID (Linux app packages). Only Chainway does not document it.

The April 2026 R700 refresh was built for exactly our use case — Impinj name "high-speed package
sortation on conveyors". They are moving onto our ground, not away from it.

**Where the CM4 still genuinely wins is the *quality* of the runtime, not its existence.** A full
Debian userland with GBs of RAM running Java 17 / Spring Boot is a materially different proposition
from 256 MB of C/C++ heap on an R720 or a Python sandbox on an FX9600. If the application needs an
embedded database, a local web UI, ERP connectors, or days of offline buffering, the CM4 is the only
option in this list that comfortably hosts it. Say *that* — "we run a real Spring Boot application
server, not an SDK callback" — not "we have edge compute".

---

## 7. Where CM4 + module is genuinely weaker

Ordered by how much damage each does in a technical evaluation.

1. **Antenna diversity — the most serious gap, by a distance.** One mono-static port through an SP4T
   to two antennas, against 4 ports standard and 8 on FX9600/FXR90. For a sealed 40-tag carton,
   spatial and polarisation diversity is the single biggest determinant of finding the last tag — far
   more than power or sensitivity. Two honest nuances in our favour: commercial 4-/8-port readers are
   *also* mono-static and *also* time-share their ports, so the gap is coverage rather than
   simultaneity; and nobody in this table offers bi-static, so that is not a stick anyone can beat us
   with. But 2 antennas against 8 is. **If we do one engineering thing before Reliance, make it four
   antennas.**
2. **SP4T insertion loss** — roughly 0.5–1.5 dB each way, so ~1–3 dB round trip off the link budget
   versus a native port, compounding with an already-lower module sensitivity. **We have not measured
   ours. Know the number before a competitor asks.**
3. **Regulatory ownership.** India's 865–867 MHz is de-licensed under GSR 564(E) at up to 4 W ERP,
   but **WPC/ETA approval is still mandatory** — RF test reports from a NABL-accredited lab, ~₹17,500
   all-in, 30–35 days. Impinj and Zebra amortise that across global volume and hand the customer a
   certified SKU. We own the test campaign, and a carrier respin means re-testing.
4. **Support, RMA, procurement risk.** A single small vendor's custom hardware is a line item on a
   risk register at Reliance scale. Closed with contract terms — spares pool, on-site SLA, escrow —
   not engineering.
5. **IP rating and PoE.** Competitors run IP50 to IP68; all take PoE/PoE+. The CM4 has no native PoE
   PD and a SIM7500 at 30 dBm would likely exceed 802.3af's 12.95 W. **Both are softer than they look
   for an enclosed indoor tunnel with 24 V at every conveyor station — concede the spec, contest the
   relevance.**
6. **Thermal.** CM4 silicon is fine and the "hobbyist part, EOL risk" attack is answerable with a
   citation: −20…+85 °C standard, −40…+85 °C extended since March 2025, production committed to at
   least January 2034. The real risk is the SIM7500 at 30 dBm at high duty inside a sealed tunnel
   head, where commercial readers publish characterised derating and we do not.
7. **MTBF.** No published MTBF found for the R700, FX9600, ALR-F800 or any other reader here — so
   this is a weaker attack on us than it first appears. The real asymmetry is field hours, not a
   datasheet number.
8. **Phase/RSSI locationing.** xArray/xSpan and ATR7000 do it. A tunnel does not need it. Low impact.
9. **Gen2X — the one to actually worry about.** The April 2026 R700 refresh added **Gen2X Tag Read
   Range** and **Gen2X Tag Selection** ("the reader specifies which tags should respond during an
   inventory sweep, reducing unwanted reads in dense environments"), with partners reporting up to 40%
   improvement in reading ability (vendor-reported). Gen2X needs Impinj M800-class tags **and**
   Impinj-licensed reader firmware. **Whether the SIM7500 enables Gen2X is unknown.** If Reliance's
   tags are M800-based and an R700 can select and range-extend where we cannot, it will out-read us on
   exactly the dense-dark-carton case that decides the deal. **Highest-value open question here.**

---

## 8. Pricing (approximate)

**US street** (atlasRFIDstore, Aug 2026): Zebra FX7500 4-port $1,103 · ThingMagic Sargas 2-port
$1,084 · Zebra FX9600 4-port $1,274 · **Impinj R700 $1,499** · ThingMagic IZAR 4-port $1,689 · Zebra
FXR90 4-port $1,781 · FX9600 8-port $2,080 · Speedway R420 $2,195 · FXR90 8-port $2,296 · ATR7000
$3,816.

**India** (RFID4U India): Zebra FX9600 4-port ₹78,943 · FX7500 2-port ₹80,595 · FX7500 4-port
₹87,396 · FX9600 8-port ₹1,18,681 · **Impinj R700 ₹1,24,875**.

Indian B2B marketplace listings for the FX9600 range ₹57,000–₹90,000 — unverified sellers, possibly
grey; treat as noise, not a price floor.

**No turnkey tunnel vendor publishes pricing.** Clustag, Checkpoint, CYBRA, Vertical Systems, Nedap
and Detego are all quote-only, so there is **no verified data on complete-system pricing** — which is
the number we actually compete on. **The structural point: the reader is a minority of a tunnel's
cost.** Shielded enclosure, antennas, conveyor integration and commissioning dominate. A
reader-price argument will not win this on its own.

---

## 9. Bottom line

We do not credibly win on "expected vs found" or on "edge compute", because both are ordinary:
expected-count reconciliation is what every tunnel product on the market does by definition, a
count-based stop trigger has been in LLRP since 2007 and ships in Zebra's SDK today, and nine of
eleven reader vendors already host customer applications on the reader.

Where we do win is on three things that are checkable and hard to copy:

- **Integration density.** 7 opto-isolated 24 V outputs plus 4 inputs in the reader itself — more I/O
  than any commercial reader here — removes CYBRA-style separate GPIO and edge-controller boxes from
  the system BOM. One certified box replaces reader + PLC I/O module + edge PC, with the WPC/ETA and
  support burden owned locally rather than through a foreign OEM's channel.
- **Application depth on-device.** A genuine JVM application server with GBs of RAM, not a 256 MB
  C/C++ toolkit or a Python sandbox.
- **Local engineering responsiveness**, as the commercial third.

We do **not** win on antenna diversity, and that is the one gap that will actually cost us
completeness on a sealed 40-tag carton. Two antennas behind an SP4T against four to eight ports is
the weakness a competent evaluator will find. **Fix it in hardware before fixing anything in the
pitch.**

**Two things to nail down before any of this is customer-facing:**

1. Get Silion's written answer on **Gen2X**. If Reliance's tags are M800-class and an R700 can select
   and range-extend where we cannot, that beats every other argument here.
2. **Reconcile our own spec sheet.** Silion publishes ≥900 tags/s, not >1000, and publishes no
   sensitivity figure at all — while −87 dBm is the Impinj **E510** number, not the **E710's**
   −93 dBm. Whichever way that discrepancy resolves, a competitor will check it.

---

## 10. Not verified — stated plainly

- Impinj's India (865–867 MHz) SKU support — support portal renders as a JS shell; datasheet lists only ETSI and Global part numbers
- The full LLRP `TagObservationTrigger` enumeration verbatim — GS1 returns HTTP 403 to automated fetch
- Zebra FX9600 maximum read rate — not published by Zebra
- Alien ALR-F800 read rate and sensitivity — not published by Alien
- Kathrein ARU 3500 Gen4 GPIO count, PoE, API protocols and India band — datasheet gated
- Nordic ID AR85 / Sampo S2 RF specifications
- **Whether the SIM7500 supports Gen2X, and whether it exposes tag phase**
- SIM7500 unit pricing, and therefore any BOM-vs-reader cost delta
- Turnkey tunnel system pricing from any vendor — universally quote-only
- Usable channel count in India's 865–867 MHz
- MTBF for any reader in this analysis, including the commercial ones

---

### Key sources

Impinj [R700 datasheet](https://www.cisper.com/datasheets/impinj/Impinj_R700_RAIN_RFID_Reader_Datasheet.pdf) ·
[IoT Device Interface](https://www.impinj.com/products/technology/key-features/iot-device-interface) ·
[R720](https://www.impinj.com/library/blog/new-impinj-r720-reader-delivers-enterprise-grade-e) ·
[R700 Apr-2026 refresh](https://siliconangle.com/2026/04/16/impinj-boosts-edge-computing-power-updated-r700-rain-rfid-reader/) ·
[Clustag MOT](https://www.impinj.com/library/partner-solutions/rielec-clus-mot-station-for-shipment-verification) ·
Zebra [FX9600](https://www.zebra.com/us/en/products/spec-sheets/rfid/rfid-readers/fx9600.html) ·
[FXR90](https://www.zebra.com/content/dam/zebra_dam/en/spec-sheets/fxr90-spec-sheet-en-us.pdf) ·
[IoT Connector](https://zebradevs.github.io/rfid-ziotc-docs/introduction/intro/index.html) ·
[SDK trigger settings](https://techdocs.zebra.com/dcs/rfid/android/2-0-2-94/tutorials/triggersettings/) ·
[Kathrein ARU 3500 Gen4](https://www.kathrein-solutions.com/en/product/aru-3500-antenna-reader-gen4/) ·
[CAEN Quattro](https://www.caenrfid.com/en/products/quattro-r4321p/) ·
[ThingMagic IZAR](https://novanta.com/precision-medicine/product/thingmagic-izar-rfid-reader/) ·
[Chainway UR4](https://www.cisper.com/datasheets/Chainway/Chainway_UR4_datasheet.pdf) ·
[Turck Q300](https://www.turck.us/attachment/B3123.pdf) ·
[Silion SIM7500](https://en.silion.com.cn/Portal/article/index/cid/36/id/275.html) ·
[Checkpoint tunnels](https://checkpointsystems.com/rfid-solutions/rfid-tunnels/) ·
[CYBRA RFID Cage](https://cybra.com/hardware/rfid-tunnel/) ·
[Vertical Systems RAPID](https://vertsys.com/rapid-rfid-read-tunnel/) ·
[Nedap iD Cloud](https://www.nedap.com/en/retail/inventory-engine/id-cloud/supply-chain) ·
[RAIN System Design Guidelines v2](https://therainalliance.org/wp-content/uploads/2024/04/RAIN-RFID_System_Design_Guidelines-V2-UPDATED-2.pdf) ·
[GS1 UHF regulations](https://www.gs1.org/docs/epc/uhf_regulations.pdf) ·
[LLRP AISpecStopTrigger](http://llrp.org/docs/javaapidoc/org/llrp/ltk/generated/parameters/AISpecStopTrigger.html) ·
[Auburn RFID Lab](https://rfid.auburn.edu/papers/pages/RFIDItem-levelQuantityAuditingforApparelSupplierDistributionCenters.php) ·
[WPC/ETA for RFID readers](https://www.professionalutilities.com/wpc-certificate/rfid-reader.php) ·
[CM4 extended temperature](https://www.raspberrypi.com/news/new-extended-temperature-range-for-compute-module-4/) ·
[atlasRFIDstore pricing](https://www.atlasrfidstore.com/fixed-rfid-readers/) ·
[RFID4U India pricing](https://rfid4ustore.in/rfid-readers/fixed-rfid-readers/)
