"""OWNER: Esha. Beam-search planner (the "Tree of Thoughts" idea from class: BFS/beam search over plans).

State  = a partial plan (ordered stops chosen so far).
Expand = add one more requested stop (fixed place, or one of the 3 nearest matching places).
Prune  = drop partial plans that ALREADY break a rule (forward checking: time window missed,
         place closed, over budget, over the drive cap). This uses the simulator, not the LLM.
Score  = Gemini rates every surviving partial plan 1-10 ("how likely can this still become a
         good full plan?"). This is our EVALUATION FUNCTION / heuristic.
Keep   = only the best `beam_width` partial plans at each depth (beam search, not full BFS).
Every node is saved in search_log so the app can draw the tree (kept = orange, pruned = gray)."""
import time

from pydantic import BaseModel

from agent.toolbox import find_places, get_place, simulate
from core.llm import ask
from core.schemas import Plan, PlannedStop, PlanResult, SearchNode, Task

PER_STOP_OPTIONS = 3      # how many places to try for a flexible stop
MAX_TO_SCORE = 24         # cap on candidates sent to Gemini per depth (controls cost)


class Score(BaseModel):
    idx: int
    score: float


class Scores(BaseModel):
    scores: list[Score]


def _expand(task: Task, partial: list[PlannedStop]) -> list[list[PlannedStop]]:
    done = {p.stop_id for p in partial}
    last = partial[-1].place_id if partial else task.start_place_id
    children = []
    for r in task.stops:
        if r.id in done:
            continue
        if r.kind == "fixed":
            options = [r.place_id]
        else:
            options = [p.id for p in find_places(r.category, last, r.max_price_usd, limit=PER_STOP_OPTIONS)]
        for place_id in options:
            children.append(partial + [PlannedStop(stop_id=r.id, place_id=place_id)])
    return children


def _describe(task: Task, partial: list[PlannedStop]) -> str:
    sim = simulate(task, partial, finish=False)
    steps = ", ".join(f"{t['stop_id']}@{get_place(t['place_id']).name} {t['arrive']}-{t['depart']}" for t in sim.timeline)
    left = [r.id for r in task.stops if r.id not in {p.stop_id for p in partial}]
    return f"{steps} | drive {sim.total_drive_min:g} min | spent ${sim.total_cost_usd:g} | still to do: {left or 'nothing'}"


def _score(task: Task, partials: list[list[PlannedStop]], seed: int):
    lines = "\n".join(f"[{i}] {_describe(task, p)}" for i, p in enumerate(partials))
    windows = "; ".join(f"{r.id}: {r.category or r.place_id}" + (f" arrive {r.window[0]}-{r.window[1]}" if r.window else "")
                        for r in task.stops)
    prompt = f"""You are scoring partial day plans for this request: {task.request_text}
Limits: home by {task.day_end}, budget ${task.budget_usd:g}, driving <= {task.max_drive_min:g} min.
Stops and windows: {windows}

Rate EACH partial plan from 1 (hopeless) to 10 (very likely to become a valid, efficient full plan),
considering time left for the remaining stops, their windows, closing times, money and driving left.

PARTIAL PLANS:
{lines}

Return a score for every index."""
    reply = ask(prompt, schema=Scores, temperature=0.7, seed=seed)
    got = {s.idx: s.score for s in Scores.model_validate_json(reply["text"]).scores}
    return [got.get(i, 0.0) for i in range(len(partials))], reply


def plan_beam(task: Task, seed: int = 0, beam_width: int = 3, **kwargs) -> PlanResult:
    start = time.perf_counter()
    calls = tin = tout = 0
    log = [SearchNode(node_id=0, parent_id=None, depth=0, partial_plan=[], kept=True)]
    beam = [(0, [])]  # (node_id, partial plan)
    try:
        for depth in range(1, len(task.stops) + 1):
            children = []  # (parent_id, partial)
            for parent_id, partial in beam:
                for child in _expand(task, partial):
                    children.append((parent_id, child))

            # forward checking: drop children that already break a hard rule
            feasible, pruned = [], []
            for parent_id, child in children:
                ok = simulate(task, child, finish=(depth == len(task.stops))).passed
                (feasible if ok else pruned).append((parent_id, child))
            for parent_id, child in pruned:
                log.append(SearchNode(node_id=len(log), parent_id=parent_id, depth=depth,
                                      partial_plan=child, kept=False))
            if not feasible:          # nothing valid: keep going with the least-bad ones
                feasible, pruned = pruned, []
            feasible = sorted(feasible, key=lambda pc: simulate(task, pc[1], finish=False).total_drive_min)[:MAX_TO_SCORE]

            scores, reply = _score(task, [c for _, c in feasible], seed)
            calls += 1
            tin += reply["tokens_in"]
            tout += reply["tokens_out"]

            ranked = sorted(zip(scores, feasible), key=lambda x: -x[0])
            new_beam = []
            for rank, (score, (parent_id, child)) in enumerate(ranked):
                node = SearchNode(node_id=len(log), parent_id=parent_id, depth=depth,
                                  partial_plan=child, score=score, kept=rank < beam_width)
                log.append(node)
                if node.kept:
                    new_beam.append((node.node_id, child))
            beam = new_beam

        best_partial = beam[0][1]  # highest-scored complete plan
        return PlanResult(plan=Plan(task_id=task.id, stops=best_partial), method="beam", search_log=log,
                          llm_calls=calls, tokens_in=tin, tokens_out=tout,
                          seconds=time.perf_counter() - start)
    except Exception as e:
        return PlanResult(plan=None, method="beam", search_log=log, llm_calls=calls, tokens_in=tin,
                          tokens_out=tout, seconds=time.perf_counter() - start,
                          error=f"{type(e).__name__}: {e}")
