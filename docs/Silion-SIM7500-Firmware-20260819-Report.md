# SIM7500 firmware update 20.26.03.30 → 20.26.08.19 — before and after

**For Silion.** Prepared by Intelli RFID engineering, 2026-09-11. All results were measured on one
module on the day. Where there is no "before" figure for this module, the table says so rather than
borrowing one.

## Summary

- Flashed with the 2026-08-19 MiniTP package, using your Python upgrade script over UART. Clean.
- **`RG_IN` is now accepted as an operating region.** On 20.26.03.30 it was refused
  (`MT_CMD_FAILED_ERR`), even after the authentication region had been written to `RG_IN`.
- **The operating-region whitelist opened from 4 regions to 26.** Please confirm whether that is
  intended for a module whose authentication region is INDIA (question 2).
- Everything else we checked is unchanged: identity, authentication region, Impinj firmware, baud,
  power-on behaviour, and the RF-mode fallback.

## Module and setup

| | |
|---|---|
| Module | SIM7500, serial `30262503F5` |
| Hardware version | `31.00.0E.80`. The authentication region was written to `RG_IN` on 2026-09-07 with `SpecParamsForReader(0, true, …)` (was `31.00.00.80` / `RG_PRC`) |
| APP descriptor | `31.70.00.20`, name `SIM7500` |
| Bootloader | `22.02.18.00` |
| Impinj E710 | `2.02.02` (already the package's version, so not flashed) |
| Host / link | Raspberry Pi CM4, UART `/dev/ttyAMA0`, 115200 baud |
| Java SDK | API-java-v260827 (`jarVersion:260730_v3.8.3.4r-soVersion:20260611`) |

## Update procedure

1. Read the current application out of flash (`读Flash固件APP应用层.py`) and compare it with
   `EX10_HC_APPV222_MiniTP_2026-3-30-17.29-V2.2.2`. **Byte-identical**: 237,908 bytes, MD5
   `dedff3132d75281d2aebb19103986141`, and `0x08` verify OK.
2. Flash `EX10_HC_APPV222_MiniTP_2026-8-19-15.53-V2.2.2` (MD5 `8ae95254be2bd26e590a3d03cd8f0447`)
   with `升级模块单片机固件.py`, started with the module in the bootloader. 1,948 packets in 79.3 s,
   `CHECK_Firmware` OK, first entry to APP in 653 ms.
3. Power-cycle the module (`EN` low for 2 s) and re-read identity, authentication region and the
   region scan.

## Before and after

| Item | Before: 20.26.03.30 | After: 20.26.08.19 | |
|---|---|---|---|
| Firmware date / sw version | `20260330` / `20.26.03.30` | `20260819` / `20.26.08.19` | changed |
| Hardware version | `31.00.0E.80` | `31.00.0E.80` | same |
| Authentication region (`SpecParamsForReader` type 0 read) | `RG_IN` | `RG_IN` | same |
| Bootloader / APP descriptor | `22.02.18.00` / `31.70.00.20` | `22.02.18.00` / `31.70.00.20` | same |
| Impinj E710 firmware | `2.02.02` | `2.02.02` | same |
| Stored baud | 115200 | 115200 | same |
| Layer at power-up / autoboot flag | bootloader / `00000000` | bootloader / `00000000` | same |
| **`RG_IN` as operating region** | **refused**, `MT_CMD_FAILED_ERR` (tested twice, including as the first command after boot) | **accepted**, reads back `RG_IN` | changed |
| `RG_IN` hop table | — | `865100 865700 866300 866900` kHz | changed |
| **Operating regions accepted** (`ParamSet` + `ParamGet` read-back) | **4**: `RG_NA`, `RG_EU3`, `RG_PRC`, `RG_OPEN` | **26** (list below) | changed |
| Region after power-up | `RG_NA` | `RG_NA` | same |
| Custom hop table `{865700, 866300, 866900}` under `RG_EU3` | accepted, reads back | accepted, reads back | same |
| RF mode: invalid values (222, 999, 0) | `MT_OK_ERR`, silently become 107 | `MT_OK_ERR`, silently become 107 | same |
| RF mode: accepted values | not measured on this module | `101 103 105 107 111 112 113 115`, bare `203`, all 13 `0xFF000000 \| id` | — |
| Antenna return loss (VSWR) on a working antenna | not measured on a working antenna | 16 dB (VSWR 1.3767) on all four channels | — |
| Tag reading, application level | reading normally | reading normally: 30 tags, 0 read errors, acceptance PASS | same |

## Operating regions after the update

**Accepted (26):** `RG_NA` `RG_EU3` `RG_KR` `RG_PRC` `RG_OPEN` `RG_IN` `RG_JP` `RG_CE_HIGH`
`RG_HK` `RG_TAIWAN` `RG_MALAYSIA` `RG_SOUTH_AFRICA` `RG_BRAZIL` `RG_THAILAND` `RG_SINGAPORE`
`RG_AUSTRALIA` `RG_URUGUAY` `RG_VIETNAM` `RG_ISRAEL` `RG_PHILIPPINES` `RG_INDONESIA`
`RG_NEW_ZEALAND` `RG_PERU` `RG_RUSSIA` `RG_JP2_LBT6` `RG_JP3_NLBT19`

**Refused (5):** `RG_EU` (2), `RG_EU2` (7), `RG_PRC2` (10), `RG_CE_LOW_HIGH` (30), `RG_LAOS` (33)

Before the update, with the same authentication region, only `RG_NA` (1), `RG_EU3` (8), `RG_PRC` (6)
and `RG_OPEN` (255) were accepted.

## Questions

1. What changed between the 2026-03-30 and 2026-08-19 builds? The package has no release notes. We
   are most interested in region handling.
2. With the authentication region set to INDIA, the module now accepts 26 operating regions,
   including `RG_NA`, `RG_KR` and `RG_JP`. Is that intended? For deployment in India we need a module
   that can only operate in `RG_IN`. How do we achieve that?
3. Does `RG_IN` enforce the Indian limits in firmware (maximum power, channel plan, dwell time), or
   is that left to the host? The module accepts 30 dBm under `RG_IN`.
4. The module still powers up on `RG_NA`. Is there a supported way to make `RG_IN` the power-on
   default, and what else does saving defaults change?
5. What does a bare RF-mode value of `203` select? And is it intended that unknown values return
   `MT_OK_ERR` and fall back to 107, rather than returning an error?
6. Does the module report antenna return loss in 1 dB steps? Every channel reads identically to
   seven figures (16.0 dB, or 6.0 dB on a faulty port).
7. Upgrade tool: in APP the module names itself `SIM7500`, which normalises to `SIMx500`. That is not
   in `NeedMiniTPFirmware`'s list (which has `SIMx500新`), so the script shows the SIMx100/SMP warning
   for a MiniTP module. In the bootloader it names itself `SIM7100,INDIA,80`. We confirmed the family
   by the flash dump before proceeding. Could the naming table be corrected?

Raw outputs are available on request: probe before and after, the flash dump comparison, the region
scans, the RF-mode scans and the acceptance runs.
