"""Tests the three planners with a FAKE Gemini (no API key, no cost), using the stand-in tools.
Run with:  pytest"""
import json

import pytest

from core.schemas import Task


def fake_ask(prompt, schema=None, temperature=0.0, seed=0):
    name = schema.__name__ if schema else ""
    if name == "Plan":
        text = {"task_id": "D001", "stops": [{"stop_id": "s1", "place_id": "P_market_01"},
                                             {"stop_id": "s2", "place_id": "P_rest_01"},
                                             {"stop_id": "s3", "place_id": "P_library_01"}]}
    elif name == "ReactStep":
        if "Step 1." not in prompt:
            text = {"thought": "find a cheap restaurant", "action": "find_places",
                    "category": "restaurant", "near_place_id": "P_market_01", "max_price_usd": 20}
        else:
            text = {"thought": "done", "action": "finish",
                    "plan": [{"stop_id": "s1", "place_id": "P_market_01"},
                             {"stop_id": "s2", "place_id": "P_rest_01"},
                             {"stop_id": "s3", "place_id": "P_library_01"}]}
    elif name == "Scores":
        n = prompt.count("\n[")
        text = {"scores": [{"idx": i, "score": 10 - i * 0.1} for i in range(n)]}
    else:
        raise AssertionError(name)
    return {"text": json.dumps(text), "tokens_in": 100, "tokens_out": 20}


@pytest.fixture
def task():
    return Task(**json.load(open("data/tasks_dev/D001.json")))


@pytest.mark.parametrize("method", ["one_shot", "react", "beam"])
def test_planner_returns_valid_plan(monkeypatch, task, method):
    import agent.beam, agent.one_shot, agent.react
    for mod in (agent.one_shot, agent.react, agent.beam):
        monkeypatch.setattr(mod, "ask", fake_ask)
    from agent.planner import plan
    from agent.toolbox import check_plan
    r = plan(task, method=method)
    assert r.error is None, r.error
    assert {s.stop_id for s in r.plan.stops} == {"s1", "s2", "s3"}
    result = check_plan(task, r.plan)
    assert result.timeline  # the simulator played the day out
    if method == "beam":
        assert result.passed, result.violations
        assert any(not n.kept for n in r.search_log) or len(r.search_log) > 1


def test_simulator_catches_late_window(task):
    from agent.toolbox import check_plan
    from core.schemas import Plan, PlannedStop
    bad = Plan(task_id="D001", stops=[PlannedStop(stop_id="s3", place_id="P_library_01"),
                                      PlannedStop(stop_id="s2", place_id="P_rest_03"),   # $22 > $20 cap
                                      PlannedStop(stop_id="s1", place_id="P_market_01")])
    r = check_plan(task, bad)
    rules = {v.rule for v in r.violations}
    assert not r.passed and "price_cap" in rules
