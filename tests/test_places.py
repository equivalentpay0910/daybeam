# Tests for the get_place() function in tools/places.py.
# Makes sure a place can be found using its ID and
# that the correct information is returned from places.csv.

from tools.places import get_place, find_places




def test_get_place():
    place = get_place("P_market_01")

    assert place.name == "DEV Downtown Farmers Market"
    assert place.category == "farmers_market"
    assert place.price_usd == 0.0



# Checks that find_places() filters restaurants by category and price.
#Ensures the correct category and price limit are applied
#Confirms the results are sorted by A* travel times
def test_find_places_filters():
    places = find_places(
        category="restaurant",
        near_place_id="P_market_01",
        max_price_usd=20
    )

    assert len(places) == 3
    assert all(p.category == "restaurant" for p in places)
    assert all(p.price_usd <= 20 for p in places)
    assert "P_rest_03" not in [p.id for p in places]


# Checks that the results are sorted by driving time,
# rather than alphabetically or by price.
def test_find_places_sorted_by_driving_time():
    from tools.routing import route

    places = find_places(
        category="restaurant",
        near_place_id="P_market_01",
        max_price_usd=20
    )

    travel_times = [
        route("P_market_01", p.id)
        for p in places
    ]

    assert travel_times == sorted(travel_times)