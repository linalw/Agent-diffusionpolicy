#!/usr/bin/env bash
# P111 - the compliant closure: the offline algebra, the battery, the no-harm.
#
#   bash logs/p111/run_p111.sh algebra   # the static model + the ladder (offline)
#   bash logs/p111/run_p111.sh replay    # C_s5 / R_s5, then the `--same` guard
#   bash logs/p111/run_p111.sh battery   # T1/T2/T4 x 4 seeds (+ S1 x 2)
#   bash logs/p111/run_p111.sh report    # the tables + the census
#   bash logs/p111/run_p111.sh noharm    # the acceptance with every knob unset
#
# Two or three Isaac instances can run at once (the sim is not GPU bound: 32 %
# utilisation, ~1 GB of 32 GB); each stream writes disjoint files.
set -euo pipefail
cd "$(dirname "$0")/../.."
OUT=logs/p111

case "${1:-report}" in
  algebra)
    python3 ${OUT}/algebra.py --check
    python3 ${OUT}/algebra.py | tee ${OUT}/algebra.txt
    ;;
  replay)
    bash ${OUT}/cells.sh C:5 R:5
    python3 ${OUT}/p111_report.py --same ${OUT}/C_s5.log logs/p108/S_s5.log \
        --drop '[cage],[cycle],[carry],place trace'
    python3 ${OUT}/p111_report.py --same ${OUT}/R_s5.log logs/p108/E_s5.log \
        --drop '[cage],[cycle],[carry],place trace'
    ;;
  battery)
    # R is P108's E arm; the replay above is what licenses the reuse, and
    # `R:202` closes the rigid arm at four seeds (P108 ran E at 5/6/101).
    bash ${OUT}/cells.sh R:202 T1:5 T1:6 T1:101 T1:202
    bash ${OUT}/cells.sh T2:5 T2:6 T2:101 T2:202
    bash ${OUT}/cells.sh T4:5 T4:6 T4:101 T4:202 S1:5 S1:6
    ;;
  report)
    python3 ${OUT}/census.py | tee ${OUT}/census.txt
    python3 ${OUT}/p111_report.py ${OUT}/{C,R,T1,T2,T4,S1}_s*.log
    ;;
  noharm)
    SKIP_SELFCHECK=1 ACCEPT_LOG=${OUT}/accept_noharm.log scripts/accept.sh \
        > ${OUT}/accept_noharm.driver 2>&1 || true
    tail -4 ${OUT}/accept_noharm.driver
    python3 ${OUT}/p111_report.py --same ${OUT}/accept_noharm.log \
        logs/p110/accept_noharm.log --drop '[cage]'
    ;;
  *)
    echo "unknown step: $1" >&2; exit 2 ;;
esac
