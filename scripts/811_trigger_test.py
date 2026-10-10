"""Offline unit test for the encoder-based intercept trigger (P4b1).

No simulator, no torch: the trigger is pure geometry over the fruit/jaw vectors
and the belt encoder speed.

    python3 scripts/811_trigger_test.py
"""

from __future__ import annotations

import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "src"))

from fruit_sorting.policy.trigger import TriggerSettings, should_fire  # noqa: E402


def main() -> int:
    failures = 0

    def check(name: str, condition: bool, detail: str = "") -> None:
        nonlocal failures
        status = "PASS" if condition else "FAIL"
        if not condition:
            failures += 1
        print(f"  [{status}] {name}{(' - ' + detail) if detail else ''}")

    jaw = (0.333, -0.020, 1.253)
    # Fruit upstream 6 cm, belt moving -y at 0.06 m/s.
    fruit = (0.340, 0.040, 1.184)
    measured = (0.0, -0.022, 0.0)  # a rolling fruit reads slower than the belt
    settings = TriggerSettings(mode="off")

    fired, info = should_fire(settings, fruit, jaw, encoder_speed=-0.06,
                              measured_velocity=measured)
    check("off never fires", not fired)
    check("off still reports the geometry", info["dy"] > 0 and info["dx"] > 0)

    settings = TriggerSettings(mode="arrival", lead=1.0)
    fired, info = should_fire(settings, fruit, jaw, encoder_speed=-0.06,
                              measured_velocity=measured)
    check("arrival fires at 6 cm / 1.0 s with lead 1.0", fired,
          f"t_arrive={info['t_arrive']:.3f}")
    check("encoder is preferred over the slow measurement", info["source"] == "encoder")

    fired, _ = should_fire(settings, fruit, jaw, encoder_speed=-0.06,
                           measured_velocity=measured, finger=0.044)
    check("arrival is independent of the finger", fired)

    fired, _ = should_fire(TriggerSettings(mode="arrival", lead=0.90), fruit, jaw,
                           encoder_speed=-0.06, measured_velocity=measured)
    check("a shorter lead waits one tick longer", not fired)

    # 20 cm upstream is a 3.3 s arrival: outside the 0.90 s lead.
    fired, info = should_fire(settings, (0.340, 0.18, 1.184), jaw,
                              encoder_speed=-0.06)
    check("does not fire early", not fired, f"t_arrive={info['t_arrive']:.3f}")

    # Out of lateral alignment: the jaws would close on air. The W4 default
    # (0.16 m) admits the v9/V1 scattered band; an explicit 0.06 still refuses
    # the same fruit.
    fired, _ = should_fire(settings, (0.55, 0.0, 1.184), jaw, encoder_speed=-0.06)
    check("lateral gate rejects a misaligned fruit", not fired)
    fired, _ = should_fire(settings, (0.44, 0.0, 1.184), jaw, encoder_speed=-0.06)
    check("default lateral admits the outer band (dx=0.107)", fired)
    fired, _ = should_fire(
        TriggerSettings(mode="arrival", lead=1.0, lateral=0.06),
        (0.44, 0.0, 1.184), jaw, encoder_speed=-0.06,
    )
    check("explicit lateral=0.06 still refuses dx=0.107", not fired)

    # A stationary fruit: the policy's own gate owns that case.
    fired, _ = should_fire(settings, (0.340, 0.0, 1.184), jaw, encoder_speed=0.0,
                           measured_velocity=(0.0, 0.0, 0.0))
    check("stationary fruit does not fire", not fired)

    settings = TriggerSettings(mode="assist", lead=1.0, finger=0.040)
    fired, _ = should_fire(settings, fruit, jaw, encoder_speed=-0.06, finger=0.044)
    check("assist holds while the policy is open", not fired)
    fired, _ = should_fire(settings, fruit, jaw, encoder_speed=-0.06, finger=0.036)
    check("assist fires once the policy is near closed", fired)

    env = dict(os.environ)
    try:
        os.environ["FRUIT_POLICY_TRIGGER"] = "arrival"
        os.environ["FRUIT_POLICY_TRIGGER_LEAD"] = "0.5"
        os.environ["FRUIT_POLICY_TRIGGER_ENCODER"] = "0"
        os.environ["FRUIT_POLICY_TRIGGER_FRAME"] = "jaw"
        os.environ["FRUIT_POLICY_TRIGGER_PRESENT"] = "1"
        parsed = TriggerSettings.from_env()
        check("from_env parses mode/lead/encoder/frame/present",
              parsed.mode == "arrival" and parsed.lead == 0.5
              and not parsed.use_encoder and parsed.frame == "jaw"
              and parsed.present)
        del os.environ["FRUIT_POLICY_TRIGGER_PRESENT"]
        check("present defaults off", not TriggerSettings.from_env().present)
        os.environ["FRUIT_POLICY_TRIGGER"] = "bogus"
        try:
            TriggerSettings.from_env()
            check("from_env rejects a bogus mode", False)
        except ValueError:
            check("from_env rejects a bogus mode", True)
        os.environ["FRUIT_POLICY_TRIGGER"] = "arrival"
        os.environ["FRUIT_POLICY_TRIGGER_FRAME"] = "bogus"
        try:
            TriggerSettings.from_env()
            check("from_env rejects a bogus frame", False)
        except ValueError:
            check("from_env rejects a bogus frame", True)
    finally:
        os.environ.clear()
        os.environ.update(env)

    print(f"[trigger test] {'OK' if failures == 0 else f'{failures} FAILURES'}")
    return 1 if failures else 0


if __name__ == "__main__":
    raise SystemExit(main())
