# Intelli RFID Reader

Software for the Intelli RFID reader: a Silion **SIM7500** UHF module (Impinj **E710**) on a
Raspberry Pi **Compute Module 4** running the applications.

## Repository layout

Each app is its **own git repository**, remoted to AWS CodeCommit. This directory is a workspace, not
a monorepo — there is no repository at this level.

```
intelli-rfid-reader/
├── API-linux-java-v260721/     vendor SDK (not in git)
├── Hardware/                   datasheets and manuals (not in git)
└── apps/
    ├── intelli-rfid-core/          shared library — repo
    ├── intelli-rfid-reader-test/   bench acceptance — repo
    ├── intelli-rfid-tunnel/        warehouse portal — repo
    └── intelli-rfid-wayside/       trackside railway — repo
```

## The apps

| App | Where it runs | What it does | Port |
|---|---|---|---|
| **[reader-test](apps/intelli-rfid-reader-test/)** | Bench | New reader arrives: is it good? Reads a few tags, writes a few tags, reports pass/fail | 8080 |
| **[tunnel](apps/intelli-rfid-tunnel/)** | Warehouse entry/exit | A box of ~40 tagged articles passes through; a third-party app asks what was in it | 8081 |
| **[wayside](apps/intelli-rfid-wayside/)** | Trackside | A train passes; produce the consist | 8082 |

**[intelli-rfid-core](apps/intelli-rfid-core/)** is the shared library underneath all three: the
vendor SDK wrapper, the tag pipeline, the common REST surface, health checks and durable spooling.

> **On the fourth repository.** You asked for three apps. Core is a fourth repo because all three
> talk to the same module through the same JNI library and need the same reader plumbing —
> duplicating it would mean fixing every reader bug three times, in three repos. If you would rather
> have three, the core sources can be folded into each app; say so and it is a mechanical change.

## First build

The vendor jar is not on Maven Central, so install it once per machine:

```bash
cd apps/intelli-rfid-core
./tools/install-vendor-jar.sh     # finds ../../API-linux-java-v260721
mvn install
```

Then any app:

```bash
cd ../intelli-rfid-tunnel
mvn package
```

## Deploying to a reader

```bash
mvn package
scp -r target/*.jar deploy/ intelli@reader:/tmp/
ssh intelli@reader 'cd /tmp && sudo ./deploy/install.sh'
```

Each app's `deploy/install.sh` creates the service user, installs a systemd unit, and prepares
`/opt/intelli`, `/etc/intelli` and `/var/lib/intelli`.

Two things it cannot do for you:

1. **Copy the native library.** `API-linux-java-v260721/libs/aarch64/libModuleAPIJni.so` must land in
   `/opt/intelli/lib/`. Pass `SDK_LIB=/path/to/libs/aarch64` to the installer to have it done.
2. **Write the site config.** Put site-specific settings in
   `/etc/intelli/<app>/application.yml`; they override the packaged defaults.

### Serial port

The apps default to `/dev/ttyAMA0`. On a CM4 confirm with `dmesg | grep tty`. If the module is behind
a USB bridge it will be `/dev/ttyUSB0` instead.

The service user must be in the `dialout` group or the app will start and then fail to open the port
— which looks exactly like a reader fault. The installer handles this.

## Shared REST surface

Every app exposes these, from core:

```
GET  /api/reader/status              state, counters, module identity
GET  /api/tags/stream                SSE tag stream
POST /api/diagnostics/antennas       VSWR sweep
POST /api/tags/ops/write-epc         write an EPC with read-back verification
GET  /actuator/health                reader state for monitoring
```

Watch a reader with nothing but curl:

```bash
curl -N http://reader:8080/api/tags/stream
```

See [the core README](apps/intelli-rfid-core/README.md) for the full list and for the SDK gotchas
worth knowing before touching the reader code.

## Regulatory region

All three default to `RG_IN` — the 865–867 MHz Indian band. Change `rfid.reader.region` for
deployments elsewhere.
