"""OWNER: Kami (runner) + Esha (analysis).
Runs every planner on every task, several seeds each, and writes eval/results/results.csv.

Usage (from the repo root):
    python -m eval.run_eval                          # Kami's real tasks in data/tasks/
    python -m eval.run_eval --tasks data/tasks_dev   # Esha's 3 dev tasks (quick test)
    python -m eval.run_eval --limit 5 --seeds 0      # first 5 tasks, 1 seed (cheap smoke test)
"""
import argparse
import csv
import glob
import json
import os

from agent.planner import plan
from agent.toolbox import check_plan, which_tools
from core.schemas import Task

if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--tasks", default="data/tasks")
    ap.add_argument("--methods", default="one_shot,react,beam")
    ap.add_argument("--seeds", default="0,1,2")
    ap.add_argument("--limit", type=int, default=0)
    ap.add_argument("--out", default="eval/results/results.csv")
    a = ap.parse_args()

    paths = sorted(glob.glob(os.path.join(a.tasks, "*.json")))
    if a.limit:
        paths = paths[: a.limit]
    tasks = [Task(**json.load(open(p))) for p in paths]
    methods = a.methods.split(",")
    seeds = [int(s) for s in a.seeds.split(",")]
    os.makedirs(os.path.dirname(a.out), exist_ok=True)

    with open(a.out, "w", newline="") as f:
        w = csv.writer(f)
        w.writerow(["task_id", "difficulty", "n_stops", "method", "seed", "passed", "n_violations",
                    "violation_rules", "drive_min", "cost_usd", "llm_calls", "tokens_in", "tokens_out",
                    "seconds", "error"])
        for t in tasks:
            for m in methods:
                for s in seeds:
                    r = plan(t, method=m, seed=s)
                    c = check_plan(t, r.plan) if r.plan else None
                    w.writerow([t.id, t.difficulty, len(t.stops), m, s, bool(c and c.passed),
                                len(c.violations) if c else "",
                                ";".join(v.rule for v in c.violations) if c else "",
                                c.total_drive_min if c else "", c.total_cost_usd if c else "",
                                r.llm_calls, r.tokens_in, r.tokens_out, round(r.seconds, 3), r.error or ""])
                    f.flush()
                    print(f"{t.id} {m:<8} seed {s}: {'PASS' if c and c.passed else 'FAIL'}"
                          f"{'  (' + r.error + ')' if r.error else ''}", flush=True)
    print("\nTools used:", which_tools())
    print("Saved:", a.out)
