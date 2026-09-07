# Resume here — CM4 session, next sitting

**Rewritten 2026-09-07 at the end of the session that FIXED the deafness, upgraded the SDK and made
the armed EAN authoritative. It supersedes the 09-07 "the reader is deaf, it is hardware" head that
stood here earlier the same day — that diagnosis was wrong and the section below says why.**

---

## ✅ 2026-09-07 — THE READER READS AGAIN. It was one antenna branch, not the module.

**38 of 38 articles, SETTLED, `complete: true`, RSSI −25 dBm.** The unit is deployed, running and
healthy. Nothing here is blocked.

### What was actually wrong

The SIM7500 has **one** antenna port; the board's PE42442A SP4T splits it to J20/J25 under
**GPIO8/9**, and the module cannot see the switch. **Every earlier "both ports tried" test was run
with a single antenna**, so flipping `ANT=2` listened into a bare connector and proved nothing.

With an antenna on both ports and the tags unmoved: **J20 best −49 dBm over 3 EPCs, J25 best
−25 dBm over 8.** −25 is this rig's baseline, so the module, PA and switch are fine and the ~24 dB
loss is inside the J20 branch. J20 is the port the systemd unit had always selected.

### State the unit was left in

- **Service running**, PID under systemd, jar and `.so` both v260827, site config patched.
- **Antenna select is ANT2 / J25** — set by `ExecStartPre` in `deploy/intelli-rfid-tunnel.service`.
  `run.sh` still defaults to `ANT=1`, so **a bare `run.sh ProbeBasic` tests the BROKEN branch.**
- Region `RG_EU3`, 27 dBm, session S1, `settle-ms` 800, FastID on, `valid-eans` empty.
- Everything committed and pushed in all four repos that changed.

### Next actions, in order

1. **Bisect the J20 branch — physical, no software.** Swap the two cables at the board, leave the
   antennas and tags where they are, re-run both ports:
   ```bash
   sudo systemctl stop intelli-rfid-tunnel && sleep 3 && pgrep -x java   # must print nothing
   ANT=1 /home/intelli-sbc/api/run/run.sh ProbeBasic
   ANT=2 /home/intelli-sbc/api/run/run.sh ProbeBasic
   ```
   Weakness follows the cable → replace the cable. Weakness stays on J20 → it is the board's J20
   connector or that arm of the SP4T. **Then put the unit back to ANT1** (`pinctrl set 8 op dh`,
   `9 op dl` in the unit file) so the documented default is the live one again.
2. **Re-derive `settle-ms` from the new 38-article cartons.** 800 was derived on 09-04 from an
   18-tag unshadowed population. Sort each result's matched-tag `firstSeen`, diff consecutive,
   take the worst across many cartons, double it. **Do it over the matched tags only** — foreign
   tags no longer hold the window open, so including them measures a window the reader does not use.
3. **Antenna multiplexing is still unwritten.** Nothing drives GPIO8/9 at runtime, so the second
   antenna is dead weight. `docs/Hardware-IntelliRFIDv2.md` §7.3 has the design question: measure
   stop-inventory → toggle → restart, then pick a dwell from that number. Start/stop is 0–3 ms and
   20–60 ms measured, and bare start/stop is NOT rate-limited, so this is cheaper than §7.3 assumes.
4. **`intelli-rfid-reader-test` still ships `company-prefix: 8905527`** while the tunnel ships
   `8909478`, so the bench harness refuses to commission the SKU the tunnel writes. One-line fix,
   not done because nothing this session needed it.
5. **Optional: `SuccessExitStatus=143` in the unit file.** A clean `systemctl stop` currently leaves
   the service reporting `failed`. Cosmetic, but it misleads.

### What shipped this session

- **SDK v260827** in core and tunnel (`com.uhf:module-api-j:2.6.0827`). No API signature changed;
  2.6.0721 is still in `~/.m2` so rollback is one pom line. It did **not** fix the deafness.
- **The site config was loading TWO `.so` files** — `native-lib-path` into the old SDK tree plus
  `-Djava.library.path=/opt/intelli/lib`. Byte-identical until now, two different versions after the
  upgrade. Both now point at `/opt/intelli/lib`.
- **The shipped SKU allowlist is gone.** `rfid.gs1.valid-eans: []`, so the reader arms for whatever
  EAN the WMS sends. `PackagedConfigTest` fails the build if a customer's SKUs reappear there.
- **Settle is scoped to the armed SKU, in two phases.** Foreign tags no longer extend a carton —
  but only once an article of the SKU has actually been heard, because scoping from t=0 closes
  shadowed cartons early and makes `stopReason` report SETTLED where it should report TIMEOUT.
- 251 tunnel tests, 61 core tests, all passing.

### The measurement, so it is not re-derived

Nine Super Fast cartons on the deployed jar, ANT2, v260827:

| seq | stopReason | tags | matched | lastNewTagMs | RSSI |
|---|---|---|---|---|---|
| 855 | SETTLED | 18 | 18 / 18 | 801 | −51…−29 |
| 856 | SETTLED | 29 | 29 / 38 | 801 | −51…−26 |
| 858 | SETTLED | 34 | 34 / 38 | 832 | −50…−31 |
| 859 | SETTLED | **38** | **38 / 38** | 806 | −49…−25 |

Carton time 2.09–2.98 s. `lastNewTagMs` 801–883 against `settle-ms` 800 — the watchdog's ~100 ms
tick, matching 09-04. First 38-article carton this project has read; the previous largest was 18.

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
