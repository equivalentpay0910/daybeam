# test for my own function (kami)

from tools.places import get_place


def test_get_place():
    place = get_place("P_market_01")

    assert place.name == "Example Farmers Market"
    assert place.category == "farmers_market"
    assert place.price_usd == 0.0
