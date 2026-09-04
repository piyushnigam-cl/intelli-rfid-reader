# Resume here — CM4 session, next sitting

**Rewritten 2026-09-04 at the end of the shutdown-safety session.** Everything below is either
measured on this hardware or read from the tree; where it is inference it says so.

---

## The state of the unit right now

**The app is running and healthy.** `intelli-rfid-tunnel` active, PID 8013, listening on 8081,
started 15:51:56. The jar was deployed at 15:51 from commit `19f3a3d`.

**The board was powered off and back on once today, deliberately** — an IN3 shutdown test at 15:23.
It came back on its own power cycle. See "what this session found" below, because that test is what
the whole session came out of.

**Deployed and live:**

- The late shutdown-lamp hook at `/usr/lib/systemd/system-shutdown/intelli-lamp.shutdown` (0755,
  installed 15:51). `intelli-shutdown-lamp.service` is gone — `systemctl is-enabled` says
  `not-found`, which is correct and is what you want to see.
- Step 5 of the shutdown sequence now runs `/bin/sync`.

**Committed and pushed but NOT deployed:** `e71a5f2`, which parks O7. It changes no runtime
behaviour on the tunnel path — `FieldChannel.OUT7.function()` becomes null, so `FieldIo.write()`
refuses it and `/api/v1/diagnostics/io` reports OUT7 with no `function` field. It rides along on the
next `deploy/redeploy.sh` and needs nothing special.

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

### 3. O7 is parked; the panel drawings said otherwise

O7 had carried no traffic since the one-lamp decision on 2026-09-04, but still declared
`SAFE_TO_POWER_OFF`, so `isParked()` was false and `docs/Tunnel-Interconnect.md` v0.5 still told the
panel builder to fit a lamp beside the shutdown button. Built to that drawing, an operator would
read a dark `SAFE_TO_POWER_OFF` as "not yet safe" and wait forever, next to the lamp that was
actually telling them. Now parked in code and withdrawn from every document.

**O7 is earmarked, not merely free.** It is the only spare output on J26, and the one capability
this design lost and never replaced is the 1 Hz liveness heartbeat that let a watchdog stop the line
after 3 s of silence. Do not spend it on anything smaller without settling that first.

---

## Next actions, in order

1. 🔴 **Reconcile `power-off-os` in the site config.** `/etc/intelli/intelli-rfid-tunnel/application.yml`
   line 282 is `power-off-os: true`, and the comment block immediately above it says **"FALSE FOR
   NOW, deliberately"**. The value is what runs; the comment is what the next person believes. Same
   shape as the old `session: 2` drift. Needs root — the file is `root:intelli-sbc 0640`.

   Decide which is meant. **True is a real hazard on a bench unit**: a spurious IN3 hold powers the
   board off and it needs hands at the panel to come back.

2. **Watch O6 through the next IN3 shutdown.** This is the acceptance test for the lamp fix and
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

5. **Deploy `e71a5f2`** whenever convenient — `deploy/redeploy.sh`. Nothing depends on it.

6. **Consider fsync per spool append.** The step-5 sync covers the shutdown path, but a carton
   result is still only durable within ~30 s of an unexpected cut. That is a hot-path change (one
   fsync per carton on eMMC) and a separate decision from anything done this session.

7. **Still open from before, unchanged:** the EnC stop delay versus EnS placement (a carton is
   dragged if EnC stops the instant EnS fires), and the discharge-starts-EnC consequence of the
   module-fault path — both in `CLAUDE.md`.

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

All five clean and pushed at the end of this session.

| Repo | Head |
|---|---|
| `intelli-rfid-reader` (docs) | `Shutdown: the lamp was one phase early…` + the O7 doc update |
| `intelli-rfid-tunnel` | `e71a5f2` Park O7 |
| `intelli-rfid-core` | `b058f42` unchanged this session |
| `intelli-rfid-reader-test` | `940c4d8` unchanged this session |
| `intelli-rfid-admin` | `bdf8ab3` unchanged this session |
