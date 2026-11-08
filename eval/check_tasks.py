"""OWNER: Esha. Checks that every task can actually be solved, using the REAL A* drive times.

It tries every possible plan (every order and every matching place) with forward checking,
and counts how many plans pass all the rules. A task with 0 valid plans is impossible,
so analyze.py leaves it out (no planner could ever pass it).

Run:  python -m eval.check_tasks --tasks data/tasks_dev
Saves eval/results/feasible.csv"""
import argparse, csv, glob, json, os, time

from agent.toolbox import load_places, simulate
from core.schemas import PlannedStop, Task


def count_valid_plans(task: Task) -> tuple[int, int]:
    places = load_places()
    options = {}
    for r in task.stops:
        if r.kind == "fixed":
            options[r.id] = [r.place_id]
        else:
            options[r.id] = [p.id for p in places if p.category == r.category
                             and (r.max_price_usd is None or p.price_usd <= r.max_price_usd)]
    n = len(task.stops)
    valid = explored = 0
    stack = [[]]
    while stack:  # depth-first search over partial plans
        partial = stack.pop()
        used_stops = {p.stop_id for p in partial}
        used_places = {p.place_id for p in partial}
        for r in task.stops:
            if r.id in used_stops:
                continue
            for pid in options[r.id]:
                if pid in used_places:
                    continue
                child = partial + [PlannedStop(stop_id=r.id, place_id=pid)]
                explored += 1
                done = len(child) == n
                if simulate(task, child, finish=done).passed:
                    if done:
                        valid += 1
                    else:
                        stack.append(child)
    return valid, explored


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--tasks", default="data/tasks_dev")
    ap.add_argument("--out", default="eval/results/feasible.csv")
    args = ap.parse_args()
    os.makedirs(os.path.dirname(args.out), exist_ok=True)
    rows = []
    for path in sorted(glob.glob(os.path.join(args.tasks, "*.json"))):
        task = Task(**json.load(open(path)))
        t0 = time.time()
        valid, explored = count_valid_plans(task)
        print(f"{task.id} {task.difficulty:6} valid plans: {valid:5}  ({time.time() - t0:.0f}s)"
              + ("   <- IMPOSSIBLE, will be skipped" if valid == 0 else ""))
        rows.append({"task_id": task.id, "difficulty": task.difficulty, "valid_plans": valid})
    with open(args.out, "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=["task_id", "difficulty", "valid_plans"])
        w.writeheader()
        w.writerows(rows)
    print(f"\nSaved {args.out}. Impossible tasks: {[r['task_id'] for r in rows if r['valid_plans'] == 0] or 'none'}")


if __name__ == "__main__":
    main()
