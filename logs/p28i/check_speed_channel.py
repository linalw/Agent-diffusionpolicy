#!/usr/bin/env python3
"""P28-B stub check: the belt-speed channel (26th proprio scalar), offline.

Tier-C-level implementation evidence for `logs/p28/SPEED_CHANNEL_DESIGN.md`
section 2.2 (recommendation (b)). No simulator, no dataset battery: everything
below is the real code over synthetic inputs plus the real
`checkpoints/moe_v13s/policy_best.pt` artifact.

Layers:

1. **Source / AST** - the gate is read in exactly one place per assembly site;
   the speed scalar is appended only under the gate; the two observation
   builders (`rl_env.proprio`, `scripts/60_eval_policy.py`) call the *same*
   helper; `policy/data.py` (and `policy/finetune.py`) are in
   `rl_env._MANIFEST_SOURCES`; `correction.py` slices with the loaded head's
   config instead of the module constants (the P28-A audit bug).
2. **The B0 identity** -(a) the widened first layer: the extra column is exactly
   0, the 25 old columns and the bias are bitwise the base artifact, the
   normaliser gains the fixed (0.12, 0.05) entry and nothing else changes;
   (b) a fixed synthetic batch through the old and the new model: the deployed
   (batch-1) forward is **bit-identical**, the batched training-shape forward
   differs only by float32 reduction order (bounded, and at the double-precision
   rounding floor in a float64 reference of the same layer - 2.2e-16, not an
   algorithmic difference), and the channel's *value* has exactly no influence
   at step 0 (0.0 vs 0.08 vs 0.12 vs 0.15 are bit-identical); (b') the shipped
   inference path (`PolicyRunner.act`, CPU/fp32, seeded) returns a byte-identical
   chunk from moe_v13s (25-D) and from the widened artifact (26-D).
3. **The pin chain** - `index.json` entry -> `"shard"` -> `<shard>/manifest.json`
   -> `supply.belt_speed`, then the caller's declaration, then 0.12; a store
   that mixes two speeds resolves per episode; a declaration that contradicts a
   manifest raises; the live `datasets/ss008` manifest (collected with the
   P28-A field) reads 0.08.
4. **The 25-D path is byte-inert with the gate off** - the proprio vector, the
   per-frame assembly and `compute_normalizer` are bitwise the pre-P28-B
   expressions; the observation is 25-D.
5. **The training path needs no new machinery** - a 26-D store's
   `compute_normalizer` produces 26 entries with the fixed pair (so
   `train.py`'s dims-from-the-sample build stays correct), and `widen_proprio`
   is idempotent (a second call is a no-op).

Run:  python3 logs/p28i/check_speed_channel.py
Exit code 0 = all checks PASS.
"""

from __future__ import annotations

import ast
import copy
import json
import os
import pathlib
import shutil
import sys

import numpy as np

ROOT = pathlib.Path(__file__).resolve().parents[2]
SRC = ROOT / "src"
for entry in (str(SRC),):
    if entry not in sys.path:
        sys.path.insert(0, entry)

import torch  # noqa: E402

from fruit_sorting.policy import data as policy_data  # noqa: E402
from fruit_sorting.policy.data import EpisodeStore  # noqa: E402
from fruit_sorting.policy.finetune import widen_proprio  # noqa: E402
from fruit_sorting.policy.model import ConditionalUNet1D  # noqa: E402
from fruit_sorting.policy.runtime import PolicyRunner  # noqa: E402

CHECKPOINT = ROOT / "checkpoints" / "moe_v13s" / "policy_best.pt"
TMP = ROOT / "logs" / "p28i" / "_tmp"
LIVE_SHARD = ROOT / "datasets" / "ss008"  # the P28-C 0.08 shard (read-only)

failures: list[str] = []
notes: list[str] = []


def check(label: str, ok: bool, detail: str = "") -> None:
    print(f"  [{'PASS' if ok else 'FAIL'}] {label}{(' - ' + detail) if detail else ''}")
    if not ok:
        failures.append(label)


def note(text: str) -> None:
    print(f"         {text}")
    notes.append(text)


def _source(rel: str) -> tuple[str, ast.Module]:
    path = ROOT / rel
    text = path.read_text(encoding="utf-8")
    return text, ast.parse(text)


def _func(tree: ast.Module, cls: str | None, name: str) -> ast.FunctionDef:
    for node in ast.walk(tree):
        if cls is not None and isinstance(node, ast.ClassDef) and node.name == cls:
            for sub in node.body:
                if isinstance(sub, ast.FunctionDef) and sub.name == name:
                    return sub
        if cls is None and isinstance(node, ast.FunctionDef) and node.name == name:
            return node
    raise SystemExit(f"STUB FAIL: {cls or ''}.{name} not found")


def _calls(node: ast.AST, name: str) -> list[ast.Call]:
    out = []
    for sub in ast.walk(node):
        if isinstance(sub, ast.Call) and isinstance(sub.func, ast.Name):
            if sub.func.id == name:
                out.append(sub)
    return out


# --------------------------------------------------------------------------- #
# Synthetic stores (tiny images; the assembly, not the pixels, is under test)
# --------------------------------------------------------------------------- #
def write_store(
    root: pathlib.Path,
    *,
    frames: int = 20,
    episodes: int = 1,
    manifest: dict | None = None,
    shard: str | None = None,
    speeds: tuple[float, ...] = (),
) -> pathlib.Path:
    """Write a smallest-viable store: index.json + npz episodes (+ manifest)."""
    root.mkdir(parents=True, exist_ok=True)
    rng = np.random.default_rng(11)
    index = []
    for episode in range(episodes):
        name = f"episode_{episode:05d}.npz"
        arrays = {
            "joint_positions": rng.normal(0.0, 0.2, (frames, 22)).astype(np.float32),
            "finger_opening": rng.uniform(0.0, 0.044, (frames, 1)).astype(np.float32),
            "tactile": rng.uniform(0.0, 2.0, (frames, 2)).astype(np.float32),
            "goal": np.concatenate(
                [
                    rng.normal(0.3, 0.05, (frames, 3)),
                    np.tile([0.0, -0.12, 0.0], (frames, 1)),
                    rng.uniform(0.03, 0.07, (frames, 1)),
                    np.zeros((frames, 1)),
                ],
                axis=1,
            ).astype(np.float32),
            "action": rng.normal(0.0, 0.3, (frames, 9)).astype(np.float32),
            "fruit_position": np.concatenate(
                [
                    rng.normal(0.3, 0.03, (frames, 2)),
                    np.full((frames, 1), 1.2),
                ],
                axis=1,
            ).astype(np.float32),
            "image_rgb": rng.integers(0, 255, (frames, 8, 8, 3), dtype=np.uint8),
            "image_distance_to_image_plane": rng.uniform(
                0.4, 1.2, (frames, 8, 8, 1)
            ).astype(np.float32),
            "target_mask": rng.integers(0, 2, (frames, 8, 8), dtype=np.uint8) * 255,
        }
        np.savez_compressed(root / name, **arrays)
        entry = {
            "file": name,
            "index": episode,
            "category": "apple",
            "grade": "A",
            "arm": "left",
            "bin_index": 0,
            "diameter": 0.06,
            "success": True,
            "notes": [],
            "frames": frames,
        }
        if shard is not None:
            entry["shard"] = shard
        if speeds:
            entry["speed_tag"] = float(speeds[episode % len(speeds)])
        index.append(entry)
    (root / "index.json").write_text(json.dumps(index, indent=2), encoding="utf-8")
    if manifest is not None:
        (root / "manifest.json").write_text(json.dumps(manifest, indent=2), encoding="utf-8")
    return root


def small_store(**kwargs) -> EpisodeStore:
    return EpisodeStore(
        str(kwargs.pop("root")),
        obs_horizon=2,
        action_horizon=16,
        image_size=8,
        **kwargs,
    )


# --------------------------------------------------------------------------- #
# 0. the gate's shipped value
# --------------------------------------------------------------------------- #
print("section 0: the gate")
gate_env = os.environ.pop(policy_data.SPEED_CHANNEL_ENV, None)
check("gate unset -> the channel is off", not policy_data.speed_channel_enabled())
check(
    "the fixed normaliser pair is (0.12, 0.05)",
    (policy_data.SPEED_CHANNEL_MEAN, policy_data.SPEED_CHANNEL_STD) == (0.12, 0.05),
)
check(
    "the shipped gate default is 0 (opt-in only)",
    os.environ.get(policy_data.SPEED_CHANNEL_ENV) is None
    and policy_data.speed_channel_enabled() is False,
)
check(
    "no silent pin default exists (P28 Gate A B2)",
    not hasattr(policy_data, "SPEED_PIN_DEFAULT"),
)
check(
    "the legacy provenance table covers the anchor and refuses the 0.15 lineage",
    policy_data.SPEED_PIN_KNOWN.get("demos_v11") == 0.12
    and policy_data.SPEED_PIN_KNOWN.get("demos_v10") == 0.06
    and "demos_v12_015" not in policy_data.SPEED_PIN_KNOWN
    and "v12_s0_015" not in policy_data.SPEED_PIN_KNOWN,
)

# --------------------------------------------------------------------------- #
# 1. source / AST checks
# --------------------------------------------------------------------------- #
print("\nsection 1: source checks (the 13 design sites this lane owns)")
rl_text, rl_tree = _source("src/fruit_sorting/rl_env.py")
proprio_fn = _func(rl_tree, "SortingRLEnv", "proprio")
speed_appends = [
    node
    for node in ast.walk(proprio_fn)
    if isinstance(node, ast.If)
    and any(
        isinstance(sub, ast.Attribute) and sub.attr == "_speed_channel"
        for sub in ast.walk(node.test)
    )
]
check(
    "rl_env.proprio: the speed append sits under `if self._speed_channel:`",
    len(speed_appends) == 1
    and len(_calls(speed_appends[0], "belt_speed_scalar")) == 1
    and len(_calls(proprio_fn, "belt_speed_scalar")) == 1,
)
init_fn = _func(rl_tree, "SortingRLEnv", "__init__")
check(
    "rl_env.__init__ reads the gate once into `_speed_channel`",
    rl_text.count("self._speed_channel = speed_channel_enabled()") == 1
    and len(_calls(init_fn, "speed_channel_enabled")) == 1,
)
check(
    "rl_env refuses a checkpoint whose proprio_dim disagrees with the gate",
    # P227w: the width the env *builds* is the arm's own (its articulation's DOF
    # count + finger + 2 tactile + the gated channels: 25 on the bimanual
    # OpenArm, 12 on the single Panda), not the OpenArm's constant - the refusal
    # is the same comparison.
    "want_proprio = (" in rl_text
    and "_own_dof" in rl_text
    and "(1 if self._speed_channel else 0)" in rl_text
    and "got_proprio != want_proprio" in rl_text,
)
sources = ast.literal_eval(
    next(
        node.value
        for node in rl_tree.body
        if isinstance(node, ast.Assign)
        and any(getattr(t, "id", "") == "_MANIFEST_SOURCES" for t in node.targets)
    )
)
check(
    "_MANIFEST_SOURCES pins policy/data.py and policy/finetune.py (design 2.5.2)",
    "src/fruit_sorting/policy/data.py" in sources
    and "src/fruit_sorting/policy/finetune.py" in sources,
)
check(
    "the run manifest records belt_speed and the channel gate (design 6.1)",
    '"belt_speed": abs(float(self.cfg.belt_speed))' in rl_text
    and '"speed_channel": bool(self._speed_channel)' in rl_text,
)

eval_text, eval_tree = _source("scripts/60_eval_policy.py")
check(
    "60_eval_policy is in lockstep: same helper, gated, one append site",
    len(_calls(eval_tree, "belt_speed_scalar")) == 1
    and "if SPEED_CHANNEL:" in eval_text
    and eval_text.count("belt_speed_scalar(") == 1,
)
check(
    "60_eval_policy reads the same gate",
    "SPEED_CHANNEL = speed_channel_enabled()" in eval_text,
)
check(
    "neither builder inherits the trigger's encoder knob (Gate A sec. 1)",
    "use_encoder=self.trigger_settings" not in rl_text
    and "belt_speed_scalar(" in rl_text
    and "trigger_settings.use_encoder," not in eval_text,
)
check(
    "both builders pass the configured belt speed as the no-belt fallback",
    "fallback=self.cfg.belt_speed" in rl_text
    and "fallback=cfg.belt_speed" in eval_text,
)

data_text, data_tree = _source("src/fruit_sorting/policy/data.py")
proprio_store = _func(data_tree, "EpisodeStore", "proprio")
check(
    "policy/data.py: the column is appended only under `if self.speed_channel:`",
    len(
        [
            node
            for node in ast.walk(proprio_store)
            if isinstance(node, ast.If)
            and "self.speed_channel" in ast.unparse(node.test)
        ]
    )
    == 1,
)
check(
    "policy/data.py: compute_normalizer WRITES the fixed pair (design C2)",
    "obs_mean[-1] = SPEED_CHANNEL_MEAN" in data_text
    and "obs_std[-1] = SPEED_CHANNEL_STD" in data_text,
)
check(
    "policy/data.py: the pin chain reads supply.belt_speed from a manifest",
    'holder = data.get("supply")' in data_text or 'data.get("supply")' in data_text,
)

corr_text, corr_tree = _source("src/fruit_sorting/policy/correction.py")
correct_fn = _func(corr_tree, "CorrectionController", "correct")
check(
    "correction.py slices with the head's config, not the module constants",
    'self.head.config["obs_dim"]' in corr_text
    and 'self.head.config["goal_dim"]' in corr_text
    and "x[:, :OBS_DIM]" not in ast.unparse(correct_fn),
)
check(
    "CorrectionController takes its widths from the payload (Gate A)",
    'cfg.get("obs_dim", len(norm["obs_mean"]))' in corr_text
    and 'cfg.get("goal_dim", len(norm["goal_mean"]))' in corr_text
    and "obs.shape[0] != self.obs_dim" in ast.unparse(correct_fn),
)
fid_text, fid_tree = _source("scripts/119_rl_fidelity.py")
check(
    "119_rl_fidelity has a two-width feed + --data-speed (Gate A B3)",
    "--data-speed" in fid_text
    and len(_calls(fid_tree, "proprio_for")) >= 1
    and "B0 criterion <= 1e-6" in fid_text,
    "no equality assertion for B0",
)

# --------------------------------------------------------------------------- #
# 2. B0: the widened artifact is the anchor at step 0
# --------------------------------------------------------------------------- #
print("\nsection 2: B0 - the widened 26-D artifact is the 25-D anchor at step 0")
import hashlib  # noqa: E402

check("the anchor checkpoint exists", CHECKPOINT.exists(), str(CHECKPOINT))
anchor_md5 = hashlib.md5(CHECKPOINT.read_bytes()).hexdigest()
note(f"anchor md5 {anchor_md5}")
base = torch.load(CHECKPOINT, map_location="cpu", weights_only=False)
base_state = copy.deepcopy(base["model"])
base_norm = copy.deepcopy(base["normalizer"])
base_config = dict(base["config"])
check("the anchor is 25-D", int(base_config["proprio_dim"]) == 25)

wide_state = copy.deepcopy(base_state)
wide_norm = copy.deepcopy(base_norm)
wide_config = dict(base_config)
widened = widen_proprio(wide_state, wide_norm, wide_config)
check("widen_proprio reports a widening", widened is True)
check(
    "config proprio_dim 25 -> 26",
    int(base_config["proprio_dim"]) == 25 and int(wide_config["proprio_dim"]) == 26,
)
key = "condition.proprio.0.weight"
w_base = base_state[key]
w_wide = wide_state[key]
check(
    "the first Linear is (128, 25) -> (128, 26)",
    tuple(w_base.shape) == (128, 25) and tuple(w_wide.shape) == (128, 26),
    f"{tuple(w_base.shape)} -> {tuple(w_wide.shape)}",
)
check(
    "the new column is EXACTLY 0",
    bool(torch.equal(w_wide[:, 25], torch.zeros(128, dtype=w_wide.dtype))),
)
check(
    "the 25 old columns are bitwise the artifact's",
    bool(torch.equal(w_wide[:, :25], w_base)),
)
check(
    "the bias and every other tensor are bitwise unchanged",
    bool(torch.equal(wide_state["condition.proprio.0.bias"],
                     base_state["condition.proprio.0.bias"]))
    and all(
        torch.equal(wide_state[name], base_state[name])
        for name in base_state
        if name != key
    ),
)
check(
    "the normaliser grows by exactly the fixed (0.12, 0.05) entry",
    len(wide_norm["obs_mean"]) == 26
    and len(wide_norm["obs_std"]) == 26
    and abs(float(wide_norm["obs_mean"][25]) - policy_data.SPEED_CHANNEL_MEAN) <= 1e-6
    and abs(float(wide_norm["obs_std"][25]) - policy_data.SPEED_CHANNEL_STD) <= 1e-6
    and np.array_equal(
        np.asarray(wide_norm["obs_mean"][:25], dtype=np.float32),
        np.asarray(base_norm["obs_mean"], dtype=np.float32),
    )
    and np.array_equal(
        np.asarray(wide_norm["obs_std"][:25], dtype=np.float32),
        np.asarray(base_norm["obs_std"], dtype=np.float32),
    )
    and all(np.array_equal(np.asarray(wide_norm[k]), np.asarray(base_norm[k]))
            for k in ("action_mean", "action_std", "goal_mean", "goal_std")),
)
check(
    "widen_proprio is idempotent (a second call is a no-op)",
    widen_proprio(wide_state, wide_norm, wide_config) is False
    and int(wide_config["proprio_dim"]) == 26
    and tuple(wide_state[key].shape) == (128, 26),
)
wide_norm_again = copy.deepcopy(wide_norm)
check(
    " ... and it does not re-append a second entry",
    len(wide_norm_again["obs_mean"]) == 26,
)

torch.manual_seed(0)
model_old = ConditionalUNet1D(
    action_dim=9, image_channels=5, obs_horizon=2, goal_dim=8, proprio_dim=25
).eval()
model_new = ConditionalUNet1D(
    action_dim=9, image_channels=5, obs_horizon=2, goal_dim=8, proprio_dim=26
).eval()
model_old.load_state_dict(base_state)
model_new.load_state_dict(wide_state)


def _batch(batch: int, speed: float = 0.08):
    rng = torch.Generator().manual_seed(1000 + batch)
    goal = torch.randn(batch, 8, generator=rng)
    proprio = torch.randn(batch, 25, generator=rng)
    image = torch.randn(batch, 2, 5, 128, 128, generator=rng) * 0.1
    sample = torch.randn(batch, 9, 16, generator=rng)
    steps = torch.randint(0, 100, (batch,), generator=rng)
    proprio_new = torch.cat(
        [proprio, torch.full((batch, 1), speed, dtype=proprio.dtype)], dim=-1
    )
    return goal, proprio, proprio_new, image, sample, steps


with torch.no_grad():
    # (i) the channel's value has exactly no influence at step 0.
    goal, p25, _, image, sample, steps = _batch(3)
    outs = {}
    for speed in (0.0, 0.08, 0.12, 0.15):
        p26 = torch.cat([p25, torch.full((3, 1), speed)], dim=-1)
        outs[speed] = model_new(sample, image, goal, p26, steps)
    spread = max(
        float((outs[speed] - outs[0.0]).abs().max()) for speed in (0.08, 0.12, 0.15)
    )
    check(
        "the channel value has zero influence (0.0/0.08/0.12/0.15 bit-identical)",
        spread == 0.0,
        f"max|delta| = {spread:.3e}",
    )

    # (ii) old vs new at the deployed shape (batch 1) and at the training shape.
    deltas = {}
    for batch in (1, 3, 32):
        goal, p25, p26, image, sample, steps = _batch(batch)
        c_old = model_old.condition(goal, p25)
        c_new = model_new.condition(goal, p26)
        o_old = model_old(sample, image, goal, p25, steps)
        o_new = model_new(sample, image, goal, p26, steps)
        deltas[batch] = (
            float((c_old - c_new).abs().max()),
            float((o_old - o_new).abs().max()),
        )
        note(
            f"batch {batch:2d}: conditioning max|delta| {deltas[batch][0]:.3e}, "
            f"denoiser output max|delta| {deltas[batch][1]:.3e}"
        )
    check(
        "batch 1 (the deployed inference shape) is BIT-IDENTICAL",
        deltas[1] == (0.0, 0.0),
        f"cond {deltas[1][0]:.1e} / out {deltas[1][1]:.1e}",
    )
    check(
        "batched forwards differ only by float32 reduction order (<= 5e-6)",
        all(cond <= 1e-6 and out <= 5e-6 for cond, out in deltas.values()),
        ", ".join(f"b{b}: {o:.1e}" for b, (_c, o) in deltas.items()),
    )
    # A float64 reference of the SAME first layer: if the function is identical,
    # the 26-column splice cannot show up here at all.
    x64 = torch.randn(64, 25, generator=torch.Generator().manual_seed(5), dtype=torch.float64)
    bias64 = base_state["condition.proprio.0.bias"].double()
    y_old64 = x64 @ w_base.double().T + bias64
    x64_new = torch.cat([x64, torch.full((64, 1), 0.08, dtype=torch.float64)], dim=-1)
    y_new64 = x64_new @ w_wide.double().T + bias64
    check(
        "float64 reference: no algorithmic difference (<= 1e-14, the fp64 floor)",
        float((y_old64 - y_new64).abs().max()) <= 1e-14,
        f"max|delta| = {float((y_old64 - y_new64).abs().max()):.3e}",
    )

# --------------------------------------------------------------------------- #
# 2b. B0 through the shipped inference path (PolicyRunner, CPU/fp32, seeded)
# --------------------------------------------------------------------------- #
print("\nsection 2b: B0 through the shipped runtime (`PolicyRunner.act`)")
TMP.mkdir(parents=True, exist_ok=True)
init_path = TMP / "spd_init.pt"
torch.save(
    {
        "model": wide_state,
        "normalizer": wide_norm,
        "config": wide_config,
        "val_loss": base.get("val_loss", float("nan")),
        "provenance": {
            "kind": "p28b_speed_channel_init",
            "base_checkpoint": str(CHECKPOINT),
            "base_checkpoint_md5": anchor_md5,
            "surgery": "widen_proprio: zero column + fixed (0.12, 0.05) entry",
        },
    },
    init_path,
)
os.environ["FRUIT_POLICY_SEED"] = "1234"
runner_old = PolicyRunner(str(CHECKPOINT), device="cpu", use_half=False)
runner_new = PolicyRunner(str(init_path), device="cpu", use_half=False)
check(
    "the runtime reads 25-D from the anchor and 26-D from the widened artifact",
    int(runner_old.config["proprio_dim"]) == 25
    and int(runner_new.config["proprio_dim"]) == 26
    and len(runner_old.normalizer.obs_mean) == 25
    and len(runner_new.normalizer.obs_mean) == 26,
)
rng = np.random.default_rng(7)
rgb = (rng.random((24, 42, 3)) * 255).astype(np.uint8)
depth = (rng.random((24, 42)) + 0.4).astype(np.float32)
mask = (rng.random((24, 42)) > 0.6).astype(np.float32)
p25 = rng.normal(0.0, 0.3, (25,)).astype(np.float32)
goal = rng.normal(0.0, 0.2, (8,)).astype(np.float32)


def act(runner: PolicyRunner, proprio: np.ndarray, steps: int = 4) -> np.ndarray:
    runner.reset()
    runner.push_frame(rgb, depth, mask)
    runner.push_frame(rgb, depth, mask)
    runner.generator = torch.Generator(device=runner.device).manual_seed(1234)
    return runner.act(proprio, goal, num_steps=steps)


chunk_old = act(runner_old, p25)
chunk_new = act(runner_new, np.concatenate([p25, [0.08]]).astype(np.float32))
check(
    "the deployed action chunk is BYTE-IDENTICAL (25-D vs 26-D artifact)",
    bool((chunk_old == chunk_new).all()),
    f"max|delta| = {float(np.abs(chunk_old - chunk_new).max()):.3e}",
)
chunk_new_015 = act(runner_new, np.concatenate([p25, [0.15]]).astype(np.float32))
check(
    "the channel's value has zero influence on the deployed chunk",
    bool((chunk_new == chunk_new_015).all()),
    f"max|delta| = {float(np.abs(chunk_new - chunk_new_015).max()):.3e}",
)

# --------------------------------------------------------------------------- #
# 3. the pin chain, and the synthesised column
# --------------------------------------------------------------------------- #
print("\nsection 3: the pin chain (`shard` -> manifest -> supply.belt_speed)")
stores = TMP / "stores"
if stores.exists():
    shutil.rmtree(stores)
write_store(
    stores / "s_manifest",
    manifest={"supply": {"belt_speed": 0.15}, "created": "synthetic"},
)
# An unpinned store with no speed evidence, under a name the provenance table
# does not know -> must raise (P28 Gate A B2).
write_store(stores / "unknown_store", manifest={"created": "synthetic", "episodes": 1})
# A legacy 0.12 lineage name (the anchor's own shard name) with no manifest and
# no supply block -> the documented table resolves it.
write_store(stores / "v11_s0")
# The legacy 0.15 shard name: deliberately NOT in the table -> must raise.
write_store(stores / "v12_s0_015")
write_store(stores / "shards" / "a", manifest={"supply": {"belt_speed": 0.08}})
write_store(stores / "shards" / "b", manifest={"supply": {"belt_speed": 0.15}})
merged = stores / "s_merged"
write_store(merged, episodes=2)
entries = json.loads((merged / "index.json").read_text(encoding="utf-8"))
entries[0]["shard"] = str(stores / "shards" / "a")
entries[1]["shard"] = str(stores / "shards" / "b")
(merged / "index.json").write_text(json.dumps(entries, indent=2), encoding="utf-8")

store_manifest = small_store(root=stores / "s_manifest", speed_channel=True)
check(
    "a manifest's supply.belt_speed pins the episode (0.15)",
    store_manifest.belt_speeds == [0.15]
    and store_manifest.speed_sources[0].startswith("manifest:"),
    f"{store_manifest.belt_speeds} {store_manifest.speed_sources}",
)
store_unknown = None
unknown_error = ""
try:
    store_unknown = small_store(root=stores / "unknown_store", speed_channel=True)
except ValueError as exc:
    unknown_error = str(exc)
check(
    "an unpinned store with no manifest value RAISES (no silent 0.12) - B2",
    store_unknown is None and "no belt-speed pin" in unknown_error,
    unknown_error.splitlines()[0] if unknown_error else "no error (silent 0.12!)",
)
store_known = small_store(root=stores / "v11_s0", speed_channel=True)
check(
    "the documented legacy lineage resolves without a manifest (v11_s0 -> 0.12)",
    store_known.belt_speeds == [0.12]
    and store_known.speed_sources == ["known:v11_s0"],
    f"{store_known.belt_speeds} {store_known.speed_sources}",
)
store_015 = None
raised_015 = ""
try:
    store_015 = small_store(root=stores / "v12_s0_015", speed_channel=True)
except ValueError as exc:
    raised_015 = str(exc)
check(
    "the 0.15 legacy shard is NOT in the table, so it must be pinned - B2",
    store_015 is None and "no belt-speed pin" in raised_015,
    raised_015.splitlines()[0] if raised_015 else "no error (silent 0.12!)",
)
store_declared = small_store(
    root=stores / "v12_s0_015", speed_channel=True, belt_speed=0.15
)
check(
    "the legacy pin resolves an unpinned/unknown store (declared 0.15)",
    store_declared.belt_speeds == [0.15]
    and store_declared.speed_sources == ["declared"],
    f"{store_declared.belt_speeds} {store_declared.speed_sources}",
)
store_merged = small_store(root=merged, speed_channel=True)
check(
    "a merged store resolves PER EPISODE through its shard stamp ([0.08, 0.15])",
    store_merged.belt_speeds == [0.08, 0.15],
    f"{store_merged.belt_speeds} {store_merged.speed_sources}",
)
store_agrees = small_store(root=stores / "s_manifest", speed_channel=True, belt_speed=0.15)
check(
    "a declaration that AGREES with the manifest is accepted (manifest wins)",
    store_agrees.belt_speeds == [0.15]
    and store_agrees.speed_sources[0].startswith("manifest:"),
    f"{store_agrees.belt_speeds} {store_agrees.speed_sources}",
)
conflict_path = stores / "s_manifest"
try:
    small_store(root=conflict_path, speed_channel=True, belt_speed=0.12)
    raised = False
    message = ""
except ValueError as exc:
    raised = True
    message = str(exc)
check(
    "a declared pin that contradicts the manifest RAISES (design 2.2 risk 2)",
    raised and "pin conflict" in message,
    message.splitlines()[0] if message else "no error",
)
# The belt sentinel (P28 Gate A section 1, correction 2): no belt -> the
# configured speed, never 0.0.
class _NoBelt:
    belt = None


try:
    policy_data.belt_speed_scalar(_NoBelt())
    sentinel_raised = False
except RuntimeError:
    sentinel_raised = True
check(
    "no belt and no fallback raises (0.0 is not a valid channel value)",
    sentinel_raised,
)
check(
    "no belt with the configured speed reports it (abs, not 0.0)",
    abs(policy_data.belt_speed_scalar(_NoBelt(), fallback=-0.12) - 0.12) <= 1e-9,
    f"{policy_data.belt_speed_scalar(_NoBelt(), fallback=-0.12)}",
)


def old_expression(store: EpisodeStore, ep: int, t: int) -> np.ndarray:
    episode = store.episodes[ep]
    return np.concatenate(
        [
            episode["joint"][t].astype(np.float32),
            episode["finger"][t].astype(np.float32),
            episode["tactile"][t].astype(np.float32),
        ]
    )


sample_merged = store_merged[0]
ep0, t0 = store_merged.windows[0]
last_index = len(store_merged) - 1
ep1, t1 = store_merged.windows[last_index]
check(
    "the synthesised column is the episode's pin, last dim",
    sample_merged["proprio"].shape == (26,)
    and np.float32(sample_merged["proprio"][-1]) == np.float32(0.08)
    and np.array_equal(
        sample_merged["proprio"][:25], old_expression(store_merged, ep0, t0)
    ),
)
check(
    "the second episode carries its own pin (0.15)",
    ep1 != ep0
    and store_merged[last_index]["proprio"].shape == (26,)
    and np.float32(store_merged[last_index]["proprio"][-1]) == np.float32(0.15)
    and np.array_equal(
        store_merged[last_index]["proprio"][:25],
        old_expression(store_merged, ep1, t1),
    ),
)
if LIVE_SHARD.joinpath("manifest.json").exists():
    live = policy_data._manifest_belt_speed(str(LIVE_SHARD / "manifest.json"))
    check(
        "the live P28-C shard (datasets/ss008, the P28-A field) reads 0.08",
        live == 0.08,
        f"{live}",
    )
else:  # pragma: no cover - the shard is expected on disk
    note("datasets/ss008/manifest.json absent, live-field check skipped")

# --------------------------------------------------------------------------- #
# 4. the 25-D path is byte-inert with the gate off
# --------------------------------------------------------------------------- #
print("\nsection 4: the gate-off (25-D) path is byte-inert")
os.environ.pop(policy_data.SPEED_CHANNEL_ENV, None)
plain_root = stores / "s_manifest"
plain = small_store(root=plain_root)  # gate off, no explicit pin
check("gate off: the store is 25-D", plain.proprio_dim == 25 and not plain.speed_channel)
check(
    "gate off: one frame is bitwise the shipped expression",
    plain[0]["proprio"].shape == (25,)
    and np.array_equal(
        plain[0]["proprio"], old_expression(plain, *plain.windows[0])
    ),
)
all_frames_equal = all(
    np.array_equal(plain.proprio(ep), np.concatenate(
        [plain.episodes[ep]["joint"], plain.episodes[ep]["finger"],
         plain.episodes[ep]["tactile"]], axis=-1))
    for ep in range(len(plain.episodes))
)
check("gate off: `proprio(t=None)` is bitwise the shipped all-frames expression",
      bool(all_frames_equal))
plain_norm = plain.compute_normalizer()
check(
    "gate off: compute_normalizer is bitwise the shipped computation",
    len(plain_norm.obs_mean) == 25
    and all(
        np.array_equal(
            np.asarray(getattr(plain_norm, field), dtype=np.float32),
            np.asarray(reference, dtype=np.float32),
        )
        for field, reference in (
            (
                "obs_mean",
                np.concatenate(
                    [np.concatenate([e["joint"], e["finger"], e["tactile"]], axis=-1)
                     for e in plain.episodes],
                    axis=0,
                ).mean(0),
            ),
            (
                "obs_std",
                np.concatenate(
                    [np.concatenate([e["joint"], e["finger"], e["tactile"]], axis=-1)
                     for e in plain.episodes],
                    axis=0,
                ).std(0) + 1e-6,
            ),
        )
    ),
)
# The gate on, then off again: no state is carried by the module.
check(
    "the gate is read per store, not cached module-side",
    (
        EpisodeStore(str(plain_root), obs_horizon=2, action_horizon=16, image_size=8,
                     speed_channel=True).proprio_dim
        == 26
        and EpisodeStore(str(plain_root), obs_horizon=2, action_horizon=16, image_size=8,
                         speed_channel=False).proprio_dim
        == 25
    ),
)
check(
    "gate off: the model sees 25 dims and the shipped 5-channel image stack",
    plain[0]["proprio"].shape[0] == 25 and plain[0]["image"].shape[1] == 5,
)

# --------------------------------------------------------------------------- #
# 5. the 26-D training path (no new machinery) and VLASH
# --------------------------------------------------------------------------- #
print("\nsection 5: the 26-D training path")
wide_store = small_store(root=merged, speed_channel=True)
merged_plain = small_store(root=merged)  # the same windows, gate off
plain_reference = merged_plain.compute_normalizer()
wide_norm_computed = wide_store.compute_normalizer()
check(
    "compute_normalizer yields 26 entries with the FIXED pair at the last dim",
    len(wide_norm_computed.obs_mean) == 26
    and len(wide_norm_computed.obs_std) == 26
    and abs(float(wide_norm_computed.obs_mean[25]) - policy_data.SPEED_CHANNEL_MEAN) <= 1e-6
    and abs(float(wide_norm_computed.obs_std[25]) - policy_data.SPEED_CHANNEL_STD) <= 1e-6
    and np.array_equal(
        np.asarray(wide_norm_computed.obs_mean[:25], dtype=np.float32),
        np.asarray(plain_reference.obs_mean, dtype=np.float32),
    )
    and np.array_equal(
        np.asarray(wide_norm_computed.obs_std[:25], dtype=np.float32),
        np.asarray(plain_reference.obs_std, dtype=np.float32),
    ),
)
check(
    "the 26-D normalised channel is on the documented z grid (0.08 -> -0.80)",
    abs(
        float(
            (0.08 - float(wide_norm_computed.obs_mean[-1]))
            / float(wide_norm_computed.obs_std[-1])
        )
        + 0.80
    )
    <= 1e-6,
)
sample_wide = wide_store[0]
check(
    "the store's sample width matches its declared proprio_dim",
    sample_wide["proprio"].shape[0] == wide_store.proprio_dim == 26,
)
check(
    "train.py needs no change: dims come from the sample (26)",
    "proprio_dim=sample[\"proprio\"].shape[0]" in (ROOT / "src/fruit_sorting/policy/train.py").read_text(encoding="utf-8"),
)
check(
    "a 26-D Normalizer normalises a 26-D sample (loud on a width mismatch)",
    wide_norm_computed.normalize_obs(sample_wide["proprio"]).shape == (26,),
)
try:
    plain_norm.normalize_obs(sample_wide["proprio"])
    mismatch_loud = False
except ValueError:
    mismatch_loud = True
check("a 26-D sample through the 25-D normaliser raises", mismatch_loud)

# VLASH: the state offset must carry the channel, from the store (not a copy).
from fruit_sorting.policy.finetune import _OffsetWindows, _WeightedWindows  # noqa: E402

inner = _WeightedWindows(wide_store, wide_norm_computed, [1.0] * len(wide_store))
offset = _OffsetWindows(inner, wide_store, wide_norm_computed, 5, seed=3)
offsets = [offset[0]["proprio"].shape[0] for _ in range(20)]
check(
    "the VLASH state offset keeps the 26th dim on every draw",
    set(offsets) == {26},
    f"shapes seen = {sorted(set(offsets))}",
)

# P28 Gate A B3: 119's two-width feed. The 25-D arm must receive exactly the
# store's first 25 dims (bitwise the shipped vector); the 26-D arm all 26.
import importlib.util  # noqa: E402

_spec = importlib.util.spec_from_file_location(
    "rl_fidelity", str(ROOT / "scripts" / "119_rl_fidelity.py")
)
_fid = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(_fid)


class _PolicyWidth:
    """The only attribute `proprio_for` reads."""

    def __init__(self, width: int) -> None:
        self.config = {"proprio_dim": width}


_vector26 = wide_store[0]["proprio"]
_v25, _w25 = _fid.proprio_for(_PolicyWidth(25), _vector26)
_v26, _w26 = _fid.proprio_for(_PolicyWidth(26), _vector26)
check(
    "119 two-width feed: the 25-D arm gets the store prefix, bitwise",
    _w25 == 25
    and np.array_equal(_v25, _vector26[:25])
    and np.array_equal(_v25, old_expression(wide_store, *wide_store.windows[0])),
)
check(
    "119 two-width feed: the 26-D arm gets the whole vector",
    _w26 == 26 and np.array_equal(_v26, _vector26),
)
#: P227y: the feed's own rule is "the checkpoint's width, taken from the store's
#: vector when the store is wider" - so the refusal is a width the store **cannot**
#: supply (wider than the vector). The old case used 24 against a 26-D store,
#: which is a legal prefix; the single-arm artifact is 12-D and must be accepted
#: from its own 12-D store.
try:
    _fid.proprio_for(_PolicyWidth(27), _vector26)
    _bad_width = False
except ValueError:
    _bad_width = True
check("119 two-width feed: a width the store cannot supply refuses", _bad_width)
_v12, _w12 = _fid.proprio_for(
    _PolicyWidth(12), np.asarray(np.arange(12), dtype=np.float32)
)
check(
    "119 two-width feed: the single-arm 12-D width is accepted from its own store",
    _w12 == 12 and np.array_equal(_v12, np.arange(12, dtype=np.float32)),
)

# --------------------------------------------------------------------------- #
print("\n" + "=" * 78)
for text in notes:
    print(f"note: {text}")
print("=" * 78)
if failures:
    print(f"FAIL: {len(failures)} check(s) failed")
    for label in failures:
        print(f"  - {label}")
    raise SystemExit(1)
print(f"PASS: all checks ({len(notes)} notes)")
raise SystemExit(0)
