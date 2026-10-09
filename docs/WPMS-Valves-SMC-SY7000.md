# WPMS pneumatic valves: SMC SY7100-5U1 and SY7300-5U1

The wayside reader drives the WPMS valves from J26 OUT1–OUT7, through the interposer
(`Wayside-Reader-Design.md` §2.0). This note covers what the valves are, what they need electrically,
and what that means for the interposer and the app. Written 2026-10-09 from a cloud session.

**Sources and their limits.** SMC's catalogue PDFs could not be downloaded from the session (the
egress proxy refuses smcworld.com, smc.eu and the distributor hosts). The figures below come from
SMC's web-catalogue entries and distributor listings found by search, plus the SY7000 analysis
already in `intelli-pcb-interposer/TechDocs/23-Aug-26/README.md` §3.5. That analysis was made
against SMC's own catalogue (`SY.New.pdf`, electrical data on pp. 18 and 319, and the
`SY7100-5U1.pdf` drawing), which sits in the WPMS board's `ExternalSystems/Components/` folder and
is not in any repo synced here. **Confirm every value marked ⚠ against that catalogue or the valve
label before relying on it.**

## What is fitted (operator, 2026-10-09)

| Qty | Part | Use | J26 |
|---|---|---|---|
| 6 | **SY7100-5U1** | Air blow, one per WPMS module | OUT2–OUT7 |
| 1 | **SY7300-5U1** | WPMS flaps open/close | OUT1 (see the double-solenoid problem below) |

## Decoding the part numbers

| Field | SY7100-5U1 | SY7300-5U1 | Meaning |
|---|---|---|---|
| `SY7` | SY7000 | SY7000 | Series: 5-port pilot solenoid valve, the largest body of SY3000/5000/7000 |
| 2nd digit | **1** | **3** | Actuation: 1 = **2-position single solenoid** (spring return); 3 = **3-position closed centre** (two solenoids) |
| 3rd digit | 0 | 0 | 0 = **plug-in type**, rubber seal: the valve has no lead wires and connects through its sub-plate or manifold |
| `5` | 24 VDC | 24 VDC | Rated coil voltage |
| `U` | ✓ | ✓ | **Light/surge voltage suppressor, non-polar** |
| `1` | ? | ? | ⚠ Not decoded by any source found; check the catalogue's how-to-order table |

Other listed properties of both: internal pilot, pilot valve rated 0.7 MPa. Manual override is
listed as **push-turn locking** on SMC's own page and as non-locking push by some distributors ⚠.

## Electrical: fits the interposer comfortably

| Quantity | SY7000 value | Against the interposer (≤ 80 mA per output) |
|---|---|---|
| Coil power, standard | 0.35 W (SMC web catalogue) | **14.6 mA** at 24 V, 18 % of the limit |
| Coil power, power-saving circuit | 0.1 W holding (SMC web catalogue) | 4.17 mA holding, **16.7 mA inrush** |
| Suppressor | Built in, non-polar (`U`) | Meets the interposer's "suppressed coils only" rule (§3.5) |
| Voltage tolerance (power-saving type) | −7 % / +10 % at 24 VDC | 22.3–26.4 V at the coil |

⚠ Which circuit the `-5U1` coils have is not confirmed. The interposer analysis assessed both, and
both pass. Six air valves plus the flap valve draw about **0.1 A in total at 24 V**, negligible for
the field supply.

Things that still apply, from the interposer analysis (§3.4–3.5):
- **OUT must be positive with respect to FIELD_COM.** "Non-polar" describes the valve's suppressor,
  not our output: the interposer's unidirectional TVS still sets the polarity.
- **Minimum energise time.** The photorelay switches in ≤ 10 ms each way, so the shortest useful
  pulse is ~50 ms. If the coils have SMC's power-saving circuit, it needs **more than 67 ms** of
  energising to latch the valve. **Use ≥ 100 ms for any pulse** and the question goes away.
- **Response.** One listing gives ≤ 32 ms for the SY7100 at 0.5 MPa without the light/suppressor ⚠.
  Add up to 10 ms for the photorelay. Air and flaps take longer than the electrics, so measure the
  real open time on site rather than designing to these figures.

## 🔴 The SY7300 needs two outputs, and J26 has given it one

A **3-position closed-centre** valve has **two solenoids**, A and B:

| Coil A | Coil B | Valve position | Flaps (assuming A = open) |
|---|---|---|---|
| on | off | Position A | Driven open |
| off | on | Position B | Driven closed |
| off | off | **Centre, all ports blocked** | **Stay wherever they are** |
| on | on | Not allowed | — |

So with only OUT1 wired to one coil:
- OUT1 on opens the flaps. **OUT1 off does not close them**: the valve returns to centre, the
  cylinder is locked in place, and the flaps stay open. Nothing can drive them closed.
- **On power loss, a dead JVM or an IN3 shutdown, the flaps freeze where they are**, open if a train
  was passing. With every J26 output de-energised as the safe state, this valve's safe state is
  "hold", not "closed".

Options, for the operator to choose:
1. **Swap the flap valve for an SY7100-5U1** (2-position single, spring return), plumbed so that
   de-energised = flaps closed. One output, and power loss closes the flaps. This matches the other
   six valves and keeps every output's safe state at "off = closed / no air". **Recommended**, if
   "closed on power loss" is what the WPMS wants.
2. **Keep the SY7300 and give coil B an output.** J26 is full (OUT1–OUT7 used), so one air channel
   would have to give way, or two air valves would share a channel. The app then needs a dead time
   of **≥ 20 ms with both coils off** between A and B. The photorelays are bounded only above at
   10 ms, so switching both at once can energise A and B together. There is no hardware interlock.
3. **Keep the SY7300 on OUT1 only, deliberately**, if the WPMS vendor wants hold-on-failure and
   closes the flaps some other way. Then the reader can open the flaps but never close them, which
   needs saying in the operator instructions.

Also worth asking the WPMS vendor: is "closed centre, hold position on failure" their intended
behaviour, so the flaps do not slam shut on a train's measurement?

## Pneumatic notes ⚠

- Pressure: the pilot valve is rated to 0.7 MPa. Related SY7000 3-position listings give
  −100 kPa to 0.7 MPa. The minimum operating pressure differs between single and 3-position valves
  in SMC's tables, so check it for the site supply.
- Ambient and fluid temperature: −10 to 50 °C, no freezing (from an SY7000 3-position listing). A
  trackside enclosure in Mumbai sun can exceed 50 °C; check where the valves are mounted.
- Flow: a sibling, SY7100-5UF1, is listed at 1593 l/min. Not confirmed for `-5U1`.

## Sources

- [SMC web catalogue: SY7100-5U1](https://www.smcworld.com/webcatalog/s3s/en-jp/detail/?partNumber=SY7100-5U1)
- [SMC web catalogue: SY3000/5000/7000 plug-in type](https://www.smcworld.com/webcatalog/en-jp/seriesList/?id=SY-E) (0.35 W standard / 0.1 W power-saving)
- [SMC instruction manual, new SY3000/5000/7000](https://www.smcworld.com/upfiles/etc/international/imm/SY7000V-SMU07EN_NewSY3000_5000_7000_.pdf) (power-saving circuit: > 67 ms energising, −7 %/+10 %)
- [automationdistribution.com: SY7100-5U1, plug-in base-mounted](https://automationdistribution.com/smc-sy7100-5u1-4-5-port-solenoid-valve-pack-of-1/)
- [Proax: SY7100-5U1](https://proax.ca/en/product/272102/smcsy71005u1) and [SY7300-5U1](https://proax.ca/en/product/273014/smcsy73005u1)
- [Rubix: SY7100-5U1-NA](https://uk.rubix.com/en/solenoid-valve/p-G2010142339) (response time ≤ 32 ms)
- [Rubix: SY7100-5UF1](https://uk.rubix.com/en/solenoid-valve/p-G2010111927) (flow)
- [RS: SY7000 3-position closed centre](https://uk.rs-online.com/web/p/pneumatic-solenoid-valves/0362779) (pressure and temperature)
- `intelli-pcb-interposer/TechDocs/23-Aug-26/README.md` §3.4–3.5 and `INTERPOSER-DESIGN.md` §2
