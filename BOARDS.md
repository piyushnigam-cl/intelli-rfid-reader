# Which board is this? — run this first, every session

Every CM4 in this project checks out the **same workspace at the same path**
(`~/rfid/intelli-rfid-reader`), under the **same user** (`intelli-sbc`), with the **same prompt shape**,
the **same `CLAUDE.md`** and the **same memory directory**. Nothing in the files tells you which
board you are on. Only the board can tell you.

That has already cost us. On 2026-09-29 a whole session on `intellisbc2` (the SAMD21 flash, its
UART pins, a wayside run) was recorded as `intellisbc`, and three pushed commit messages still say
so. On 2026-10-10 a session on `intellisbc2` opened with a to-do list for `intellisbc`.

## Step 1 — identify, before reading anything else as "this unit"

```bash
hostname; hostname -I
tr -d '\0' < /proc/device-tree/serial-number; echo
systemctl is-enabled intelli-rfid-tunnel intelli-wayside-reader intelli-wms-test 2>&1 | paste -sd' '
grep -h 'reader-id' /etc/intelli/*/application.yml 2>/dev/null
```

Match the output against the table below. **If it does not match any row, stop and ask the
operator.** It may be a new board, a cloned image that still carries another board's hostname (the
suspected cause of the 10-03 mDNS conflict), or a row in this file that has gone out of date.

## Step 2 — say it, and keep saying it

- **Open your first reply with the hostname**: "On `intellisbc2` (wayside dev)…".
- **Every measurement written down carries the hostname.** That covers `CLAUDE.md`, `docs/`,
  memory, and `RESUME-NEXT-SESSION.md`, where each section heading already names the board.
- **Every commit message on a hardware finding names the board.**
- **Read `RESUME-NEXT-SESSION.md` for *this* board's latest section**, which is not always the top
  one. Sections from other boards are context and not your to-do list.
- When `CLAUDE.md` says "this unit" or "the production unit", it means **`intellisbc`** unless the
  text names another board.

## The boards

| | `intellisbc` | `intellisbc2` | `intellisbc3` |
|---|---|---|---|
| **Role** | **Production tunnel** (Reliance warehouse) | **Wayside development** (since 2026-09-29) | Tunnel reader, **being set up** (2026-09-28) |
| mDNS | **`intellisbc-3.local`** since 2026-10-03 (name conflict; `intellisbc.local` is broken) | `intellisbc2.local` | — |
| LAN IP (DHCP, can move) | 192.168.0.180 | 192.168.0.181 | — |
| CM4 serial | not recorded | `1000000058fd96b2` | — |
| `reader-id` | 1 | 2 (wayside: `intellisbc2-dev`) | 3 |
| SIM7500 serial | `30262503F5` | `30262503F8` | — |
| Module fw / auth | `20.26.08.19` / `RG_IN` | `20.26.08.19` / `RG_IN` | — |
| Enabled services | `intelli-rfid-tunnel` (:8081), `intelli-wms-test` (:8083), `openvpn-client@intelli` | `intelli-wayside-reader` (:8082). The tunnel unit is installed but **disabled**; the two conflict | — |
| Antenna | ANT2 / J25 (J20 is the bad branch) | ANT2 / J25 (J20 read 0 tags; whether an antenna was fitted is unknown) | — |
| SAMD21 (U21) | never probed | runs `intelli-wayside-reader-mcu` v1 | — |
| **sudo for Claude** | **No.** Hand privileged steps to the operator | **Yes, passwordless** (`/etc/sudoers.d/90-intelli-sbc-nopasswd`) | — |
| Who deploys | Operator runs `deploy/redeploy.sh` | Claude may deploy | — |
| VPN | yes (`10.8.0.40`) | none | — |

The laptop (Cowork, Windows) is the fourth seat. It has no module attached, and nothing measured
belongs to it.

## Keeping this file true

- **A board changing role, hostname, services, sudo or antenna updates its column here in the same
  commit.** That includes a tunnel being disabled or a module being flashed. A stale row is worse
  than no row, because it will be believed.
- **Adding a board means adding a column before its first measurement.** `export/setup-new-cm4.sh`
  sets the hostname and reader-id; copy them here. Fill in the CM4 serial from step 1, because it
  survives a reimage and a hostname does not.
- The IP is a DHCP lease and has moved subnets before. It is a hint only; the hostname and the CM4
  serial are the identity.
