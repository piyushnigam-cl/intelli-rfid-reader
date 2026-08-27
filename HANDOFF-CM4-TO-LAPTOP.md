# Handoff: CM4 → laptop, 2026-08-27

**Direction matters.** `CM4-BENCH-HANDOFF.md` is the laptop talking to the CM4. This document is the
reply: the CM4 session reporting back to the design session on the Windows laptop.

You wrote the bundle; none of it had ever been compiled or run. It has now been run against real
hardware. **Everything below is observation, not inference.** Where it contradicts something you
wrote, the module is right.

Read this, pull the code (§1), then answer the questions in §8 so the tunnel app can start.

---

## 1. First: pull. Your working copy is behind.

All three repos are now on CodeCommit in `ap-south-1` and **your local copies do not have any of
this work**. Nothing here exists on your laptop yet.

| Repo | HEAD | What it is |
|---|---|---|
| `intelli-rfid-core` | `237ea27` | shared library — 4 new commits |
| `intelli-rfid-reader-test` | `925d4a6` | bench acceptance — 2 new commits |
| `intelli-rfid-reader` | `9584a42` | **new** — workspace docs only, ignores `apps/` |

```bash
# the two app repos: you already have these, they fast-forward
git -C apps/intelli-rfid-core          pull --ff-only origin main
git -C apps/intelli-rfid-reader-test   pull --ff-only origin main
```

The workspace docs repo is new — the project root was not a git repo before. `CLAUDE.md`,
`CM4-BENCH-HANDOFF.md`, `docs/` and this file live there now. To attach your existing root
directory to it without disturbing `apps/`:

```bash
cd <workspace root>
git init -b main
git remote add origin https://git-codecommit.ap-south-1.amazonaws.com/v1/repos/intelli-rfid-reader
git fetch origin
git checkout -f main          # its .gitignore excludes apps/, so your app repos are untouched
```

**Authentication:** IAM HTTPS Git credentials, generated per-user in the IAM console. Use your own —
they are not in this repo and must never be committed. Two things that cost time here:

- Those Git credentials authenticate **git operations only**. They cannot create a repository —
  that needs real AWS keys with `codecommit:CreateRepository`, or the console.
- Pushing to a CodeCommit repo that does not exist yet fails with `repository not found`, which
  reads exactly like an auth failure and is not one. Create the repo first.

`intelli-rfid-tunnel` and `intelli-rfid-wayside` **do not exist** — not locally, not in CodeCommit.
See §8.

---

## 2. The headline: the reader works, end to end

```
POST /api/acceptance/run  ->  200, verdict PASS

  connection    PASS  Connected to /dev/ttyAMA0
  module-info   PASS  MODOULE_NONE, firmware 20.26.03.30, 1 antenna port
  antenna-vswr  PASS  1 port within limits, worst VSWR 1.119
  tag-read      PASS  1 distinct tag, best RSSI -27
  tag-write     PASS  Wrote ...3E9D, verified, restored ...3E62
```

Read **and** write are proven on real hardware. The write test's restore was verified independently
afterwards by re-inventorying the tag with a standalone probe, so it is not the test trusting its
own read-back.

### Bench rig (standing — this is what "the reader" means in this document)

Vendor **SIM7500 "Develop Component A" dev board**, wired to the **CM4** over **`/dev/ttyAMA0`**,
powered by a **DC-DC converter**. Not the IntelliRFID v2.1 carrier: **one antenna port**, no SP4T
switch, no opto field I/O, no SAMD21.

Always run with `--rfid.reader.antenna-count=1`. The packaged default of 4 is for the v2.1 carrier.
The module confirms it: `logictype=MODULE_ONE_ANT`, `antports=1`.

### Baselines — record these, they are how ESD damage gets detected later

| Property | Value |
|---|---|
| SDK version | `jarVersion:260319_v3.8.2.3r-soVersion:20260611` |
| Hardware / software version | `31.00.00.80` / `20.26.03.30` |
| Min / max power | 500 / 3000 (5–30 dBm) |
| **RSSI baseline** | **-26 dBm** at ~30 cm, 20 dBm read power |
| **VSWR baseline** | **1.119** across all four channels |
| Temperature | 33 °C idle → 41 °C after a session of runs (force-stop is 90 °C) |
| Bench tag EPC | `8A8070003A1D00021F0C3E62` |

A ±3 dB RSSI shift against that baseline is the ESD-degradation signal, and it only means anything
because the distance and power are recorded with it.

---

## 3. Region: the module refuses `RG_IN` — but this is being solved by reflashing

The blocker that stopped the first read. Setting every `Region_Conf` in turn and reading it back
gives exactly one accepted value:

```
ACCEPTED: [RG_EU3 (8)]
everything else, RG_IN (4) included -> MT_CMD_FAILED_ERR / 0x10b FAULT_INVALID_REGION
```

- `MTR_PARAM_RF_SUPPORTEDREGIONS` returns `MT_INVALID_PARA` on this firmware. You cannot ask the
  module what it supports; it has to be probed by set-and-read-back.
- **`RG_IN` is region 4, not 7.** Region 7 is `RG_EU2`.
- Under `RG_EU3` the module hops **865.7 / 866.3 / 866.9 / 867.5 MHz**. The first three are inside
  India's 865–867 MHz band, so EU3 is a usable bench stand-in; 867.5 MHz is above it.

**Plan of record: this gets fixed by flashing the firmware, not worked around in software.** So:

> **Do not design around `RG_EU3`.** Keep `RG_IN` as the configured region for the tunnel and
> wayside apps. Treat EU3 as a bench-only override on this one dev board until it is reflashed.

Worth confirming separately whether production modules are ordered as an India SKU, so this is a
one-off and not a per-unit flashing step.

---

## 4. Three bugs found and fixed — all in code you wrote, all verified on hardware

### 4.1 The JNI library never loaded (`core`, launch-time)

`rfid.reader.native-lib-path` binds correctly and `NativeLibraryLoader` does `System.load()` the
`.so` successfully. **It still fails**, because the vendor's own class loads the library
independently:

```
com.uhf.api.cls.JniModuleAPI.<clinit>  ->  System.loadLibrary("ModuleAPIJni")
```

`System.loadLibrary` searches **only** `java.library.path`. A prior `System.load()` of the very same
file does not satisfy it. `new Reader()` throws `UnsatisfiedLinkError`, surfacing as HTTP **500**.

The comment at `ReaderSession.java:104` — *"Must happen before the vendor Reader class is touched at
all"* — describes a sequencing that cannot work on its own. **Not fixed in code**, because the
honest fix is in the launcher:

```bash
java -Djava.library.path=/opt/intelli/lib -jar <app>.jar ...
```

**This must go into every launch command, script and systemd unit for the tunnel app.** Fixing
`NativeLibraryLoader` to do it properly would mean mutating `java.library.path` and resetting
`ClassLoader.sys_paths`, which is fragile and not worth it.

### 4.2 `connect()` reported failure on a working reader — `d4ea1e5`

`ReaderService.connect()` called `session.startReading()` unconditionally. POLLED has no continuous
loop, so it threw out of a connect that had **already succeeded** — session open and usable, but
`POST /api/reader/connect` answered 409, which reads as a hardware fault.

Worse latent case: with `auto-start=true` — **the default for the tunnel app** — the connector
thread treated the throw as a failed connect and retried forever against an already-open reader.

Fixed: `connect()` returns after `open()` when `readMode == POLLED`. `/api/reader/start` still
throws for POLLED — asking for a loop in a mode that has none is a genuine state conflict and 409 is
right there.

### 4.3 Core's controllers 400'd on every unnamed `@RequestParam` — `1f234f3`

core has no parent pom by design, so it never inherited `<parameters>true</parameters>` from
`spring-boot-starter-parent` the way the apps do. Without it Spring cannot recover a parameter name
by reflection, and the endpoint fails **at request time** with HTTP 400 — code that compiles and
starts cleanly, then 400s on first use.

Four endpoints were dead across all three apps: `/api/tags/recent`, `/api/diagnostics/inventory`,
`/api/tags/ops/read`, `/api/tags/ops/lock`. It went unnoticed because the acceptance suite reaches
`inventoryOnce()` through `AcceptanceService`, never over HTTP.

**This one matters most for the tunnel app**, which is HTTP-facing by definition. Fixed in core's
pom; there is now a note in `CLAUDE.md` → Conventions saying it must stay.

### 4.4 VSWR reported 100 readings when 4 were real — `237ea27`

`checkAntennas()` iterated the vendor's fixed 100-entry array, so every report carried 4 real
readings plus 96 of `{frequencyKhz: 0, vswr: 0.0}`.

The cause was not padding needing trimmed — **`AntPortsVSWR` already carries a `frecount` field**
saying how many entries were filled, and it was not being read. Measured: `frecount=4`,
`vswrs.length=100`.

It also exposed a worse latent bug: on an empty sweep `worst` stayed `0.0`, and `0.0 <= vswrLimit`
is true, so **an antenna that returned no measurements at all was reported healthy** — a dead port
passing acceptance. Now returns unhealthy with `NaN`.

---

## 5. Corrected vendor SDK facts — fold these into your mental model

These are all in `CLAUDE.md` now, but they change how you write reader code:

- **`ParamGet(MTR_PARAM_FREQUENCY_REGION, ...)` takes a `Region_Conf[]`, not an `int[]`.** The vendor
  doc (`docs_en/doc_Dev_J_html/api_params.html`) says `int[1]` and is **wrong** — an `int[]` throws
  `ClassCastException` from inside `Reader.ParamGet`. `ParamSet` on the same parameter does accept a
  bare `Region_Conf`, which is what core passes.
- **`AntPortsVSWR.frecount`** tells you how many of the 100 `vswrs` entries are real. Read it.
- **`TAGINFO.Frequency` is in kHz** (`865700` = 865.7 MHz). This is how the EU3 channel plan was
  established — genuinely useful, not just diagnostic noise.
- **`GetHardwareDetails` reports `module=MODOULE_NONE`** (vendor's spelling) on a perfectly healthy
  module. Not an error; do not code a check against it.
- `TagInventory_Raw(int[] ants, int antcnt, short timeoutMs, int[] outCount)` then `GetNextTag(TAGINFO)`
  per tag works exactly as core already uses it. Confirmed.

Everything else in your SDK notes held up.

---

## 6. Working process on the CM4 — two things that will bite you if you assume otherwise

**Long-running processes are not reliably manageable from Claude Code on this box.** A backgrounded
JVM gets killed at tool-call boundaries, and `pkill -f '<app-name>'` matches the wrapper shell and
kills that instead (exit 144). The working patterns are: run app + drive it + stop it **inside a
single command**, or ask the operator to start and stop it in their own terminal.

**Prefer one-shot Java programs over a server for diagnostics.** `apps/intelli-rfid-reader-test/tools/bench-probe/`
holds three, with a `run.sh` that sets `-Djava.library.path` for you:

| | What it does |
|---|---|
| `Probe.java` | Region enum wire values, module identity, current region, power range, temperature. Passive — never transmits. |
| `Probe2.java` | Region acceptance scan by set-and-read-back, then inventory sweeps printing EPC / RSSI / frequency. **Transmits.** |
| `Probe3.java` | Whether `AntPortsVSWR.frecount` is populated. |

These are what produced the first tag read and every measured number in this document. Reach for
this shape first when you need a hardware answer.

Also: **`git` was not installed on the CM4** and now is (2.39.5). Environment as found — JDK 17,
Maven, `libModuleAPIJni.so` in `/opt/intelli/lib`, user in `dialout`, `enable_uart=1`,
`dtoverlay=disable-bt`, serial console off, `/dev/ttyAMA0` free — all already correct. `/etc/intelli/`
does not exist, so no site config overrides are in play.

One non-bug worth knowing: **`/api/tags/recent` returns `[]` in POLLED mode.** The recent buffer is
filled by the dispatcher off the continuous read loop, and POLLED has none — `inventoryOnce()` hands
tags straight back to the caller. Expected, not a regression. It will behave differently in the
tunnel app, which will not be POLLED.

---

## 7. What is NOT tested

Be blunt about the gap, because it is large and it shapes what the tunnel app can be verified
against here:

- **Multi-antenna anything.** This board has **one** antenna port. Antenna switching, per-antenna
  power, the SP4T, `MTR_PARAM_READER_CONN_ANTS` across several ports — all unexercised.
- **Continuous / fast read modes.** Everything above ran in `POLLED`. `startReading()`, the JNI
  callback path, the bounded queue, the dispatcher thread, SSE streaming, drop counting under
  overload — **none of it has ever run**. This is the single biggest untested area and it is exactly
  what the tunnel app depends on.
- **Multi-tag populations.** Every test used one tag. Q tuning, session/target behaviour, dedup
  windows, a 40-article box — untested.
- **Field I/O, opto inputs, the v2.1 carrier** — not present on this board.
- **The API-key security package.** It compiles and its unit tests pass; it has never been exercised
  over the wire. `reader-test` sets `rfid.security.enabled: false`.

---

## 8. What I need from you: how to start `intelli-rfid-tunnel`

`apps/` on the CM4 contains only `intelli-rfid-core` and `intelli-rfid-reader-test`. There is no
tunnel source here, no tunnel repo locally, and no `intelli-rfid-tunnel` repo in CodeCommit.

Please reply with a handoff covering:

1. **Does tunnel source already exist on your side?** If you have drafted it, push it and tell me
   the repo name — I will create the CodeCommit repo (I have Git credentials but *not* AWS API
   credentials, so someone must create the repo in the console first; say if you can). If it does
   not exist, say so and give me the structure to build from scratch.

2. **The read path.** Tunnel needs continuous inventory, which as noted in §7 has **never run**. What
   `read-mode` should it use — `NORMAL`, or one of the fast modes? Given Ex10 and Impinj fast modes
   are mutually exclusive and sticky, which is the intended default and why?

3. **Session lifecycle concretely.** `CLAUDE.md` says settle is measured from the last *new* EPC with
   a minimum-duration guard. I need the actual numbers to start with, plus how you want them derived
   from real data later: settle window ms, minimum session duration ms, RSSI threshold, dedup window.

4. **`expectedTags`.** Where does it come from — supplied by the third-party WMS on session open,
   looked up, or configured? This is what separates "population settled" from "nothing is missing",
   so I want to get its plumbing right first rather than retrofit it.

5. **The third-party API contract.** What does the WMS call, and what does it get? Is it polling,
   SSE, or a callback on session close? Is `rfid.security.enabled` on for tunnel (core defaults to
   true) and what scopes does the WMS key need?

6. **Commissioning.** Tunnel also writes warehouse tags. Same `writeEpc` path as the acceptance
   test, or a different EPC scheme?

7. **What to verify first, given one antenna.** Realistically I can test: continuous read mode
   coming up at all, the callback → queue → dispatcher path, SSE, session open/settle/close logic,
   and commissioning writes — all with a **single antenna and a handful of tags**, not a 40-article
   box moving through a portal. Tell me what a meaningful first bench milestone looks like under
   that constraint, and what has to wait for real tunnel hardware.

Answer 1–3 first if you want to keep it short; that is enough to start.

---

*CM4 session, 2026-08-27. Every number in this document was measured on the module, not inferred.*
