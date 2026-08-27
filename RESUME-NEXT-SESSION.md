# Resume here — CM4 session, next sitting

Written at the end of 2026-08-27. Everything below is measured on hardware unless it says otherwise.
Start with §1: there is one unfinished experiment and it is the most important thing on the list.

---

## 1. THE UNFINISHED TEST — S2 flag persistence

**Run this first.** It was cut short and the partial result already contradicts a design decision.

### What happened

The settling test was run with Gen2 **S2** (the tunnel's configured session) and a carrier-off gap
between trials, on the assumption that S2's inventoried flags decay while the carrier is off. They
did not.

```
S2, 4 s gap  — trial 1: 18 tags. trials 2-10: ZERO tags, all ten timed out at 8 s.
S2, 15 s gap — 4 trials: ZERO tags, every one.
S0, 3 s gap  — 4 trials: 18/18 tags every time.   <-- control: rig and tags are fine
```

So on this tag stock the S2 inventoried flag persists **longer than 15 seconds**. The S0 control
rules out the rig, the antenna, the tags and the probe: it is specifically S2 state.

### Why it matters

The tunnel is configured `session: 2`, and the laptop's §2/§8 reasoning is that the carrier-off
window between boxes lets S2 flags decay back to A. **Measured, that window needs to be >15 s.** At
one box per 20 s that is uncomfortably tight, and if boxes ever arrive faster, **the second box
reads as empty** — the exact failure mode the handoff warns about for Target A/B alternation, but
arriving by a different route.

### What to run

Bracket the actual persistence, then decide. Gaps to try: **20 s, 30 s, 45 s, 60 s, 120 s.**

```bash
cd apps/intelli-rfid-reader-test/tools/bench-probe
# args: port power session trials settleMs gapMs readDurMs fast
./run.sh ProbeSettle /dev/ttyAMA0 3000 2 4 1500 20000 50 0
./run.sh ProbeSettle /dev/ttyAMA0 3000 2 4 1500 30000 50 0
./run.sh ProbeSettle /dev/ttyAMA0 3000 2 4 1500 60000 50 0
```

Give it time — a 4-trial run at a 60 s gap takes about five minutes, and the whole sweep is the best
part of half an hour. That is the reason it was not finished today, not a technical obstacle.

**Also worth testing, because it may make the whole question moot:**

- **S1.** Self-decays in 500 ms – 5 s *even while powered*. The handoff rejected it because a tag can
  re-answer mid-box — but a box read is under a second (§2), so mid-box re-answering may be
  irrelevant while the fast decay solves the between-box problem outright. This looks like the more
  promising option now.
- **A Select that forces inventoried → A** at the start of each box. The SDK has
  `SelCmd_Target = SelC_Inventoried_S2` with `SelCmd_Action.Mat_SLorA_NMat_no`. If that works it
  removes the dependency on persistence entirely and is the cleanest fix. **Untested.**
- **S0** for comparison — it works reliably but has no persistence at all, so a tag answers every
  round and a dense box may never drain.

Record whatever comes out in `CLAUDE.md` and in the handoff reply, as usual.

---

## 2. Where the settling numbers landed (S0, the trials that worked)

18 tags in the field, one antenna, 30 dBm, NORMAL, `ReadDuration` 50 ms, settle 1500 ms.

| trial | first tag | last new tag | settled at | unique | discovery window |
|---|---|---|---|---|---|
| 1 | 95 ms | 547 ms | 2067 ms | 18 | 452 ms |
| 2 | 77 ms | 495 ms | 2017 ms | 18 | 418 ms |
| 3 | 88 ms | 817 ms | 2339 ms | 18 | 729 ms |
| 4 | 82 ms | 976 ms | 2519 ms | 18 | 894 ms |

And the one good S2 trial, which was the fastest of the lot: first tag 91 ms, **all 18 discovered by
260 ms**, discovery window 169 ms.

**The finding: discovery is cheap, settle dominates.** All 18 tags are found inside ~1 s, then the
session spends another 1.5 s waiting out a settle window to prove nothing else is coming. Settle is
**60–75% of total session time.**

That is a direct, measured argument for the missing `COUNT_REACHED` early exit (§4 defect 1): with
`expectedCount` supplied, these sessions could close at ~0.5–1.0 s instead of ~2.0–2.5 s. On a 5 s
box budget that is the cheapest second available and it is currently unclaimed.

Caveat, and it matters: 18 tags loose on a bench is not 40 articles packed in a box. The shapes here
(discovery finishing in under a second, a flat tail) are the shapes to expect, not the magnitudes.

---

## 3. State of play — all four repos pushed and clean

| Repo | HEAD at end of session |
|---|---|
| `intelli-rfid-reader` (workspace docs) | see `git log` |
| `intelli-rfid-core` | `237ea27` |
| `intelli-rfid-reader-test` | probes |
| `intelli-rfid-tunnel` | config + `tools/sgtin96.py` |

`intelli-rfid-wayside` still does not exist locally or in CodeCommit. Not part of this milestone.

### Done and verified on hardware

- **reader-test**: full acceptance PASS including write-and-restore.
- **Three bugs fixed in core**: `connect()` starting inventory in POLLED mode; core compiled without
  `-parameters` (four endpoints returned HTTP 400); VSWR reporting 100 readings when 4 were real.
- **Tunnel first light**: the continuous path — `startReading()` → JNI callback → bounded queue →
  dispatcher → session state machine — works end to end. `SETTLED`, `TIMED_OUT`, `complete`,
  per-session overrides and dedup all behave.
- **Carrier-on → first tag = `ReadDuration` + ~14 ms.** The module batches callbacks to the end of
  each read window. Triggered RF is safe; `read-duration-ms` is a latency knob and is set to 50.
- **Tag silicon is Impinj** (18 of 19; TMID `0x190`), so FastID and Impinj fast mode are available.
- **SGTIN-96 codec** written and self-tested against both Reliance vectors, both directions.

### Open, in rough priority order

1. **S2 persistence** — §1 above.
2. **`COUNT_REACHED` / early exit on count** — not implemented; §2 shows what it is worth. Waiting on
   the laptop to say whether it lands here or with the `/api/v1` layer.
3. **`MTR_PARAM_TAG_FILTER`: on-air Select or firmware post-filter?** Never attempted. Test: does
   session duration move when foreign tags are in range?
4. **Impinj fast mode vs Ex10 vs NORMAL**, now that the tags are known to be Impinj. Ex10 measured
   **14× slower** than NORMAL on this sparse population — that needs re-testing on a real box before
   `read-mode: EX_FAST` stays the packaged default.
5. **The API-key package over the wire** — still never exercised; everything ran with
   `rfid.security.enabled=false`.
6. **The queue under real pressure** — 16 callbacks/s against a queue of 8192 is no test at all.
   Needs a real box.
7. **Spool startup behaviour** — the tunnel refuses to start if `/var/lib/intelli` is unwritable.
   Crash or degrade is a product decision for the laptop.

---

## 4. Things that will waste your time if you forget them

- **`-Djava.library.path=/opt/intelli/lib` on every java command.** `native-lib-path` alone does not
  work — the vendor's static initialiser calls `System.loadLibrary`.
- **`--rfid.reader.region=RG_EU3` on the bench.** The module refuses `RG_IN`; leave `RG_IN` in the
  config file. (Piyush intends to fix this by reflashing.)
- **`--rfid.reader.antenna-count=1`** — dev board has one port.
- **Ask the operator to start and stop long-running apps.** Backgrounded JVMs get killed at tool-call
  boundaries and `pkill -f '<app>'` kills the wrapper shell. Run app + drive + stop inside a single
  command, or hand it over.
- **A session opened via `POST /api/inventory/sessions` returns immediately.** It does not block until
  close — poll `/sessions/current` until 204 then read `/latest`. Polling too early returns the
  *previous* session's result and looks like a bug in whatever you were testing.
- **`--tunnel.auto-trigger=false`** if you want to drive sessions yourself; otherwise one is already
  open and yours is rejected.
- **Do not test S2 with the carrier left on.** See §1. It looks exactly like a dead reader.

---

*CM4 session, 2026-08-27.*
