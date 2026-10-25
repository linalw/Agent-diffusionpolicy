#!/usr/bin/env bash
# P40 phase 3 / R-S (item 2) - the nearest-above-floor arm.
#
# The knob-off arm of the pair ran first in the same stretch
# (`logs/p40/p3/nearest_off.log`, 01:25:36-01:30:02, **376/376** filtered
# `[fruit]` lines identical to `logs/p39/p3/accept_C.log`) - that is the
# byte-identity proof for the unset path. This driver is the ON arm only: the
# first attempt at a single-claim pair passed the env assignment through `$@`,
# which bash cannot expand into a prefix assignment (`FRUIT_...=1: command not
# found`, exit 127, no simulator run), so the arm is executed here instead.
set -uo pipefail
cd "$(dirname "$0")/../../.." || exit 1

export FRUIT_SELECT_NEAREST_ABOVE_FLOOR=1
SKIP_SELFCHECK=1 ACCEPT_LOG=logs/p40/p3/nearest_accept.log scripts/accept.sh
