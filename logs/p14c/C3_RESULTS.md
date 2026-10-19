# P14-C.3 RESULTS: the ev1 attribution on the direct interface (2026-10-19)

Status: **read complete, closed as an attribution NULL**. The P13's reading — "the mechanism
endpoints are the ones the heads carry" (`logs/p13/B_RESULTS.md` line 32) — is **refuted**: all
three ablations reproduce the full movement, so the carrier is the **plain fine-tune itself**,
not the event heads, not the transition loss, not the 6 epochs.

## 1. The design (what was compared)

All runs: the direct interface, the W7-B pin (`FRUIT_POLICY_TRIGGER=arrival`,
`..._LEAD=0.9`, `FRUIT_DYNAMIC_PICK=1`, `FRUIT_SUPPLY_SCATTER=0`, `FRUIT_POLICY_TRIGGER_LATERAL=0.06`),
`FRUIT_ACQ_DIAG=1`, seed 77, 15 episodes, camera 240,424, checkpoint runtime verified.
The C.2 ablations are 6-epoch fine-tunes **from `moe_v13s`** on `datasets/demos_v12` +
`datasets/demos_v11` base (`--lr 5e-5 --weight-mode ones`), identical to ev1's recipe except
the two flags (`logs/p14c/IMPLEMENTATION.md`):

| arm | ckpt | flags | role |
| --- | --- | --- | --- |
| A | `moe_v13s` (`61da390a`) | — | the un-fine-tuned control (P13's A record reused) |
| B | `ev1` (`c2656cc2`) | heads=1, tw=1.0 | the P13 treatment (P13's B record reused) |
| A1 | `ev_a1` (`0c18f6be`) | heads=1, tw=0 | the heads without the transition loss |
| A2 | `ev_a2` (`74a58e4a`) | heads=0, tw=1.0 | the loss without the heads |
| A3 | `ev_a3` (`275e06f9`) | heads=0, tw=0 | **the plain 6-epoch fine-tune** |

## 2. The table (the C.3 read; `logs/p14c/read_c3.py`, `logs/p14c/50_c3_read.txt`)

| run | outcome | left close-start \|y\| med / p90 | left chases (195t+) | no-contact (L) | carried-not-placed | ticks med (ok) |
| --- | --- | --- | --- | --- | --- | --- |
| A `moe_v13s` | 10/15 | **178.2 / 275.0 mm** | 4 | 5 | 0 | 1799 |
| B `ev1` (full) | 9/15 | **4.3 / 5.4 mm** | 1 | 1 | 5 | 1808 |
| A1 heads-only | 9/15 | **4.0 / 5.0 mm** | 1 | 1 | 5 | 1817 |
| A2 loss-only | 10/15 | **5.1 / 5.3 mm** | 1 | 1 | 4 | 1772 |
| A3 plain 6-epoch | 11/15 | **3.0 / 4.9 mm** | 1 | 2 | 2 | 1820 |

Outcomes at N=1 per arm (9–11/15 across all five) sit in the known single-sample band; the
**mechanism endpoints are large-margin** (178 mm vs 3–5 mm; 5 vs 1–2 no-contact) and are the
read of record, per the standing rule (one seed = one branch; quote mechanism, not rate deltas).

## 3. The verdict

1. **No single factor carries the movement.** A3 (both flags off — a plain BC top-up) reproduces
   the acquisition collapse (178.2 → 3.0 mm), the chase reduction (4 → 1), the no-contact
   reduction (5 → 2) and the class redraw toward carried (0 → 2). A1/A2 sit on the same values.
   The P13's heads-attribution is refuted on this interface.
2. **The carrier is the plain fine-tune step** — 6 more epochs of behaviour cloning on
   `demos_v12` (a 158/158 success-only store whose windows all carry the scripted handover's
   tight close-start geometry). Continued BC tightens the policy's handover; nothing about the
   event-head architecture is required.
3. **The class redraw is the conserved-mass pattern again**: every arm that tightens the
   acquisition moves failure mass into the carried class (A 5 nc / 0 carried → B/A1 1/5,
   A2 1/4, A3 2/2). The mechanism movement does not reduce the total failure mass.
4. **The reverted event-heads code (`e078f43`) stays reverted** — correctly: no measured
   mechanism value on these endpoints, and the movement is not code-specific (it reproduces
   with both flags off). The P14-A canary anomaly's suspicion attached to that code therefore
   has no mechanism support here; its residual sample difference remains unidentified.
5. **The P13's ev1 checkpoint keeps its role only as a record**, not as a candidate: A3 (the
   simplest form) is its equal on every endpoint measured here.

## 4. Caveats

* N=1 per ablation arm (seed 77); the A/B controls are the P13's own seed-77 records (env
  byte-matched: the A arm reproduces the P13's 178.5 mm median to 0.3 mm).
* The `[acq]` diag is pure reporting (established run-neutral in earlier phases); all five runs
  carry it.
* The A3 tails still carry the reach-cliff flail class (max |y| 1024.9 mm; B 853.2) — the
  tails are not abolished by any arm.
* This closes the attribution question only; the outcome side (whether a top-up's class redraw
  is net-positive) remains governed by the standing N=5 paired protocol and is not claimed here.

## 5. Provenance

* Runs: `logs/p14c/B_ab/{A1,A2,A3}_1.log` (C.2), controls `logs/p13/B_ab/{A,B}_1.log`.
* Trainings: `logs/p14c/{A1,A2,A3}_train.log`, driver `logs/p14c/00_driver.log`
  (A1 0c18f6be, A2 74a58e4a, A3 275e06f9; restore verified md5-exact).
* Read: `logs/p14c/read_c3.py` → `logs/p14c/50_c3_read.txt`.
* Tree: `tasks.py` `3d88408d` (the P17-B default-off knobs present and inert), `rl_env.py`
  `60f46236`; the P13 policy code restored (model.py `89000266`).
