"""Raise ``RLIMIT_NOFILE`` before Isaac Sim starts, or say why it could not.

Isaac Sim 6.0.1-rc only raises the *soft* file-descriptor limit to a floor of
2450, and this build opens a burst of ~2100 ``/dev/nvidiactl`` descriptors the
first time the head camera's synthetic-data annotators are read. The burst
overruns the floor, the renderer fails with

    dup failed for resourceType: 3 (file descriptor: 2449)
    Too many open files (error: 24)
    [omni.rtx] Cannot create cuda external memory for resource!

and the crash reporter then cannot open its own dump pipe
(``sys_pipe failed:Too many open files``), so the process wedges and the GUI
window looks frozen. The remaining messages in that failure - ``OgnSdSemanticLabelsMap:
invalid input AOV SemanticLabelTokenSD`` - are the synthetic-data graph reacting to
the camera that no longer produces frames, not a separate fault.

``scripts/run.sh`` raises the limit before launching the interpreter. This module
does the same thing from inside the process, so calling
``$ISAAC_SIM_DIR/python.sh scripts/20_pick_place.py`` directly - which the script
docstrings used to recommend - works too instead of dying 40 s in.
"""

from __future__ import annotations

import os
import resource
import sys

#: Comfortably above the observed ~2100-descriptor burst. Override with
#: `FRUIT_FD_LIMIT` (the same variable `scripts/run.sh` honours).
TARGET_SOFT_LIMIT = int(os.environ.get("FRUIT_FD_LIMIT", "1048576"))


def raise_fd_limit(verbose: bool = True) -> int:
    """Set the soft fd limit as high as the hard limit allows.

    Returns the resulting soft limit, or ``-1`` if the limit could not be read.
    A hard limit below the target is not an error - it is only worth a note when
    it is below what the camera burst needs.
    """
    try:
        soft, hard = resource.getrlimit(resource.RLIMIT_NOFILE)
    except (ValueError, OSError):
        return -1
    if hard == resource.RLIM_INFINITY:
        want = TARGET_SOFT_LIMIT
    else:
        want = min(TARGET_SOFT_LIMIT, int(hard))
    if soft < want:
        try:
            resource.setrlimit(resource.RLIMIT_NOFILE, (want, hard))
            soft = want
        except (ValueError, OSError) as error:
            if verbose:
                print(
                    f"[fdlimit] could not raise the soft fd limit ({error}); "
                    f"launch through scripts/run.sh instead",
                    file=sys.stderr,
                )
            return int(soft)
    if verbose and soft < 4096:
        print(
            f"[fdlimit] soft fd limit is {soft}, below what the camera burst needs; "
            f"launch through scripts/run.sh instead",
            file=sys.stderr,
        )
    return int(soft)
