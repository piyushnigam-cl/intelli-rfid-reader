# Resume here — CM4 session, next sitting

**Rewritten 2026-09-04 at the end of the shutdown-safety session, appended to at 17:50 after a
second session built `intelli-wms-test`, and headed on 2026-09-07 with the RF fault — which
supersedes every "next action" below it until the reader hears a tag again.** Everything below is
either measured on this hardware or read from the tree; where it is inference it says so.

---

## 🔴 2026-09-07 — THE READER IS DEAF. IT IS HARDWARE. START HERE.

**The unit hears no tags at all, on either antenna port, with every RF parameter verified by
read-back on a brand-new vendor SDK. Do not debug this in the tunnel app.** It failed at the
Reliance site on 09-05 and was brought back to the office rig, where it is still deaf.

### What was left running

- **The tunnel service is STOPPED** (`sudo systemctl stop intelli-rfid-tunnel`). Port 8081 is not
  listening, so the admin app cannot reach this reader until it is started.
- **The module is powered and out of reset**, antenna select on **ANT1 / J20**, region left on
  `RG_EU3` at 27 dBm, session S0 — that is `ProbeBasic`'s exit state, not the app's.
- A reboot was planned immediately after this was written. **A reboot returns the pins to inputs
  with the SoC pull-down, i.e. the module OFF**, and reverts the region to `RG_NA`. Both
  `run.sh` and the systemd unit handle it; nothing else does.
- Nothing is uncommitted. `/home/intelli-sbc/api/` is NOT in any repository.

### First action next session — repeat the measurement, then bisect

```bash
sudo systemctl stop intelli-rfid-tunnel && sleep 3 && pgrep -x java   # must print nothing
/home/intelli-sbc/api/run/run.sh ProbeBasic                            # ANT=2 for J25
```

Expect, if nothing has changed: `InitReader OK`, region/power/hop-table/session all reading back
correct, and **0 tag reads**. If it now reads, the fault is intermittent and the reboot or the
reseating moved it — capture the RSSI and compare against Friday's −27 to −49 dBm before touching
anything else.

**Then the physical bisect, which is the only thing left and needs no software:**

1. **Bench dev board's antenna + cable onto this reader.** Reads → the antenna or cable is dead.
   Still silent → the reader board or the SIM7500 is dead.
2. **This antenna + cable onto the bench dev board.** The reciprocal. If 1 and 2 disagree, it is
   the connector.

### Also done 2026-09-07 — the authentication region was unlocked to RG_IN, and it was not enough

Silion supplied the procedure with the new SDK. It works, it persists, and it does **not** give us
`RG_IN` as an operating region.

- Auth region read `RG_PRC` before, reads **`RG_IN`** after, surviving a re-power.
- **Hardware version permanently changed `31.00.00.80` → `31.00.0E.80`.** Third octet is the region
  marker. Every doc quoting `31.00.00.80` for this module is stale; it is not different silicon.
- `ParamSet(MTR_PARAM_FREQUENCY_REGION, RG_IN)` **still** `MT_CMD_FAILED_ERR`, accepted set still
  `RG_NA` / `RG_EU3` / `RG_PRC` / `RG_OPEN`. Tested twice, including as the first operation after a
  fresh module boot.

**PENDING, and it is next-action 0b after the ProbeBasic re-run:** re-test `RG_IN` after a full
24 V removal rather than an `RFID_EN` toggle.

```bash
/home/intelli-sbc/api/run/run.sh ProbeAuthRead                       # expect auth region RG_IN
cd /home/intelli-sbc/api/run && java -Dregion=RG_IN \
  -Djava.library.path=/home/intelli-sbc/api/libs/linux/aarch64 \
  -cp /home/intelli-sbc/api/libs/ModuleAPI_J-v260827.jar:. ProbeSetRegion
```

If it is still refused, **the question for Silion is specific**: auth region reads `RG_IN`, hw
confirms `31.00.0E.80`, and `ParamSet` on the operating region still fails on sw `20.26.03.30` —
does the operating whitelist need new module firmware too?

To reverse the unlock: `ProbeAuthWrite` with `-Dtarget=RG_PRC`. The module was left on operating
region `RG_EU3`, deliberately — a power cycle reverts it to `RG_NA`, which is 902–928 MHz and
illegal to key up on in India.

### The evidence, so it is not re-derived

| | tags | RSSI |
|---|---|---|
| Fri 09-04, spool seq 750–752 | 18 / 18 | −27 to −49 dBm |
| Sat 09-05 at site, seq 833–837 | 2, 3, 5 | −52 to −58 dBm |
| Mon 09-07 bench, all tests | **0** | nothing |

Friday's −27 dBm sits on the recorded −26 dBm baseline, so the path was healthy then. **No code in
the read path changed across that boundary** — the only commits between are the ten `field/` files
of the 09-05 rewiring, core has nothing since 09-02, and the site `application.yml` is untouched
since 09-04 15:21. Checked by diff.

### Ruled out, with the measurement that ruled it out

| Suspected | Ruled out by |
|---|---|
| The 09-05 GTIN / `valid-eans` change | `tagCount: 0` and `totalReads: 0` — nothing answered at all; and the spool still shows the old `30361F8CDC100F…` SGTINs, so the tags were never re-commissioned |
| Any code change in Super Fast mode | diff `e71a5f2..HEAD` is ten `field/` files and nothing else |
| Site config drift | `/etc/intelli/…/application.yml` mtime 09-04 15:21, before Friday's good reads |
| Old SDK / old native lib | fresh v260827 jar + its `.so`: identical result |
| Wrong region after power cycle | found on `RG_NA`, set to `RG_EU3`, **read back**, still 0 |
| Low power | read/write 2700 **read back**, limits 500–3000 |
| Gen2 session silencing | forced S0, still 0 |
| Wrong antenna port | **both** RF1/J20 and RF2/J25 tried |
| Module enable / reset / select pins | `pinctrl get` verified at the pad on every run |
| The v260827 "hardware-version-80 region" fix | our module is hw `31.00.00.80`, so it looked promising — the new SDK changes nothing |

### Two instruments on this board that LIE, and both wasted time

- **`/api/diagnostics/antennas` (VSWR) rails at `3.0095203`** — exactly 6.000 dB return loss — with
  the antenna connected *and* with the port bare. It cannot detect a missing antenna here. The
  1.119 baseline everyone quotes is the **bench dev board**; this carrier has never had one taken.
- **`ReaderInfo.connectedAntennas` is the configured port list, not a detection.** Javadoc now
  corrected in core.

---

## ⚠ 2026-09-05 — THE FIELD IO WAS REWIRED ON SITE. READ THIS BEFORE ANYTHING BELOW IT.

Bench testing at the site required a change of wiring, and it invalidates several statements further
down this file. The channel map now is:

| Ch | BCM | Was | Is |
|---|---|---|---|
| OUT1 | 26 | `EnC_ExC_RUN` — both belts on one channel | `EnC_RUN` — Entry Conveyor alone |
| OUT5 | 21 | `LAMP_PASS` green | `ExC_RUN` — Exit Conveyor Run A |
| OUT6 | 12 | `LAMP_FAIL` red | `LAMP_PASS` green |
| OUT7 | 13 | parked spare | `LAMP_FAIL` red, **and the shutdown lamp** |
| IN4 | 25 | parked spare | `EXIT_FULL` ← the Discharge Sensor (DsS) |

OUT2/3/4 and IN1/IN2/IN3 are unchanged.

**Why:** there is no end stop on the Exit Conveyor, so a carton reaching the discharge edge with the
belt running goes on the floor. DsS has to be able to stop the ExC *without* stopping the EnC, and a
shared O1 made that impossible.

**What follows.** The line is **no longer serialised** — the previous carton can discharge while the
next is read. **J26 is full**: O7 was the last free output and the earmarked home for the 1 Hz
liveness heartbeat, and it is spent. Every claim below that O7 or IN4 is parked, spare or earmarked
is **superseded**, including §3 and next-action 5.

**The exit interlock is built (`033351c`), to the operator's policy of 2026-09-05 — one package at
a time:** IN4 asserting stops the ExC in any phase and disturbs nothing else, a read always runs to
completion, a read closing against a still-occupied edge stops the whole line with the carton held
in the read zone, and it all resumes by itself when the edge clears. The result is published either
way. IN4 is a **sampled level** on its own thread, not a `gpiomon` edge, which is what makes it
independent of the `active-low` question. **The EnC still restarts at read close** rather than at
the IN2 edge — operator's call, "fine for now", and now a choice rather than a constraint.

**Also still open: the input polarity.** `tunnel.v1.gpio.active-low` is `false` and the two accounts
of the wiring still disagree (see `application.yml`'s own comment). The deciding measurement is one
line, and IN4 makes it cheap because nothing holds line 25: `pinctrl get 25` with the DsS beam clear
and blocked, no need to stop the app.

**Deployed?** The tunnel commits are pushed. Whether `deploy/redeploy.sh` has been run is not
recorded here — check the running jar. **Until it is, `/usr/lib/systemd/system-shutdown/intelli-lamp.shutdown`
still writes BCM 12**, which now darkens the *green* lamp at poweroff and leaves the red one lit for
ever.

---

## The state of the unit right now

**The app is running and healthy.** `intelli-rfid-tunnel` active, **PID 1031**, listening on 8081,
started **17:44:52**. The jar is still the one deployed at 15:51 from commit `19f3a3d` — the restart
was a reboot, not a redeploy.

**The board went down and came back at ~17:44, and nobody asked it to.** That is the *second* power
event of the day and unlike the 15:23 one it was not a test: it killed the Claude Code session
mid-work, which is how `intelli-wms-test` came to be sitting on disk uncommitted. The reader
reopened cleanly on its own (`Reader open: module=MODOULE_NONE fw=20.26.03.30`, inventory started).
**Cause not established.** The clock disagrees with itself across `who -b` (17:44), `ps` (17:48) and
the log (17:44:52), which is the no-RTC signature of a cut rather than an ordered shutdown — but
`journalctl` is volatile here, so the transcript that would settle it is gone. **Item 3 below is
what makes the next one diagnosable; do it before chasing this one.**

**The earlier power cycle at 15:23 was deliberate** — the IN3 shutdown test. See "what this session
found" below, because that test is what the whole shutdown-safety session came out of.

**Deployed and live:**

- The late shutdown-lamp hook at `/usr/lib/systemd/system-shutdown/intelli-lamp.shutdown` (0755,
  installed 15:51). `intelli-shutdown-lamp.service` is gone — `systemctl is-enabled` says
  `not-found`, which is correct and is what you want to see.
- Step 5 of the shutdown sequence now runs `/bin/sync`.

**Committed and pushed but NOT deployed:** `e71a5f2`, which parks O7. ~~It rides along on the next
`deploy/redeploy.sh` and needs nothing special.~~ **SUPERSEDED 2026-09-05** — O7 is the red and
shutdown lamp now, so that commit's premise is gone. It is history in the branch, not something to
deploy on its own.

---

## What this session found, in the order it mattered

### 1. The IN3 shutdown is a proper OS shutdown. The lamp was the problem.

The question that started it was whether the IN3 poweroff is "like a power cycle". **It is not** —
it runs `sudo systemctl poweroff`, identical to `sudo poweroff`, and the app's own five steps take
120 ms with the full OS phase after them. What makes it *feel* instant is the comparison: bare
`sudo shutdown` is `shutdown -h +1` and waits a whole minute.

**But `intelli-shutdown-lamp.service` was putting O6 dark one phase too early.** It was ordered
`After=umount.target Before=final.target`, which is systemd's *first* phase; the root filesystem is
remounted read-only and synced in the *second*, inside `systemd-shutdown`, after `final.target`. So
the lamp said "24 V may be removed" while `/` was still mounted rw with dirty pages. Fixed by moving
it to `/usr/lib/systemd/system-shutdown/`, which `systemd-shutdown` runs after that remount. Full
reasoning is in `CLAUDE.md` and in the script's own header.

**Step 5 also never synced.** It was called "leave storage safe to interrupt" but only awaited
`CallbackSender.awaitQuiet()`, which is network quiescence. `JsonlSpool.append` has no fsync and
`dirty_expire_centisecs` is 3000, so up to 30 s of carton results could be in page cache. Now
syncs, injected as a `Runnable` so the tests pin the ordering.

### 2. There was a hard power cut at ~15:17 today, before the IN3 test

Not caused by the shutdown — established by the spool: the JVM that booted afterwards logged
`resuming from sequence 802`, so record 802 and the NUL bytes after it were already on disk before
that boot. Two files carry NUL holes from it:

| File | Damage | Done? |
|---|---|---|
| `/opt/intelli/logs/intelli-rfid-tunnel.log` | 3377 NUL bytes mid-file | left alone, it is a log |
| `/var/lib/intelli/tunnel/spool/inventory-2026-09-04.jsonl` | 1689 NUL bytes at the tail | 🔴 **not trimmed** |

Everything else is clean: 1293 files scanned, `git fsck` clean on all five repos, jar intact, no
ext4 errors, no I/O errors, root mounted with no journal replay.

**To trim the spool tail** (safe with the app running — it only appends):

```bash
cp /var/lib/intelli/tunnel/spool/inventory-2026-09-04.jsonl{,.bak}
truncate -s 194919 /var/lib/intelli/tunnel/spool/inventory-2026-09-04.jsonl
```

It is harmless as it stands — both `JsonlSpool` read paths catch the bad line and skip it at DEBUG —
which is exactly why it would otherwise sit there forever.

### 3. O7 was parked; the panel drawings said otherwise — SUPERSEDED 2026-09-05

O7 had carried no traffic since the one-lamp decision on 2026-09-04, but still declared
`SAFE_TO_POWER_OFF`, so `isParked()` was false and `docs/Tunnel-Interconnect.md` v0.5 still told the
panel builder to fit a lamp beside the shutdown button. Built to that drawing, an operator would
read a dark `SAFE_TO_POWER_OFF` as "not yet safe" and wait forever, next to the lamp that was
actually telling them. It was parked in code and withdrawn from every document.

**That lasted one day.** The site rewiring of 2026-09-05 made O7 the red lamp and the shutdown lamp,
so `isParked()` is false again — for a real reason this time — and a lamp *is* fitted there. Nothing
on J26 is parked any more.

**The heartbeat has lost its home, and this is the cost worth remembering.** O7 was earmarked
because the one capability this design lost and never replaced is the 1 Hz liveness signal that let
a watchdog stop the line after 3 s of silence and survived a hung JVM. There is no free output left
to put it back on. Getting it back now means RS-485 to the drive cards, which would free O1–O5 at
the same time.

### 4. `intelli-wms-test` — a sixth repo, written 17:33–17:46 and nearly lost

A new laptop app, port 8083: **a WMS reduced to arming Super Fast Mode and showing the carton that
comes back.** Tags expected, tags found, time taken, then every tag with EPC and TID. 20 files,
~2100 lines, `mvn package` green with tests, jar built at 17:46 in `target/`.

It is not a duplicate of admin's WMS simulator. Admin asks *does the reader behave*; this asks
*could a WMS integrator use it*, and answers it by holding **nothing but the INVENTORY key** and the
five documented endpoints. The full reasoning, and the two rules that stop it flattering the reader
(found is `matched.count`; the verdict pill is the reader's own `complete`), are in `CLAUDE.md`.

**It is a temporary app** — the customer's own integration replaces it, and it is disabled by
rotating the `site-wms` key on the reader (operator's decision, 2026-09-04). That is why the live
INVENTORY key is committed in its `application.yml` in plaintext: the jar is handed over and
double-clicked with no setup.

**It had no `.git` at all until 17:5x**, and that is the lesson worth keeping. It was written,
built, and left through a reboot with nothing tracking it — and the root `git status` stayed clean
the whole time, because the root repo ignores `apps/` by design. Nothing anywhere would have said a
word. **`git init` belongs to creating an app, not to finishing one**; at close-out, walk `apps/*/`
by directory and check each one *has* a repo, rather than iterating the repos that exist. Now
`db8e136` on `origin/main` at `.../v1/repos/intelli-wms-test`.

**Never run against a live reader.** Unit tests only. See next action 0.

---

## Next actions, in order

0. 🔴 **Run `intelli-wms-test` against this reader, end to end.** It has never met a real one — every
   claim in its README is unit-tested inference. The tunnel is up on 8081, the jar is built, and the
   bench population is 18 tags. What this first run is actually testing is the **callback path**,
   which is the half no unit test can reach: arm from the page, put a carton through, and see the
   result *arrive*. If the page sits empty with the reader reporting a perfect carton, the callback
   URL is the suspect before anything else — check `callbacks.jsonl` on the reader and remember that
   the spool replays independently of arm state, so a backlog from an earlier address will retry all
   day and read as the arm path being broken.

   Two known-honest failures to expect rather than debug: `expected-token` blank reports
   `NOT_CHECKED` (the tunnel sends no token today), and an empty TID column means FastID — which is
   on, so TIDs should appear.

1. 🔴 **Reconcile `power-off-os` in the site config.** `/etc/intelli/intelli-rfid-tunnel/application.yml`
   line 282 is `power-off-os: true`, and the comment block immediately above it says **"FALSE FOR
   NOW, deliberately"**. The value is what runs; the comment is what the next person believes. Same
   shape as the old `session: 2` drift. Needs root — the file is `root:intelli-sbc 0640`.

   Decide which is meant. **True is a real hazard on a bench unit**: a spurious IN3 hold powers the
   board off and it needs hands at the panel to come back.

2. **Watch O7 through the next IN3 shutdown** — the RED lamp, BCM 13. It was O6 until the
   2026-09-05 rewiring, and watching O6 now means watching the green PASS lamp, which does nothing
   during a shutdown. **This only works once `redeploy.sh` has reinstalled the shutdown hook**, since
   the installed copy writes BCM 12. This is the acceptance test for the lamp fix and
   nothing else proves it. Expect blinking → solid → **dark**, with a visibly longer gap before
   dark than before — that gap is the root remount-ro and final sync you were previously being
   invited to interrupt. If dark never comes, check the hook is still 0755: `systemd-shutdown`
   silently skips a file it cannot execute.

3. **Make journald persistent.** `/var/log/journal` exists but is empty, so journald writes to
   `/run` and every shutdown's transcript dies at the next boot. That is why item 2 has to be
   watched by eye rather than read out of a log afterwards.
   ```bash
   sudo systemd-tmpfiles --create --prefix /var/log/journal && sudo systemctl restart systemd-journald
   ```
   After that, `journalctl -b -1` answers "did that poweroff unmount cleanly?" in one command.

4. **Trim the spool tail** (§2 above), or decide to leave it.

5. **WITHDRAWN.** This said "deploy `e71a5f2`, which parks O7". Deploying that commit *as written*
   would blank the channel the red and shutdown lamps now live on. It has been superseded by the
   2026-09-05 rewiring commits, which are what `deploy/redeploy.sh` will pull.

6. **Consider fsync per spool append.** The step-5 sync covers the shutdown path, but a carton
   result is still only durable within ~30 s of an unexpected cut. That is a hot-path change (one
   fsync per carton on eMMC) and a separate decision from anything done this session.

7. **Still open from before:** the EnC stop delay versus EnS placement (a carton is dragged if EnC
   stops the instant EnS fires) — unchanged, and still wants the real geometry.

   **The discharge-starts-EnC consequence of the module-fault path is now solvable rather than
   solved.** It was forced while EnC and ExC shared O1; they are separate channels since 2026-09-05,
   so the fault path *can* raise O5 alone. Nothing does it yet, and `setBelts()` is where it goes.

8. **Done — the IN4 discharge interlock is built** (`033351c`), see the banner. What is *not* done
   is proving it against the real sensor: `pinctrl get 25` with the beam clear and blocked, then a
   carton driven to the edge to watch O5 drop. Until that runs, the interlock is correct in tests
   and unwitnessed on hardware.

9. **Derive `tunnel.field.exit.sample-ms` from the geometry.** It is 250 ms, which at 0.5 m/s is
   125 mm of travel past the beam before the belt is told to stop. Measure beam-to-edge, divide by
   the ExC's linear speed, halve it. If the answer is under ~100 ms the sensor is too close to the
   edge and moving it is the fix.

---

## Traps this session added to the pile

- **A NUL run inside a text file is the fingerprint of a hard cut**, and it dates the cut. ext4
  journalled the inode's new size but the data blocks never landed. Nothing logs it and the app runs
  straight over it.
- **The CM4 has no RTC that survives an unclean cut**, so the boot after one restores a stale
  timestamp and the log appears to run *backwards*. Two files stamped 15:17 can sit after a boot
  line stamped 15:15. **Order by PID, not by clock** — a low PID means a fresh boot.
- **`systemd-shutdown` silently skips a non-executable file** in `system-shutdown/`. The symptom is
  a lamp that never goes dark on a board that is off, which reads as a hung shutdown and appears in
  no log at all.

---

## Repositories

**Six now, not five** — and one of them did not exist as a repo an hour ago. All clean and pushed.

| Repo | Head |
|---|---|
| `intelli-rfid-reader` (docs) | 2026-09-05: the rewiring across `CLAUDE.md`, `docs/` and this file |
| `intelli-rfid-tunnel` | 2026-09-05: `cbe8343` the rewiring, then the O5 diagnostic-write warning |
| `intelli-rfid-core` | `b058f42` unchanged |
| `intelli-rfid-reader-test` | `940c4d8` unchanged |
| `intelli-rfid-admin` | `f843370` lamps moved up a channel, BELTS pill added |
| `intelli-wms-test` | `db8e136` **root commit** — new today |

`intelli-rfid-wayside` is a sixth app in the layout table but **is not checked out on this CM4**; do
not read its absence as a deleted repo.

**Walk `apps/*/` by directory when you do this, not the list above.** The root repo ignores `apps/`,
so an app with no `.git` is invisible to every status command you would think to run — which is
exactly how `intelli-wms-test` survived a reboot on luck alone.
