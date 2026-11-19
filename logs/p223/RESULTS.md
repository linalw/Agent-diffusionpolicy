# P223 control - the left arm is the weak one, in the scripted line too

Same shipped scripted dynamic catch, seed 808, 6 attempts, only the grade mix changes:

| supply | arm | placed | forces |
|---|---|---:|---|
| B-heavy (A:0.10, B:0.80, C:0.10) | right | **6/6** | 9.96-15.58 N |
| A-heavy (A:0.80, B:0.10, C:0.10) | left | **1/6** | 10.15 / 5.55 / 9.73 N on the three grasped; 0 on two no-grasp |

The A-heavy failures are the **left large** class: kiwi/peach/lychee grasped but **not
placed** (lifts 0.106-0.246 m; one strawberry no-grasp at 28.33 N; one orange no-grasp at
0 N). The single success is a right-arm strawberry from the 0.10 B share.

**This corrects the "learned left" reading.** The learned left is ~70 %; the **scripted
left is 1/6 = 17 %** on this branch. The left is not a learned-policy deficit - the hand/
primitive itself is weak on the left large fruit. The right is the opposite: learned 2/6
(P212), scripted **6/6**. The **best per-arm route** is therefore **right -> scripted,
left -> learned** (`FRUIT_HANDOVER_SIDE=right` + learned left); the left 70 % is the system
cap, not the right switch. The P219 5/6 and P222 3/6 are the left-favourable and
left-unfavourable branches of that same route.

**The residual is the left pad/hand**, the hardware class the record's P42/P117/P129/P132
already closed on the geometry/friction/compliance axes. No software knob is indicated on
the left.
