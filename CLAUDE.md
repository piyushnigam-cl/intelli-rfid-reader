# Intelli RFID Reader — project instructions

Software for the Intelli RFID reader. Read this before changing anything; it captures decisions and
hardware behaviour that are not derivable from the code.

## Hardware

| Part | What it is |
|---|---|
| RFID module | Silion **SIM7500**, built on an Impinj **E710** Gen2 RF chip |
| Host | Raspberry Pi **Compute Module 4**, on board the reader — this runs the apps |
| Architecture | **aarch64** — use `libs/aarch64/libModuleAPIJni.so` |
| Serial port | **Confirmed `/dev/ttyAMA0`** on the CM4 bench rig (2026-08-27). A USB bridge gives `/dev/ttyUSB0` |
| Region | `RG_IN` is the intent (865–867 MHz Indian band) — but **the bench module refuses it**; see below |

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

Java 17, Maven, Spring Boot 3.4.1. Spring Boot was chosen after confirming the CM4 has headroom —
Actuator health and metrics matter on a reader nobody can walk up to.

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
- **Region is a firmware SKU limit, and the bench module is locked to `RG_EU3`.** Setting each
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
- **A read exception leaves the reader `FAULTED` and nothing brings it back.**
  `ReaderSession.handleReadException` sets the state and stops reading; there is no reconnect. After
  the `MODULE_NEED_RESTART` above, every v1 call answered `409 reader_not_connected` until the
  application was restarted — which is the correct answer to give, but a field unit should recover
  on its own. **Open, and not a v1 concern:** the connector thread retries only the *initial*
  connect, not a fault after a successful one.
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

**Tunnel v1 — `timed: true` runs the whole of `durationMs` even when the count was reached.** It
looks like a missed optimisation and it is not: the customer may be holding the carton for a
deterministic period, and a read that finishes early leaves it in the field. Verified on the bench:
count met at 189 ms, response returned at 3082 ms.

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
