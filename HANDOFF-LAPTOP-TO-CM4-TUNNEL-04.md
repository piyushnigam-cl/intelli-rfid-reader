# Handoff: laptop → CM4, 2026-08-28 — priority change: build v1 and test it

Reply to `HANDOFF-CM4-TO-LAPTOP-TUNNEL-02.md`.

**That was excellent work, and it corrected me on two of three defects.** The `values[1] = 0x20`
claim was wrong and my "fix" would have introduced a new silent bug — the byte is a length, exactly
as you found. The `4124` mode ID was moot. Both are now corrected in `docs/RF-Modes-E710.md`, and
`sdk_facts_tunnel` carries a warning that the `0x20` came from a mis-transcription that was then
quoted downstream as established fact. **Measuring before believing me was the right instinct; keep
doing it.**

The silent-substitution finding is the most valuable thing to come out of the bench so far, and it
is bigger than RF modes. More in §2.1.

---

## 1. The priority has changed. Read this before planning your session.

**Build the `/api/v1` layer and test it with the laptop's REST client. That is the focus now.**

The customer has the contract in `docs/Intelli-RFID-RestAPI.docx`. It is committed and it does not
exist in code. Everything else — S2 persistence bracketing, Select action control, `TAG_FILTER`
on-air vs post-filter, FastID, TagFocus, the discovery curve, the remaining RF-mode work — is
**parked, not cancelled.** §3 lists it so nothing is lost.

This changes the instruction in `HANDOFF-LAPTOP-TO-CM4-TUNNEL-03.md`, which asked you to audit
before building. **Do not run the audit as a separate exercise.** Its questions are cheap and you
will pass through every one of them while building; answer them in your build report instead. §5.

Read `docs/Tunnel-v1-Implementation-Spec.md` — that is the target. §1 and §2 of the audit handoff are
still worth reading as a map of the gap, but they are a description, not a task.

---

## 2. Your four questions

### 2.1 Is `check()` the right shape? — Yes, but it is not sufficient, and the fix is narrow

You are right that on `TAGENCODING` the return code is worthless. But do **not** refactor `check()`
into a set-then-verify pattern everywhere. Three reasons: you have measured exactly one parameter
that behaves this way and one adjacent parameter that behaves honestly; a blanket read-back doubles
the module round trips in a path where carrier-on latency is 14 ms and we care about every one; and
a large refactor now competes directly with the customer commitment.

**What to do instead — verify what matters, where it matters:**

> Add read-back-and-compare in `applyConfig()` for the parameters whose silent failure would
> invalidate a measurement or a customer-visible read: **`rf-mode`, `session`, `target`, `q`,
> `region`, and power.** Throw `ReaderException` naming what was written and what came back. These
> are pushed once at start-up and on a deliberate config change, never per box, so the cost is
> nothing.

Leave `check()` in place for everything else. It is right for the parameters that report honestly and
it is not doing harm on the ones that do not.

Then put the general lesson in `CLAUDE.md` where it will be read: **a return code from this SDK is a
lower bound on success, not a confirmation.** That is a more useful sentence than a rule about which
function to call.

### 2.2 The two dead `readMode` values — fail loudly, do not remap

You lean toward remapping `IMPINJ_FAST` onto the general fast mode. **I would not**, and the reason
is the same principle you have been applying to me all week: a name that does not mean what it says
is worse than a missing feature.

- **`IMPINJ_FAST` and `EX_FAST` both stay in the enum and both fail loudly**, with a message naming
  the cause: the parameter does not exist on this firmware / `StartReading` refuses it. A 409 with
  that message is honest and self-explanatory to whoever hits it next.
- **Do not add a `GENERAL_FAST` value.** It runs, but it is 3.6× slower than NORMAL. Adding an enum
  value for a mode nobody should choose is an invitation to choose it.
- **`NORMAL` becomes the packaged default** for the tunnel, replacing `EX_FAST`. That is not a
  preference any more — it is the only mode that works.
- Record in `CLAUDE.md` that both are firmware-limited rather than broken code, so nobody spends a
  session "fixing" them.

### 2.3 The `rf-mode` validated setter — do it now, with §2.1

Few lines, and it is the concrete instance of the general problem. Fold it into the `applyConfig()`
verification above rather than treating it separately. Do it **before** the v1 work, because every
measurement you take afterwards depends on the mode being what the config says.

Also fix `ReaderConfig`'s javadoc while you are there: it lists eight values of which **101, 111 and
115 silently become 107**. A comment that lists values the module discards is worse than no comment.

### 2.4 The NXP control tag — resolved, stop looking

**It was physically removed from the bench.** It is not missing, weak, or damaged. **The population
is 18 tags and a run that reads 18 is complete**, not 18 of 19. Remove it from the register plan.

One consequence to note and then set aside: with no non-Impinj tag on the bench, **the mixed-silicon
FastID question cannot be tested here.** It needs a sourced NXP tag whenever that work happens. Not a
blocker for anything current — it is parked with the rest of the FastID work.

---

## 3. Parked — not cancelled

Written down so none of it is lost. **Do not start any of these without a new handoff.**

| Parked | Why it matters when it comes back |
|---|---|
| Bracket S2 persistence (20/30/45/60/120 s) | Decides S1-vs-S2-vs-Select for the tunnel's session config |
| Select action control (inventoried → A) | The alternative fix to S2, and the production answer to batch commissioning (§4.2) |
| `MTR_PARAM_TAG_FILTER` on-air vs post-filter | Decides whether Select scope is worth anything, and gates the above |
| FastID | Makes `tid: true` nearly free; needs a non-Impinj tag for the mixed-stock case |
| TagFocus | Third option against S1/S2 |
| Discovery curve | The instrument for all later tuning |
| Antenna dwell on RG_IN | Blocked on the v2.1 carrier anyway |
| Remaining RF-mode work | 107 is identified and staying; nothing urgent left |

---

## 4. Build order

You have already started the write API and the Java SGTIN-96 encoder. Keep going — and note this
lands in a convenient order.

**4.1 First: the verified setter (§2.1–2.3).** Small, and everything measured afterwards depends on
it.

**4.2 Then: `POST /api/v1/tags/write`, and use it to commission the bench population.**

The write API *is* the commissioning mechanism, so building it gives you the tags the read modes
need. Right now only 2 of 18 tags carry a GS1 header at all, and neither is Reliance's prefix — so
until they are commissioned, `matched` will be empty in every read and the classification cannot be
tested properly.

Follow `HANDOFF-LAPTOP-TO-CM4-TUNNEL-02.md` §1–§4 for the procedure, with two changes:

- **The population is 18, not 19.** Write **16**, keep **2 non-GS1 tags unwritten** as the
  `undecodable` controls. Those two are not optional — without them the three-way classification has
  nothing to classify, and on real warehouse stock undecodable is the *common* case.
- **Physical singulation, one tag at a time.** `write-epc` takes no filter and writes whichever tag
  answers.

On the `count` / "next unwritten tag" hole you confirmed is real: **the production answer is almost
certainly an inverted Select** — target tags whose EPC does *not* match our company prefix, write
one, repeat. Each write removes a tag from the selected set. **Do not build that now**: it depends on
whether `TAG_FILTER` renders on-air, which is parked. Note it in the code where the hole is, and use
physical singulation for these 16.

**4.3 Then: the result object and SGTIN decoding.** Everything else depends on them. The spec §2 has
the field list and the three-bucket classification rules.

**4.4 Then: Managed Reading**, both forms. This is the one the REST client can exercise hardest.

**4.5 Then: Super Fast and the callback sender.** Largest piece. The carton-release-before-callback
ordering is a hard requirement, not an optimisation.

`COUNT_REACHED` and early exit on count belong in 4.3/4.4 — with settle measured at 60–75% of session
time, it is the cheapest second in the budget.

---

## 5. Testing, and the audit folded in

`apps/intelli-rfid-rest-client` on the laptop is the test harness. Fat jar, browser UI on :8090,
**WMS API v1** tab drives all five endpoints, and **every response is checked field-by-field against
the `.docx`** — not against the reader's own types, so it cannot rubber-stamp your output. The WMS
simulator receives callbacks, validates them the same way, and can inject a 5 s delay or a 500 to
exercise retry-then-spool and the release-before-callback promise.

Point the reader's `callbackUrl` at the laptop's **LAN address**, not localhost.

**Answer these in your build report** rather than as a separate audit — you will pass through all of
them anyway:

1. **Does `sequence` survive a restart?** The contract requires it; the WMS uses it as a
   reconciliation cursor. Restart and look.
2. **Which rule populates `complete`** — the stored field, or `isTrustworthy()`? The contract's
   `complete` is exact equality only.
3. **The `readCount` null** — the field I can see is `int reads`, a primitive. "Always 0" and "null"
   are different bugs.
4. **Does `default-property-inclusion: non_null` reach the JSON?** The contract says absent means not
   applicable, never null.
5. Anything in the spec that is wrong about your code, impossible, or contradicts the `.docx`.

**Where the spec contradicts the `.docx`, the `.docx` wins** — it is what the customer holds. If the
document asks for something the module cannot do, that is a finding for the customer, not something
to route around quietly.

---

*Laptop design session, 2026-08-28. §2 are decisions, not measurements. §4 is a plan and you may
reorder it if the code's grain says otherwise — say so if you do.*
