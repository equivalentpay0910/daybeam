"""OWNER: Esha. The planners call tools ONLY through this file.

It uses Kami's real tools (tools/routing.py, tools/places.py, tools/verifier.py) as soon as
they work. Until then it falls back to simple STAND-INS so the planners can be built and tested now:
  - stand-in route(): straight-line distance x 1.3 (roads aren't straight) at 30 km/h city speed
  - stand-in places: data/places.csv -> data/places_dev.csv (fake DEV places) -> data/places_sample.csv
  - stand-in check_plan(): follows the simulation rules in interfaces.md exactly
Call which_tools() to see which version is being used.
"""
import csv
import math
import os
from functools import lru_cache

from core.schemas import CheckResult, Place, Plan, PlannedStop, Task, Violation
from core.timeutil import to_hhmm, to_min

_status = {}


def _try(real_fn, fallback_fn, name):
    """Call Kami's real function; if it isn't written yet, use the stand-in."""
    def wrapper(*args, **kwargs):
        try:
            out = real_fn(*args, **kwargs)
            _status[name] = "real"
            return out
        except NotImplementedError:
            _status[name] = "stand-in"
            return fallback_fn(*args, **kwargs)
    return wrapper


def which_tools() -> dict:
    return dict(_status)


# ---------- places ----------
@lru_cache(maxsize=1)
def _all_places() -> dict:
    out = {}
    for path in ("data/places_sample.csv", "data/places_dev.csv", "data/places.csv"):
        if os.path.exists(path):
            with open(path, newline="") as f:
                out.update({row["id"]: Place(**row) for row in csv.DictReader(f)})
    return out


def load_places() -> tuple[Place, ...]:
    """The places the planners may use.
    Once Kami's data/places.csv is a real list (20+ places), use ONLY that file.
    Until then, combine it with the DEV places so the practice tasks still work."""
    real = {}
    if os.path.exists("data/places.csv"):
        with open("data/places.csv", newline="") as f:
            real = {row["id"]: Place(**row) for row in csv.DictReader(f)}
    if len(real) >= 20:
        return tuple(real.values())
    return tuple(_all_places().values())


def _standin_get_place(place_id: str) -> Place:
    if place_id in _all_places():
        return _all_places()[place_id]
    raise KeyError(f"Unknown place id: {place_id}")


def _standin_find_places(category, near_place_id, max_price_usd=None, limit=10):
    matches = [p for p in load_places() if p.category == category
               and (max_price_usd is None or p.price_usd <= max_price_usd)]
    matches.sort(key=lambda p: _standin_route(near_place_id, p.id))
    return matches[:limit]


# ---------- routing ----------
def _km(a: Place, b: Place) -> float:
    r = 6371.0
    dlat = math.radians(b.lat - a.lat)
    dlon = math.radians(b.lon - a.lon)
    h = math.sin(dlat / 2) ** 2 + math.cos(math.radians(a.lat)) * math.cos(math.radians(b.lat)) * math.sin(dlon / 2) ** 2
    return 2 * r * math.asin(math.sqrt(h))


def _standin_route(a_place_id, b_place_id, return_path=False):
    a, b = _standin_get_place(a_place_id), _standin_get_place(b_place_id)
    minutes = round(_km(a, b) * 1.3 / 30 * 60, 1)  # 30 km/h average city driving
    if return_path:
        return minutes, [(a.lat, a.lon), (b.lat, b.lon)]
    return minutes


# ---------- wire up real-or-stand-in ----------
from tools import places as _kami_places, routing as _kami_routing, verifier as _kami_verifier  # noqa: E402

_real_get_place = _try(_kami_places.get_place, _standin_get_place, "get_place")


def get_place(place_id: str) -> Place:
    """Look in Kami's data/places.csv first; if the id isn't there (e.g. a DEV place used by
    the practice tasks), fall back to the dev/sample files."""
    try:
        return _real_get_place(place_id)
    except (KeyError, ValueError):
        return _standin_get_place(place_id)

find_places = _try(_kami_places.find_places, _standin_find_places, "find_places")
route = _try(_kami_routing.route, _standin_route, "route")


# ---------- simulation (used by the stand-in verifier and by beam search on partial plans) ----------
def simulate(task: Task, stops: list[PlannedStop], finish: bool = True) -> CheckResult:
    """Play out the day following interfaces.md. finish=False skips the end-of-day checks
    (used to score PARTIAL plans during beam search)."""
    req = {s.id: s for s in task.stops}
    violations, timeline = [], []
    clock = to_min(task.day_start)
    here = task.start_place_id
    drive = cost = 0.0
    seen = set()

    for ps in stops:
        r = req.get(ps.stop_id)
        if r is None or ps.stop_id in seen:
            violations.append(Violation(rule="missing_stop", stop_id=ps.stop_id,
                                        detail="unknown or repeated stop id"))
            continue
        seen.add(ps.stop_id)
        try:
            place = get_place(ps.place_id)
        except (KeyError, ValueError):
            violations.append(Violation(rule="unknown_place", stop_id=ps.stop_id, detail=ps.place_id))
            continue
        if r.kind == "fixed" and ps.place_id != r.place_id:
            violations.append(Violation(rule="wrong_category", stop_id=ps.stop_id,
                                        detail=f"must be {r.place_id}, got {ps.place_id}"))
        if r.kind == "flexible" and place.category != r.category:
            violations.append(Violation(rule="wrong_category", stop_id=ps.stop_id,
                                        detail=f"needs {r.category}, got {place.category}"))
        leg = route(here, ps.place_id)
        drive += leg
        arrive = clock + leg
        if r.window and arrive < to_min(r.window[0]):
            arrive = to_min(r.window[0])  # wait for the window to open
        if r.window and arrive > to_min(r.window[1]):
            violations.append(Violation(rule="window", stop_id=ps.stop_id,
                                        detail=f"arrived {to_hhmm(arrive)}, window ends {r.window[1]}"))
        if arrive < to_min(place.open):
            arrive = to_min(place.open)   # wait for the place to open
        depart = arrive + r.duration_min
        if depart > to_min(place.close):
            violations.append(Violation(rule="closed", stop_id=ps.stop_id,
                                        detail=f"{place.name} closes {place.close}, you leave {to_hhmm(depart)}"))
        if r.max_price_usd is not None and place.price_usd > r.max_price_usd:
            violations.append(Violation(rule="price_cap", stop_id=ps.stop_id,
                                        detail=f"${place.price_usd:g} > ${r.max_price_usd:g}"))
        cost += place.price_usd
        timeline.append({"stop_id": ps.stop_id, "place_id": ps.place_id,
                         "arrive": to_hhmm(arrive), "depart": to_hhmm(depart)})
        clock, here = depart, ps.place_id

    end_time = None
    if not finish:
        # forward check: a stop we haven't done yet whose window has ALREADY closed can never be met
        for sid, r in req.items():
            if sid not in seen and r.window and clock > to_min(r.window[1]):
                violations.append(Violation(rule="window", stop_id=sid,
                                            detail=f"it's {to_hhmm(clock)}, window for {sid} closed at {r.window[1]}"))
    if finish:
        for sid in req:
            if sid not in seen:
                violations.append(Violation(rule="missing_stop", stop_id=sid, detail="stop not in plan"))
        leg = route(here, task.end_place_id)
        drive += leg
        clock += leg
        end_time = to_hhmm(clock)
        if clock > to_min(task.day_end):
            violations.append(Violation(rule="late_end", detail=f"home at {end_time}, limit {task.day_end}"))
    if cost > task.budget_usd:
        violations.append(Violation(rule="over_budget", detail=f"${cost:g} > ${task.budget_usd:g}"))
    if drive > task.max_drive_min:
        violations.append(Violation(rule="over_drive_cap", detail=f"{drive:.0f} min > {task.max_drive_min:g} min"))
    return CheckResult(passed=not violations, violations=violations, total_drive_min=round(drive, 1),
                       total_cost_usd=cost, end_time=end_time, timeline=timeline)


def _standin_check_plan(task: Task, plan: Plan) -> CheckResult:
    return simulate(task, plan.stops, finish=True)


check_plan = _try(_kami_verifier.check_plan, _standin_check_plan, "check_plan")
