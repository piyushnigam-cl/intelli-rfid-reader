# Intelli RFID Reader — project instructions

Software for the Intelli RFID reader. Read this before changing anything; it captures decisions and
hardware behaviour that are not derivable from the code.

## Hardware

| Part | What it is |
|---|---|
| RFID module | Silion **SIM7500**, built on an Impinj **E710** Gen2 RF chip |
| Host | Raspberry Pi **Compute Module 4**, on board the reader — this runs the apps |
| Architecture | **aarch64** — use `libs/aarch64/libModuleAPIJni.so` |
| Serial port | **Confirmed `/dev/ttyAMA0`** on the CM4 bench rig (2026-08-27) **and on the production v2.x carrier** (2026-08-29, with `disable-bt` + `uart3`; UART3 takes `ttyAMA3`). A USB bridge gives `/dev/ttyUSB0` |
| Region | `RG_IN` is the intent (865–867 MHz Indian band) — **no module we have accepts it**; run `RG_EU3`, see below |

**On the production v2.x carrier the module is off and held in reset at boot, and neither the app
nor Linux does anything about it.** `RFID_EN` = GPIO22 (HIGH = on) and `RFID_NRST` = GPIO10
(LOW = reset) both come up as inputs with the BCM2711's pull-down. Measured 2026-08-29: with GPIO10
released, `InitReader_Notype` returns **`MT_UNKNOWN_READER_TYPE`** — a wrong answer rather than
silence, which reads like a baud or SDK-version fault and is neither. Raise the antenna select
first, then EN, then NRST: `pinctrl set 8 op dh; pinctrl set 9 op dl; pinctrl set 22 op dh;
pinctrl set 10 op dh`. The bench dev board needs none of this, so it is a production-only failure
mode. See `CM4-PRODUCTION-BRINGUP.md` step 7.

The apps run **on the reader itself**, not on a PC talking to a remote reader.

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
    └── intelli-rfid-wayside/       trackside railway — repo
```

`git init` belongs inside each app directory. **Never create a repo spanning `apps/`** — the root
repo keeps that rule by ignoring `apps/` outright, so a stray `git add -A` at the root cannot
swallow an app. Nesting the app repos would need submodules and is not what this project does.

## The apps

| App | Port | Purpose |
|---|---|---|
| `intelli-rfid-reader-test` | 8080 | A new reader arrives: is it good? Reads a few tags, writes a few tags, reports pass/fail |
| `intelli-rfid-tunnel` | 8081 | Warehouse entry/exit tunnel. A box of ~40 tagged articles passes through; a third-party app asks what was in it. Also commissions warehouse tags |

| `intelli-rfid-wayside` | 8082 | Trackside railway reader. A train passes; produce the consist |

`intelli-rfid-core` is the shared library underneath all three.

**The tunnel app is retail/warehouse. Only the wayside app is rail.** Do not conflate them.

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

## Vendor SDK facts

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
- **Region is a firmware SKU limit, the two modules differ, and neither accepts `RG_IN`.** The
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
  other six.
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

**Tunnel v1 — an undecodable tag never counts.** However many there are. On the bench population 16
of 18 tags carry no GS1 header at all, so a count that included them would close a carton on tags
that are not articles of the requested SKU and report a short carton as complete.

**Tunnel v1 — the carton is released before the callback is sent, never after.** The contract
promises the WMS that "a slow or unavailable WMS endpoint does not stall the conveyor". If the
release ever waits on the callback, the symptom at the customer's site is a stopped line — the most
expensive failure this product has and the least obviously ours. `CartonRelease` exists as a named
seam so the ordering is checkable in one line at the call site rather than being a thing that
quietly does not happen anywhere.

**Tunnel v1 — in Super Fast Mode a sensor opens the read, and settle or the exit edge closes it,
whichever comes first.** A rising edge on J26 IN1 (GPIO23) opens the session. From there **exactly
two things can close a carton**, and the one that happens first names the stop reason:

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

**Corrected 2026-08-31**, from `HANDOFF-LAPTOP-TO-CM4-TUNNEL-05.md` §3.3 — the interface sent to the
PLC vendor. It replaces an earlier rule in which the exit sensor owned the end outright, the count
and settle were both merely observed, and a count that was never met beat everything.

**Tunnel v1 — a Super Fast carton is a fast read followed by a fixed wait, and the wait is the
larger half.** Measured on the production CM4 2026-08-31 across **8 consecutive cartons** (9 tags,
`session: 1`, 27 dBm, `RG_EU3`, settle 1500 ms): every carton found **all 9 tags by 1016–1306 ms**,
then spent the rest of its 2560–2866 ms proving nothing further was coming. `durationMs −
lastNewTagMs` equals the last tag's sighting to the millisecond, so **`settle-ms` is the only lever
on carton time — the reading is already finished.** Settle fires at **1513–1591 ms**, not 1500: the
watchdog runs on a ~100 ms tick and overshoots. `PACKAGE_EXITED` cartons in the same session came in
at ~1.4 s because the IN2 edge cut the wait short, which is exactly what a conveyor's exit sensor is
for.

**Detection on the bench population is total, and the RSSI filter is discarding nothing.** Same
measurement: **72 of 72 tag detections**, every carton `SETTLED` with 9 of 9. RSSI **−41.6 to
−50.9 dBm**, each tag varying only ~1 dB run to run — so every tag sits **20 dB or more above the
−72 dBm `rssi-threshold-dbm` floor**. Tighten toward −55/−50 to make it mean "the tags in front of
the antenna", which is also how to stop commissioning's TID discovery picking arbitrary tags out of
the whole population.

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

## The PLC field interface (connector J26)

The tunnel drives a **Delta DVP12SA211R** over eleven opto-isolated field channels. The interface is
**closed**: `docs/Intelli-RFID-Reader-DVP12SA211R-PLC-Integration.docx` went to the PLC vendor on
2026-08-30 and their ladder is written against it. **Where the code and that document disagree, the
code is wrong**, and no timing in it may be rounded to a nicer number.

- **`com.intelli.rfid.tunnel.plc.FieldChannel` is the authoritative channel map** — OUT1–7 on BCM
  26/20/16/19/21/12/13, IN1–4 on BCM 23/24/18/25. **Do not take channel functions from
  `docs/PLC-INTEGRATION-DVP12SA2.md` §4**: it still carries the superseded map (`RESULT_OK` /
  `RESULT_FAIL` on OUT5/OUT6, `SPARE_IN` on IN3) *and describes itself as authoritative*. It
  disagrees with the `.docx` on five channels. `FieldChannelTest` pins the disagreement so nobody
  "fixes" the enum to match the stale file.
- **`IN1`/`IN2` are ambiguous and it will cost someone a day.** The J26 field channels and the
  SIM7500 module's own GPI pins are both called IN1/IN2 in their own documentation and are different
  silicon. Everything in this project means the J26 channels. **The module's GPI is deliberately
  unused** for the inventory trigger: it can start a read faster than we can but cannot take part in
  the verdict, the heartbeat, the shutdown handshake or the zone state machine.
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
  `tunnel.plc.disable-input-pulls`.
- **The verdict on OUT5 is width-encoded, so scheduler latency is a correctness problem.** One
  pulse per carton: **100 ms = FAIL, 500 ms = PASS**, decoded by the PLC in 60–200 and 400–600 ms
  bands, with *everything else* — any other width, more than one pulse, or nothing at all — read as
  FAIL. A 500 ms pulse that lands at 380 ms is not a slow pass, it is a **fail**, and it fails
  silently at the customer on a carton that was fine. So the width is measured and logged on every
  pulse, `outOfBand` is counted, and the hold sleeps most of the way then **spins the last 2 ms**.
  **Measured on the production CM4 2026-08-31 over 20 cartons: PASS 496–504 ms, FAIL 98–100 ms,
  none outside the band** — but the machine was near idle, and bench test 6 wants 100 cartons under
  read load before that number is trusted. `ResultSignalHardwareTest` is that measurement and is
  skipped unless `-Dplc.hardware=true`.
- **PASS is exactly `complete == true`** — the carton held what was expected. A carton whose count
  could not be judged at all is *not* a pass: the interface has two answers and no third one, and
  **there is no "no verdict"** — reaching the end of a carton undecided emits FAIL explicitly,
  because the PLC reads silence as FAIL anyway and emitting it is the difference between an outcome
  and a guess that happened to match.
- **The verdict is signalled on the thread that closed the session, not on the result executor.**
  Same reason the carton release is: both are physical signals to the conveyor and neither may wait
  on the WMS. `results` is single-threaded and `callbacks.send()` blocks for up to five attempts
  with backoff, so a verdict dispatched behind it would arrive after the PLC's window had closed —
  a dead WMS would have turned every carton into a fail. Building the result is a decode over one
  carton's tags and costs microseconds; only the send is handed off.
- **The carton trigger watches GPIO *rising* edges, but a field-asserted input is GPIO *low*.**
  24 V on an input lights the opto and pulls the pin down, so with the PLC asserting a 2 s
  `ZONE_ARRIVE` pulse the read window opens on the **trailing** edge — two seconds after the carton
  arrived. Confirmed on this board 2026-08-31 by driving line 18: a field-assert produced 0 events,
  the de-assert produced 1. **Unresolved by decision, 2026-08-31**: the optical sensor may be
  configured to match instead, and on the bench a push button gives a rising edge on *release*.
  The software fix, if it is chosen, is `gpiomon -l / --active-low` — on both v1 and v2 — which
  flips edge sense so "rising" means *the channel became active*, matching `FieldIo`. **IN3's burst
  is unaffected in substance** (five asserted pulses still give five trailing edges). Note the
  inconsistency this leaves: `/api/v1/diagnostics/io` reports field sense while the edge monitor
  triggers on raw GPIO, so the screen can show IN1 asserted at a moment the trigger has not fired.
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
- **The shutdown request on IN3 is judged after a quiet period, not on its Nth pulse.** Acting the
  instant the count is reached makes the rule "at least N" rather than **exactly N**, so a six-pulse
  burst — or an EFT storm on a line sharing its return with ten others — would be accepted on its
  way past. The tally is judged after `quiet-ms` of silence, which costs about a second against a
  60 s budget. `tunnel.plc.shutdown.pulses` is configurable for bench work with a push button;
  **at 1 there is no pattern left and any single edge is a shutdown request**, so a non-default is
  warned about at start-up.

  **Debugging the burst needs TRACE, because DEBUG reports only the outcome.** At INFO — the
  packaged default, and the live site config sets no `logging:` block at all — you get the start-up
  `Watching IN3 (BCM 18)…` line, the `pulses != 5` warning, and the WARN when a burst is *accepted*,
  and nothing else. DEBUG on `com.intelli.rfid.tunnel.plc` adds only "burst outran its window" and
  "burst of N is not a shutdown request", both of which fire after the fact. **Neither level records
  an individual edge**, and an edge swallowed by `tunnel.v1.gpio.debounce-ms` is logged by
  `GpioEdgeMonitor` under a different logger again — so a five-pulse pattern that fails to fire
  leaves no way to see how many edges actually arrived. `ShutdownRequestMonitor.onEdge` therefore
  traces every edge with its running tally and its offset into the window; set
  `logging.level.com.intelli.rfid.tunnel.plc: TRACE` for bench test 5.
- **The serial counter needs no flushing at shutdown, by construction.** `SequenceCounter.next()`
  calls `channel.force(true)` before returning each number, so the high-water mark is durable at
  every instant rather than at exit. Step 4 of the shutdown sequence therefore *confirms* — it reads
  the file back independently of the in-memory counter, which is the only check that would catch the
  two having drifted — rather than committing anything.
- **The heartbeat gets its own thread and nothing else ever goes on it.** OUT6 toggles at 1 Hz and
  the PLC stops the conveyor if it sees no transition for 3 s, so anything that can block — a
  callback retrying against a dead WMS, a spool replay, an inventory round — must not be able to sit
  in front of the next toggle. Deadlines are absolute rather than sleeps, because sleeping the
  half-period accumulates every write's latency into permanent drift.
- **The heartbeat stops last, and that ordering is load-bearing.** It is a `SmartLifecycle` at
  `Integer.MIN_VALUE` so Spring stops it after every other bean has flushed. It means only "the
  application is running", never "the module is up". Dropping it earlier tells the PLC it is safe to
  cut power while the serial counter is still being written — the exact corruption the shutdown
  sequence exists to prevent.

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

## Gotchas

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
