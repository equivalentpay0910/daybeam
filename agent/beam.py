"""OWNER: Esha. beam planner."""
from core.schemas import PlanResult, Task


def plan_beam(task: Task, seed: int = 0, **kwargs) -> PlanResult:
    raise NotImplementedError
