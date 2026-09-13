"""Grounded Race Engineer: an LLM selects evidence, never invents telemetry.

All display sentences are rendered from the cursor's trusted snapshot. A local
Ollama model may prioritise fact IDs; invalid output, downtime or no configured
model returns deterministic commentary. No model or network is required on stage.
"""
from __future__ import annotations

import json
import os
from pathlib import Path
from urllib.request import Request, urlopen


def build_facts(root: Path, rnd: int, lap: int, driver: str) -> list[dict]:
    raw = json.loads((root / f"artifacts/demo/replay/R{rnd:02d}.json").read_text(encoding="utf-8"))
    if not 1 <= lap <= raw["laps"]:
        raise ValueError("Lap outside the recorded race")
    row = next((r for r in raw["laps_data"] if r["lap"] == lap and r["driver"] == driver), None)
    if row is None:
        return [dict(id="missing", text=f"No timing observation for {driver} on lap {lap}.")]
    if row.get("track_status") != "1" or row.get("in_lap") or row.get("out_lap"):
        return [dict(id="suspended", text=f"{driver}: green-pace forecasting is paused on lap {lap}; "
                     "this is a pit lap or a lap with a non-green track status.")]
    data = json.loads((root / f"artifacts/demo/intelligence/R{rnd:02d}.json").read_text(encoding="utf-8"))
    state = next((s for s in data["snapshots"] if s["lap"] == lap and s["driver"] == driver), None)
    if state is None:
        return [dict(id="warming", text=f"{driver}: collecting enough observations for a pace forecast.")]
    facts = [dict(id="context", text=f"{driver}, lap {lap}: {state['compound']} tyres, "
                  f"{state['tyre_age']:.0f} laps old.")]
    forecast = next((f for f in state["forecasts"] if f["horizon"] == 3), state["forecasts"][0])
    text = f"Continuing this stint under green flags, predicted lap {forecast['target_lap']} pace is {forecast['pace_s']:.2f} seconds"
    if forecast["lower_s"] is not None:
        text += f", with an empirical interval of {forecast['lower_s']:.2f} to {forecast['upper_s']:.2f} seconds"
    facts.append(dict(id="forecast", text=text + "."))
    trend = state["pace_trend_s_per_lap"]
    facts.append(dict(id="trend", text=f"The recent pace trend is {trend:+.3f} seconds per lap; "
                      "fuel, track and traffic also contribute, so this is not a pure wear measurement."))
    scenario = state.get("stop_scenarios", {}).get("HARD")
    if scenario and scenario["supported"]:
        text = f"A HARD-tyre stop scenario estimates a {scenario['step_s']:+.2f} second-per-lap pace step"
        if scenario["radius_s"] is not None:
            text += f", with empirical uncertainty of plus or minus {scenario['radius_s']:.2f} seconds per lap"
        facts.append(dict(id="stop", text=text + "; this does not establish a position gain."))
    # Outcomes become available at the target lap, not when the forecast was issued.
    completed = [e for e in data["evaluation"] if e["driver"] == driver and e["target_lap"] <= lap]
    if completed:
        mae = sum(abs(e["predicted_s"]-e["actual_s"]) for e in completed)/len(completed)
        facts.append(dict(id="evidence", text=f"Across {len(completed)} resolved forecasts so far, "
                          f"this driver's mean absolute error is {mae:.2f} seconds."))
    facts.append(dict(id="basis", text=f"The predictor was trained only through round {data['training_through_round']}; "
                      "future observations are excluded from this commentary."))
    return facts


def validate_selection(value: object, facts: list[dict]) -> list[str]:
    if not isinstance(value, dict) or set(value) != {"fact_ids"}:
        raise ValueError("Expected only fact_ids")
    ids = value["fact_ids"]
    allowed = {f["id"] for f in facts}
    if (not isinstance(ids, list) or not 1 <= len(ids) <= 3
            or not all(isinstance(i, str) and i in allowed for i in ids)
            or len(set(ids)) != len(ids)):
        raise ValueError("Unknown or duplicate fact IDs")
    return ids


def commentary(facts: list[dict], *, use_llm: bool = True) -> dict:
    model = os.environ.get("PITWALL_OLLAMA_MODEL", "") if use_llm else ""
    defaults = [f["id"] for f in facts if f["id"] in ("forecast", "trend", "evidence")][:3]
    ids = defaults or [facts[0]["id"]]
    source, reason = "template", "Local LLM not configured"
    if model:
        prompt = ("You are a Formula 1 race engineer selecting the most useful evidence for this moment. "
                  "Return a JSON object with only fact_ids: one to three distinct IDs from the facts. "
                  "Prioritise actionable uncertainty and forecast evidence. Do not invent facts, "
                  "numbers, pit commands or a position-gain claim. Facts:\n" + json.dumps(facts))
        request = Request("http://127.0.0.1:11434/api/generate",
            data=json.dumps(dict(model=model, prompt=prompt, stream=False,
                format={"type":"object", "properties":{"fact_ids":{"type":"array",
                    "items":{"type":"string", "enum":[f["id"] for f in facts]},
                    "minItems":1, "maxItems":3}}, "required":["fact_ids"], "additionalProperties":False},
                                 options=dict(temperature=0, num_predict=100))).encode(),
            headers={"Content-Type":"application/json"})
        try:
            with urlopen(request, timeout=2.) as response:
                payload = json.loads(response.read(65536))
            ids = validate_selection(json.loads(payload["response"]), facts)
            source, reason = "local_llm", None
        except (OSError, ValueError, KeyError, TypeError):
            reason = "Local LLM unavailable or its evidence selection failed validation"
    chosen = {f["id"]: f["text"] for f in facts}
    return dict(source=source, model=model or None, reason=reason,
                fact_ids=ids, text=" ".join(chosen[i] for i in ids))
