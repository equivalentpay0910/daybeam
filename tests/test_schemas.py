"""Run with:  pytest   (from the repo root). Checks the example task matches the shared format."""
import json
from core.schemas import Plan, PlannedStop, Task


def test_example_task_loads():
    t = Task(**json.load(open("data/tasks/T001_example.json")))
    assert t.id == "T001" and len(t.stops) == 3


def test_plan_shape():
    p = Plan(task_id="T001", stops=[PlannedStop(stop_id="s1", place_id="P_market_01")])
    assert p.stops[0].place_id == "P_market_01"
