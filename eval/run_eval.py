"""OWNER: Kami (runner) + Esha (analysis).
Runs every planner on every task, 3 seeds each, and writes eval/results/results.csv.
Usage:  python -m eval.run_eval
"""
import csv, glob, json, os
from core.schemas import Task
from agent.planner import plan
from tools.verifier import check_plan

METHODS = ["one_shot", "react", "beam"]
SEEDS = [0, 1, 2]

if __name__ == "__main__":
    os.makedirs("eval/results", exist_ok=True)
    tasks = [Task(**json.load(open(p))) for p in sorted(glob.glob("data/tasks/*.json"))]
    with open("eval/results/results.csv", "w", newline="") as f:
        w = csv.writer(f)
        w.writerow(["task_id", "difficulty", "method", "seed", "passed", "n_violations",
                    "drive_min", "cost_usd", "llm_calls", "tokens_in", "tokens_out", "seconds", "error"])
        for t in tasks:
            for m in METHODS:
                for s in SEEDS:
                    r = plan(t, method=m, seed=s)
                    c = check_plan(t, r.plan) if r.plan else None
                    w.writerow([t.id, t.difficulty, m, s, bool(c and c.passed),
                                len(c.violations) if c else "", c.total_drive_min if c else "",
                                c.total_cost_usd if c else "", r.llm_calls, r.tokens_in,
                                r.tokens_out, round(r.seconds, 3), r.error or ""])
                    print(t.id, m, s, "PASS" if c and c.passed else "FAIL", flush=True)
