# DayBeam interfaces (the contract between our three parts)

Everyone codes against this file. If you need to change something here, post in the group chat first.
The exact Python versions of every format live in `core/schemas.py`.

## Who owns what

| Part | Owner | Files |
| --- | --- | --- |
| Shared formats, LLM client | Esha | `core/` |
| Planners: one-shot, ReAct, beam | Esha | `agent/` |
| Roads + A*, places, verifier, test tasks, eval runner | Kami | `tools/`, `data/`, `eval/run_eval.py` |
| Streamlit app, map, search-tree view, deploy | David | `app/` |
| Results analysis + charts | Esha | `notebooks/` |

## Data formats

**Time:** always `"HH:MM"` (24-hour). Use `core/timeutil.py` to convert.

**Place** (one row of `data/places.csv`)
`id, name, category, lat, lon, price_usd, open, close`
Categories: `home, farmers_market, restaurant, cafe, library, park, museum, grocery` (add more only after telling the group).

**Task** (one file per task in `data/tasks/`, see `T001_example.json`)
- `start_place_id`, `end_place_id`, `day_start`, `day_end`, `budget_usd`, `max_drive_min`
- `stops`: list of requested stops. Each is either
  - `fixed`: a specific `place_id`, or
  - `flexible`: a `category` (+ optional `max_price_usd`) and the planner picks the place
  - optional `window: [from, to]` = must ARRIVE in this window; `duration_min` = time spent there
- The planner chooses the ORDER of stops.
- `request_text`: plain-English version given to the LLM.

**Plan** (what every planner outputs)
```json
{"task_id": "T001", "stops": [{"stop_id": "s1", "place_id": "P_market_01"},
                              {"stop_id": "s2", "place_id": "P_rest_01"}]}
```
Only order + place choices. The LLM never writes times; `check_plan()` computes them.

## Simulation rules (how a day is played out)
1. Leave the start place at `day_start`.
2. For each stop in order: `arrive = previous depart + route(prev, this)`. If early for the window, wait until it opens. `depart = arrive + duration_min`.
3. Drive to the end place; must arrive by `day_end`.

A plan **passes** only if every rule holds: all requested stops present exactly once, right category,
place open on arrival and at departure, arrival inside the window, per-stop price cap,
total cost <= budget, total drive <= max_drive_min, home by day_end.

## Functions

```python
# tools/routing.py  (Kami)
route(a_place_id, b_place_id, return_path=False)
    -> float minutes                      # return_path=False
    -> (minutes, [(lat, lon), ...])       # return_path=True, for the map

# tools/places.py  (Kami)
get_place(place_id) -> Place
find_places(category, near_place_id, max_price_usd=None, limit=10) -> list[Place]   # sorted by drive time

# tools/verifier.py  (Kami)
check_plan(task, plan) -> CheckResult
    # passed, violations[rule, stop_id, detail], total_drive_min, total_cost_usd, end_time,
    # timeline [{stop_id, place_id, arrive, depart}]  <- David shows this

# agent/planner.py  (Esha)
plan(task, method="one_shot"|"react"|"beam", seed=0, beam_width=3) -> PlanResult
    # plan, method, search_log [SearchNode], llm_calls, tokens_in, tokens_out, seconds, error
```

**SearchNode** (for the tree view): `node_id, parent_id, depth, partial_plan, score, kept`.
Root has `parent_id = None`. `kept = False` means beam search pruned it (draw it gray).

## Evaluation
`python -m eval.run_eval` runs 3 planners x every task x seeds 0,1,2 -> `eval/results/results.csv`.
Metrics: success rate (passed), violations, drive minutes, cost, LLM calls, tokens, seconds.

## Deadlines
- Oct 31: one task runs end to end (plan -> check_plan -> shown in app)
- Nov 3: full eval run done
- Nov 4-7: slides + backup demo video
- Nov 8-9: rehearsals
