### P30-C (2026-10-21/22, branch `p-supply`, Tier-C offline): the reachable pick station and the boundary-respecting descent — the premise is corrected with numbers (the pick pose is *inside* the band on the current tree and the 40-90 mm is v1 history), the station family is closed analytically (the elevation is invariant, the only non-null geometry is a ridge = the rejected nest), and the descent is down to the arrival settle + a 16.8 mm reporting bias

**The directive and the scope.** Owner: components **1** (a pick station the arm can reach) and
**3** (a boundary-respecting descent) approved; **any feeder/nest regularisation rejected** —
the scattered dynamic supply stays. Read-only lane: no simulator run, no `src/`/`scripts/`
`configs/` edit, no default changed, no commit; writes only under `logs/p30c/`.

**The premise correction (the phase's first finding).** On the current tree **both descending
lines already command a reachable pose**: the station ladder reads **3.9 mm** (left) / **6.0 mm**
(right) IK residual at the pick point (x = 0.34), clean to x = 0.39 and a cliff at x = 0.42
(55.3/55.2 mm; `logs/v1/61_station_reach_seeded.log`); the along-belt aim (station + 17.3 mm)
is **17.3 mm inside** the measured band on both arms
(`logs/r10/reach_intercept_{left,right}.json`); and the measured `end=` is **8.3-10.8 mm**
(dynamic acceptance, median 9.4, n = 10, `logs/p30a/01_accept_control.log`), **8.1-15.3 mm**
(the two-line mass base, median 9.2, n = 60) and **1.9-5.2 mm** (the current indexed line,
median 4.8, `logs/fast/16_accept_indexed_v7.log`). The AGENTS §2 / README "Every descent ends
40-90 mm short" is the **v1** record (`logs/160/161`: 40.4-89.7 mm, median 49.1, n = 20), whose
pre-grasp target was the **fruit's centre**; the current code sends the jaw to
`belt_top + grasp_clearance` (`tasks.py:8861`) and the dynamic catch to `fruit + 0.070`. The v1
shortfall decomposes as **|dz| median 34.0 mm + lateral median 14.3 mm** from the `align=` rows
— i.e. exactly the `finger_drop − r` term plus the fruit's station offset, and both are gone
from the command today.

**The reach deficit that survives is vertical and it is a *hand* term.** The measured jaw floor
is `belt_top + 0.0586` (`logs/p30a/10_probe_parts_default.log`, jaw z 1.2286; `logs/166` reads
`+0.0768`), the fruit's centre is `belt_top + r` (r = 14-35 mm), so a TCP target *at* the
fruit's centre is **23.6-44.6 mm** (P0) / **41.8-62.8 mm** (166) below the floor — and with the
belt removed the same drive reaches z = 1.049, **180 mm lower**, so the slab binds and the
joints/mount do not. The shipped aims clear the floor by **+26.4..+44.5 mm** (dynamic, measured on 180 logged
`fruit_z` rows; the r-range algebra reads +25.4..+46.4) and **+36.4 mm** (indexed).

**The station family is closed analytically.** Any uniform elevation Δ of the station surface
raises the fruit's centre *and* the jaw's floor by Δ, so the margin `finger_drop − r` is
**invariant** (the z-axis form of the P12-B.2 "the catch is fruit-relative" derivation) — this
is why a raised segment is catch-null before any run. The three hardware candidates: **S1 the
full-band raised segment** - null by the invariant (and its ramps are the obstruction class);
**S2 the partial-width deck** - measured negative (D3: battery **12/20 -> 1/20** x2,
`recirculated` **0 -> 13**, no-contact **2 -> 12**, flails **1 -> 11**, close-start y median
**-3.8 -> +142.0 mm**; the deck's 100 mm x-span leaves a 20 mm vertical face at x = 0.29 while
the fruit can be at x = 0.20); **S3 the narrow centre ridge** - the *only* support the fingers
clear (clearance requires < ~the fruit's diameter), and it **centres the fruit laterally**,
i.e. the rejected nest, with the record's own precedent (the 8 mm v2 `FRUIT_PICK_STOP` ridge at
x = 0.371) removed in v3 because it **gated** the fruit. **Pick: S3' — no new geometry**: the
station is delivered as a *measured reachable height* (`FRUIT_STATION_FLOOR` = 0.0586) + the
existing per-attempt `[boundary]` row + a clamp guard on any *pad-target* descent (a no-op on
both shipped lines). Falsifier: a measured-floor margin **< +6 mm** on the shipped band, a
finger-belt contact row, or a `47` stop below `belt_top + 0.0586`. The one *hardware*
successor is named and not picked: a **short-tip finger** (cut 24-45 mm off `finger_drop`),
which re-baselines the grip (R6-B/W8-B/S3/D2a) and is a phase, not a knob.

**The descent is down to two bounded residuals.** (R1) the **arrival**: the dynamic line
settles at 8.3-10.8 mm against the catch-up's 6 mm tolerance, so the post-descent solver always
starts short — the P16 (a) completed descent (`FRUIT_DYNAMIC_ARRIVE_TOL=0.006`,
`_MAX=24`; built, default off, `_arrive_hold` at `tasks.py:10650`) closes it in <= 24 ticks
(<= 24 mm of belt travel, 10-25 % of the ~96 mm capture window); expected `end=` median
9.4/9.2 -> **<= 6.0 mm**, the catch-up's first-row residual 14.6 -> <= 8, `|v|max` unchanged
(0.105-0.118 vs the 0.161 budget), the lurch bound unchanged. Its *value* is the P16 open
question (K1: the shortfall most likely does not feed the capture), and the phase is built so
that the negative is cheap and definitive. (R2) the **reporting**: `[boundary] belt_margin`
uses `FRUIT_FINGER_LEN` (60 mm) instead of the measured floor, so it is **16.8 mm optimistic**
at the 166 pose and prints **+24 mm** for the smallest fruit where the true clearance is
**+7.2 mm**; two further one-line row fixes ride the same arm (the aim reads -2.7 mm against
the code's 20 mm-inset band on *every* attempt although it is 17.3 mm inside the measured band;
and the right two-line station's station-relative frame shifts the printed number by 100 mm).

**The pre-registration (sketch, `STATION_DESCENT_DESIGN.md` §4).** Arms: C0 the control
(P30-A record: 7/10 acceptance, 11/20 battery), **S** the reporting arm (constant + row, must be
*bit-identical*), **D** the completed descent, **S+D**; scenarios A the acceptance (10), B the
two-line patch mass base SEED = 11 (20), C the indexed acceptance (`FRUIT_DYNAMIC_PICK=0`, the
clamp's predicted-null control). Endpoints: the dynamic `end=` median <= 6.0, the catch-up
residual <= 8, the achieved/commanded ratio 0.92-0.96 -> >= 0.97, the measured-floor margin
>= +6 mm, the indexed `end=` **unmoved**; the census/falls/total failure mass as the outcome
(class, not rate — the rate is one deterministic branch sample); the motion budgets gated only
where a budget exists. Kills K1 `end=` does not fall (publish the boundary's true edge), K2 a
class re-draw (>= +2), K3 a finger-belt contact, K4 a non-bit-identical double, K5 the no-harm
fails, K6 the clamp fires on a shipped path. No-harm: acceptance **381/381** byte-identical +
`fingerprint: matches` (`406745c5`), the patch battery **950/950** vs
`logs/p12a2/10_seed11_mass.log`, the dense re-record 442/442 + `190` PASS, `selfcheck.sh` PASS.
Cost **~1.5-2 h** Tier A solo, no scene build, no new asset.

**The strongest risk**: this closes the *sim*, not the *robot* — the pads are kinematic and
teleported, so the deficit is invisible in production only because the command was raised;
`finger_drop` (58.6-76.8 mm) > `r` (14-35 mm) is a **gripper** fact, and P30-C must not be
reported as "the pick station is delivered".

**Offline verification**: `logs/p30c/reach_geometry.py --assert` — **14/14 pinned numbers
hold** (the band edges, the aim's two margins, the deficit range, the floor's optimism, the
three `end=` baselines incl. the current indexed line). Pins as read: `tasks.py` `e27b18a4`,
`assets.py` `d820710d`, `conveyor.py` `c837f9a1`, `scene.py` `ab85dca2`, `rl_env.py` `59150f85`,
`fruits.py` `d28546d2`, `configs/waypoints.json` `d81c6f1c`; git HEAD `e1b9936`.
