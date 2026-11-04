"""OWNER: Esha. One-shot planner: ONE call to Gemini, no tools, no search.
It sees the request + the list of places and writes the whole plan in one go.
This is our baseline: fast and cheap, but it has to guess travel times."""
import time

from agent.toolbox import load_places
from core.llm import ask
from core.schemas import Place, Plan, PlanResult, Task


def describe_stop(s) -> str:
    """Turn one requested stop into a readable line for the prompt."""
    if s.kind == "fixed":
        what = f"go to place {s.place_id}"
    else:
        what = f"visit ANY place with category '{s.category}'"
        if s.max_price_usd is not None:
            what += f" costing at most ${s.max_price_usd:g}"
    when = f", arrive between {s.window[0]} and {s.window[1]}" if s.window else ""
    return f"- {s.id}: {what}{when}, stay {s.duration_min} min"


def build_prompt(task: Task, places: list[Place]) -> str:
    """Everything the model needs, written out plainly."""
    stops = "\n".join(describe_stop(s) for s in task.stops)
    place_lines = "\n".join(
        f"- {p.id} | {p.name} | {p.category} | ${p.price_usd:g} | open {p.open}-{p.close} | ({p.lat:.4f}, {p.lon:.4f})"
        for p in places
    )
    return f"""You are a day-planning assistant for San Jose, California.

USER REQUEST:
{task.request_text}

HARD RULES:
- Start at {task.start_place_id}, leaving at {task.day_start}.
- End at {task.end_place_id} by {task.day_end}.
- Total spending must be at most ${task.budget_usd:g}.
- Total driving must be at most {task.max_drive_min:g} minutes.
- Include every requested stop exactly once. You choose the ORDER.
- Each place must be open while you are there.

REQUESTED STOPS:
{stops}

PLACES YOU MAY USE (id | name | category | price | hours | (lat, lon)):
{place_lines}

Driving times are not given. Estimate them from the coordinates (roughly 2-3 minutes per km in the city).

Return a plan with task_id "{task.id}" and an ordered list of stops. For each stop give its stop_id
and the place_id you chose (for fixed stops, use the given place). Use only place ids from the list.
Do not include the start or end place as stops."""


def plan_one_shot(task: Task, seed: int = 0, **kwargs) -> PlanResult:
    """Ask Gemini once for a full plan in the exact Plan format."""
    start = time.perf_counter()
    try:
        prompt = build_prompt(task, list(load_places()))
        # temperature 0.7 so the 3 seeds give 3 different samples (each is cached separately)
        reply = ask(prompt, schema=Plan, temperature=0.7, seed=seed)
        plan = Plan.model_validate_json(reply["text"])
        plan.task_id = task.id  # make sure it matches, even if the model typed it wrong
        return PlanResult(plan=plan, method="one_shot", llm_calls=1,
                          tokens_in=reply["tokens_in"], tokens_out=reply["tokens_out"],
                          seconds=time.perf_counter() - start)
    except Exception as e:  # bad JSON, API error, etc. -> counted as a failed plan, not a crash
        return PlanResult(plan=None, method="one_shot", llm_calls=1,
                          seconds=time.perf_counter() - start, error=f"{type(e).__name__}: {e}")
