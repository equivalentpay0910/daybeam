
"""Generate reproducible planning tasks for DayBeam evaluation.

Creates easy, medium, and hard tasks using the development
places dataset. The generated tasks will be checked against
the shared Task schema before being saved.
"""
#Task(**task_data) checks that generated tasks have the correct required fields.
#model_dump(mode="json") converts the validated task into JSON-compatible data.
#OUTPUT_DIR.mkdir(...) creates the destination folder if needed.
# json.dump(...) writes the task to a permanent JSON file.



import json
import random
from pathlib import Path

from core.schemas import Task


# Fixed seed so the same tasks can be generated again
RANDOM_SEED = 42

# Location for saving the generated tasks
OUTPUT_DIR = Path("data/tasks")


def save_task(task_data: dict):
    """Validate a task and save it as a JSON file."""

    # Validate against the shared schema
    task = Task(**task_data)

    # Make sure the output folder exists
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    # Save one JSON file per task
    file_path = OUTPUT_DIR / f"{task.id}.json"

    with open(file_path, "w", encoding="utf-8") as file:
        json.dump(task.model_dump(mode="json"), file, indent=2)

    return file_path


# Creates a description based on the task's actual requirements.
def make_request_text(task_data):
    parts = []

    for stop in task_data["stops"]:
        if stop["kind"] == "fixed":
            name = stop["place_id"]
        else:
            name = stop["category"].replace("_", " ")

        description = f"Visit {name}"

        if stop.get("window"):
            description += (
                f" between {stop['window'][0]}"
                f" and {stop['window'][1]}"
            )

        if stop.get("max_price_usd") is not None:
            description += (
                f" costing at most ${stop['max_price_usd']}"
            )

        parts.append(description)

    stops_text = "; ".join(parts)

    return (
        f"Plan a day with these stops in any suitable order: "
        f"{stops_text}. "
        f"Start at {task_data['day_start']} and return "
        f"by {task_data['day_end']}. "
        f"Total budget is ${task_data['budget_usd']} "
        f"and driving must stay under "
        f"{task_data['max_drive_min']} minutes."
    )


# Generates 30 reproducible evaluation tasks.
def generate_tasks():
    templates = {
        "easy": "D001",
        "medium": "D002",
        "hard": "D003"
    }

    created = 0
    skipped = 0

    for number in range(1, 31):
        task_id = f"T{number:03d}"

        # Preserve the original example as T001
        if number == 1:
            continue

        if number <= 10:
            difficulty = "easy"
        elif number <= 20:
            difficulty = "medium"
        else:
            difficulty = "hard"

        output_file = OUTPUT_DIR / f"{task_id}.json"

        # Do not overwrite existing tasks
        if output_file.exists():
            skipped += 1
            continue

        source_id = templates[difficulty]
        source_file = (
            Path("data/tasks_dev") / f"{source_id}.json"
        )

        with open(source_file, encoding="utf-8") as file:
            task_data = json.load(file)

        task_data["id"] = task_id
        task_data["difficulty"] = difficulty

        # Use the task number to create repeatable variations
        variation = number % 4

        if difficulty == "easy":
            task_data["budget_usd"] = [25, 30, 35, 40][variation]
            task_data["day_end"] = ["17:00", "18:00", "18:30", "19:00"][variation]

            # Sometimes require a specific farmers market
            if number % 2 == 0:
                task_data["stops"][0]["kind"] = "fixed"
                task_data["stops"][0]["place_id"] = "P_market_01"
                task_data["stops"][0]["category"] = None

            task_data["stops"][1]["max_price_usd"] = [16, 18, 20, 20][variation]

        elif difficulty == "medium":
            task_data["budget_usd"] = [25, 30, 35, 40][variation]
            task_data["max_drive_min"] = [35, 40, 45, 50][variation]
            task_data["day_end"] = ["16:00", "16:30", "17:00", "17:30"][variation]

            # Vary the required lunch spending limit
            task_data["stops"][2]["max_price_usd"] = [16, 18, 20, 18][variation]

            # Some tasks require a specific park
            if number % 2 == 0:
                task_data["stops"][3]["kind"] = "fixed"
                task_data["stops"][3]["place_id"] = "P_park_01"
                task_data["stops"][3]["category"] = None

        else:
            task_data["budget_usd"] = [70, 75, 80, 85][variation]
            task_data["max_drive_min"] = [45, 50, 55, 60][variation]
            task_data["day_end"] = ["18:00", "19:00", "19:30", "20:00"][variation]

            # Vary the museum visit duration
            task_data["stops"][0]["duration_min"] = [60, 75, 90, 105][variation]

            # Sometimes require the main library
            if number % 2 == 0:
                task_data["stops"][3]["kind"] = "fixed"
                task_data["stops"][3]["place_id"] = "P_library_01"
                task_data["stops"][3]["category"] = None

        # Generate wording that matches the constraints
        task_data["request_text"] = make_request_text(task_data)

        # Validate and save
        save_task(task_data)
        created += 1

    print(f"New tasks created: {created}")
    print(f"Existing generated tasks preserved: {skipped}")
    print("Task generation complete.")


if __name__ == "__main__":
    generate_tasks()