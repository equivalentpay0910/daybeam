"""OWNER: Kami. Places data (data/places.csv) + lookup."""
import csv
from pathlib import Path
from core.schemas import Place



def get_place(place_id: str) -> Place:
    # Find places.csv inside the project's data folder
    file_path = Path(__file__).resolve().parent.parent / "data" / "places.csv"

    # Open the CSV file
    with open(file_path, newline="", encoding="utf-8") as file:
        reader = csv.DictReader(file)

        # Check each place in the CSV
        for row in reader:
            if row["id"] == place_id:
                return Place(**row)

    # If no matching place was found
    raise ValueError(f"Unknown place ID: {place_id}")



def find_places(category: str, near_place_id: str, max_price_usd: float | None = None,
                limit: int = 10) -> list[Place]:
    """Places of this category, cheapest-enough, sorted by drive time from near_place_id."""
    raise NotImplementedError("Kami: load data/places.csv and filter")
