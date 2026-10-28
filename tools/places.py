"""OWNER: Kami. Places data (data/places.csv) + lookup."""
from core.schemas import Place


def get_place(place_id: str) -> Place:
    raise NotImplementedError


def find_places(category: str, near_place_id: str, max_price_usd: float | None = None,
                limit: int = 10) -> list[Place]:
    """Places of this category, cheapest-enough, sorted by drive time from near_place_id."""
    raise NotImplementedError("Kami: load data/places.csv and filter")
