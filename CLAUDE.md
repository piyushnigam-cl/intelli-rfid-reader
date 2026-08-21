# Intelli RFID Reader — project instructions

Software for the Intelli RFID reader. Read this before changing anything; it captures decisions and
hardware behaviour that are not derivable from the code.

## Hardware

| Part | What it is |
|---|---|
| RFID module | Silion **SIM7500**, built on an Impinj **E710** Gen2 RF chip |
| Host | Raspberry Pi **Compute Module 4**, on board the reader — this runs the apps |
| Architecture | **aarch64** — use `libs/aarch64/libModuleAPIJni.so` |
| Serial port | Defaults to `/dev/ttyAMA0`. Confirm with `dmesg \| grep tty`. A USB bridge gives `/dev/ttyUSB0` |
| Region | `RG_IN` — the 865–867 MHz Indian band |

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
is a workspace, not a monorepo — there is no repo at this level.

```
intelli-rfid-reader/
├── API-linux-java-v260721/     vendor SDK — NOT in git, copied separately
├── Hardware/                   datasheets — NOT in git
└── apps/
    ├── intelli-rfid-core/          shared library — repo
    ├── intelli-rfid-reader-test/   bench acceptance — repo
    ├── intelli-rfid-tunnel/        warehouse portal — repo
    └── intelli-rfid-wayside/       trackside railway — repo
```

`git init` belongs inside each app directory. Never create a repo spanning `apps/`.

## The apps

| App | Port | Purpose |
|---|---|---|
| `intelli-rfid-reader-test` | 8080 | A new reader arrives: is it good? Reads a few tags, writes a few tags, reports pass/fail |
| `intelli-rfid-tunnel` | 8081 | Warehouse entry/exit tunnel. A box of ~40 tagged articles passes through; a third-party app asks what was in it. Also commissions warehouse tags |
| `intelli-rfid-wayside` | 8082 | Trackside railway reader. A train passes; produce the consist |

`intelli-rfid-core` is the shared library underneath all three.

**The tunnel app is retail/warehouse. Only the wayside app is rail.** Do not conflate them.

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
  what ran before it.
- **Single-tag operations cannot run during continuous inventory.** The `/api/tags/ops` endpoints
  stop and restart inventory around each call.
- **`new Reader()` triggers the JNI library load** via `JniModuleAPI`'s static initialiser. This is
  why `ReaderSession` creates its handle lazily inside `open()` — constructing it eagerly threw
  `UnsatisfiedLinkError` during Spring bean creation and killed the context before any retry logic
  could run, crash-looping a field unit instead of letting it report unhealthy. **Do not move it
  back into a field initialiser.**
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

## Conventions

- Framework-free code goes in `com.intelli.rfid.core`; anything Spring goes in
  `com.intelli.rfid.spring`. Core must stay usable from a plain CLI, so its Spring dependencies are
  `<optional>`.
- Every vendor `READER_ERR` is checked and wrapped in a `ReaderException` carrying the module's own
  detail string. Never discard a return code.
- `ReaderException` maps to HTTP **409**, not 500 — almost every one means "the reader is not in a
  state where it can do that", which is a state conflict, not a server bug.
- Config values that depend on a site (settle windows, RSSI thresholds, antenna geometry) get a
  comment saying how to tune them from real data, not just a default.

## Gotchas

- **Maven incremental compile goes stale.** After editing a core source file, `mvn install` can
  report success while apps still bundle the old class. Use `mvn clean install` on core after
  editing it. Verify with `javap -c -p -cp target/classes <Class>` when behaviour contradicts source.
- Site config lives in `/etc/intelli/<app>/application.yml` and overrides the packaged defaults.
- The service user must be in the `dialout` group or the app starts and then fails to open the
  serial port — which looks exactly like a reader fault.
