
# Tests the DayBeam constraint checker.
# Makes sure valid plans pass and plans that break
# the user's requirements are correctly rejected.

import json

from core.schemas import Task, Plan, PlannedStop
from tools.verifier import check_plan


def load_test_task():
    # Load the development planning task
    with open("data/tasks_dev/D001.json") as file:
        return Task(**json.load(file))


def test_verifier_accepts_valid_plan():
    task = load_test_task()

    plan = Plan(
        task_id="D001",
        stops=[
            PlannedStop(stop_id="s1", place_id="P_market_01"),
            PlannedStop(stop_id="s2", place_id="P_rest_01"),
            PlannedStop(stop_id="s3", place_id="P_library_01")
        ]
    )

    result = check_plan(task, plan)

    assert result.passed is True
    assert result.violations == []
    assert len(result.timeline) == 3


def test_verifier_rejects_price_cap():
    task = load_test_task()

    plan = Plan(
        task_id="D001",
        stops=[
            PlannedStop(stop_id="s1", place_id="P_market_01"),
            PlannedStop(stop_id="s2", place_id="P_rest_03"),
            PlannedStop(stop_id="s3", place_id="P_library_01")
        ]
    )

    result = check_plan(task, plan)

    rules = {violation.rule for violation in result.violations}

    assert result.passed is False
    assert "price_cap" in rules




# Checks whether the verifier catches a missing requested stop.
def test_verifier_missing_stop():
    task = load_test_task()

    plan = Plan(
        task_id="D001",
        stops=[
            PlannedStop(stop_id="s1", place_id="P_market_01"),
            PlannedStop(stop_id="s2", place_id="P_rest_01")
        ]
    )

    result = check_plan(task, plan)
    rules = {v.rule for v in result.violations}

    assert result.passed is False
    assert "missing_stop" in rules


# Checks whether the AI selected a place from the wrong category.
def test_verifier_wrong_category():
    task = load_test_task()

    plan = Plan(
        task_id="D001",
        stops=[
            PlannedStop(stop_id="s1", place_id="P_market_01"),
            PlannedStop(stop_id="s2", place_id="P_library_01"),
            PlannedStop(stop_id="s3", place_id="P_library_01")
        ]
    )

    result = check_plan(task, plan)
    rules = {v.rule for v in result.violations}

    assert result.passed is False
    assert "wrong_category" in rules


# Checks whether total spending exceeds the user's budget.
def test_verifier_over_budget():
    task = load_test_task()

    # Set a smaller budget to deliberately test this rule
    task = task.model_copy(update={"budget_usd": 1.0})

    plan = Plan(
        task_id="D001",
        stops=[
            PlannedStop(stop_id="s1", place_id="P_market_01"),
            PlannedStop(stop_id="s2", place_id="P_rest_01"),
            PlannedStop(stop_id="s3", place_id="P_library_01")
        ]
    )

    result = check_plan(task, plan)
    rules = {v.rule for v in result.violations}

    assert result.passed is False
    assert "over_budget" in rules



# Checks that the verifier catches a missed arrival window.
#These are deliberately invalid scenarios. Passing a test means my checker correctly detected the violated constraint.
def test_verifier_late_window():
    task = load_test_task()

    # Make the market's arrival deadline earlier than the day starts
    task.stops[0].window = ("07:00", "08:00")

    plan = Plan(
        task_id="D001",
        stops=[
            PlannedStop(stop_id="s1", place_id="P_market_01"),
            PlannedStop(stop_id="s2", place_id="P_rest_01"),
            PlannedStop(stop_id="s3", place_id="P_library_01")
        ]
    )

    result = check_plan(task, plan)
    rules = {v.rule for v in result.violations}

    assert "window" in rules


# Checks that a visit outside opening hours is rejected.
def test_verifier_closed_place():
    task = load_test_task()

    # Move the day's start to after the market closes
    task.day_start = "14:00"
    task.day_end = "23:00"

    plan = Plan(
        task_id="D001",
        stops=[
            PlannedStop(stop_id="s1", place_id="P_market_01"),
            PlannedStop(stop_id="s2", place_id="P_rest_01"),
            PlannedStop(stop_id="s3", place_id="P_library_01")
        ]
    )

    result = check_plan(task, plan)
    rules = {v.rule for v in result.violations}

    assert "closed" in rules


# Checks whether the plan exceeds the maximum driving time.
def test_verifier_over_drive_cap():
    task = load_test_task()

    # Set a very small driving limit for this test
    task.max_drive_min = 0.1

    plan = Plan(
        task_id="D001",
        stops=[
            PlannedStop(stop_id="s1", place_id="P_market_01"),
            PlannedStop(stop_id="s2", place_id="P_rest_01"),
            PlannedStop(stop_id="s3", place_id="P_library_01")
        ]
    )

    result = check_plan(task, plan)
    rules = {v.rule for v in result.violations}

    assert "over_drive_cap" in rules