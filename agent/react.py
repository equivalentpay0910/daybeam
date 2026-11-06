"""OWNER: Esha. ReAct planner (Reason + Act).
Gemini works in a loop: THINK -> pick a TOOL -> we run it -> it sees the result -> repeat,
until it calls "finish" with a plan. Unlike one-shot, it gets REAL travel times and place data
from the tools, but it only follows one line of reasoning (no search over alternatives)."""
import time
from typing import Literal, Optional

from pydantic import BaseModel

from agent.toolbox import find_places, get_place, route
from core.llm import ask
from core.schemas import Plan, PlannedStop, PlanResult, Task

MAX_STEPS = 10


class ReactStep(BaseModel):
    """The exact shape Gemini must reply in at every step."""
    thought: str
    action: Literal["find_places", "route", "finish"]
    category: Optional[str] = None          # for find_places
    near_place_id: Optional[str] = None     # for find_places
    max_price_usd: Optional[float] = None   # for find_places
    from_place_id: Optional[str] = None     # for route
    to_place_id: Optional[str] = None       # for route
    plan: Optional[list[PlannedStop]] = None  # for finish


def _stop_line(s) -> str:
    if s.kind == "fixed":
        what = f"go to place {s.place_id}"
    else:
        what = f"any place with category '{s.category}'"
        if s.max_price_usd is not None:
            what += f" costing at most ${s.max_price_usd:g}"
    when = f", arrive between {s.window[0]} and {s.window[1]}" if s.window else ""
    return f"- {s.id}: {what}{when}, stay {s.duration_min} min"


def _header(task: Task) -> str:
    stops = "\n".join(_stop_line(s) for s in task.stops)
    return f"""You are a day-planning agent for San Jose, California. You can use tools to look things up.

USER REQUEST: {task.request_text}

HARD RULES:
- Start at {task.start_place_id} leaving {task.day_start}; end at {task.end_place_id} by {task.day_end}.
- Total spend <= ${task.budget_usd:g}. Total driving <= {task.max_drive_min:g} minutes.
- Include every requested stop exactly once; you choose the order. Places must be open while you are there.
- If you arrive before a window opens, you wait until it opens.

REQUESTED STOPS:
{stops}

TOOLS (pick exactly one action per step):
- find_places: give category, near_place_id, optional max_price_usd -> nearby places with price and hours
- route: give from_place_id and to_place_id -> driving minutes
- finish: give plan = ordered list of {{stop_id, place_id}} (do not include start/end)

Think step by step, use tools to check prices, hours and drive times, then finish. You have at most {MAX_STEPS} steps."""


def _run_tool(step: ReactStep) -> str:
    """Run the tool Gemini asked for and describe the result in plain text."""
    try:
        if step.action == "find_places":
            found = find_places(step.category, step.near_place_id, step.max_price_usd, limit=5)
            if not found:
                return "No places found."
            lines = []
            for p in found:
                mins = route(step.near_place_id, p.id)
                lines.append(f"{p.id} | {p.name} | ${p.price_usd:g} | open {p.open}-{p.close} | {mins:g} min drive")
            return "\n".join(lines)
        if step.action == "route":
            return f"{route(step.from_place_id, step.to_place_id):g} minutes"
    except Exception as e:
        return f"Tool error: {type(e).__name__}: {e}"
    return "Unknown action."


def plan_react(task: Task, seed: int = 0, **kwargs) -> PlanResult:
    start = time.perf_counter()
    transcript = []
    calls = tin = tout = 0
    try:
        for step_no in range(1, MAX_STEPS + 1):
            last = step_no == MAX_STEPS
            prompt = _header(task) + "\n\nSO FAR:\n" + ("\n".join(transcript) or "(nothing yet)")
            if last:
                prompt += "\n\nThis is your LAST step: you must use action 'finish' now."
            reply = ask(prompt, schema=ReactStep, temperature=0.7, seed=seed)
            calls += 1
            tin += reply["tokens_in"]
            tout += reply["tokens_out"]
            step = ReactStep.model_validate_json(reply["text"])
            if step.action == "finish" and step.plan:
                return PlanResult(plan=Plan(task_id=task.id, stops=step.plan), method="react",
                                  llm_calls=calls, tokens_in=tin, tokens_out=tout,
                                  seconds=time.perf_counter() - start)
            observation = _run_tool(step)
            transcript.append(f"Step {step_no}. Thought: {step.thought}\n"
                              f"Action: {step.action} {step.model_dump(exclude={'thought', 'action', 'plan'}, exclude_none=True)}\n"
                              f"Result:\n{observation}")
        raise RuntimeError("Never finished with a plan")
    except Exception as e:
        return PlanResult(plan=None, method="react", llm_calls=calls, tokens_in=tin, tokens_out=tout,
                          seconds=time.perf_counter() - start, error=f"{type(e).__name__}: {e}")
