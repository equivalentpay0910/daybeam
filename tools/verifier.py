"""OWNER: Kami. The goal test. Plain code, no LLM. Every result in the project depends on this."""
from collections import Counter

from core.schemas import CheckResult, Plan, Task, Violation
from tools.places import get_place
from tools.routing import route



# Converts a clock time such as "09:30" into minutes after midnight.
def time_to_minutes(time_text: str) -> int:
    hours, minutes = map(int, time_text.split(":"))
    return hours * 60 + minutes


# Converts minutes after midnight back to a 24-hour clock time.
def minutes_to_time(total_minutes: float) -> str:
    hours = int(total_minutes // 60)
    minutes = int(total_minutes % 60)
    return f"{hours:02d}:{minutes:02d}"




# Checks that the AI included every requested stop exactly once.
# Also checks whether selected places exist and match the request.
# Returns a list of violations if something is wrong.

def check_stops(task: Task, plan: Plan) -> list[Violation]:
    violations = []

    # Count how many times each stop appears in the plan
    stop_counts = Counter(stop.stop_id for stop in plan.stops)

    for request in task.stops:
        count = stop_counts[request.id]

        if count != 1:
            violations.append(Violation(
                rule="missing_stop",
                stop_id=request.id,
                detail=f"Expected this stop once, but found {count}"
            ))

    # Check each selected place
    requests = {request.id: request for request in task.stops}

    for stop in plan.stops:
        request = requests.get(stop.stop_id)

        if request is None:
            violations.append(Violation(
                rule="missing_stop",
                stop_id=stop.stop_id,
                detail="This stop was not requested"
            ))
            continue

        try:
            place = get_place(stop.place_id)
        except ValueError:
            violations.append(Violation(
                rule="unknown_place",
                stop_id=stop.stop_id,
                detail=f"Unknown place: {stop.place_id}"
            ))
            continue

        # Check that the chosen place matches a fixed request
        if request.kind == "fixed" and stop.place_id != request.place_id:
            violations.append(Violation(
                rule="wrong_category",
                stop_id=stop.stop_id,
                detail="The selected place does not match the fixed request"
            ))

        # Check the category for a flexible stop
        if request.kind == "flexible" and place.category != request.category:
            violations.append(Violation(
                rule="wrong_category",
                stop_id=stop.stop_id,
                detail=f"Expected {request.category}, got {place.category}"
            ))

    return violations



def check_plan(task: Task, plan: Plan) -> CheckResult:
    """Simulate the day and check every rule.

    Simulation rules (everyone agrees on these):
      1. Leave task.start_place_id at task.day_start.
      2. For each stop in plan order: arrive = previous depart + route(prev, this).
         If arrive is before the stop's window start, WAIT until the window start.
         depart = arrive + duration_min.
      3. After the last stop, drive to task.end_place_id; must arrive by task.day_end.
    Rules to check: every requested stop appears exactly once; flexible stops use a place
    of the right category; place is open on arrival and still open at departure; arrival
    inside the window; per-stop price cap; total cost <= budget; total drive <= max_drive_min.
    """
    # First, check that the selected stops are valid
    violations = check_stops(task, plan)

    # Match each requested stop with its requirements
    requests = {stop.id: stop for stop in task.stops}

    # Start the day at the user's starting location
    current_place = task.start_place_id
    current_time = float(time_to_minutes(task.day_start))

    total_drive = 0.0
    total_cost = 0.0
    timeline = []

    # Simulate each stop in the order chosen by the AI
    for stop in plan.stops:
        request = requests.get(stop.stop_id)

        # Skip stops we cannot safely simulate
        if request is None:
            continue

        try:
            place = get_place(stop.place_id)
        except ValueError:
            continue

        # Calculate travel time to this stop
        driving_time = route(current_place, stop.place_id)
        total_drive += driving_time

        arrival = current_time + driving_time

        # Wait if we arrive before the requested time window
        if request.window:
            window_start = time_to_minutes(request.window[0])
            window_end = time_to_minutes(request.window[1])

            if arrival < window_start:
                arrival = float(window_start)

            if arrival > window_end:
                violations.append(Violation(
                    rule="window",
                    stop_id=stop.stop_id,
                    detail="Arrived after the allowed time window"
                ))

        departure = arrival + request.duration_min

        # Check whether the place is open during the visit
        if (arrival < time_to_minutes(place.open)
                or departure > time_to_minutes(place.close)):
            violations.append(Violation(
                rule="closed",
                stop_id=stop.stop_id,
                detail=f"{place.name} is closed during the visit"
            ))

        # Check individual stop price limit
        if (request.max_price_usd is not None
                and place.price_usd > request.max_price_usd):
            violations.append(Violation(
                rule="price_cap",
                stop_id=stop.stop_id,
                detail=f"Price ${place.price_usd} exceeds the stop limit"
            ))

        total_cost += place.price_usd

        # Record arrival and departure for David's app
        timeline.append({
            "stop_id": stop.stop_id,
            "place_id": stop.place_id,
            "arrive": minutes_to_time(arrival),
            "depart": minutes_to_time(departure)
        })

        current_time = departure
        current_place = stop.place_id

    # Drive back to the ending location
    drive_home = route(current_place, task.end_place_id)
    total_drive += drive_home
    current_time += drive_home

    # Check the total spending limit
    if total_cost > task.budget_usd:
        violations.append(Violation(
            rule="over_budget",
            detail="Total cost exceeds the budget"
        ))

    # Check the maximum allowed driving time
    if total_drive > task.max_drive_min:
        violations.append(Violation(
            rule="over_drive_cap",
            detail="Total driving time exceeds the limit"
        ))

    # Check whether the user gets home before the deadline
    if current_time > time_to_minutes(task.day_end):
        violations.append(Violation(
            rule="late_end",
            detail="Returned home after the deadline"
        ))

    return CheckResult(
        passed=len(violations) == 0,
        violations=violations,
        total_drive_min=total_drive,
        total_cost_usd=total_cost,
        end_time=minutes_to_time(current_time),
        timeline=timeline
    )