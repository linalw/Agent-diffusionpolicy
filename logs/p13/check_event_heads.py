#!/usr/bin/env python3
"""P13-A offline stub: the event-structure supervision lane, pinned.

Mechanism-menu item #6 (`docs/papers/MECHANISMS.md`): the phase + TtT auxiliary
heads (ForeTime #50) and the transition-weighted loss (DAM-VLA #42), default
off. This stub runs no simulator and no training; it pins, on CPU:

  1. the knob resolution (`FRUIT_POLICY_EVENT_HEADS`,
     `FRUIT_POLICY_EVENT_TRANSITION_WEIGHT`; both default off, and the
     `finetune` parameters that resolve them default to None);
  2. the knob-off byte-identity of the shipped model path: the default
     `ConditionalUNet1D` state_dict is exactly the shipped key set (checked
     against `checkpoints/moe_v13s/policy_best.pt`), consumes the same RNG
     draws, and its forward output is bit-identical whether or not a
     `proprio_history` is passed; the event-head variant is a strict superset
     whose action output is also bit-identical (read-only branch);
  3. the head shapes (phase logits (B, 4), TtT (B,) in [0, 1]) and the label
     derivation on synthetic transitions (close/carry/place frames, phases,
     TtT arithmetic, the missing-boundary fallback), plus a real-store sanity
     read on three demos_v11 episodes;
  4. the loss-weighting arithmetic: `transition_gauss` exact values, the
     transition-weighted `_window_weights` (off = episode weight only;
     on = weight * (1 + alpha * g)), and `window_loss_terms` against the
     shipped formula and the manual gamma^j chunk mean.

Run:  python3 logs/p13/check_event_heads.py | tee logs/p13/21_stub_check.txt
"""

from __future__ import annotations

import inspect
import os
import pathlib
import sys
from types import SimpleNamespace

import numpy as np
import torch

ROOT = pathlib.Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "src"))

from fruit_sorting.policy import finetune as ft  # noqa: E402
from fruit_sorting.policy.model import ConditionalUNet1D, EventHeads  # noqa: E402

CKPT = ROOT / "checkpoints" / "moe_v13s" / "policy_best.pt"

failures: list[str] = []


def check(label: str, ok: bool) -> None:
    print(f"  [{'PASS' if ok else 'FAIL'}] {label}")
    if not ok:
        failures.append(label)


def model_kwargs(config: dict) -> dict:
    return dict(
        action_dim=int(config["action_dim"]),
        image_channels=int(config["image_channels"]),
        obs_horizon=int(config["obs_horizon"]),
        goal_dim=int(config["goal_dim"]),
        proprio_dim=int(config["proprio_dim"]),
        num_skills=int(config.get("num_skills", 5)),
    )


def main() -> int:
    print(f"P13-A stub: checkpoint {CKPT.relative_to(ROOT)}  torch {torch.__version__}")

    # ---------------------------------------------------------------- 1 ----- #
    print("\n1. the knobs (default off)")
    for key in ("FRUIT_POLICY_EVENT_HEADS", "FRUIT_POLICY_EVENT_TRANSITION_WEIGHT"):
        os.environ.pop(key, None)
    settings = ft.event_settings_from_env()
    check("unset -> heads off, transition weight 0.0",
          settings == {"event_heads": False, "transition_weight": 0.0})
    check("finetune's knobs default to None (env-resolved)",
          inspect.signature(ft.finetune).parameters["event_heads"].default is None
          and inspect.signature(ft.finetune).parameters["event_transition_weight"].default is None)
    os.environ["FRUIT_POLICY_EVENT_HEADS"] = "1"
    os.environ["FRUIT_POLICY_EVENT_TRANSITION_WEIGHT"] = "1.5"
    settings = ft.event_settings_from_env()
    check("env 1 / 1.5 -> heads on, transition weight 1.5",
          settings == {"event_heads": True, "transition_weight": 1.5})
    os.environ.pop("FRUIT_POLICY_EVENT_HEADS")
    os.environ.pop("FRUIT_POLICY_EVENT_TRANSITION_WEIGHT")
    check("unset again -> off (no leakage)",
          ft.event_settings_from_env() == {"event_heads": False, "transition_weight": 0.0})

    # ---------------------------------------------------------------- 2 ----- #
    print("\n2. the shipped model path, byte-identical with the knob off")
    ckpt = torch.load(str(CKPT), map_location="cpu", weights_only=False)
    kwargs = model_kwargs(ckpt["config"])
    torch.manual_seed(0)
    base = ConditionalUNet1D(**kwargs)
    torch.manual_seed(0)
    base_again = ConditionalUNet1D(**kwargs, event_heads=False)
    check("default state_dict == the shipped checkpoint's key set",
          set(base.state_dict().keys()) == set(ckpt["model"].keys()))
    check("event_heads=False adds no keys",
          set(base_again.state_dict().keys()) == set(base.state_dict().keys()))
    torch.manual_seed(7)
    ConditionalUNet1D(**kwargs)
    state_a = torch.get_rng_state()
    torch.manual_seed(7)
    ConditionalUNet1D(**kwargs, event_heads=False)
    state_b = torch.get_rng_state()
    check("off construction RNG stream identical to the shipped path",
          torch.equal(state_a, state_b))
    base.load_state_dict(ckpt["model"])

    torch.manual_seed(0)
    event_model = ConditionalUNet1D(**kwargs, event_heads=True)
    event_keys = {k for k in event_model.state_dict() if k.startswith("event.")}
    base_keys = {k for k in event_model.state_dict() if not k.startswith("event.")}
    check("event_heads=True adds exactly the event.* keys",
          base_keys == set(ckpt["model"].keys()) and len(event_keys) == 8)
    missing, unexpected = event_model.load_state_dict(ckpt["model"], strict=False)
    check("the base checkpoint loads with only event.* missing",
          not unexpected and all(k.startswith("event.") for k in missing)
          and set(missing) == event_keys)
    check("a filtered (base-only) state_dict loads strictly",
          set(base.state_dict().keys()) == base_keys)

    batch = 2
    sample = torch.randn(batch, 9, 16)
    image = torch.randn(batch, 2, 5, 128, 128)
    goal = torch.randn(batch, 8)
    proprio = torch.randn(batch, 25)
    timesteps = torch.tensor([3, 7])
    history = torch.randn(batch, 8, 25)
    base.eval()
    event_model.eval()
    with torch.no_grad():
        out_off = base.denoise(sample, (image, goal, proprio), timesteps)
        out_off_history = base.denoise(
            sample, (image, goal, proprio), timesteps, proprio_history=history
        )
        out_on = event_model.denoise(sample, (image, goal, proprio), timesteps)
        out_on_history = event_model.denoise(
            sample, (image, goal, proprio), timesteps, proprio_history=history
        )
    check("off: a passed history is ignored (bit-identical output)",
          torch.equal(out_off, out_off_history))
    check("event model without history == shipped output (bit-identical)",
          torch.equal(out_off, out_on))
    check("event model with history == shipped output (read-only branch)",
          torch.equal(out_off, out_on_history))
    check("off model leaves last_event None", base.last_event is None)
    check("on model without history leaves last_event None",
          ConditionalUNet1D(**kwargs, event_heads=True).last_event is None)

    # ---------------------------------------------------------------- 3 ----- #
    print("\n3. head shapes + the label derivation")
    heads = EventHeads(cond_dim=128)
    phase_logits, ttt = heads(torch.randn(4, 8, 128))
    check("EventHeads: (B, H, cond) -> phase (B, 4), TtT (B,)",
          tuple(phase_logits.shape) == (4, 4) and tuple(ttt.shape) == (4,))
    check("TtT is a probability", bool(((ttt >= 0) & (ttt <= 1)).all()))
    phase_logits, ttt = event_model.last_event
    check("model path: last_event shapes (B, 4) / (B,)",
          tuple(phase_logits.shape) == (batch, 4) and tuple(ttt.shape) == (batch,))

    # Synthetic episode: close ramp at frame 10, lift leg at 12, place at 20.
    finger = np.full(25, 0.044, dtype=np.float32)
    finger[10:] = 0.043
    skills = np.zeros(25, dtype=np.int64)
    skills[12:] = 2
    skills[20:] = 3
    labels = ft.episode_event_labels({"finger": finger, "skills": skills})
    check("synthetic close/carry/place = 10/12/20",
          (labels["close"], labels["carry"], labels["place"]) == (10, 12, 20))
    check("transitions = [10, 12, 20]", labels["transitions"] == [10, 12, 20])
    check("phases 0/1/2/3 at frames 5/11/13/21",
          labels["phase"][[5, 11, 13, 21]].tolist() == [0, 1, 2, 3])
    horizon = ft.EVENT_TTT_HORIZON
    expected_ttt = {
        7: (10 - 7) / horizon, 11: (12 - 11) / horizon,
        13: (20 - 13) / horizon, 20: 1.0, 24: 1.0,
    }
    check("TtT = distance-to-next-transition / horizon, 1.0 after the last",
          all(abs(float(labels["ttt"][t]) - v) < 1e-6 for t, v in expected_ttt.items()))
    check("TtT stays in [0, 1]",
          bool(((labels["ttt"] >= 0) & (labels["ttt"] <= 1)).all()))
    # Fallback: no skills -> phases 0/1 only, transitions = [close].
    fallback = ft.episode_event_labels({"finger": finger, "skills": None})
    check("missing leg labels fall back to close-only phases",
          fallback["transitions"] == [10]
          and set(np.unique(fallback["phase"]).tolist()) == {0, 1}
          and fallback["ttt"][9] == 1.0 / horizon and fallback["ttt"][10] == 1.0)

    # Real-store sanity (three demos_v11 episodes; fast, no images decoded here).
    import json

    from fruit_sorting.policy.skills import label_episode

    index = json.loads((ROOT / "datasets" / "demos_v11" / "index.json").read_text())

    def real_episode(entry: dict) -> dict:
        data = np.load(ROOT / "datasets" / "demos_v11" / entry["file"])
        return {
            "finger": data["finger_opening"],
            "skills": label_episode(
                data["fruit_position"], data["finger_opening"], data["goal"]
            ),
        }

    ok_real = True
    real_rows = []
    for entry in index[:3]:
        real = ft.episode_event_labels(real_episode(entry))
        real_rows.append((real["close"], real["carry"], real["place"]))
        ok_real &= (
            real["close"] is not None and real["carry"] is not None
            and real["place"] is not None
            and real["close"] < real["carry"] < real["place"]
            and set(np.unique(real["phase"]).tolist()) == {0, 1, 2, 3}
        )
    print(f"      real (close, carry, place) rows: {real_rows}")
    check("real demos_v11 episodes: ordered boundaries, all four phases",
          ok_real)

    # History construction + normalization on the same real episode.
    normalizer = ft.Normalizer(
        action_mean=np.zeros(9, dtype=np.float32),
        action_std=np.ones(9, dtype=np.float32),
        obs_mean=np.zeros(25, dtype=np.float32),
        obs_std=np.ones(25, dtype=np.float32),
        goal_mean=np.zeros(8, dtype=np.float32),
        goal_std=np.ones(8, dtype=np.float32),
    )
    data = np.load(ROOT / "datasets" / "demos_v11" / index[0]["file"])
    first = real_episode(index[0])
    event_data = ft.episode_event_data(
        {"finger": first["finger"], "skills": first["skills"],
         "joint": data["joint_positions"], "tactile": data["tactile"]},
        normalizer,
    )
    raw = np.concatenate(
        [data["joint_positions"][0], data["finger_opening"][0], data["tactile"][0]]
    ).astype(np.float32)
    check("history shape (T, 8, 25), edge-padded, oldest first",
          event_data["history"].shape == (len(data["finger_opening"]), 8, 25)
          and np.array_equal(event_data["history"][0], np.repeat(raw[None], 8, axis=0)))
    check("history[t] ends at the frame's proprio",
          np.array_equal(event_data["history"][30, -1],
                         np.concatenate([data["joint_positions"][30],
                                         data["finger_opening"][30],
                                         data["tactile"][30]]).astype(np.float32)))

    # 3b. the VLASH offset keeps the event labels aligned (P13-A composition).
    fake_episode = {
        "action": np.zeros((30, 9), dtype=np.float32),
        "joint": np.zeros((30, 22), dtype=np.float32),
        "finger": np.zeros((30, 1), dtype=np.float32),
        "tactile": np.zeros((30, 2), dtype=np.float32),
        "skills": None,
    }
    fake_store = SimpleNamespace(
        episodes=[fake_episode], windows=[(0, 3)], action_horizon=16,
    )
    fake_labels = [{
        "history": np.repeat(np.arange(30, dtype=np.float32)[:, None, None], 8 * 25,
                             axis=1).reshape(30, 8, 25),
        "phase": np.arange(30, dtype=np.int64),
        "ttt": np.arange(30, dtype=np.float32) / 30.0,
    }]
    class _FakeInner:
        def __len__(self) -> int:
            return 1

        def __getitem__(self, index: int) -> dict:
            return {"skill": torch.tensor(0)}

    inner = _FakeInner()
    untouched = ft._OffsetWindows(inner, fake_store, normalizer, 0,
                                  event_labels=fake_labels)[0]
    check("offset delta_max=0 leaves the inner sample untouched",
          "phase" not in untouched)
    aligned = True
    for seed in range(8):
        sample = ft._OffsetWindows(inner, fake_store, normalizer, 5, seed=seed,
                                   event_labels=fake_labels)[0]
        s = int(sample["phase"])
        aligned &= (
            3 <= s <= 3 + 11  # t + delta, delta <= length - horizon - t
            and torch.equal(sample["history"][0, 0], torch.tensor(float(s)))
            and abs(float(sample["ttt"]) - s / 30.0) < 1e-6
        )
    check("offset history/phase/TtT all move to t+delta", aligned)

    # ---------------------------------------------------------------- 4 ----- #
    print("\n4. the loss weighting's arithmetic")
    check("gauss at the transition = 1",
          ft.transition_gauss(10, [10]) == 1.0)
    check("gauss at tau-6 = exp(-1/2) (lead sigma 6)",
          abs(ft.transition_gauss(4, [10]) - np.exp(-0.5)) < 1e-12)
    check("gauss at tau+2 = exp(-1/2) (trail sigma 2)",
          abs(ft.transition_gauss(12, [10]) - np.exp(-0.5)) < 1e-12)
    check("gauss far away -> ~0",
          ft.transition_gauss(60, [10]) < 1e-12)
    check("gauss with no transitions = 0",
          ft.transition_gauss(10, []) == 0.0)

    store = SimpleNamespace(
        episodes=[{"meta": {}}],  # no reward -> base weight 1.0
        windows=[(0, 4), (0, 10), (0, 12), (0, 20)],
    )
    plain = ft._window_weights(
        store, mode="ones", beta=4.0, vbar=0.0, failure_weight=0.05,
        base_weight=1.0,
    )
    check("transition mode off == episode weights only (shipped path)",
          plain == [1.0, 1.0, 1.0, 1.0])
    weighted = ft._window_weights(
        store, mode="ones", beta=4.0, vbar=0.0, failure_weight=0.05,
        base_weight=1.0, transitions=[[10, 12, 20]], transition_weight=1.0,
    )
    expected = [
        1.0 + ft.transition_gauss(t, [10, 12, 20]) for t in (4, 10, 12, 20)
    ]
    check("transition mode on == weight * (1 + alpha * g), exact",
          all(abs(a - b) < 1e-12 for a, b in zip(weighted, expected))
          and abs(weighted[1] - 2.0) < 1e-12)

    predicted = torch.randn(4, 9, 16)
    noise = torch.randn(4, 9, 16)
    weight = torch.tensor([1.0, 2.0, 1.0, 3.0])
    loss, per_window = ft.window_loss_terms(predicted, noise, weight)
    per_window_manual = torch.nn.functional.mse_loss(
        predicted, noise, reduction="none"
    ).flatten(1).mean(1)
    check("chunk_gamma=None == the shipped formula, bit for bit",
          torch.equal(per_window, per_window_manual)
          and torch.equal(loss, (weight * per_window_manual).sum() / weight.sum()))
    loss_gamma, per_window_gamma = ft.window_loss_terms(
        predicted, noise, weight, chunk_gamma=0.8
    )
    gamma = 0.8 ** torch.arange(16)
    per_window_gamma_manual = (
        torch.nn.functional.mse_loss(predicted, noise, reduction="none")
        * gamma[None, None, :]
    ).sum(dim=(1, 2)) / (gamma.sum() * 9)
    check("gamma^j chunk mean == the manual arithmetic, bit for bit",
          torch.equal(per_window_gamma, per_window_gamma_manual)
          and torch.equal(loss_gamma, (weight * per_window_gamma_manual).sum() / weight.sum()))

    # The saved-checkpoint split: base keys only + the prefix-free head state.
    base_state, event_state = ft.event_state_split(event_model.state_dict())
    full_keys = set(event_model.state_dict().keys())
    check("event_state_split: disjoint, complete, prefix-free head state, "
          "base-only loads strictly",
          not (set(base_state) & set(event_state))
          and set(base_state) | {"event." + k for k in event_state} == full_keys
          and set(base_state) == set(ckpt["model"].keys())
          and not any(k.startswith("event.") for k in event_state))

    print()
    if failures:
        print(f"FAIL: {len(failures)} check(s) failed.")
        return 1
    print("PASS: all event-heads checks passed.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
