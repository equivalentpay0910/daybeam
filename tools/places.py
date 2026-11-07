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
    # Load all places from the CSV file
    file_path = Path(__file__).resolve().parent.parent / "data" / "places.csv"

    places = []

    with open(file_path, newline="", encoding="utf-8") as file:
        reader = csv.DictReader(file)

        for row in reader:
            place = Place(**row)

            # Filter by requested category
            if place.category != category:
                continue

            # Filter by maximum price, if provided
            if max_price_usd is not None and place.price_usd > max_price_usd:
                continue

            places.append(place)

    # Import here to avoid a circular import with routing.py
    from tools.routing import route

    # Calculate driving time from the starting place
    places.sort(
        key=lambda place: route(near_place_id, place.id)
    )
    # Return only the requested number of places
    return places[:limit]