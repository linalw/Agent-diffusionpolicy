### P30-A (2026-10-21/22, branch `p-supply`): the belt's side rails - the census says no rail touches the grasp, the one in the place path is a 35 mm ledge the transfer lift already clears, and the removal is delivered default-off with a measured 40 mm height cost

**The directive and the scope.** Owner: *"if the conveyor's side rails/edges interfere with fruit
grasping and placing, remove the belt's side rails/edges"* - rails/fences only, no frame, no slab,
and the scattered dynamic supply stays. The phase answers it with a geometry census, a
default-off removal/lowering knob, and the simulator arms.

**The census** (`logs/p30a/rails_geometry.py`, offline, `--assert` pins 16 clearances;
`logs/p30a/RAILS_DESIGN.md`). Eight rail-like boxes exist in the cell; three facts settle the
question. (1) The main belt's **frame rails** (`conveyor.py:266-277`, `main_frame_rail_width/
_offset`) are **outside the slab and carry no `CollisionAPI`** - render only. (2) The main belt's
**guide rails** (`conveyor.py:278-294`, `FRUIT_RAIL_HEIGHT` 0.075, `belt_channel_x` 0.13) are
**off by default** (`FRUIT_RAILS=0`, `assets.py:230`); their inner faces are at x=0.2095/0.4705,
so with them on the *supply band* (x=0.20-0.36) loses its lower 25-45 mm and the open hand
(+/-0.066) **overlaps the N rail by 15 mm** at a band-edge grasp. They were the original
interference and were removed in the v2 belt work (WORKLOG "why the belt got wider" line 701:
"the fingers were jammed against the rails at the open position and could never close"). (3) The
only **always-built rail colliders** are the raised output belts' four side rails
(`conveyor.py:573-611`): 25 mm thick, 50 mm tall, standing **35 mm proud of the belt top**, the
inner pair's outer face flush with the slab's inner edge (|y|=0.425).

**The grasp is not a rail problem - it is the slab, and that is out of scope.**
`scripts/47_robot_collision.py` (usage documented in `RESULTS.md` section 1) drives the jaw 0.35 m
straight down from the grasp pose: the jaw stops at z=1.229 (59 mm above the belt top) with both
finger boxes *inside the slab*, and the run is **bit-identical with the output belts absent, with
their rails present, and with the inner rail removed** (`logs/p30a/10/12/13`). With
`FRUIT_RAILS=1` it is a *different, worse* stop: 18 mm higher, 56 mm off in x, and the right
finger's final box (x to 0.493, z 1.182-1.254) **inside the P guide rail's box**
(`logs/p30a/11`) - the regression evidence for keeping that knob off. The descent shortfall of
`logs/166`/`167` is the belt slab, as before.

**The place: the rail is a transit constraint at +21..+54 mm and a landing ledge.**
The payload crosses y=0.4125 on every place transit; at the shipped transfer height
(`output_place_z + FRUIT_OPENARM_TRANSFER_LIFT = 1.53`) its lowest point is ~1.420, i.e. **+35 mm
over the rail top** (measured +31..+54 on `logs/692`, and +33..+55 on this phase's arms; no place
leg in four arms comes closer than +33 mm, and every negative row there is the escaped-payload
class at -215..-219 mm), and fingertips +61 mm. The lift exists *because*
the rail used to be swept (48 m/s², `logs/445`); at lift 0 the payload would be **-45 mm to the
rail top and -10 mm inside the slab**. The population read (all 10 195 `released at` rows in the
repo) says the rail is also a *catch ledge*: releases landing on its 25 mm top face (|y|
0.400-0.425, n=234) are **placed 96.6 %** of the time, releases inboard of it (n=552, 5.4 %)
only **47.6 %** - so removal would turn the rail band into gap releases, and the real place-path loss is
the *short* lateral release, not the rail.

**The change** (default = the shipped geometry, **byte-inert**): `FRUIT_OUTPUT_RAILS`
(`assets.py:340-348`, `output_rail_keep` at 516: `both`|`outer`|`inner`|`none`, validated in
`__post_init__`) and `FRUIT_OUTPUT_RAIL_HEIGHT` (`assets.py:349-355`, default 0.05). `OutputBelt.
build` authors the kept rails only, with the height; the default arithmetic reproduces the shipped
boxes exactly (`rail_bottom = output_belt_top_z - 0.015`, `centre = rail_bottom + h/2` = the old
`+0.01` at h=0.05) and the audit `say()` line prints **only when a knob is off its default**.
`scene.py` untouched. Byte-identity: the acceptance replays `logs/p28/noharm_accept.log`
**381/381** and the two-line patch battery replays `logs/p12a2/10_seed11_mass.log` **950/950**
(the tree also carries the P30-B `FRUIT_HOME_HUB` lane's uncommitted `tasks.py`/`rl_env.py`/
`20_pick_place.py` changes, untouched here and inert at their defaults - which is what those two
replays demonstrate).

**The runs** (`logs/p30a/RESULTS.md`, all via `154_claim_run.sh`+`run.sh`, same tree).
Acceptance (baseline 7/10): control **7/10**, 15.1 s/attempt, `fingerprint: matches`
(`406745c5`), gate FAIL only on the 0.75 rate floor - the pre-existing P25-flip branch
(`logs/p28/CLOSE_OUT.md` item 7), not this phase; `outer` **8/10**, 15.2 s/attempt, budgets pass
but the fingerprint **differs** - a moved branch whose first differing row is a *placed* fruit's
post-release state, with the place legs' clearance unchanged (min +35 mm, zero rail skims in
both). Two-line patch battery (SEED=11, 20 attempts; baseline 11/20): control **11/20**, 9.5
s/attempt, 3.47 fruit/min; `outer` **11/20**, 9.5 s/attempt, 3.47 fruit/min, per-arm 5/6 -> 3/8
and `diverted` 3 -> 2 (a moved branch, first differing row a release x of 0.666 vs 0.688); supply
unchanged (`queue_peak=0`, `recirculated=0`, same `[supply]` pool line), the same 10 placed fruit
reach the tray in both. The **viable-lift pair** isolates the contact: at `lift=0.04` the payload
is 5 mm under the rail's top and 30 mm over the slab, and rails-on reads **18-20 m/s² on the
3/9 place legs that go below the rail** against **4.0-7.6 m/s²** with the inner rail removed -
**same rate, 6/9 both** (the `-9/-7/-4 mm` rows in the rail-free arm have *no* jolt, which is
what proves the metric alone cannot claim a contact). The lift-0 arms fail on the **slab**, not
the rail: acceptance `outer`+lift0 **3/10** (|a|max 37.2 m/s², payload released at z=0.58/0.81),
battery `outer`+lift0 **4/20** vs rails+lift0 **3/20**, both 8.6-8.8 s/attempt.

**The verdict**: grasp - no rail interference, and the slab is out of scope; place - the inner
rail is a +21..+54 mm transit constraint at the shipped lift and costs **~40 mm of transfer
height** when it is lowered (measured as the 18-20 m/s² contact), while it is also a
96.6 %-effective ledge for short releases; so **no shipped-default change** (the shipped lift does
not need the 40 mm and the A4/A5 pair is rate-neutral), the knobs are the operator option, and the
named residuals are the short lateral release (P3 territory) and P3's "0.375 inner edge" that does
not exist (the real edges are the slab at 0.425 and the rail's inner face at 0.400 -
`RAILS_DESIGN.md` section 4).
