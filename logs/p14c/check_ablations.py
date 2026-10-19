#!/usr/bin/env python3
"""P14-C.1: the three ablation checkpoints load + carry the expected payload.

Runs on the RESTORED (shipped/reverted) tree after the trainings:

  1. `PolicyRunner` (strict `load_state_dict`) loads each of ev_a1/ev_a2/ev_a3
     and one `act()` returns a finite chunk - the shipped-runtime interface;
  2. payload structure: `model` is base keys only (no `event.*`) in all three;
     `event_heads` block (8 prefix-free tensors) present in A1 only; provenance
     names the moe_v13s base pin and the per-arm knobs (A3 carries no event
     fields by construction);
  3. A1's heads re-attach: the e078f43 `model.py` (self-contained; imported
     standalone from a temp copy) builds `ConditionalUNet1D(event_heads=True)`,
     loads the base + event state, and the heads emit finite outputs;
  4. weight deltas vs `moe_v13s` per module (the P13 `60_weight_delta.txt`
     format) for all four candidates (ev1 recomputed for comparability).

Run:  python3 logs/p14c/check_ablations.py | tee logs/p14c/50_runtime_check.txt
"""

from __future__ import annotations

import hashlib
import importlib.util
import pathlib
import sys

import numpy as np
import torch

ROOT = pathlib.Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "src"))

from fruit_sorting.policy.runtime import PolicyRunner  # noqa: E402

CKPTS = {
    "ev1": ROOT / "checkpoints" / "ev1" / "policy_best.pt",
    "ev_a1": ROOT / "checkpoints" / "ev_a1" / "policy_best.pt",
    "ev_a2": ROOT / "checkpoints" / "ev_a2" / "policy_best.pt",
    "ev_a3": ROOT / "checkpoints" / "ev_a3" / "policy_best.pt",
}
BASE = ROOT / "checkpoints" / "moe_v13s" / "policy_best.pt"
BASE_MD5 = "61da390a85fa209496b54477a8255d23"
CAM = (240, 424)
MODEL_EV = pathlib.Path("/tmp/opencode/p14c/model_ev.py")  # e078f43 model.py copy

failures: list[str] = []


def check(label: str, ok: bool) -> None:
    print(f"  [{'PASS' if ok else 'FAIL'}] {label}")
    if not ok:
        failures.append(label)


def md5(path: pathlib.Path) -> str:
    return hashlib.md5(path.read_bytes()).hexdigest()


def load_ev_model_module():
    """Import the e078f43 model.py standalone (torch/nn only, no package deps)."""
    spec = importlib.util.spec_from_file_location("model_ev", MODEL_EV)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def module_of(key: str) -> str:
    parts = key.split(".")
    return ".".join(parts[:2]) if parts[0] == "condition" else parts[0]


def weight_delta(a: dict, b: dict) -> None:
    shared = [k for k in a if k in b and a[k].shape == b[k].shape]
    total, count = 0.0, 0
    per: dict[str, list[float]] = {}
    for k in shared:
        d = (a[k].float() - b[k].float()).abs()
        total += float(d.sum())
        count += d.numel()
        per.setdefault(module_of(k), []).append(float(d.max()))
    print(f"  overall mean |delta| = {total / max(count, 1):.6f} over {count} params")
    print(f"  {'module':<24} max|d|  keys")
    for mod in sorted(per):
        print(f"  {mod:<24}{max(per[mod]):.6f} {len(per[mod]):>5}")


def main() -> int:
    device = "cuda" if torch.cuda.is_available() else "cpu"
    base_payload = torch.load(str(BASE), map_location="cpu", weights_only=False)

    for name, ckpt in CKPTS.items():
        if not ckpt.exists():
            check(f"{name}: checkpoint exists", False)
            continue
        print(f"\n=== {name}  {ckpt.relative_to(ROOT)}  md5 {md5(ckpt)} "
              f"({ckpt.stat().st_size} bytes) ===")

        # 1. the shipped runtime
        try:
            runner = PolicyRunner(str(ckpt), device=device)
            rgb = np.zeros((*CAM, 3), dtype=np.uint8)
            depth = np.zeros(CAM, dtype=np.float32)
            runner.push_frame(rgb, depth)
            runner.push_frame(rgb, depth)
            chunk = runner.act(np.zeros(25, dtype=np.float32),
                               np.zeros(8, dtype=np.float32), num_steps=8)
            check("shipped PolicyRunner loads strictly + act() returns a finite chunk",
                  chunk.shape == (runner.action_horizon, runner.config["action_dim"])
                  and bool(np.isfinite(chunk).all()))
        except Exception as exc:  # noqa: BLE001 - the record wants the reason
            check(f"shipped PolicyRunner loads strictly ({exc!r})", False)

        payload = torch.load(str(ckpt), map_location="cpu", weights_only=False)
        prov = payload.get("provenance", {})
        check("model entry: base keys only (no event.*)",
              not any(k.startswith("event.") for k in payload["model"]))
        check(f"provenance base pin == moe_v13s {BASE_MD5[:8]}",
              prov.get("base_checkpoint_md5") == BASE_MD5)
        check("provenance: 6 epochs, lr 5e-5, weight_mode ones",
              prov.get("epochs") == 6 and prov.get("lr") == 5e-5
              and prov.get("weight_mode") == "ones")
        check("history: 6 epochs",
              len(prov.get("history", [])) == 6)

        event_block = payload.get("event_heads", None)
        if name == "ev_a1":
            state = (event_block or {}).get("state", {})
            check("event_heads block: 8 prefix-free tensors",
                  len(state) == 8 and not any(k.startswith("event.") for k in state))
            check("provenance: heads on, transition weight 0.0",
                  prov.get("event_heads") is True
                  and prov.get("event_transition_weight") == 0.0)
            hist = prov.get("history", [])
            check("head metrics recorded per epoch (phase_acc, ttt_mae)",
                  all("event_phase_acc" in row and "event_ttt_mae" in row for row in hist))
        elif name == "ev_a2":
            check("no event_heads payload block", event_block is None)
            check("provenance: heads off, transition weight 1.0",
                  prov.get("event_heads") is False
                  and prov.get("event_transition_weight") == 1.0)
        elif name == "ev_a3":
            check("no event_heads payload block", event_block is None)
            check("provenance: no event fields (plain 6-epoch run)",
                  not any(k.startswith("event") for k in prov))
        else:  # ev1
            state = (event_block or {}).get("state", {})
            check("ev1 event_heads block: 8 prefix-free tensors",
                  len(state) == 8 and not any(k.startswith("event.") for k in state))

    # 3. A1's heads re-attach (e078f43 model.py imported standalone)
    a1 = CKPTS["ev_a1"]
    if a1.exists() and MODEL_EV.exists():
        print("\n=== ev_a1 head re-attach (e078f43 model.py) ===")
        try:
            mod = load_ev_model_module()
            payload = torch.load(str(a1), map_location="cpu", weights_only=False)
            config = payload["config"]
            model = mod.ConditionalUNet1D(
                action_dim=int(config["action_dim"]),
                image_channels=int(config["image_channels"]),
                obs_horizon=int(config["obs_horizon"]),
                goal_dim=int(config["goal_dim"]),
                proprio_dim=int(config["proprio_dim"]),
                num_skills=int(config.get("num_skills", 5)),
                event_heads=True,
            )
            model.load_state_dict(payload["model"], strict=False)
            model.event.load_state_dict(payload["event_heads"]["state"])
            model.eval()
            with torch.no_grad():
                hist = model.condition.proprio(torch.randn(3, 8, 25).reshape(-1, 25))
                phase_logits, ttt = model.event(hist.reshape(3, 8, -1))
            check("heads re-attach; finite (3, 4) / (3,) outputs",
                  tuple(phase_logits.shape) == (3, 4) and tuple(ttt.shape) == (3,)
                  and bool(torch.isfinite(phase_logits).all())
                  and bool(torch.isfinite(ttt).all()))
        except Exception as exc:  # noqa: BLE001
            check(f"heads re-attach ({exc!r})", False)
    else:
        check("ev_a1 + the e078f43 model.py copy available for the re-attach check", False)

    # 4. weight deltas vs moe_v13s
    print("\n=== weight deltas vs moe_v13s (payload['model'], shared keys) ===")
    for name, ckpt in CKPTS.items():
        if not ckpt.exists():
            continue
        payload = torch.load(str(ckpt), map_location="cpu", weights_only=False)
        print(f"\n{name} vs base:")
        weight_delta(payload["model"], base_payload["model"])

    print()
    if failures:
        print(f"FAIL: {len(failures)} check(s) failed.")
        return 1
    print("PASS: all three ablations load in the shipped runtime with the expected payloads.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
