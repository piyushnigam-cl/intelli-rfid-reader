#!/usr/bin/env python3
"""fw_probe.py - identity probe for the Silion SIM7500 before and after a firmware update.

Laptop draft 2026-09-11. Tested only against canned frames, NOT yet against a module.

Uses the vendor's own ModuleAPI.py (../lib, unmodified). Sends QUERY commands only:
  0x0C layer, 0x05/0x03 version, 0x10 serial, AA04 Impinj version, AA40 06 00 baud,
  AA40 04 00 power-on-to-APP flag.
The one exception is --to-app, which sends 0x04 (start the application) when the module is
sitting in its bootloader - e.g. after read_app_flash.py, which leaves it there.

Deliberately does NOT use ModuleAPI.Create(): when a typed address does not answer, Create()
falls back to probing EVERY /dev/tty* at every baud - on the v2.1 carrier that includes
/dev/ttyAMA3, the SAMD21 supervisor. This script tries the one port it is given and stops.

usage:  python3 fw_probe.py [/dev/ttyAMA0[:115200]] [--to-app]
exit:   0 = module answered, 2 = no answer, 3 = answered but something needs attention
"""
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', 'lib'))
import ModuleAPI as M  # noqa: E402  (vendor module, path set above)

# Firmware date as reported (0x05 bytes 13..16, BCD) -> MCU build in the 2026-08-19 package.
# The mapping is by date only (INFERRED: our modules report 20260330 and a 2026-03-30 build exists).
KNOWN_MCU_BUILDS = {
    '20250118': 'V1.0.2 MiniTP 2025-01-18 (GEN2 line)',
    '20250714': 'V2.1 MiniTP 2025-07-14',
    '20251127': 'V2.2 MiniTP 2025-11-27',
    '20260129': 'V2.2.2 MiniTP 2026-01-29',
    '20260330': 'V2.2.2 MiniTP 2026-03-30  <- what every module we own shipped with',
    '20260509': 'V2.2.2 MiniTP 2026-05-09',
    '20260612': 'V2.2.2 MiniTP 2026-06-12',
    '20260807': 'V2.2.2 MiniTP 2026-08-07',
    '20260819': 'V2.2.2 MiniTP 2026-08-19  <- TARGET of this kit',
}
TARGET_MCU_DATE = '20260819'
TARGET_IMPINJ = '2.02.02'   # ex10_app_2.2.2.bin; ASCII version string at file offset 164
AUTOBOOT_ON = bytes.fromhex('A5A55A5A')


def parse_port(argv):
    port, baud = '/dev/ttyAMA0', 115200
    for a in argv:
        if a.startswith('/dev/'):
            if ':' in a:
                port, b = a.rsplit(':', 1)
                baud = int(b)
            else:
                port = a
    return port, baud


def ext_query(rdr, code, data):
    """Send an AA-extended query; return the raw reply or b'' on a non-zero status."""
    M.DataTransport(rdr, M.build_command(code, data))
    r = bytes(M.DataReceive(rdr) or b'')
    return r if len(r) >= 7 and M.check_zero(r[3:5]) else b''


def main(argv):
    port, baud = parse_port(argv)
    to_app = '--to-app' in argv
    attention = []

    print(f'== fw_probe on {port}:{baud}')
    rdr = M._TryConnectSerial(port, baud, mode='manual', printtime=False)
    if not rdr or isinstance(rdr, str):
        print(f'NO ANSWER on {port}:{baud}.')
        print('  Is the tunnel service stopped and no java left holding the port (pgrep -x java)?')
        print('  v2.1 carrier: the service ExecStopPost drops RFID_EN - re-raise it:')
        print('    pinctrl set 8 op dh; pinctrl set 9 op dl; pinctrl set 22 op dh; pinctrl set 10 op dh')
        print('  Do NOT run the vendor upgrade scripts until this probe gets an answer.')
        return 2
    try:
        layer = M.GetLayer(rdr, P=False)
        if layer == 0x11 and to_app:
            print('module is in its BOOTLOADER; --to-app given, sending 0x04 ...')
            layer = M.SwitchToAPPLayer(rdr, timeout=5, P=True)
        layer_name = {0x12: 'APP (0x12)', 0x11: 'BOOTLOADER (0x11)'}.get(layer, f'UNKNOWN (0x{layer:X})')
        print(f'layer            : {layer_name}')

        ok, _, raw, hw_idx = M._GetVersionRawInfo(rdr, P=True)
        if not ok:
            print('version query failed')
            return 3
        raw = bytes(raw)
        print(f'version reply    : {M.Bytes2HEX(raw, sep=" ")}')
        fw_date = raw[13:17].hex()
        print(f'fw date          : {fw_date}  ->  {KNOWN_MCU_BUILDS.get(fw_date, "NOT a build in this package")}')
        # Bytes 9..12 are the hardware-version field the Java SDK reports. Its third octet is the
        # auth (certification) region - MEASURED 2026-09-07 on the production module: 31.00.00.80
        # under auth RG_PRC, 31.00.0E.80 after the write to RG_IN. Vendor table: 00 CHINA, 0E INDIA.
        ver = raw[9:13]
        auth = M.CertificationRegionCodes.get(ver[2], 'not in vendor table')
        print(f'hw version field : {M.Bytes2HEX(ver, sep=".")}   (bench 31.00.00.80; production 31.00.0E.80 since 09-07)')
        print(f'auth region      : 0x{ver[2]:02X} = {auth}   (3rd octet; must be unchanged by a flash)')
        if hw_idx != 9:
            hw = raw[hw_idx:hw_idx + 4]
            print(f'hw descriptor    : {M.Bytes2HEX(hw, sep=".")}   (offset {hw_idx}; what the vendor tool names the module from)')
        print(f'module name      : {M.GetModuleName(rdr, P=False)}   (vendor tool naming)')
        print(f'serial number    : {M.GetModuleSerialNumber(rdr, P=False)}')

        if layer != 0x12:
            attention.append('module is not in APP - Impinj version, baud and power-on flag need APP; '
                             're-run with --to-app')
        else:
            impinj = M.GetImpinjVersionFromModule(rdr, P=False)
            print(f'Impinj E710 fw   : {impinj}  (kit carries {TARGET_IMPINJ})')
            b = M.Getbaudrate(rdr, P=False)
            print(f'stored baud      : {b or "unknown"}')
            if b and b != 115200:
                attention.append(f'module baud is {b}, not 115200 - the Java app will not connect')
            r = ext_query(rdr, 0xAA40, [4, 0])
            flag = r[-6:-2] if r else b''
            print(f'power-on -> APP  : {M.Bytes2HEX(flag, sep=" ") or "unknown"}  '
                  f'({"yes" if flag == AUTOBOOT_ON else "NO - after a power cycle it will sit in the bootloader"})')
            if flag and flag != AUTOBOOT_ON:
                attention.append('power-on-to-APP flag is off')

            print('-- verdict')
            print('  MCU app    : ' + ('already on the target build' if fw_date == TARGET_MCU_DATE
                                      else f'{fw_date} -> run mcu/upgrade_mcu.py'))
            print('  Impinj E710: ' + ('already 2.02.02 - SKIP impinj/upgrade_impinj.py' if impinj == TARGET_IMPINJ
                                      else f'{impinj} -> run impinj/upgrade_impinj.py AFTER the MCU step'))
            if fw_date not in KNOWN_MCU_BUILDS:
                attention.append('fw date is not a MiniTP build in this package - STOP, ask Silion which line this module takes')
        for a in attention:
            print('  ATTENTION  : ' + a)
        return 3 if attention else 0
    finally:
        try:
            rdr.close()
        except Exception:
            pass


if __name__ == '__main__':
    sys.exit(main(sys.argv[1:]))
