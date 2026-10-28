# P58 results — the direct supply profile (the four-cell ledger)

**Shipped:** `FRUIT_FEED_CADENCE`, `FRUIT_SUPPLY_BAND_INTERLOCK` (+ `FRUIT_SUPPLY_BAND_MAX=4`)
and `FRUIT_DIRECT_FEED` resolve **on for `presentation == "direct"` only**; an
explicit environment value wins. `FRUIT_DIRECT_CONTINUOUS` stays 0 (opt-in via
`--continuous N`). No motion reference moved; the scripted line, the handoff
presentation and the two-line scheduler are byte-unchanged.

## The cells (seeds 77/101/202, 15 picks each, the shipped per-pick interface)

| arm | `window` mean | `==1` | `==0` | starved rounds (`sel_gap>=169`) | final `skipped` | `on_belt` | wall s/pick |
|---|---|---|---|---|---|---|---|
| control (shipped, pre-P58) | 2.57 | 4/45 | 0 | 0/42 (by the reset's re-stock) | 104/107/105 | 5.2 | 29.66 |
| **A′ cap 3** | 2.02 | 12/45 | 0 | **1/42** | 41/36/39 | 9.2 | 34.07 |
| **A″ cap 4 (shipped)** | **2.38** | 9/45 | 0 | **0/42** | **8/4/9** | 11 | **35.40** |
| **A‴ interlock off** | 2.20 | 12/45 | 0 | **5/42 (169/380/170/289/291)** | 2/0/2 | 10.8 | 35.43 |

The registered branch rule (Oracle 1 re-review): B1 needs `window>=2.38` and no
starve → A‴ fails both; B2 (starves at least as often as A′) → **A‴ fires B2** with
5/42 vs A′'s 1/42 and A″'s 0/42; B3 unreached. **The unit is the triple at cap 4**;
**cap 3 is a measured regression** (the cap binds, refuses ~2.5 patch partners per
pick, thins the window 2.38 → 2.02 and starves 1/42).

## The two counter readings that must travel together

1. **`supply_skipped` is not the slot-loss counter on the non-bed path.** A
   depth-capped release does `_next_release = max(_next_release, sim_time + period)`
   and `break`s (`fruits.py:~2391`) **without** incrementing `supply_skipped`; the
   counted sites are the clear refusals and the patch's **partner-half** refusal.
   The loss surfaces as a **starved feed round** (`sel_gap >= 169`). That is why
   A‴ reads the *best* `skipped` (2/0/2) and the *worst* boundary (5/42).
2. **`on_belt` is not a catch metric.** `on_belt = admitted + below_window` holds
   on all 45 blocks; at cap 4 the below-station share is **6.24/block** (control
   0.20), i.e. 54 % of candidate rows are already past the 0.180 window floor.
   The catchable read is the `window` distribution.

The control's 2.57 is a **post-reset-burst instant** (one feed per episode, ~7
stale slots dropped per reset — the timed refresh the owner rejected), so it is
quoted as the rejected baseline, never as the composition bar.

## The wall

**+19.3 % (29.66 → 35.40 s/pick) at a flat simulated span** (1827 → 1824 ticks per
pick) = 0.01623 → 0.01941 s/tick with 6 → 12 live bodies. A **harness** cost, not
a cell-throughput regression: P55 measured the feeder alone at +11.1 % at constant
span, and P33 phase A the body physics at +24 % for 21 vs 6.6 live bodies. It is
reported, never gated, and never attributed to the policy.

## Validation on the final tree

| check | result |
|---|---|
| `scripts/selfcheck.sh` (+ the new `230_p58_supply_selftest.py` leg) | **PASS**, 0 failures |
| `scripts/accept.sh` (all knobs unset) | **6/10** (the recorded branch) + **`fingerprint: matches`**, `[fruit]` **377/377 identical** to the P41 profile-era record (`logs/p41/p2/accept_profile.log`, diff 0) — an **import guard**: the scripted path never constructs `SortingRLEnv` |
| two-line 10-attempt dense run + `scripts/190_towline_gate.sh` | **PASS** (matches `configs/motion_reference_twoline.json`, floor 0.60) |
| `scripts/211_bed_audit.py` | **ok** (115 checks) |
| direct smoke (2 episodes, `--record`) | `[supply] direct profile: cadence=on(default) band=on(4)(default) feed=on(default)`; manifest `supply` block present with `defaulted` all true and `continuous: 0` |

## Re-baseline

Every direct number measured before P58 is a **pre-profile (burst) number**;
`FRUIT_FEED_CADENCE=0 FRUIT_SUPPLY_BAND_INTERLOCK=0 FRUIT_DIRECT_FEED=0` restores
it (compose with `FRUIT_ARM_PARK=ready` for the pre-P43 and
`FRUIT_POLICY_TRIGGER_ACQ=0` for the pre-P54 baselines).

## Not covered (named, not closed)

`FRUIT_SUPPLY_BAND_MAX` 5–6; `FRUIT_SUPPLY_TARGET_FROM` 0.40 (the substitute for
the same cap); the two-line (its own `feed_pump`; `_feed_scope` excludes it);
the handoff presentation (inert); any store recorded under the profile; and the
hybrid canary (`60_eval_policy.py` builds its own spawner, so `moe_v12` is
untested under the profile).
