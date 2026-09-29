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
