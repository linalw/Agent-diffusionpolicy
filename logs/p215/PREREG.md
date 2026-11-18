# P215 pre-registration - a size-dependent direct clamp on the small-fruit class

The residual success class is the 3.0-3.4 cm fruit. The head estimate on a 3.1 cm lychee
is **1.74-2.13 mm** (P214), so the small fruit is not a perception problem; the grip is.
The direct real-jaw spec is 60 N, which is the large-fruit setting; a 3 cm fruit at 60 N
may be squeezed out. `FRUIT_FINGER_MAXFORCE_DIRECT_SMALL` overrides the cap only for
fruit at/below `..._SMALL_DIA` (default 0.040 m); 0/unset is the global cap.

**Cell.** A lychee-only supply (`FRUIT_SUPPLY_SPECIES=lychee`, all 3.1 cm), P207 R5
recipe, seed 808, 6 episodes per arm: control small cap **60 N** (= the global 60) and
treatment **20 N**. The global cap stays 60 in both; only the small-fruit branch differs.
The cell is a class mechanism, not the shipped mix.

**Endpoints.** Placed count (report only), the `[drive]` row proving the 20 N cap, the
`[grip]`/`[close]` force and span, and the carry outcome. Falsifiers: F1 the small cap does
not appear in the `[drive]` row (not armed); F2 the count falls by 2 or more; F3 the
tension force drops below the 9.7-9.9 N plateau with no count gain. A pass earns a
seed-303 repeat and the mixed pool; no default is flipped.
