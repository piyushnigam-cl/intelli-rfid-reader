# Screenshot notes

One entry each time the operator says "see screenshot": the newest file in `~/screenshots` on the
board, transcribed. A copy of each image is kept in `docs/screenshots/`. Newest entries go at the
bottom.

---

## 2026-09-29 19:05: RFID tag data format (Table-3)

Source: `Screenshot 2026-09-29 190539.png` →
[`screenshots/2026-09-29-190539-rfid-tag-data-format.png`](screenshots/2026-09-29-190539-rfid-tag-data-format.png).
It is the train-set tag format for the Charkop wayside reader, as given by the operator. The table
names no source document; ask which one it comes from.

**Transcription** (SIZE is in hex digits):

| SL | Field | Size | Code | Remarks |
|---|---|---|---|---|
| 1 | TAG Masking | 3 | `8A8` | For masking the TAG info |
| 2 | LINE NO | 2 | 02, 07, 09 etc | LINE-2=02, LINE-7=07, LINE-9=09 etc |
| 3 | TRAIN SET NO | 4 | 0001, 0002 etc | Train set-1=0001, Train set-2=0002, Train set-59=0059 etc |
| 4 | CAR TYPE | 1 | A, B, C | DMC=A, TC=B, MC=C |
| 5 | CAR POSITION | 1 | 1,2,3,4,5,6 | DMC-1=1, TC-1=2, MC-1=3, MC-2=4, TC-2=5, DMC-2=6 |
| 6 | CAR SERIAL NO | 4 | 0117, 0122 etc | 0001, 0002, 0118, 0192 etc |
| 7 | CAR SIDE | 1 | D, E | D=DOWN LINE, E=UP LINE |

*Table-3: RFID tag data format*

**Checked against the five tags on the intellisbc2 bench the same evening:**

| EPC | Line | Set | Type | Pos | Side | Serial | Last 8 hex |
|---|---|---|---|---|---|---|---|
| `8A8020013A1D00021F0C5233` | 02 | 0013 | A (DMC) | 1 (DMC-1) | D | 0002 | `1F0C5233` |
| `8A8020008A1D00021F0C12E9` | 02 | 0008 | A (DMC) | 1 (DMC-1) | D | 0002 | `1F0C12E9` |
| `8A8020008A6D00021F0C11D6` | 02 | 0008 | A (DMC) | 6 (DMC-2) | D | 0002 | `1F0C11D6` |
| `8A8070003A1D00021F0C3E62` | 07 | 0003 | A (DMC) | 1 (DMC-1) | D | 0002 | `1F0C3E62` |
| `8A8070003A6D00021F0C3F9D` | 07 | 0003 | A (DMC) | 6 (DMC-2) | D | 0002 | `1F0C3F9D` |

Three differences between the table and the real tags. Settle them with whoever wrote the tags:

1. **On the tags, CAR SIDE (SL 7) comes BEFORE CAR SERIAL NO (SL 6).** In table order the serial
   would read `D000`, which is not a number. In tag order every field is valid. The decoder follows
   the tags.
2. **The table covers 16 of the EPC's 24 hex digits.** On every bench tag the remaining 8 digits
   equal the last 4 bytes of the chip's TID, so they make each EPC unique. The table does not
   mention them.
3. **Every bench tag has serial `0002` and side `D`**, whether it is a DMC-1 or a DMC-2. That may be
   bench test data rather than real car serials.

Consistent with the table: all five are type `A` (DMC), at position 1 or 6, which are DMC-1 and
DMC-2, the two ends of a six-car train. Line 02 set 0008 and line 07 set 0003 each have both ends
present.

---

## 2026-09-29 19:30: train set lookup (TS NO, ID-2, LINE NO)

Source: `Screenshot 2026-09-29 193015.png` →
[`screenshots/2026-09-29-193015-train-set-lookup.png`](screenshots/2026-09-29-193015-train-set-lookup.png).
It is a spreadsheet of 63 train sets in three column blocks. It is the lookup that turns a tag's line
and ID-2 into the train set number (operator, same evening). The machine-readable copy is
`apps/intelli-wayside-reader/src/main/resources/train-sets.csv`.

**Transcription**, in TS order (the third block writes LINE NO as `2`, the same as `02`):

| TS NO | ID-2 | LINE NO |
|---|---|---|
| TS01 | 001 | 02 |
| TS02 | 002 | 02 |
| TS03 | 003 | 02 |
| TS04 | 004 | 02 |
| TS05 | 001 | 07 |
| TS06 | 002 | 07 |
| TS07 | 003 | 07 |
| TS08 | 004 | 07 |
| TS09 | 005 | 07 |
| TS10 | 006 | 07 |
| TS11 | 005 | 02 |
| TS12 | 006 | 02 |
| TS13 | 007 | 02 |
| TS14 | 008 | 02 |
| TS15 | 009 | 02 |
| TS16 | 010 | 02 |
| TS17 | 011 | 02 |
| TS18 | 012 | 02 |
| TS19 | 013 | 02 |
| TS20 | 014 | 02 |
| TS21 | 015 | 02 |
| TS22 | 016 | 02 |
| TS23 | 017 | 02 |
| TS24 | 018 | 02 |
| TS25 | 019 | 02 |
| TS26 | 020 | 02 |
| TS27 | 021 | 02 |
| TS28 | 022 | 02 |
| TS29 | 007 | 07 |
| TS30 | 008 | 07 |
| TS31 | 009 | 07 |
| TS32 | 010 | 07 |
| TS33 | 011 | 07 |
| TS34 | 012 | 07 |
| TS35 | 013 | 07 |
| TS36 | 014 | 07 |
| TS37 | 015 | 07 |
| TS38 | 016 | 07 |
| TS39 | 017 | 07 |
| TS40 | 018 | 07 |
| TS41 | 019 | 07 |
| TS42 | 020 | 07 |
| TS43 | 021 | 07 |
| TS44 | 022 | 07 |
| TS45 | 023 | 02 |
| TS46 | 024 | 02 |
| TS47 | 025 | 02 |
| TS48 | 026 | 02 |
| TS49 | 027 | 02 |
| TS50 | 028 | 02 |
| TS51 | 029 | 02 |
| TS52 | 030 | 02 |
| TS53 | 031 | 02 |
| TS54 | 032 | 02 |
| TS55 | 033 | 02 |
| TS56 | 034 | 02 |
| TS57 | 035 | 02 |
| TS58 | 036 | 02 |
| TS59 | 037 | 02 |
| TS60 | 038 | 02 |
| TS61 | 039 | 02 |
| TS62 | 040 | 02 |
| TS63 | 041 | 02 |

Checked: 63 rows, TS 01 to 63 with none missing, and no (line, ID-2) pair used twice. Line 02 uses
ID-2 001 to 041, and line 07 uses 001 to 022, each exactly once.

**The rule, from the operator:** ignore any EPC not starting `8A8`. The next two characters are the
line (02 or 07), then ID-2; the lookup gives TS NO, and the TrainSetNumber is `TS` + TS NO. Example
given: `8A80 2003 8A6D` → **TS60**.

**The example fixes where ID-2 sits, and it is not the literal "next 3 characters".** After `8A8`
and `02`, the next three characters of that EPC are `003`, which is TS03. TS60 is line 02 with
ID-2 **038**. That is the last three digits of Table-3's 4-digit TRAIN SET NO field, which is
characters 6 to 9 (1-based) of the EPC (`0038`), so ID-2 = characters 7 to 9. The decoder follows
the example, reading the 4-digit field as a number. **Awaiting the operator's confirmation.**

**TrainSetNumber is `train.id` in the JSON** (operator, 19:33 the same evening).

The bench tags under that rule: `8A8020013A1D…` → line 02, ID-2 013 → **TS19**;
`8A8020008A1D…` / `…A6D…` → 02, 008 → **TS14**; `8A8070003A…` → 07, 003 → **TS07**.
