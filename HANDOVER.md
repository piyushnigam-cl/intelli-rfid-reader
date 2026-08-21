# Handover — Windows laptop → CM4

Everything needed to pick this project up on the reader and carry on with Claude Code there.

Written 2026-08-21. Source machine: `piyush-laptop`, `C:\Claude\intelli-rfid-reader`.

**This is not a one-way handover.** The two machines have standing roles — see
[Working model](#0-working-model) below — so expect to move code across in both directions as the
project continues.

---

## 0. Working model

The project is built across two machines, each doing what only it can do.

| | Cowork on the Windows laptop | Claude Code on the CM4 |
|---|---|---|
| Reader attached | No | **Yes** |
| Does | System design, architecture, first drafts | Implementation, real-hardware runs, testing |
| Can verify | Compilation, unit tests, API shapes | Everything, including the module itself |

The split matters because **nothing produced on the laptop has touched a reader**. Draft code
compiles and its unit tests pass, but every claim it makes about module behaviour is inference from
the vendor documentation. The CM4 is where those claims become facts — or get corrected.

So the loop is:

1. **Design and draft here.** Architecture, interfaces, first implementations, unit tests.
2. **Move it across** — push to CodeCommit, pull on the CM4.
3. **Implement and test there** against the real module.
4. **Write the corrections back into `CLAUDE.md`** so the next design session starts from what the
   hardware actually does, not from what the docs implied.

Step 4 is the one that is easy to skip and the one that compounds. `CLAUDE.md` is the only channel
by which hardware truth reaches future design sessions — project memory does not cross machines.

Things especially worth recording after a CM4 session:

- Vendor API signatures or behaviour that differ from what the docs said
- The actual serial port and any permission or `raspi-config` steps that were needed
- Tuned values: `tunnel.settle-ms`, `rssi-threshold-dbm`, `wayside.antenna-order`, antenna spacing
- Read rates and RSSI ranges actually observed — these turn guessed thresholds into measured ones
- Anything that surprised you

### Moving code back the other way

When the CM4 is ahead, that is the source of truth. Push from there and pull on the laptop:

```bash
# on the CM4
cd ~/intelli-rfid-reader/apps/<app>
git add -A && git commit -m "..." && git push

# on the laptop
cd C:\Claude\intelli-rfid-reader\apps\<app>
git pull
```

Keeping both sides on CodeCommit is what makes this cheap. It is the main reason to do the push in
section 2 rather than copying the folder once and diverging.

## 1. What exists right now

Four git repositories under `apps/`, each with **one commit on `main`** and a CodeCommit remote in
`ap-south-1`. **Nothing has been pushed yet**, and the CodeCommit repositories may not exist
server-side.

| Repo | Files | Remote |
|---|---|---|
| `intelli-rfid-core` | 35 | `https://git-codecommit.ap-south-1.amazonaws.com/v1/repos/intelli-rfid-core` |
| `intelli-rfid-reader-test` | 14 | `…/intelli-rfid-reader-test` |
| `intelli-rfid-tunnel` | 15 | `…/intelli-rfid-tunnel` |
| `intelli-rfid-wayside` | 18 | `…/intelli-rfid-wayside` |

Commits are authored as `Piyush Nigam <this.is.piyush@gmail.com>`.

**Verified working:** all four modules build; **50 tests pass** (core 10, reader-test 5, tunnel 13,
wayside 22). All three apps boot as executable jars *without* the native library present, report
`OUT_OF_SERVICE` on `/actuator/health`, and degrade with a clear error naming the missing `.so`.

### Not in git

Two directories sit outside the repos and **must be copied separately**:

- `API-linux-java-v260721/` — the vendor SDK. Required to build (the jar) and to run (the `.so`).
- `Hardware/` — datasheets and manuals. Reference only.

### Cleanup before you copy

`_to_delete\` holds the transfer tarball and some stale git lock files. The desktop bridge could not
delete them. Delete that folder on Windows:

```powershell
Remove-Item -Recurse -Force C:\Claude\intelli-rfid-reader\_to_delete
```

---

## 2. Getting it onto the CM4

### Option A — via CodeCommit (recommended)

Cleanest: the repos end up properly remoted on both machines.

**On Windows**, create the repositories and push:

```powershell
cd C:\Claude\intelli-rfid-reader
bash setup-codecommit.sh --create      # needs AWS CLI configured for ap-south-1

# then, per app
cd apps\intelli-rfid-core          ; git push -u origin main
cd ..\intelli-rfid-reader-test     ; git push -u origin main
cd ..\intelli-rfid-tunnel          ; git push -u origin main
cd ..\intelli-rfid-wayside         ; git push -u origin main
```

If push asks for credentials, set the helper once:

```
git config --global credential.helper "!aws codecommit credential-helper $@"
git config --global credential.UseHttpPath true
```

**On the CM4:**

```bash
mkdir -p ~/intelli-rfid-reader/apps && cd ~/intelli-rfid-reader/apps
for a in intelli-rfid-core intelli-rfid-reader-test intelli-rfid-tunnel intelli-rfid-wayside; do
  git clone https://git-codecommit.ap-south-1.amazonaws.com/v1/repos/$a
done
```

Then copy the SDK across separately (it is not in git):

```bash
# from the Windows machine
scp -r C:\Claude\intelli-rfid-reader\API-linux-java-v260721 pi@<cm4>:~/intelli-rfid-reader/
```

### Option B — copy the whole folder

Simpler, no AWS needed. Copy `C:\Claude\intelli-rfid-reader\` wholesale to the CM4 by scp, rsync or
USB. The `.git` directories come with it, so history and remotes are preserved.

Delete `_to_delete\` first, and skip any `apps/*/target/` directories — they are build output.

```bash
# on the CM4, afterwards
cd ~/intelli-rfid-reader
find apps -name target -type d -prune -exec rm -rf {} +
```

One caveat: git may report every file as modified because of CRLF line endings. Fix with:

```bash
git config --global core.autocrlf input
```

---

## 3. Setting up the CM4

```bash
sudo apt update
sudo apt install -y openjdk-17-jdk maven git

java -version     # expect 17
mvn -v
```

Raspberry Pi OS ships Java 17 in bookworm. If you get Java 11, install 17 explicitly and select it
with `sudo update-alternatives --config java`.

### Serial port

```bash
dmesg | grep tty          # find the module's port
sudo usermod -aG dialout $USER
# log out and back in for the group to take effect
```

On a CM4 the primary UART is `/dev/ttyAMA0`. You may need to free it from the console:

```bash
sudo raspi-config    # Interface Options → Serial Port → login shell NO, hardware YES
```

### Build

```bash
cd ~/intelli-rfid-reader/apps/intelli-rfid-core
./tools/install-vendor-jar.sh
mvn install

cd ../intelli-rfid-reader-test && mvn package
```

`install-vendor-jar.sh` looks for the SDK at `../../API-linux-java-v260721`. Override with
`JAR=/path/to/ModuleAPI_J-v260721.jar` if it lives elsewhere.

### First run against real hardware

```bash
cd ~/intelli-rfid-reader/apps/intelli-rfid-reader-test
java -jar target/intelli-rfid-reader-test-1.0.0-SNAPSHOT.jar \
  --rfid.reader.native-lib-path=$HOME/intelli-rfid-reader/API-linux-java-v260721/libs/aarch64 \
  --rfid.reader.address=/dev/ttyAMA0
```

Then open `http://<cm4>:8080/` and run an acceptance check. This is the fastest way to confirm the
whole chain — serial port, permissions, native library, module — is working.

---

## 4. Continuing with Claude Code on the CM4

```bash
# Node 18+ required
curl -fsSL https://deb.nodesource.com/setup_20.x | sudo -E bash -
sudo apt install -y nodejs
npm install -g @anthropic-ai/claude-code

cd ~/intelli-rfid-reader
claude
```

`CLAUDE.md` in the project root is loaded automatically at the start of every session. It carries
the architecture, the vendor SDK gotchas, and the domain rules that are easy to get wrong — that is
the mechanism by which context survives this move.

**Project memory does not transfer.** The notes from the Windows sessions live in the desktop app's
own storage. `CLAUDE.md` and this file are the handover; nothing else comes across.

That cuts both ways: notes a CM4 session keeps do not reach the laptop either. Whatever the hardware
teaches you, put it in `CLAUDE.md` and commit it — that is the only channel between the two.

### The gap in that plan

`CLAUDE.md` lives at the project root, **outside all four repos** — so as things stand it does not
travel by `git push` / `git pull`, which is exactly the channel it is supposed to use. Right now it
moves only by the same manual route as the vendor SDK, which means it will drift.

Three ways to close it, best first:

1. **A workspace repo at the project root** that tracks *only* the root files — `CLAUDE.md`,
   `HANDOVER.md`, `README.md`, `setup-codecommit.sh` — with `apps/`, `API-linux-java-*/` and
   `Hardware/` in its `.gitignore`. This is not a monorepo: it does not span the apps, and each app
   keeps its own independent repository. It is a fifth small repo whose only job is carrying the
   shared context between machines.

2. **Keep it in `intelli-rfid-core`** and run `claude` from `apps/intelli-rfid-core/` when doing
   reader work. Free, but the file stops being project-wide, and sessions started at the root will
   not load it.

3. **Copy it by hand** alongside the SDK. Works until the first time someone forgets, which is when
   the hardware corrections stop reaching the design sessions.

Option 1 is the only one that makes step 4 of the loop automatic. Ask and it can be set up.

---

## 5. Three decisions that need you

These are placeholders chosen with no site data. They are the difference between a reader that works
and one that looks like it works.

### `tunnel.settle-ms` — currently 1500

Too short and you close on a gap in the read pattern and lose the tags at the back of the box; too
long and the line waits.

Tune with data: run a few hundred real boxes, look at `lastNewTagMs` across the results, take the
99th percentile and add margin.

### `wayside.antenna-order` — currently `[1, 2]`

Must match the physical mounting order along the track, in the UP direction. If it does not,
direction inference will be **confidently wrong**, which is worse than reporting nothing. Leave it
empty rather than guessing — the code reports `UNKNOWN` and that is an honest answer.

### `rfid.reader.address` — currently `/dev/ttyAMA0`

Confirm per unit with `dmesg | grep tty`.

Two more worth revisiting once you have real data: `rssi-threshold-dbm` (−72 tunnel, −70 wayside) is
what rejects a neighbouring box or an adjacent track, and `wayside.antenna-spacing-m` (0) disables
speed estimation until you measure the real geometry.

---

## 6. Session record — what was built and why

### Architecture decisions

**Spring Boot** — chosen after confirming the CM4 has headroom. On a smaller board it would have
been the wrong call; here Actuator health and metrics matter more than the ~200 MB footprint,
because these readers sit where nobody can walk up to them.

**A fourth repository, `intelli-rfid-core`** — you asked for three apps. All three talk to the same
module through the same JNI library and need the same reader plumbing; duplicating ~1,500 lines
across three repos would mean fixing every reader bug three times. If you would rather have exactly
three, folding core into each app is a mechanical change.

**Spring lives inside core with `<optional>` dependencies** rather than in a fifth repo. Core stays
usable from a plain CLI, and the `com.intelli.rfid.spring` half activates only when an app puts
Spring Boot on the classpath.

**JSONL spooling rather than a database** — the file is greppable during a site visit, survives an
ungraceful power cut with at most one torn trailing line, and needs no migration when the result
shape changes.

### Three bugs the verification caught

Two were real and would have bitten in the field.

**1. The JNI load killed the Spring context.** Constructing the vendor `Reader` triggers
`System.loadLibrary` via a static initialiser. That happened during bean creation, so a missing or
mismatched `.so` threw `UnsatisfiedLinkError` before any connect-retry logic could run — a field
unit whose module was still enumerating at boot would crash-loop instead of coming up and reporting
unhealthy. Fixed by creating the vendor handle lazily inside `open()`.

**2. A failed connect stranded a tunnel session.** `open()` put the session in the active slot and
*then* tried to start reading. When that threw, the empty session stayed active and blocked every
subsequent open until the watchdog timed it out — one failed connect turned into a tunnel that
refused work for thirty seconds. Fixed with a rollback.

**3. `DedupWindow` mixed two clocks.** It seeded its sweep deadline from `System.currentTimeMillis()`
while every other decision used the caller-supplied timestamp, so the sweep would never fire and the
map would grow without bound. Caught by a unit test.

A fourth, non-code: **Maven's incremental compile silently bundled a stale core class** into the app
jar, which made bug 1 look unfixable through two rounds of "the fix isn't working". `mvn clean
install` on core after editing it.

### Test coverage

50 tests, concentrated on the logic that is genuinely hard rather than on getters:

- `DedupWindowTest` — suppression windows, per-antenna distinctness, unbounded-growth sweep
- `RecentTagBufferTest` — capacity bounds, per-EPC rollup, ordering
- `AcceptanceServiceTest` — probe-EPC derivation is length-preserving and self-inverse
- `InventorySessionTest` — settle semantics, re-reads not deferring settle, completeness vs
  expectation, timed-out sessions never trustworthy, marginal-sighting detection
- `PassBuilderTest` — consist ordering, two-tags-one-wagon collapse, direction inference in both
  directions and its refusal to guess, speed estimation, suspect-pass detection
- `WagonDecoderTest` — all three modes and the fallback that never loses a wagon

---

## 7. Quick reference

```bash
# Shared across all three apps
GET  /api/reader/status              state, counters, module identity
GET  /api/tags/stream                SSE tag stream
POST /api/diagnostics/antennas       VSWR sweep — first check on a coverage complaint
POST /api/tags/ops/write-epc         write an EPC with read-back verification
GET  /actuator/health                reader state for monitoring

# reader-test
POST /api/acceptance/run             full bench check, returns pass/fail report
GET  /                               operator page

# tunnel
POST /api/inventory/sessions         open (409 if one is running)
GET  /api/inventory/sessions/current live view
GET  /api/inventory/completed?since=N durable catch-up feed, from disk

# wayside
GET  /api/passes/latest              most recent consist
GET  /api/passes/{id}/consist        just the ordered wagon ids
GET  /api/passes/completed?since=N   durable catch-up feed
GET  /api/passes/forwarding          uplink state and backlog depth
```

Watch a reader with nothing but curl:

```bash
curl -N http://<cm4>:8080/api/tags/stream
```

Deploy as a service:

```bash
cd apps/<app> && mvn package && sudo deploy/install.sh
sudo systemctl start <app>
journalctl -u <app> -f
```

Pass `SDK_LIB=.../libs/aarch64` to `install.sh` to have it place the native library for you.
