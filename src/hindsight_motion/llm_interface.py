"""A synthetic, local-only language/motion interface probe; never drives a robot.

The explicit rule tests selection; hand-authored labels independently check it.
Catalog samples are invented coordinates, not qualified robot trajectories.
"""
from __future__ import annotations

import argparse
from collections import Counter
from copy import deepcopy
import hashlib
import json
from pathlib import Path
import time


RULES = """You are testing a synthetic interface, not controlling a robot.
Select a catalog motion using exactly this priority rule:
1. If geometry_known is false, or current support is not double, select null.
2. If rear_x_m <= beam_end_x_m + margin_m, select crouch.
3. Otherwise if upright is false, select recover.
4. Otherwise if goal_error_m > goal_tolerance_m or abs(speed_m_s) > stop_speed_m_s, select brake.
5. Otherwise select hold (hold is required even if already stationary).
Return only a JSON object. Use the selected catalog ID, not the behavior name.
Do not invent fields, units, samples, timing, contacts or a substitute ID.
The catalog is illustrative; selection does not certify physical feasibility.
"""


def canonical(value):
    return json.dumps(value, sort_keys=True, separators=(",", ":"), allow_nan=False)


def digest(value):
    return hashlib.sha256(canonical(value).encode()).hexdigest()


def fixtures():
    """Six declared states, each with an ID/order/instruction nuisance variant."""
    states = [
        ("body_not_clear", {}, "crouch"),
        ("body_clear", {"rear_x_m": 1.3}, "recover"),
        ("moving_at_goal", {"rear_x_m": 1.3, "upright": True}, "brake"),
        ("stationary_at_goal", {"rear_x_m": 1.3, "upright": True, "speed_m_s": 0.0}, "hold"),
        ("unknown_geometry", {"geometry_known": False}, None),
        ("unsupported_entry", {"support": "left"}, None),
    ]
    cases = []
    for name, changes, expected_behavior in states:
        for variant in range(2):
            state = dict(geometry_known=True, support="double", rear_x_m=1.05,
                         beam_end_x_m=1.0, margin_m=0.15, upright=False,
                         goal_error_m=0.1, speed_m_s=0.2)
            state.update(changes)
            task = dict(task_id="traverse-v1", frame="map_x_forward_z_up",
                        goal_x_m=2.0, goal_tolerance_m=0.25,
                        stop_speed_m_s=0.1, hold_s=1.0,
                        upright_pelvis_min_m=0.8)
            catalog = []
            ids = ["m17", "m42", "m08", "m93"] if not variant else ["k61", "k04", "k77", "k32"]
            for i, behavior in enumerate(["crouch", "recover", "brake", "hold"]):
                pelvis = {"crouch": [0.6, 0.6], "recover": [0.6, 0.85],
                          "brake": [0.85, 0.85], "hold": [0.85, 0.85]}[behavior]
                motion = dict(motion_id=ids[i], frame="local_x_forward_z_up", units="m_s",
                              decoder="synthetic-only-v1", state_digest=digest(state)[:12],
                              dt_s=0.1, committed_prefix_samples=1,
                              root_dx_m=[0.0, 0.0 if behavior == "hold" else 0.02],
                              pelvis_z_m=pelvis, desired_support=["double", "double"])
                catalog.append(dict(behavior=behavior, motion=motion))
            expected = next((c["motion"]["motion_id"] for c in catalog
                             if c["behavior"] == expected_behavior), None)
            if variant:
                catalog = list(reversed(catalog))
            cases.append(dict(case_id=f"{name}_v{variant}", group=name, variant=variant,
                              expected_id=expected,
                              actor=dict(instruction=("Pass the beam, recover upright and stop."
                                                      if not variant else
                                                      "Finish upright beyond the obstacle; stop and hold."),
                                         task=task, observation=state, catalog=catalog)))
    return cases


def rule_baseline(actor):
    s, t = actor["observation"], actor["task"]
    if not s["geometry_known"] or s["support"] != "double":
        return None
    if s["rear_x_m"] <= s["beam_end_x_m"] + s["margin_m"]:
        behavior = "crouch"
    elif not s["upright"]:
        behavior = "recover"
    elif s["goal_error_m"] > t["goal_tolerance_m"] or abs(s["speed_m_s"]) > t["stop_speed_m_s"]:
        behavior = "brake"
    else:
        behavior = "hold"
    return next(c["motion"]["motion_id"] for c in actor["catalog"] if c["behavior"] == behavior)


def envelope(actor, selected_id, route):
    if route == "sidecar":
        return dict(motion_id=selected_id, task_id=actor["task"]["task_id"])
    motion = next((c["motion"] for c in actor["catalog"]
                   if c["motion"]["motion_id"] == selected_id), None)
    return deepcopy(dict(motion_id=selected_id, task=actor["task"], motion=motion))


def messages(case, route):
    schema = ("Return exactly {\"motion_id\": ID_OR_NULL, \"task_id\": TASK_ID}. "
              "The caller keeps the original task and selected motion in a sidecar."
              if route == "sidecar" else
              "Return exactly {\"motion_id\": ID_OR_NULL, \"task\": EXACT_TASK_OBJECT, "
              "\"motion\": EXACT_SELECTED_MOTION_OBJECT_OR_NULL}. Copy every field and array.")
    # No labels or expected IDs enter the actor prompt.
    return [dict(role="system", content=RULES + schema),
            dict(role="user", content=canonical(case["actor"]))]


def strict_json(raw):
    def pairs(items):
        value = {}
        for k, v in items:
            if k in value:
                raise ValueError(f"duplicate key: {k}")
            value[k] = v
        return value
    def constant(value):
        raise ValueError(f"nonfinite number: {value}")
    value = json.loads(raw, object_pairs_hook=pairs, parse_constant=constant)
    if not isinstance(value, dict):
        raise ValueError("expected a JSON object")
    return value


def differences(expected, actual, path=""):
    """Report exact semantic changes without treating boolean true as numeric 1."""
    if isinstance(expected, dict):
        if not isinstance(actual, dict):
            return [path or "$schema"]
        errors = []
        for key in expected.keys() | actual.keys():
            p = f"{path}.{key}" if path else key
            errors.extend([p] if key not in expected or key not in actual else
                          differences(expected[key], actual[key], p))
        return sorted(errors)
    if isinstance(expected, list):
        if not isinstance(actual, list) or len(expected) != len(actual):
            return [path]
        return [p for i, (a, b) in enumerate(zip(expected, actual))
                for p in differences(a, b, f"{path}[{i}]")]
    if isinstance(expected, (int, float)) and not isinstance(expected, bool):
        return [] if type(actual) in (int, float) and expected == actual else [path]
    return [] if type(actual) is type(expected) and actual == expected else [path]


def score(case, route, raw):
    result = dict(json_valid=False, id_valid=False, choice_correct=False,
                  task_preserved=False, selected_payload_preserved=False,
                  interface_success=False, errors=[])
    try:
        out = strict_json(raw)
    except (ValueError, TypeError) as exc:
        result["errors"] = [f"parse: {exc}"]
        return result
    result["json_valid"] = True
    selected = out.get("motion_id")
    allowed = {c["motion"]["motion_id"] for c in case["actor"]["catalog"]}
    result["id_valid"] = "motion_id" in out and (selected is None or
                           (isinstance(selected, str) and selected in allowed))
    result["choice_correct"] = result["id_valid"] and selected == case["expected_id"]
    expected = envelope(case["actor"], selected, route)
    errors = differences(expected, out)
    result["errors"] = errors
    result["task_preserved"] = not any(e == "task" or e.startswith("task.") or e == "task_id" for e in errors)
    result["selected_payload_preserved"] = result["id_valid"] and not any(
        e == "motion" or e.startswith("motion.") for e in errors)
    # For sidecar these preservation flags belong to the deterministic wrapper,
    # not to the language model. Correctness still requires the correct choice.
    result["interface_success"] = result["choice_correct"] and not errors
    return result


def summarize(rows, planned):
    summary = {}
    for route in ("relay", "sidecar"):
        subset = [r for r in rows if r["route"] == route]
        scores = [r["score"] for r in subset]
        summary[route] = dict(planned=planned, completed=len(subset), unrun=planned-len(subset),
                             **{k: sum(s[k] for s in scores) for k in
                                ["json_valid", "id_valid", "choice_correct", "task_preserved",
                                 "selected_payload_preserved", "interface_success"]},
                             errors=dict(Counter(e for s in scores for e in s["errors"])))
    return summary


def run(args):
    plan_path = Path(args.plan)
    plan = json.loads(plan_path.read_text())
    cases = fixtures()
    if len(cases) * len(plan["routes"]) != plan["max_generations"]:
        raise ValueError("fixture count changed; version the registration")
    out = Path(args.output)
    out.mkdir(parents=True, exist_ok=False)
    receipt = dict(protocol=plan, plan_sha256=hashlib.sha256(plan_path.read_bytes()).hexdigest(),
                   source_sha256=hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
                   fixture_sha256=digest(cases), backend=args.backend,
                   scope=plan["scope"], status="started", physical_trials=0)
    (out / "receipt.json").write_text(json.dumps(receipt, indent=2) + "\n")
    rows = []
    try:
        if args.backend == "transformers":
            import torch
            import transformers
            torch.set_num_threads(plan["threads"])
            torch.manual_seed(plan["seed"])
            tokenizer = transformers.AutoTokenizer.from_pretrained(
                plan["model"], revision=plan["revision"], local_files_only=True, trust_remote_code=False)
            model = transformers.AutoModelForCausalLM.from_pretrained(
                plan["model"], revision=plan["revision"], local_files_only=True,
                trust_remote_code=False, torch_dtype=torch.float32).to("cpu").eval()
            receipt["runtime"] = dict(torch=torch.__version__, transformers=transformers.__version__,
                                      dtype="float32", device="cpu")
        start = time.monotonic()
        # Interleave routes, preserving unfinished cases as unrun.
        for case in cases:
            for route in plan["routes"]:
                if time.monotonic() - start >= plan["max_inference_wall_seconds"]:
                    break
                prompt = messages(case, route)
                tick = time.monotonic()
                row = dict(case_id=case["case_id"], group=case["group"], variant=case["variant"],
                           route=route, prompt_sha256=digest(prompt), actor=case["actor"])
                if args.backend == "rule":
                    raw = canonical(envelope(case["actor"], rule_baseline(case["actor"]), route))
                else:
                    rendered = tokenizer.apply_chat_template(prompt, tokenize=False,
                                                             add_generation_prompt=True,
                                                             enable_thinking=plan["enable_thinking"])
                    inputs = tokenizer(rendered, return_tensors="pt")
                    with torch.inference_mode():
                        tokens = model.generate(**inputs, max_new_tokens=plan["max_new_tokens"],
                                                max_time=plan["max_generation_seconds"],
                                                do_sample=plan["do_sample"])
                    generated = tokens[0, inputs.input_ids.shape[1]:]
                    raw = tokenizer.decode(generated, skip_special_tokens=True).strip()
                    row.update(input_tokens=inputs.input_ids.shape[1], output_tokens=len(generated),
                               token_limit_reached=len(generated) == plan["max_new_tokens"],
                               eos_observed=int(generated[-1]) in ([model.generation_config.eos_token_id]
                                   if isinstance(model.generation_config.eos_token_id, int)
                                   else model.generation_config.eos_token_id))
                row.update(raw=raw, elapsed_s=time.monotonic()-tick, score=score(case, route, raw))
                rows.append(row)
                with (out / "responses.jsonl").open("a") as f:
                    f.write(json.dumps(row) + "\n")
                print(case["case_id"], route, row["score"]["interface_success"], flush=True)
        receipt["status"] = "completed" if len(rows) == plan["max_generations"] else "budget_stopped"
    except Exception as exc:
        receipt.update(status="infrastructure_error", error=f"{type(exc).__name__}: {exc}")
        raise
    finally:
        receipt["summary"] = summarize(rows, len(cases))
        receipt["completed_generations"] = len(rows)
        (out / "receipt.json").write_text(json.dumps(receipt, indent=2) + "\n")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--plan", default="configs/llm_interface_v1.plan.json")
    parser.add_argument("--output", required=True)
    parser.add_argument("--backend", choices=["rule", "transformers"], default="rule")
    run(parser.parse_args())
