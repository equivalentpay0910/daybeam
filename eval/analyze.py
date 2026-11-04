"""OWNER: Esha. Turns eval/results/results.csv into the summary table + charts for the slides.

Usage:  python -m eval.analyze            -> prints the table, saves charts to eval/results/
"""
import sys

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import pandas as pd

ORANGE, NAVY, GRAY = "#E8590C", "#1E3A64", "#9AA5B1"
COLORS = {"one_shot": GRAY, "react": NAVY, "beam": ORANGE}
LABELS = {"one_shot": "One-shot", "react": "ReAct", "beam": "Beam search"}
ORDER = ["one_shot", "react", "beam"]


def summarize(df: pd.DataFrame) -> pd.DataFrame:
    # success rate per seed first, so we can report mean +/- spread across the 3 runs
    per_seed = df.groupby(["method", "seed"])["passed"].mean().reset_index()
    spread = per_seed.groupby("method")["passed"].agg(["mean", "std"]).rename(
        columns={"mean": "success_rate", "std": "success_std"})
    other = df.groupby("method").agg(avg_violations=("n_violations", "mean"),
                                     avg_llm_calls=("llm_calls", "mean"),
                                     avg_tokens=("tokens_total", "mean"),
                                     avg_seconds=("seconds", "mean"),
                                     runs=("passed", "size"))
    out = spread.join(other).reindex([m for m in ORDER if m in spread.index])
    return out


def main(path="eval/results/results.csv"):
    df = pd.read_csv(path)
    df["passed"] = df["passed"].astype(str).str.lower().eq("true")
    df["n_violations"] = pd.to_numeric(df["n_violations"], errors="coerce").fillna(0)
    df["tokens_total"] = df["tokens_in"] + df["tokens_out"]
    s = summarize(df)

    print("\n=== Summary by planner ===")
    show = s.copy()
    show["success_rate"] = (show["success_rate"] * 100).round(0).astype(int).astype(str) + "%"
    show["success_std"] = (show["success_std"].fillna(0) * 100).round(0).astype(int).astype(str) + " pts"
    print(show.round(2).to_string())

    by_diff = df.groupby(["difficulty", "method"])["passed"].mean().unstack().reindex(
        index=[d for d in ["easy", "medium", "hard"] if d in df["difficulty"].unique()])
    print("\n=== Success rate by difficulty ===")
    print((by_diff * 100).round(0).to_string())

    rules = df["violation_rules"].dropna().astype(str).str.split(";").explode()
    rules = rules[rules != ""]
    if len(rules):
        print("\n=== Most common violations ===")
        print(rules.value_counts().head(8).to_string())

    methods = list(s.index)
    labels = [LABELS[m] for m in methods]
    colors = [COLORS[m] for m in methods]

    # Chart 1: success rate with spread across seeds
    fig, ax = plt.subplots(figsize=(6, 4))
    ax.bar(labels, s["success_rate"] * 100, yerr=s["success_std"].fillna(0) * 100, color=colors, capsize=6)
    ax.set_ylabel("Plans that pass every rule (%)")
    ax.set_ylim(0, 100)
    ax.set_title("Does search make the agent plan better?")
    for side in ("top", "right"):
        ax.spines[side].set_visible(False)
    fig.tight_layout()
    fig.savefig("eval/results/chart_success.png", dpi=200)

    # Chart 2: success vs cost (tokens per task) -- the trade-off slide
    fig, ax = plt.subplots(figsize=(6, 4))
    for m in methods:
        ax.scatter(s.loc[m, "avg_tokens"], s.loc[m, "success_rate"] * 100, s=220, color=COLORS[m], zorder=3)
        ax.annotate(LABELS[m], (s.loc[m, "avg_tokens"], s.loc[m, "success_rate"] * 100),
                    textcoords="offset points", xytext=(10, 6))
    ax.set_xlabel("Average tokens per task (cost)")
    ax.set_ylabel("Success rate (%)")
    ax.set_ylim(0, 105)
    ax.set_title("Is the extra search worth the cost?")
    for side in ("top", "right"):
        ax.spines[side].set_visible(False)
    fig.tight_layout()
    fig.savefig("eval/results/chart_tradeoff.png", dpi=200)

    # Chart 3: success by difficulty
    fig, ax = plt.subplots(figsize=(7, 4))
    (by_diff[[m for m in ORDER if m in by_diff.columns]] * 100).rename(columns=LABELS).plot(
        kind="bar", ax=ax, color=[COLORS[m] for m in ORDER if m in by_diff.columns], rot=0)
    ax.set_ylabel("Success rate (%)")
    ax.set_xlabel("Task difficulty")
    ax.set_ylim(0, 100)
    ax.set_title("Where does search help most?")
    for side in ("top", "right"):
        ax.spines[side].set_visible(False)
    fig.tight_layout()
    fig.savefig("eval/results/chart_difficulty.png", dpi=200)

    s.to_csv("eval/results/summary.csv")
    print("\nSaved: eval/results/summary.csv, chart_success.png, chart_tradeoff.png, chart_difficulty.png")


if __name__ == "__main__":
    main(*sys.argv[1:])
