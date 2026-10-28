"""OWNER: Kami. The goal test. Plain code, no LLM. Every result in the project depends on this."""
from core.schemas import CheckResult, Plan, Task


def check_plan(task: Task, plan: Plan) -> CheckResult:
    """Simulate the day and check every rule.

    Simulation rules (everyone agrees on these):
      1. Leave task.start_place_id at task.day_start.
      2. For each stop in plan order: arrive = previous depart + route(prev, this).
         If arrive is before the stop's window start, WAIT until the window start.
         depart = arrive + duration_min.
      3. After the last stop, drive to task.end_place_id; must arrive by task.day_end.
    Rules to check: every requested stop appears exactly once; flexible stops use a place
    of the right category; place is open on arrival and still open at departure; arrival
    inside the window; per-stop price cap; total cost <= budget; total drive <= max_drive_min.
    """
    raise NotImplementedError("Kami: implement + write tests in tests/test_verifier.py")
