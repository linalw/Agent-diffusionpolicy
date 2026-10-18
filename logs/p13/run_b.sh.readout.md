# P13-B readouts (the Oracle's fix 4; run after the battery)

- The re-seat count: `grep -ac "re-seated on the moving fruit" logs/p13/B_ab/*.log` per arm.
  **Context**: the direct interface has produced 0 re-seat markers in every prior direct
  battery (the class is scripted-line only, R11-A); the kill is read on both arms' counts,
  with the flail/chase class (the R9's 6-vs-1) as the analogous degradation signature if the
  marker cannot fire.
- The 200-tick catch-up chase count: `grep -ac "catchup=200t" logs/p13/B_ab/*.log` per arm.
