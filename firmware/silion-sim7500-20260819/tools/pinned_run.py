"""pinned_run.py - run a Silion vendor script unmodified, with ModuleAPI.Create pinned to /dev/ttyAMA0.

    python3 tools/pinned_run.py probe/read_app_flash.py
    python3 tools/pinned_run.py mcu/upgrade_mcu.py

Ours, not vendor. Used for the production flash dump 2026-09-11.
The vendor Create() falls back to probing every /dev/tty* when the typed address does not answer;
on the v2.1 carrier that includes /dev/ttyAMA3, the SAMD21 power supervisor. Here the script exits instead (code 2 no answer, 4 wrong address)."""
import os, runpy, sys
script = os.path.abspath(sys.argv[1])
sys.path.insert(0, os.path.join(os.path.dirname(script), '..', 'lib'))
sys.argv = [script]
import ModuleAPI as M
def pinned_create(addr=None, *a, **k):
    cfg = M._parse_manual_serial_address(addr.strip()) if isinstance(addr, str) and addr.strip() else None
    if cfg is None or cfg[0] != '/dev/ttyAMA0':
        print(f'[pinned_run] refusing address {addr!r}: only /dev/ttyAMA0 is allowed'); raise SystemExit(4)
    rdr = M._TryConnectSerial(cfg[0], cfg[1], mode='manual', printtime=False)
    if not rdr or isinstance(rdr, str):
        print('[pinned_run] /dev/ttyAMA0 did not answer - NOT falling back to a port scan'); raise SystemExit(2)
    return rdr
M.Create = pinned_create
os.chdir(os.path.dirname(script))
runpy.run_path(script, run_name='__main__')
