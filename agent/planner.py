"""OWNER: Esha. The three planners. The app and the eval runner only call plan()."""
from core.schemas import PlanResult, Task


def plan(task: Task, method: str = "one_shot", seed: int = 0, beam_width: int = 3) -> PlanResult:
    """method: "one_shot" | "react" | "beam"  (stretch: "bfs", "mcts")"""
    if method == "one_shot":
        from agent.one_shot import plan_one_shot
        return plan_one_shot(task, seed=seed)
    if method == "react":
        from agent.react import plan_react
        return plan_react(task, seed=seed)
    if method == "beam":
        from agent.beam import plan_beam
        return plan_beam(task, seed=seed, beam_width=beam_width)
    raise ValueError(f"Unknown method: {method}")
