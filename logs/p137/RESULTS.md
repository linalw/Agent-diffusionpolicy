# P137 results - the selector's last constant-speed term, removed and not binding

`FRUIT_SELECT_LIVE_SPEED` (default **on**): the selector's station window is
`time x speed`, and the speed is now the **belt's own** (`_selector_speed`,
`_belt_speed_estimate()`) instead of the authored `cfg.belt_speed`;
`=0` restores the old read, and an encoder-less stub falls back to the config
value (so the offline selector selftests are unchanged).

## 1. Inertness - the gate - PASSES

The shipped (constant-speed) acceptance with the change:

| | |
|---|---|
| rate | **7/10 = 70 %** |
| fingerprint | **`matches configs/motion_reference.json`** |
| `190` | **PASS** |
| `[fruit]` stream | **459/459 byte-identical** to `logs/p136/accept_final.log` |

So on a constant belt the change is **resolution-only**: the encoder reads the
authored speed and the window is the same number to the bit. **No reference
re-record is owed** and none was made.

## 2. The mechanism cell - the term does not bind

Belt wave 0.04 m/s at 0.5 Hz (P135's scenario), 3 attempts, seed 5, the same
instrumentation before and after:

| | before (`logs/p135/recheck/wave_w.log`) | after (`logs/p137/wave_after.log`) |
|---|---|---|
| catch residuals | 5.4 / 5.8 / 6.0 mm | **5.4 / 5.8 / 6.0 mm** |
| catch ticks | 12 / 13 / 11 | **12 / 13 / 11** |
| placed | 2/3 | 2/3 |

Identical. The window's error (up to 36 mm) is smaller than the slack the
selector has in this cell, so the *selection* is not the binding term - which is
what the record already said from the other side (P99: the interval is the
sequencing of two overlapped arms, not the arrival; P58/P59: the depth means do
not rank the arms).

## 3. What this closes

Every place the catch consults a **speed** now reads the belt's own (the descent's
schedule, the gate, the catch-up's lead, the selector's window). The remaining
constant-speed assumption was the last one and it is removed. **Not a lever**: the
change is a correctness fix whose measured behaviour is identical in both
scenarios the project has; it ships because it is inert on the acceptance and
wrong without it.

Pins: `tasks.py` (`_selector_speed` + its three call sites), `scripts/176` (three
new checks: stub -> config, live encoder -> follows, `=0` -> config).
