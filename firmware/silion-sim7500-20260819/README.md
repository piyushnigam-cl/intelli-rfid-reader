# Silion SIM7500 firmware kit — package dated 2026-08-19

**How to use it: `docs/CM4-Firmware-Update-Handoff.md`.** This file only says what is here.

Built 2026-09-11 on the laptop from the vendor package
`Silion/固件升级20260819_MiniTP贴片/` (untracked; the `.rar` is beside it). Only the V2.2.2
MiniTP line is carried, because that is what our modules run. Files were renamed to ASCII;
**contents are byte-identical** (MD5s below match the vendor's own table in `ModuleAPI.py` for the
Impinj file). Vendor Python is unmodified apart from git's LF normalisation.

| Kit path | Vendor original | MD5 |
|---|---|---|
| `mcu/EX10_HC_APPV222_MiniTP_2026-08-19-1553_V2.2.2.bin` | `2.2.2_GEN2X_模块单片机_MiniTP贴片/EX10_HC_APPV222_MiniTP_2026-8-19-15.53-V2.2.2 新版本SIMX500-新旧版本SIMX600-X800-X900贴片模块-SIMX110双口模块固件.bin` | `8ae95254be2bd26e590a3d03cd8f0447` |
| `impinj/ex10_app_2.2.2.bin` (reports `2.02.02`) | `2.2.2_GEN2X_英频杰芯片_IMPINJ/ex10_app_2.2.2.bin` | `07387ffe66580c96b8de8640903c4ca9` |
| `rollback/EX10_HC_APPV222_MiniTP_2026-03-30-1729_V2.2.2.bin1` — the build our modules shipped with | same folder, `…2026-3-30-17.29-V2.2.2 ….bin1` | `dedff3132d75281d2aebb19103986141` |
| `lib/ModuleAPI.py` | `Python3源码_可以忽视/其他源码_可以忽视/ModuleAPI.py` | — |
| `mcu/upgrade_mcu.py` | `…/升级模块单片机固件.py` (module MCU upgrade) | — |
| `impinj/upgrade_impinj.py` | `…/升级英频杰芯片固件.py` (Impinj chip upgrade) | — |
| `probe/read_app_flash.py` | `…/读Flash固件APP应用层.py` (read the application out of flash) | — |
| `tools/set_autoboot_app.py` | `…/上电默认自动切换APP应用层.py` (power-on-to-APP flag) — only if needed | — |
| `probe/fw_probe.py` | **ours**, read-only identity probe | — |

`SHA256SUMS` covers the three images: `sha256sum -c SHA256SUMS`.

Layout is load-bearing: each vendor upgrade script flashes **the first `.bin` in its own folder**,
so `mcu/` and `impinj/` must each hold exactly one `.bin`. The rollback image is `.bin1` so nothing
picks it up by accident — the same trick Silion used for their retired builds. Run vendor scripts
with `PYTHONPATH=../lib`.
