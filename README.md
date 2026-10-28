# DayBeam

**Does search make AI agents better planners?**
DayBeam plans a day in San José ("farmers market before noon, lunch under $20, home by 6") and
compares three ways an LLM agent can plan: one-shot, ReAct, and beam search. Every plan is checked
against real travel times (A* on San José roads), opening hours, budget, and time windows.

CS 156 (Intro to AI), SJSU, Fall 2026: Esha Hooda, Muhammad Kamran Khan, David Nguyen.

## Setup (once)
```bash
git clone https://github.com/equivalentpay0910/daybeam.git
cd daybeam
python -m venv .venv
source .venv/bin/activate          # Windows: .venv\Scripts\activate
pip install -r requirements.txt
cp .env.example .env               # then paste the API key into .env
pytest                             # should say 2 passed
```

## Run
```bash
streamlit run app/app.py           # the app
python -m eval.run_eval            # the full evaluation
```

## Layout
```
core/       shared formats (schemas.py), LLM client with caching (llm.py)
agent/      planners: one_shot, react, beam            (Esha)
tools/      routing (A*), places, verifier             (Kami)
eval/       evaluation runner + results                (Kami + Esha)
app/        Streamlit app                              (David)
data/       places.csv, tasks/*.json
notebooks/  analysis + experiments (Colab)
tests/      pytest tests
```
See `interfaces.md` for the formats and function signatures everyone codes against.

## Team rules
- Work on a branch (`git checkout -b kami/routing`), open a pull request, one teammate reviews, then merge.
- Never commit `.env` or API keys.
- Run `pytest` before opening a pull request.
