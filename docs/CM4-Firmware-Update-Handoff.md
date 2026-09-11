# LAPTOP → CM4: update the SIM7500 to Silion's 2026-08-19 firmware, over the serial port

**Direction: laptop → CM4.** Written 2026-09-11 from the vendor package alone — **nothing here has
touched a module.** Claims are tagged **MEASURED** (our own earlier hardware runs), **READ** (vendor
Python source, which is exactly what their `.exe` tools are built from) or **INFERRED**.
Kit: `firmware/silion-sim7500-20260819/` (its `README.md` maps every file to the vendor original).
**Revised 2026-09-11** after pulling the 09-07 CM4 work: the production module's auth region is now
`RG_IN`, and that turns this update into the `RG_IN` test (§0, §6).
**Reviewed on the production CM4 2026-09-11**, before any module was touched: kit checksums pass,
`python3-serial` 3.5 and `tmux` are installed, and every vendor function `fw_probe.py` calls exists in
`lib/ModuleAPI.py` (its connect sends only a `0x03` version query). Three corrections from that review
are folded in: the port is not locked (§3.1, §5), and on the production unit the antenna select and
the RSSI baseline must be ANT2/J25 (§3.1, §3.7). **The same day the production baseline was probed**
(§3.2). That corrected two more draft expectations: the module powers up in its bootloader with the
autoboot flag off, which is normal here (§3.2, §3.6). And the family warning appears only if the
upgrade script starts with the module in APP (§3.4).

## 0. The short version

- **What changes:** the module's MCU application, from V2.2.2 build **2026-03-30** (what every module
  we own reports: sw `20.26.03.30`) to V2.2.2 build **2026-08-19**. The Impinj E710 chip firmware is
  probably already `2.02.02`, the version this package carries — the probe confirms, and if so that
  step is skipped.
- **How:** on the CM4, over `/dev/ttyAMA0` at **115200**, using Silion's own Python upgrade scripts,
  unmodified. No Windows tool can do it: on the v2.1 carrier the module's UART goes only to CM4
  GPIO14/15 and the USB flash path was removed from the board.
- **Order: there is only one board.** The laptop draft said to flash the bench dev-board module
  first. **Operator, 2026-09-11: the production CM4 is the only board in use**, so there is no
  bench module to go first. This unit is both the trial and the target, and the §3.3 flash dump is
  the whole of the safety margin. It proves the family, and it is the byte-exact backup of what this
  module runs today, alongside the `rollback/` image. Treat every "bench" line below as not
  applicable. The `RG_IN` answer could only ever come from this module anyway, because it is the only
  one whose auth region has been written to `RG_IN`.
- **Gate:** the vendor script's own sanity check will very likely warn that our module takes a
  *different* firmware family. §2 explains why, and step 3.3 is the flash dump that settles it. Do not
  click through that warning without the dump.
- **Don't:** use the 921600 "quick upgrade" tool; leave the address prompt blank; flash over a bare
  SSH session; power-cycle during a write. §5.
- **This is the test the `RG_IN` question is waiting for.** On 2026-09-07 the production module's
  auth region was written from `RG_PRC` to `RG_IN` (its hw string now reads `31.00.0E.80`), and
  `RG_IN` was *still* refused as an operating region on sw `20.26.03.30`. CLAUDE.md left one open
  question: does the operating whitelist need new module firmware? This is new module firmware, so
  **the region scan on the production module after the flash is the most important result here**
  (§3.7, §6).

## 1. What is in the package

**READ.** Two firmware components, two transports:

| Component | Vendor name | How it is written |
|---|---|---|
| Module MCU application | 模块单片机 · `EX10_HC_APPV…_MiniTP_<date>.bin` | Silion bootloader. `0x09` resets into the bootloader, `0x01` writes 128 B per packet from **`0x08008000`**, `0x08` verifies a 4-lane byte sum over the image, `0x04` starts the application. |
| Impinj E710 firmware | 英频杰芯片 · `ex10_app_<ver>.bin` | Relayed **by the running MCU application**: extended command `AA54`, 228 B per packet, `AA54 FF` commits. Written in APP, not in the bootloader. |

Four release lines, each pairing an MCU build with an E710 build: `1.1` (folder labelled GEN2) and
`2.1`, `2.2`, `2.2.2` (labelled GEN2X). The 2.2.2 folder holds six MCU builds from 2026-01-29 to
2026-08-19; Silion renamed every one except 08-19 to `.bin1`, because their tool flashes the first
`.bin` it finds in its own folder. **There are no release notes.**

The `.exe` files are PyInstaller builds of the scripts in `Python3源码_可以忽视` ("Python source — can
be ignored"). For us that source is the only usable path. `ModuleAPI.py` handles Linux explicitly
(`/dev/ttyAMA*`, `address:baud` syntax) and needs only `python3-serial`, already in the bring-up
apt list. `alive_progress` is optional; it falls back to a text progress bar.

## 2. Is this the right firmware family for our module?

Silion ships two MCU families: **MiniTP/SMD** and **SIMx100/SMP**. Flashing the wrong one leaves a
module whose application does not run.

For MiniTP:
- **MEASURED:** both modules reported hw `31.00.00.80`, sw `20.26.03.30`. The production module has
  read `31.00.0E.80` since its 2026-09-07 auth-region write: the third octet is the auth region, and
  the string still ends `0x80`.
- **READ:** the vendor tool treats a hardware version ending `0x80` as a new-style module whose real
  descriptor sits later in the `0x05` reply. In its bootloader-start path, a module whose version
  reads `…80` is classed as MiniTP.
- **INFERRED:** `20.26.03.30` is the firmware-date field, and this package contains a MiniTP V2.2.2
  build dated exactly 2026-03-30. The MiniTP 2.2/2.2.2 file names list "新版本SIMX500" (new-version
  SIMx500), our module family.

Against it: **READ, and reproduced here against the vendor function.** When `upgrade_mcu.py` starts
with the module in APP, it checks the module's self-reported name against a list containing only
`'SIMx500新'`. A module that calls itself `SIM7500…` fails that list, and the script then warns:

> `警告:当前模块更像应使用SIMx100/SMP字样固件,但所选文件名不匹配` — "this module looks like it takes
> SIMx100/SMP firmware; the chosen file name does not match"

That is most likely the tool's naming table rather than a real mismatch. "Most likely" is not good
enough for an irreversible write, though. **Step 3.3 settles it:** read the current application out of
flash and compare it with the 2026-03-30 MiniTP build. If they are byte-identical, the module is
running the MiniTP line, the warning is cosmetic, and you proceed. If they are not identical, stop and
send Silion the probe output.

## 3. Procedure — once per module

Kit on the CM4: `~/rfid/intelli-rfid-reader/firmware/silion-sim7500-20260819` (after `git pull`).
Everything below runs **inside `tmux`**. The scripts are interactive, and a dropped SSH session kills
a write halfway through.

### 3.0 Kit
```bash
cd ~/rfid/intelli-rfid-reader && git pull
cd firmware/silion-sim7500-20260819 && sha256sum -c SHA256SUMS
command -v tmux || sudo apt install tmux     # on the production CM4 since 2026-09-11; check the bench rig
tmux new -s fw
```

### 3.1 Free the port, power the module
```bash
sudo systemctl stop intelli-rfid-tunnel      # production; bench: stop whatever holds the port
pgrep -x java                                # must print nothing
fuser -v /dev/ttyAMA0                        # must print nothing
```
**These two checks are the only guard on the port. Nothing else will stop you.** **READ:** pyserial
on Linux takes no lock unless it is opened with `exclusive=True`
(`serialposix.py`: `if self._exclusive is not None: … flock`), and `ModuleAPI.py` never passes it. The
vendor's "port occupied" message (`被占用，拒绝访问`) matches Windows error text (`拒绝访问。`) and
cannot fire here. So with the tunnel JVM still up, the probe and the upgrade scripts **open
`/dev/ttyAMA0` anyway**. The two processes then take turns on each other's replies. For the probe that
is a confusing answer. **During a write it is a corrupted packet stream into flash.** If
`pgrep -x java` or `fuser` prints anything, stop there.

**v2.1 carrier only.** The unit's `ExecStopPost` drops `RFID_EN`, so stopping the service **turns
the module off**. Raise it again, in the usual order (antenna select, then EN, then NRST).
**Select ANT2/J25**, the branch the unit runs: J20 is 24 dB down (CLAUDE.md, "The RF path was NOT
dead"). The flash itself does not care, since no RF is keyed. But the select stays wherever this line
puts it through §3.6 and into the §3.7 measurements, and the service's own `ExecStartPre` selects ANT2.
```bash
pinctrl set 8 op dl; pinctrl set 9 op dh; pinctrl set 22 op dh; pinctrl set 10 op dh; sleep 0.2
#            ^^ V1 low        ^^ V2 high  = RF2 -> J25 (ANT2).  8 dh / 9 dl would be J20, the bad branch.
```
Bench dev board: nothing to do.

### 3.2 Probe — read-only
```bash
python3 probe/fw_probe.py /dev/ttyAMA0:115200 | tee probe-before.txt
```
**Production baseline, MEASURED 2026-09-11** (`probe-before-production-2026-09-11.txt` in the kit):

| field | production module |
|---|---|
| layer at power-up | **`BOOTLOADER (0x11)`**, and it stays there (re-probed a minute later) |
| power-on → APP flag | **`00 00 00 00` = off** |
| fw date | `20260330`, the V2.2.2 MiniTP 03-30 build |
| hw version field | `31.00.0E.80`, auth `0x0E INDIA` |
| hw descriptor (APP `0x05`, offset 25) | `31.70.00.20` |
| bootloader ver | `22.02.18.00` |
| module name | BOOT: `SIM7100,INDIA,80` · APP: **`SIM7500`** (see §3.4) |
| serial | `30262503F5` |
| Impinj E710 | `2.02.02`, already the kit's version, so **§3.5 is skipped** |
| stored baud | `115200` |

**The module powering up in its bootloader is normal on this unit, not a fault.** The flag is off, and
the tunnel has connected after every `RFID_EN` cycle it has ever had, each of which is a cold start
into the bootloader. So the Java SDK starts the application itself on connect. **Run the probe with
`--to-app` from the start**, which sends that same `0x04`. Without it, the Impinj, baud and flag lines
are not read.

The laptop draft expected `APP (0x12)` and power-on → APP `yes`. That was wrong for production. The
bench module is unmeasured; expect the same until its probe says otherwise.
Also expect the hw version field and auth region: bench `31.00.00.80` → `0x00`; **production
`31.00.0E.80` → `0x0E INDIA`**. Record that line, because §3.6 checks the flash left it alone. On
`NO ANSWER`, fix that before anything else. The probe talks only to the port it is given; the vendor
scripts do not (§5). On production, also run `ProbeAuthRead` (bench-probe) now, so there is an SDK-side
reading from before the flash to compare against.

### 3.3 Back up the application and prove the family
Mandatory on the first module; recommended on every module, because the dump doubles as a backup.
```bash
cd probe && PYTHONPATH=../lib python3 read_app_flash.py
#   请输入读写器地址(可留空自动搜索):  ->  /dev/ttyAMA0:115200      (never blank - §5)
#   ... reads from 08008000 until blank flash, writes <name>_<date>_<time>.bin here, runs a 0x08 verify
#   loops back to the address prompt -> Ctrl+C
D=$(ls -t *.bin | head -1); R=../rollback/EX10_HC_APPV222_MiniTP_2026-03-30-1729_V2.2.2.bin1
ls -l "$D" "$R"; cmp -n "$(stat -c%s "$R")" "$D" "$R" && echo "IDENTICAL over the 03-30 image"
cd .. && python3 probe/fw_probe.py /dev/ttyAMA0 --to-app     # the read leaves it in the bootloader
```
- `IDENTICAL` means proceed. If the dump is longer than the image, note the extra length. That is
  leftover flash from an earlier build, not a mismatch.
- A difference inside the image means **stop**.
- If the bootloader refuses the read, nothing is harmed but the proof is missing. Stop and get Silion
  to confirm in writing that hw `31.00.00.80` / fw `20260330` takes MiniTP.

### 3.4 Flash the MCU application
```bash
cd mcu && PYTHONPATH=../lib python3 upgrade_mcu.py
```
**Whether the §2 family warning appears depends on which layer the module is in when the script
starts.** **READ** in `upgrade_mcu.py` (`NeedMiniTPFirmware`) and checked against the production
baseline:
- **Started in BOOT:** the script reads the hardware field (`31.00.0E.80`), sees it end in `0x80`, and
  classes the module as MiniTP. So **no warning**. The name it prints there is `SIM7100,INDIA,80`,
  because `0x05` is unsupported in the bootloader and it decodes the short field instead. That
  `7100` is a naming artefact; don't read a family into it.
- **Started in APP:** it names the module from the `0x05` descriptor as `SIM7500` and normalises that
  to `SIMx500`. Its MiniTP list holds `SIMx500新` but not `SIMx500`, so **the SIMx100/SMP warning
  appears**. This is the naming-table gap §2 describes.

So the warning is evidence of neither family. The §3.3 dump still decides. After 3.3 the module is in
the bootloader anyway, so you can skip that `--to-app` and go straight into 3.4.
| It prints | Meaning | You |
|---|---|---|
| `请输入读写器地址(可留空自动搜索):` | reader address (blank = search everything) | `/dev/ttyAMA0:115200` |
| `模块名称:… 模块序列号:…` then `当前在BOOT` | name/serial, now in bootloader | — |
| `警告:当前模块更像应使用SIMx100/SMP…` + `是否继续[Y/n]:` | the §2 warning | Enter **only if 3.3 said IDENTICAL**, else `n` |
| `文件大小=249272字节` … `确认升级请按任意键…` + `是否继续[Y/n]:` | check model, serial, file; confirm | Enter |
| progress `x/1948` | writing | wait — **do not interrupt** |
| `升级完成` → `Successful CHECK_Firmware` → `首次进入APP Successful` | written, verified, application started | — |
| `写Flash升级更新固件APP应用层完成，已断开…` then the address prompt again | done | Ctrl+C |
| `升级失败，即将退出` or `Error CHECK_Firmware` | failed | §4 |

1,948 packets of 139 B each. At 115200 that is 12 ms of wire time per packet plus flash time, so
expect roughly 30–90 s (**INFERRED**).

### 3.5 Impinj E710 — only if the probe said so
If 3.2 printed `SKIP impinj/upgrade_impinj.py`, skip this step. Otherwise, **after** 3.4:
```bash
cd ../impinj && PYTHONPATH=../lib python3 upgrade_impinj.py
#   address -> /dev/ttyAMA0:115200
#   选中文件英频杰芯片版本:2.02.02,模块当前英频杰芯片版本:X 版本相同，可能无需升级 = same, no need -> n
#                                                        …不相同，可以升级        = different  -> Enter
#   988 packets; 最后一步，已发送AA 54 FF = last step, up to 5 s
#   成功升级2.2.2英频杰芯片固件完成(2.02.02名称一致2.02.02) = success, version re-read matches -> Ctrl+C
```

### 3.6 Power-cycle, then re-probe
```bash
pinctrl set 22 op dl; sleep 2; pinctrl set 22 op dh; sleep 0.3     # v2.1 (NRST stays high)
#   bench: pull the DC for 5 s
python3 probe/fw_probe.py /dev/ttyAMA0:115200 --to-app | tee probe-after.txt
```
Expect: **`BOOTLOADER` at power-up, exactly as before the flash** (production baseline, §3.2), then
`APP` after the probe's `0x04`. Also fw date `20260819`, baud `115200`, and power-on → APP still
`00 00 00 00`. And **the hw version field unchanged**: production still `31.00.0E.80` / auth `0x0E INDIA`, and
`ProbeAuthRead` agrees. If the third octet has gone back to `00`, the flash reset the auth region.
Stop and tell the user before restoring it with `ProbeAuthWrite -Dtarget=RG_IN`, because a
region-scan result from a module in that state means nothing.

**Do not run `tools/set_autoboot_app.py` just because it comes up in the bootloader.** The laptop
draft said the Java app would not connect to a module in that state. The production module has always
powered up that way, with the flag off, and the Java app connects every time. Setting the flag is a
change to module state that nothing needs, made in the same session as a flash, and it would muddy
any before/after comparison. **The real test is §3.7:** the tunnel service starts and reads. Only if
it cannot connect *and* the probe shows `BOOTLOADER`, set the flag: from the kit root run
`PYTHONPATH=lib python3 tools/set_autoboot_app.py`, enter the address, and at
`不自动→直接回车 / 自动→输入1并回车` type **`1`**. It ends with a `0x09` reset. Ctrl+C at the next
prompt.

### 3.7 Back into service, and re-measure what firmware can move
Restart (`sudo systemctl start intelli-rfid-tunnel` on production), then repeat the
`CM4-PRODUCTION-BRINGUP.md` step 8 probes and compare against the recorded baselines:
- **On the production unit, every `run.sh` line here takes `ANT=2`.** `run.sh` defaults to `ANT=1`,
  which is J20, the branch that is 24 dB down (CLAUDE.md). Region acceptance does not depend on the
  antenna, but the RSSI and tag-count lines below do. **A 3.7 run without `ANT=2` will look as if the
  new firmware cost 24 dB.** Bench: no `ANT=` needed.
- `ANT=2 bash run.sh Probe2 /dev/ttyAMA0 2700 1000` gives region acceptance. Before: bench `RG_EU3` only;
  production `RG_NA/EU3/PRC/OPEN`, unchanged by the 09-07 auth write. **Is `RG_IN` accepted now on
  the production module?** That is the headline result. On the bench module it proves nothing either
  way, because its auth region was never written. Use the SDK the unit currently runs (v260827). A
  probe against a stopped service must raise the four pins itself, which
  `/home/intelli-sbc/api/run/run.sh` does.
- Under `RG_EU3`, is the `{865700, 866300, 866900}` hop table still writable, and does it read back?
- What region does the module boot on after a power cycle? MEASURED on 03-30 (2026-09-07): it
  reverts to `RG_NA`, 902–928 MHz. A strings diff of the two builds shows a region label changing
  from `ETSI_LOWER` to `CHINA`, and what that means is **unknown**. Check the boot region again rather
  than assuming it is still `RG_NA`.
- Does rfMode still silently substitute 107 (`docs/RF-Modes-E710.md`)?
- RSSI baseline −26 dBm at ~30 cm and 20 dBm; 18/18 bench tags; temperature. **On production that
  baseline holds only on ANT2/J25**: measured −25 dBm there on 2026-09-07, against −49 dBm best on
  ANT1/J20 with the same tags unmoved. Compare ANT2 with ANT2, or the comparison measures the cable.
- `POST /api/acceptance/run` should return PASS.

## 4. If something goes wrong

- **Write fails partway** (`升级失败，即将退出`): the module is in its bootloader with a partial
  application. **READ:** writes start at `0x08008000` and never touch the bootloader below it. Leave
  the power on and re-run `upgrade_mcu.py`; it handles "already in bootloader". Its family check
  runs differently from the bootloader and may or may not warn. Your 3.3 result still decides.
- **Power lost during a write:** **INFERRED:** it comes back in the bootloader. The probe shows
  `BOOTLOADER`; re-run `upgrade_mcu.py`.
- **Roll back to 03-30:** rename `mcu/…08-19….bin` to `.bin1`, copy
  `rollback/…03-30….bin1` into `mcu/` as `…03-30….bin`, and re-run. After that, `mcu/` must hold
  exactly one `.bin`.
- **Impinj write fails:** the script says to redo the whole Impinj upgrade. Re-run
  `upgrade_impinj.py`.
- **Silent at 115200:** we never change the baud, but if anyone ran the 921600 tool, try
  `fw_probe.py /dev/ttyAMA0:921600`.

## 5. Do not

- **Do not use the `纯串口板快速升级` / `修改波特率921600+升级英频杰芯片+模块单片机` tool.** **READ:**
  it writes the module's *stored* baud to 921600, flashes, then writes the old baud back (that it
  restores it is what tells us the setting persists). Interrupt it and the module stays at 921600,
  and the 115200 Java app sees a dead module. v2.1 is also deliberately a 115200 board (RX desense).
  Staying at 115200 costs a minute or two.
- **Never leave the address prompt blank or mistype it.** **READ:** when a typed address does not
  answer, `ModuleAPI.Create()` falls back to probing **every** `/dev/tty*` at every baud. On v2.1
  that includes `/dev/ttyAMA3`, the SAMD21 supervisor that controls CM4 power. So run the probe first
  (it never scans), and start a vendor script only once the probe gets an answer.
- Do not flash over a bare SSH session. Use `tmux`.
- Do not write the auth region (`SpecParamsForReader` type 0 / `Ex/initregion`) as part of this.
  Production's is already `RG_IN`. The only exception is restoring it if §3.6 finds the flash reset
  it, and only after telling the user.
- Only one process on the port. A leftover JVM holding it looks like a dead module. **And on Linux
  the port is not locked (§3.1)**: a second process opens it without complaint, so the vendor
  scripts will write flash through a port the JVM is also talking on. `pgrep -x java` and `fuser`
  first, every time.

## 6. What this update will and will not settle

- **No changelog.** Ask Silion what changed between 2026-03-30 and 2026-08-19, and specifically
  whether it changes which regions a module accepts.
- **`RG_IN`: this is now the direct test.** MEASURED 2026-09-07 (CLAUDE.md): the production
  module's auth region was `RG_PRC` with hw `31.00.00.80`. After Silion's `SpecParamsForReader` write
  it is `RG_IN` with hw `31.00.0E.80`, and `ParamSet(RG_IN)` is still refused. Two things follow:
  - It confirms how the vendor tool reads the version field. Byte 2 is the auth region, and its table
    has `0x00` = CHINA and `0x0E` = INDIA.
  - It rules out the auth region as the remaining block on that module. What is left is the
    operating-region whitelist inside the module application, **which is exactly what this kit
    replaces**.

  **READ:** both builds contain the same region-name table, `INDIA` included, so any difference
  would be in logic rather than a table entry, and a strings diff cannot say which way it went. Only
  the scan can.
  - **Accepted:** record it, then decide with the user before touching site config. Radiated power
    under `RG_IN` is its own open question, and the EU3 + 3-channel hop table stays until `RG_IN`
    reads back.
  - **Still refused:** the question goes back to Silion with `probe-before.txt`, `probe-after.txt`
    and both scans.
- **Gen2X: READ.** Silion labels its 2.x E710 firmware lines "GEN2X", and our modules are on 2.2.2.
  So the chip firmware is Gen2X-capable in their own naming. Whether the SIM7500 *API* exposes
  Gen2X features remains the open question for Silion (`docs/Competitor-Analysis-Gen2-Tunnel-Readers.md`).

## 7. Report back — into `CLAUDE.md`, then push

```
SIM7500 firmware update, <date>, <bench|production>, serial <…>:
- before: fw <date>, hw field <…> (auth octet <..>), ProbeAuthRead <…>, Impinj <…>, baud <…>, power-on->APP <…>
- flash dump vs 03-30 image: IDENTICAL / differs at <offset> / read refused
- vendor family warning shown: yes/no
- MCU: OK in <s>   Impinj: skipped / OK in <s>
- after power cycle: layer <…>, fw <date>, hw field <…> (auth octet unchanged? y/n), baud <…>, power-on->APP <…>
- regions accepted: <list>   RG_IN: yes/no   boot region: <…>
- hop table {865700,866300,866900} under EU3: accepted & reads back yes/no
- rfMode 107 substitution unchanged: yes/no
- RSSI @30cm/20dBm: <…> dBm (baseline -26)   tags <n>/18   temp <…> C   acceptance PASS/FAIL
```
