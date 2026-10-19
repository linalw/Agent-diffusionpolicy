# P15 OUTCOME RESULTS (2026-10-19): the promoted M2 - the mechanism holds, the outcome loses (the carried-class trade)

The promoted arm: `FRUIT_CLOSE_CONTACT_LEAD=0.10` (the hold-window lead) on the mass base, the
outcome battery at seeds 11/11-double/5/23 (the Oracle's F4/F5 amendments: the seed-11
mechanism from the byte-identical Stage-M run; K3 at seed 11).

| endpoint | the mass base (control) | **M2** | reading |
| --- | --- | --- | --- |
| the pooled outcomes | **45/60** | **38/60 (-7)** | seed 11 11 -> 12; seed 5 17 -> **10**; seed 23 17 -> 16 |
| the falls (rows, the A2 convention) | 10 | **6** | down (seed 11 3 -> 1; 5 3 -> 3; 23 3 -> 2) |
| the no-grasp class (11/5/23) | 7/3/3 | **4/4/2** | down (the mechanism) |
| **the carried class** | 2/0/2 | **4/6/2** | **up - the trade: the seed-5 carried 0 -> 6** |
| the pooled interval | 14.29 s | 15.45 s (+8 %) | worse |
| the double (seed 11) | - | **bit-identical** (0 diff, 12/20) | K3 PASS |

**The verdict: NOT adopted.** The mechanism (the hold walk collapse, the no-grasp reduction,
the falls halving) is real and re-confirmed at the outcome level; but the gentler braked
capture **converts the failures into the carried-not-placed class** (the seed-5 0 -> 6; the
seed-11 2 -> 4), the pooled outcomes lose -7, and the interval worsens +8 %. This is the
**third instance of the same pattern** (the P11-C from-open: a mechanism win, a class re-draw,
a pooled loss) - the two-line's failure mass is a **conserved quantity** across the tested
close/carry actuators: the total failure count stays ~15, its composition moves.

**The named next (the pre-registered F7's flat branch, here outcome-negative)**: the M2 stays
opt-in (the knob remains a bare env read; a two-line-scoped default would need its own
pre-registration per `logs/p12b2/C_DECISION.md`); the published record is the mechanism win +
the carried trade; the next candidate is the **outcome-side residual - the carried class**
(the three instances' common residue), or the decision is owner-gated.

---

### CORRECTION (2026-10-19; the P17-B Oracle gate + a re-verification)

The control census in the table above (lines 11-12) is **wrong**: the on-disk mass base
(`logs/p12a2/{10_seed11,11_seed5,12_seed23}_mass.log`) reads no-grasp **7/0/1** (not 7/3/3)
and carried **2/3/2** (not 2/0/2). Re-verified from the unique `[run] attempt` rows:

| class (11/5/23) | control (verified) | M2 (verified) | delta |
| --- | --- | --- | --- |
| no-grasp | **7/0/1 = 8** | 4/4/2 = 10 | **+2** |
| carried | **2/3/2 = 7** | 4/6/2 = 12 | **+5** |
| ok | 11/17/17 = 45 | 12/10/16 = 38 | **-7** |
| total failures | **15** | **22** | **+7** |

So the M2 **lost pooled mass on every class** - it was **not** a "conserved trade": the total
failure count did not stay ~15 (15 -> 22), and the seed-5 carried moved **3 -> 6** (not 0 -> 6).
**The "conserved quantity" sentence (lines 21-22) is withdrawn on this evidence.** The surviving
readings are unchanged where they were measured on their own terms: the mechanism win (the hold
walk collapse, the falls 10 -> 6) is real, the outcome side degraded, and the carried class grew
under the lever. The same census error is corrected in `logs/p17/CAPTURE_LEVER_DESIGN.md` section
1.3 (line 144).
