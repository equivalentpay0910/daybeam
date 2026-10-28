"""OWNER: Kami. Road graph + A* routing."""

def route(a_place_id: str, b_place_id: str, return_path: bool = False):
    """Fastest driving time in MINUTES from place a to place b (directed road graph).

    return_path=False -> float minutes
    return_path=True  -> (minutes, [(lat, lon), ...]) points along the roads, for David's map
    Uses our own A* (heuristic: straight-line distance / top speed, admissible).
    """
    raise NotImplementedError("Kami: implement with OSMnx graph + own A*")
