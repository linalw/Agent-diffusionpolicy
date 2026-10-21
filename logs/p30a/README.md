# logs/p30a - P30-A: the belt's side rails (2026-10-21/22)

Read in this order:

| file | what it is |
|---|---|
| `RAILS_DESIGN.md` | the census of every rail box, the grasp/place/supply envelopes, where the interference is, and the change |
| `RESULTS.md` | the arms (probes, acceptance, two-line patch battery, the viable-lift pair) and the verdict |
| `rails_geometry.py` | the offline re-derivation of every geometry number; `--assert` pins 16 clearances |
| `population.py` / `population.txt` | the release/clearance population over all `logs/` (the catch-ledge reading) |
| `compare.py` | the `[fruit]`-stream byte-identity check (drops the rail audit row and, with `--physics-only`, the attempt book-keeping) |
| `summarise.py` | one table per log: outcome, cadence, place clearance, worst place leg, release bins |
| `run_p30a.sh`, `run_lift.sh`, `run_lift2.sh` | the batch drivers (all runs go through `scripts/154_claim_run.sh` + `scripts/run.sh`) |
| `A4A5_place_legs.txt` | the A4/A5 place-leg extraction from the accept.sh pass, kept because the `04`/`05` log names were later overwritten; `06b`/`07` reproduce it leg for leg (see `RESULTS.md` section 5) |
| `selfcheck.log` | `scripts/selfcheck.sh` on this tree: PASS, 0 failures |

Arms: `01`/`02`/`03` = acceptance (control / `FRUIT_OUTPUT_RAILS=outer` / `+lift 0`);
`06b`/`07` = the viable-lift pair (`lift 0.04`, rails both / `outer`; `06` is a warm-up crash);
`10`-`13` = the
`47_robot_collision.py` probes; `20`-`23` = the two-line patch battery, SEED=11, 20 attempts
(control / `outer` / `outer`+lift 0 / lift 0).

**Provenance warning**: `04_accept_lift040.log` and `05_accept_rails_outer_lift040.log` hold a
concurrent lane's *plain control* repeats (its driver dropped its env arguments), not the
lift-0.04 arms; their `_gate_acceptsh.txt` siblings and `A4A5_place_legs.txt` are the real A4/A5
record, and `06`/`07` are the clean re-runs.
