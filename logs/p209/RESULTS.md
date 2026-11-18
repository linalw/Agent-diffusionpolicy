# P209 result - execute half the chunk is **negative** on this stochastic policy

The action-chunk rule "predict long, execute about half" does not transfer to a policy
whose chunk is a **fresh DDIM sample** at every re-plan. Seed 808, 6 episodes per arm,
same P207 R5 recipe, the only difference `--execute-steps`:

| arm | placed | emitted p95 / max | > 0.10 | requested p95 / max | residual p95 / max | binding |
|---|---|---|---|---|---|---|
| E4 (execute 4) | **4/6** | 0.101 / 0.182 | 5.2 % | 0.145 / 0.672 | 0.110 / 0.626 | 25.2 % |
| E2 (execute 2) | **2/6** | **0.182 / 0.182** | **15.5 %** | 0.335 / 2.574 | 0.409 / 2.021 | **45.4 %** |

The mechanism **moves the wrong way**: doubling the re-plan rate doubles the number of
chunk boundaries, and each boundary is a new stochastic sample. The emitted p95 rises
0.101 -> 0.182, the >0.10 fraction triples, the request-target residual p95 rises 4x, and
the cap binds 45 % instead of 25 %. The count is 2/6 against 4/6 (a branch, but the
mechanism explains the direction). **F1 and F2 fire: not adopted, no seed-303 repeat.**

The negative is useful: it says the remaining smoothness lever is not a shorter horizon
but **averaging the overlapping predictions** (ACT-style temporal ensembling) so a new
sample does not replace the old one at every boundary. That is P210's question; no
source change was made for P209, and the P207/P208 tree stands.
