"""The slow loop: perception summary -> experience memory -> structured goal.

Design document section 4 asks for an *Experience-Augmented Agent* that decides
**which** fruit to pick and **how** (skill, bin, force budget), while the fast loop
decides *how to move*. This module is that slow loop, with two deliberate
simplifications that keep it runnable inside this repository:

* the decision graph is a small explicit node/edge structure instead of a
  LangGraph dependency, so the *shape* (observe -> retrieve -> score -> decide ->
  verify -> emit, with a bounded replan edge) is the thing that is implemented and
  testable; swapping in LangGraph later is mechanical;
* the "VLM reasoning" node is a deterministic rule scorer
  (`FRUIT_SLOW_LOOP_POLICY=rule`, the default). The interface takes the same
  structured state and returns the same structured goal, so an LLM policy can be
  dropped in behind `decide()` without touching the fast loop - and, importantly,
  the loop never blocks on a model in the 120 Hz path.

Everything the agent knows comes from `FruitSpawner.state()` plus the experience
memory written after each episode, and everything it outputs is a
`ManipulationGoal` the task can execute unchanged.
"""

from __future__ import annotations

import json
import os
import statistics
import time
from dataclasses import asdict, dataclass, field

import numpy as np

from .common import say


def size_bucket(diameter: float) -> str:
    if diameter < 0.04:
        return "2-4cm"
    if diameter < 0.06:
        return "4-6cm"
    return "6-8cm"


@dataclass
class StructuredState:
    """What the slow loop sees: the belt's fruit plus line context."""

    time: float
    belt_speed: float
    fruits: list[dict] = field(default_factory=list)


@dataclass
class ManipulationGoal:
    """The slow loop's output: what to grasp, where to put it, how hard to squeeze."""

    index: int
    category: str
    grade: str
    bin_index: int
    skill: str
    force_limit_n: float
    approach: str
    rationale: str
    confidence: float


class ExperienceMemory:
    """Append-only episode memory with category/size retrieval.

    The design asks for ``经验记忆检索``: what worked last time for fruit like this
    one. We store one JSON record per episode and retrieve success statistics per
    (category, size bucket) plus per arm, which the scorer then uses as a prior.
    """

    def __init__(self, path: str = "logs/experience.jsonl"):
        self.path = path
        self.records: list[dict] = []
        self._stats: dict[tuple, dict] = {}
        if os.path.exists(path):
            try:
                with open(path, encoding="utf-8") as fh:
                    for line in fh:
                        line = line.strip()
                        if line:
                            self.records.append(json.loads(line))
            except (OSError, json.JSONDecodeError):
                self.records = []
        for record in self.records:
            self._index(record)

    def _index(self, record: dict) -> None:
        key = (record.get("category"), record.get("bucket"))
        entry = self._stats.setdefault(key, {"n": 0, "ok": 0})
        entry["n"] += 1
        entry["ok"] += int(bool(record.get("success")))

    def remember(self, goal: ManipulationGoal, *, success: bool, arm: str,
                 notes: list[str], cycle_s: float, diameter: float) -> None:
        record = {
            "index": int(goal.index),
            "category": goal.category,
            "bucket": size_bucket(float(diameter)),
            "diameter": round(float(diameter), 4),
            "grade": goal.grade,
            "bin": int(goal.bin_index),
            "skill": goal.skill,
            "arm": arm,
            "force_limit_n": round(float(goal.force_limit_n), 1),
            "success": bool(success),
            "notes": list(notes),
            "cycle_s": round(float(cycle_s), 2),
        }
        self.records.append(record)
        self._index(record)
        try:
            os.makedirs(os.path.dirname(self.path) or ".", exist_ok=True)
            with open(self.path, "a", encoding="utf-8") as fh:
                fh.write(json.dumps(record, ensure_ascii=False) + "\n")
        except OSError:
            pass

    def prior(self, category: str, diameter: float) -> dict:
        """Success statistics for fruit like this one (with a width-1 smoothing)."""
        entry = self._stats.get((category, size_bucket(diameter)))
        if not entry or entry["n"] == 0:
            return {"n": 0, "rate": 0.5}
        # Laplace-smoothed success rate so a single lucky episode cannot dominate.
        return {"n": entry["n"], "rate": (entry["ok"] + 1.0) / (entry["n"] + 2.0)}

    def summary(self) -> str:
        if not self.records:
            return "empty"
        ok = sum(1 for r in self.records if r["success"])
        worst = sorted(self._stats.items(), key=lambda kv: kv[1]["ok"] / max(1, kv[1]["n"]))
        tail = ", ".join(f"{k[0]}/{k[1]}:{v['ok']}/{v['n']}" for k, v in worst[:3])
        return f"{len(self.records)} episodes, {ok} ok; weakest: {tail}"


class SlowLoopAgent:
    """The decision graph.

    Nodes (each a method, so the graph is inspectable):

    ``observe``   build a `StructuredState` from the spawner's fruit list;
    ``retrieve``  pull per-fruit priors out of the experience memory;
    ``score``     hard filters (size, on-belt, already diverted, arrival window)
                  then a soft score combining arrival time, arm balance, grade
                  priority, force budget and the memory prior;
    ``decide``    argmax -> `ManipulationGoal`;
    ``verify``    confidence below `min_confidence`? replan with the next candidate
                  (one bounded retry), else emit.
    """

    def __init__(self, cfg, memory: ExperienceMemory | None = None,
                 policy: str | None = None):
        self.cfg = cfg
        self.memory = memory or ExperienceMemory()
        self.policy = policy or os.environ.get("FRUIT_SLOW_LOOP_POLICY", "rule")
        self.min_confidence = float(os.environ.get("FRUIT_SLOW_MIN_CONFIDENCE", "0.35"))
        # Scorer weights. The `arrival` profile keeps the experience prior almost
        # silent so the agent behaves like the hand-tuned selector (which picks the
        # fruit closest to arriving, then balances the arms); the default gives the
        # memory prior real weight. Sweeping this is the point of the ablation.
        profile = os.environ.get("FRUIT_SLOW_PROFILE", "memory")
        defaults = {
            "memory": (0.35, 0.15, 0.10, 0.40, 0.05),
            "arrival": (0.60, 0.10, 0.10, 0.05, 0.05),
        }[profile if profile in ("memory", "arrival") else "memory"]
        self.w_arrival = float(os.environ.get("FRUIT_W_ARRIVAL", defaults[0]))
        self.w_lateral = float(os.environ.get("FRUIT_W_LATERAL", defaults[1]))
        self.w_balance = float(os.environ.get("FRUIT_W_BALANCE", defaults[2]))
        self.w_memory = float(os.environ.get("FRUIT_W_MEMORY", defaults[3]))
        self.w_grade = float(os.environ.get("FRUIT_W_GRADE", defaults[4]))
        self.profile = profile
        # Optional learned prior: logistic coefficients fitted offline from the
        # candidate-level decision log (scripts/102_fit_slow_loop.py).
        self.learned: dict | None = None
        weights_path = os.environ.get("FRUIT_SLOW_WEIGHTS", "")
        if weights_path and os.path.exists(weights_path):
            try:
                with open(weights_path, encoding="utf-8") as fh:
                    self.learned = json.load(fh)
            except (OSError, json.JSONDecodeError):
                self.learned = None
        self.arm_counts = {"left": 0, "right": 0}
        self.decisions: list[dict] = []

    # ------------------------------------------------------------------ #
    def observe(self, states: list[dict], sim_time: float, belt_speed: float) -> StructuredState:
        return StructuredState(time=float(sim_time), belt_speed=float(belt_speed), fruits=list(states))

    def retrieve(self, state: StructuredState) -> dict[int, dict]:
        return {
            int(f["index"]): self.memory.prior(f.get("category", "?"), float(f["diameter"]))
            for f in state.fruits
        }

    def score(self, state: StructuredState, index: int, priors: dict) -> tuple[float, list[str]]:
        cfg = self.cfg
        notes: list[str] = []
        fruit = next(f for f in state.fruits if int(f["index"]) == index)
        pos = np.asarray(fruit["position"], dtype=float)
        x, y, z = (float(v) for v in pos)
        lateral = x - cfg.belt_center[0]  # across the line (X)
        along = y                          # along the line (Y); +Y is upstream

        # --- hard filters (the design's 硬过滤) --------------------------- #
        if z < cfg.belt_center[2] - 0.05:
            return -1.0, ["off-belt"]
        # Only fruit that are actually *on the belt* are candidates: parked/recycled
        # fruit keep a plausible z but sit far away, and without this the scorer
        # happily selected them (goal rationales with "eta 1237.8s", logs/360).
        if abs(lateral) > 0.30 or not (cfg.pick_y - 0.30 <= along <= cfg.pick_y + 1.60):
            return -1.0, ["not on the belt"]
        if float(fruit["diameter"]) > cfg.gripper_max_object:
            return -1.0, ["too large for the jaws"]

        # --- soft score (软评分) ------------------------------------------ #
        score = 1.0
        # 1. arrival: prefer the fruit closest to the pick station but still coming.
        # `dy` is > 0 upstream (the flow is -Y) and < 0 once past the station.
        dy = along - cfg.pick_y
        if dy < 0.0:
            # already past: only acceptable near the station
            if dy < -0.12:
                return -1.0, ["already past the station"]
            score += 0.2
            notes.append("at the station")
        elif dy <= 0.35:
            score += self.w_arrival
            notes.append("arriving")
        else:
            # upstream: score by arrival time (~belt speed) so the pick is reachable
            # ETA from a *nominal* line speed: the belt is stopped whenever the
            # station is indexing, and using the measured speed then divides by the
            # 1e-3 floor and reports ETA = 1250 s (logs/360/361), which flattened the
            # arrival preference and let the agent pick fruit that could not arrive
            # in time.
            nominal = max(abs(state.belt_speed), 0.05) * 0.4
            eta = dy / max(nominal, 1e-3)
            score += np.clip(self.w_arrival * 0.85 - 0.05 * eta, 0.0, self.w_arrival * 0.85)
            notes.append(f"eta {eta:.1f}s")
        # 2. lateral offset: centred fruit are easier
        score += np.clip(self.w_lateral - abs(lateral) * 2.0, -self.w_lateral, self.w_lateral)
        # 3. arm balance: the design wants both arms used
        arm = "left" if fruit.get("grade") == "A" else "right"
        other = "right" if arm == "left" else "left"
        if self.arm_counts[arm] <= self.arm_counts[other]:
            score += self.w_balance
            notes.append(f"{arm} arm free-ish")
        # 4. memory prior
        prior = priors.get(int(fruit["index"]), {"n": 0, "rate": 0.5})
        score += self.w_memory * (float(prior["rate"]) - 0.5)
        if prior["n"]:
            notes.append(f"memory {prior['rate'] * 100:.0f}% of {prior['n']}")
        # 5. grade priority: A goes to the green bin, prefer it when close in score
        if fruit.get("grade") == "A":
            score += self.w_grade
        # 6. learned prior (if fitted): P(success | features) - 0.5, weighted
        if self.learned is not None:
            features = self._feature_vector(float(fruit["diameter"]), dy, lateral,
                                            float(fruit.get("mass", 0.0)),
                                            fruit.get("grade") == "A",
                                            priors.get(int(fruit["index"]), {"rate": 0.5}))
            z = float(np.dot(self.learned["coef"], features) + self.learned.get("intercept", 0.0))
            probability = 1.0 / (1.0 + np.exp(-np.clip(z, -30, 30)))
            weight = float(os.environ.get("FRUIT_W_LEARNED", "0.6"))
            score += weight * (probability - 0.5)
            notes.append(f"learned p={probability:.2f}")
        notes.append(f"d={float(fruit['diameter']) * 100:.1f}cm")
        return float(score), notes

    @staticmethod
    def _feature_vector(diameter: float, dy: float, lateral: float, mass: float,
                        grade_a: bool, prior: dict) -> list:
        """Order fixed so the offline fit and the runtime agree."""
        import math

        return [
            1.0,
            (float(diameter) - 0.05) / 0.02,
            float(np.clip(dy, -0.3, 1.6)) / 0.4,
            float(lateral) / 0.05,
            (float(mass) - 0.08) / 0.08,
            1.0 if grade_a else 0.0,
            float(prior.get("rate", 0.5)) - 0.5,
            math.log1p(float(prior.get("n", 0.0))) / 3.0,
        ]

    # ------------------------------------------------------------------ #
    def decide(self, states: list[dict], sim_time: float, belt_speed: float
               ) -> ManipulationGoal | None:
        if self.policy == "llm":
            goal = self._llm_decide(states, sim_time, belt_speed)
            if goal is not None:
                return goal
            # fall through to the rule policy: the slow loop must never stall the
            # line because a model is unavailable or slow.
        return self._rule_decide(states, sim_time, belt_speed)

    # ------------------------------------------------------------------ #
    def _llm_decide(self, states: list[dict], sim_time: float, belt_speed: float
                    ) -> ManipulationGoal | None:
        """Ask an OpenAI-compatible endpoint for the goal; None on any failure.

        The prompt carries exactly the structured state plus the memory priors and
        asks for a small JSON object (the same fields as `ManipulationGoal`). A
        short timeout keeps the slow loop from ever blocking the cell; any error,
        timeout or malformed answer falls back to the rule policy.
        """
        import urllib.error
        import urllib.request

        url = os.environ.get("FRUIT_LLM_URL", "")
        if not url:
            return None
        priors = self.retrieve(self.observe(states, sim_time, belt_speed))
        candidates = [
            {
                "index": int(f["index"]),
                "category": f.get("category"),
                "grade": f.get("grade"),
                "diameter_cm": round(float(f["diameter"]) * 100, 1),
                "lateral_x": round(float(f["position"][0]) - self.cfg.belt_center[0], 3),
                "along_y": round(float(f["position"][1]) - self.cfg.pick_y, 3),
                "memory_success": round(float(priors[int(f["index"])]["rate"]), 2),
                "memory_n": int(priors[int(f["index"])]["n"]),
            }
            for f in states
        ]
        prompt = (
            "You are the slow loop of a bimanual fruit-sorting cell. Pick ONE fruit to "
            "grasp next and how. Prefer fruit that will arrive at the pick station soon, "
            "that are centred on the belt, and that have a good track record in memory. "
            "The line runs along Y: `along_y` is the distance upstream (+) or past (-) "
            "the station at (pick_x, pick_y); `lateral_x` is the offset across the belt. "
            "Answer with JSON only: {\"index\": <int>, \"bin_index\": 0|1, "
            "\"skill\": \"grasp_lift_place\", \"force_limit_n\": <float>, "
            "\"approach\": \"vertical\"|\"slanted\", \"rationale\": \"<short>\", "
            "\"confidence\": <0..1>}.\n"
            f"pick_station=({self.cfg.pick_x}, {self.cfg.pick_y})\nfruit={json.dumps(candidates)}"
        )
        payload = json.dumps(
            {
                "model": os.environ.get("FRUIT_LLM_MODEL", "gpt-4o-mini"),
                "messages": [{"role": "user", "content": prompt}],
                "temperature": 0.0,
                "response_format": {"type": "json_object"},
            }
        ).encode()
        request = urllib.request.Request(
            url, data=payload, headers={"Content-Type": "application/json"}
        )
        key = os.environ.get("OPENAI_API_KEY")
        if key:
            request.add_header("Authorization", f"Bearer {key}")
        try:
            with urllib.request.urlopen(request, timeout=float(os.environ.get("FRUIT_LLM_TIMEOUT", "2.0"))) as response:
                body = json.loads(response.read().decode())
            content = body["choices"][0]["message"]["content"]
            answer = json.loads(content)
            index = int(answer["index"])
            fruit = next((f for f in states if int(f["index"]) == index), None)
            if fruit is None:
                return None
            goal = ManipulationGoal(
                index=index,
                category=str(fruit.get("category", "?")),
                grade=str(fruit.get("grade", "C")),
                bin_index=int(answer.get("bin_index", 0 if fruit.get("grade") == "A" else 1)),
                skill=str(answer.get("skill", "grasp_lift_place")),
                force_limit_n=float(answer.get("force_limit_n", 25.0)),
                approach=str(answer.get("approach", "vertical")),
                rationale=str(answer.get("rationale", "llm"))[:200],
                confidence=float(answer.get("confidence", 0.7)),
            )
            self.decisions.append({"index": index, "score": goal.confidence, "latency_ms": 0.0})
            return goal
        except (urllib.error.URLError, TimeoutError, KeyError, ValueError, json.JSONDecodeError,
                OSError):
            return None

    def _rule_decide(self, states: list[dict], sim_time: float, belt_speed: float
                     ) -> ManipulationGoal | None:
        started = time.perf_counter()
        state = self.observe(states, sim_time, belt_speed)
        priors = self.retrieve(state)
        if not state.fruits:
            return None
        scored: list[tuple[float, int, list[str]]] = []
        for fruit in state.fruits:
            value, notes = self.score(state, int(fruit["index"]), priors)
            if value >= 0.0:
                scored.append((value, int(fruit["index"]), notes))
        if not scored:
            return None
        scored.sort(key=lambda item: item[0], reverse=True)
        # `verify`: if the best candidate is not convincing, look at the runner-up
        value, index, notes = scored[0]
        if value < self.min_confidence and len(scored) > 1:
            notes = notes + ["replanned: confidence below threshold"]
            value, index, _ = scored[1]
        fruit = next(f for f in state.fruits if int(f["index"]) == index)
        diameter = float(fruit["diameter"])
        goal = ManipulationGoal(
            index=index,
            category=str(fruit.get("category", "?")),
            grade=str(fruit.get("grade", "C")),
            bin_index=0 if fruit.get("grade") == "A" else 1,
            skill="grasp_lift_place",
            # force budget by size: small fruit get a gentler budget, large ones more
            force_limit_n=float(np.clip(400.0 * float(fruit.get("mass", 0.05)), 12.0, 40.0)) * (
                0.7 if diameter < 0.04 else 1.0
            ),
            approach="vertical" if diameter < 0.045 else "slanted",
            rationale="; ".join(notes),
            confidence=float(np.clip(value, 0.0, 1.0)),
        )
        self.decisions.append(
            {"index": index, "score": value, "latency_ms": (time.perf_counter() - started) * 1000.0}
        )
        # Candidate-level record: every candidate's features plus which one was
        # chosen. The outcome is attached by `record_outcome()` once the attempt
        # finishes, which is what makes the memory usable for offline fitting
        # rather than only for success statistics.
        self.last_context = {
            "time": float(sim_time),
            "chosen": int(index),
            "score": float(value),
            "candidates": [
                {
                    "index": int(fruit["index"]),
                    "category": str(fruit.get("category", "?")),
                    "grade": str(fruit.get("grade", "C")),
                    "diameter": float(fruit["diameter"]),
                    "mass": float(fruit.get("mass", 0.0)),
                    "dx": float(fruit["position"][0] - self.cfg.belt_center[0]),
                    "dy": float(fruit["position"][1] - self.cfg.pick_y),
                    "prior_rate": float(priors.get(int(fruit["index"]), {}).get("rate", 0.5)),
                    "prior_n": float(priors.get(int(fruit["index"]), {}).get("n", 0)),
                    "score": float(next((sc for sc, ix, _ in scored if ix == int(fruit["index"])), -1.0)),
                }
                for fruit in state.fruits
            ],
        }
        self._weights = getattr(self, "_weights", None)
        return goal

    def record_outcome(self, *, success: bool, arm: str, notes: list[str],
                       cycle_s: float) -> None:
        """Attach the attempt's outcome to the last decision and persist it."""
        context = getattr(self, "last_context", None)
        if context is None:
            return
        chosen = next(
            (c for c in context["candidates"] if c["index"] == context["chosen"]), None
        )
        record = {
            "time": context["time"],
            "chosen": context["chosen"],
            "success": bool(success),
            "arm": arm,
            "notes": list(notes),
            "cycle_s": round(float(cycle_s), 2),
            "features": chosen,
            "candidates": context["candidates"],
        }
        path = os.environ.get("FRUIT_DECISION_LOG", "logs/slow_loop_decisions.jsonl")
        try:
            os.makedirs(os.path.dirname(path) or ".", exist_ok=True)
            with open(path, "a", encoding="utf-8") as fh:
                fh.write(json.dumps(record, ensure_ascii=False) + "\n")
        except OSError:
            pass
        self.last_context = None

    # ------------------------------------------------------------------ #
    def latency_ms(self) -> float:
        if not self.decisions:
            return 0.0
        return statistics.mean(d["latency_ms"] for d in self.decisions)

    def summary(self) -> str:
        return (
            f"slow loop({self.profile}): {len(self.decisions)} decisions, "
            f"mean {self.latency_ms():.2f} ms, weights(arrival={self.w_arrival:.2f} "
            f"memory={self.w_memory:.2f} balance={self.w_balance:.2f}), "
            f"memory {self.memory.summary()}"
        )
