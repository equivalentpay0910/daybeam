"""OWNER: Kami. Road graph + A* routing."""
import osmnx as ox
import heapq # module to create the priority queue that A* needs.
import math
from pathlib import Path


# Loads the driving road network around SJSU.
# Reuses a saved graph when available to avoid repeated downloads.
# Adds estimated speeds and travel times for A* routing.

def load_road_network():
    ox.settings.use_cache = True

    # Location for saving the processed road graph
    project_folder = Path(__file__).resolve().parent.parent
    graph_file = project_folder / "cache" / "sjsu_roads.graphml"

    # Load the saved graph if it already exists
    if graph_file.exists():
        return ox.io.load_graphml(graph_file)

    # Otherwise, download the road network
    center = (37.3352, -121.8811)

    graph = ox.graph_from_point(
        center,
        dist=1500,
        network_type="drive"
    )

    # Add estimated road speeds and travel times
    graph = ox.routing.add_edge_speeds(graph)
    graph = ox.routing.add_edge_travel_times(graph)

    # Create the cache folder if needed
    graph_file.parent.mkdir(parents=True, exist_ok=True)

    # Save the graph for future runs
    ox.io.save_graphml(graph, graph_file)

    return graph

# above code results: 620 nodes	Road intersections and other road-network connection points
# 1,567 edges	Directed road segments connecting those nodes

""" 
The next function estimate_time:
Estimates the minimum remaining driving time to the goal.
Uses straight-line distance divided by a speed upper bound.
The result is in seconds, matching OSMnx travel_time weights.
"""
def estimate_time(graph, current, goal, max_speed_kph):
    lat1 = math.radians(graph.nodes[current]["y"])
    lon1 = math.radians(graph.nodes[current]["x"])
    lat2 = math.radians(graph.nodes[goal]["y"])
    lon2 = math.radians(graph.nodes[goal]["x"])

    # Haversine formula: straight-line distance in kilometers
    dlat = lat2 - lat1
    dlon = lon2 - lon1

    a = (math.sin(dlat / 2) ** 2 +
         math.cos(lat1) * math.cos(lat2) *
         math.sin(dlon / 2) ** 2)

    distance_km = 6371.0088 * 2 * math.asin(
        min(1.0, math.sqrt(a))
    )

    # Convert estimated travel time from hours to seconds
    return (distance_km / max_speed_kph) * 3600

# A*.
# Finds the fastest route between two road intersection.
# Uses travel time as the cost and our estimate_time() heuristic.
# Returns the path (list of nodes) and total driving time in seconds.

def astar_search(graph, start, goal):
    # Find the highest road speed to use in our heuristic
    max_speed = max(
        data["speed_kph"]
        for _, _, _, data in graph.edges(keys=True, data=True)
    )

    # Priority queue stores (estimated total cost, actual cost, node)
    open_list = [(estimate_time(graph, start, goal, max_speed), 0.0, start)]

    # Best known travel time to each node
    g_score = {start: 0.0}

    # Tracks the previous node so we can reconstruct the path
    came_from = {}

    while open_list:
        f, current_cost, current = heapq.heappop(open_list)

        # Ignore outdated queue entries
        if current_cost > g_score[current]:
            continue

        # Stop when we've reached the destination
        if current == goal:
            path = [current]

            while current in came_from:
                current = came_from[current]
                path.append(current)

            path.reverse()
            return path, current_cost

        # Explore roads leaving the current intersection
        for neighbor, road_options in graph[current].items():
            # There may be multiple roads connecting the same nodes
            road_time = min(
                road["travel_time"]
                for road in road_options.values()
            )

            new_cost = current_cost + road_time

            # Update if we found a faster route to this neighbor
            if new_cost < g_score.get(neighbor, float("inf")):
                g_score[neighbor] = new_cost
                came_from[neighbor] = current

                h = estimate_time(graph, neighbor, goal, max_speed)
                heapq.heappush(
                    open_list,
                    (new_cost + h, new_cost, neighbor)
                )

    # No driving route exists between these intersections
    raise ValueError("No route found between the selected nodes")

def route(a_place_id: str, b_place_id: str, return_path: bool = False):
    """Fastest driving time in MINUTES from place a to place b (directed road graph).

    return_path=False -> float minutes
    return_path=True  -> (minutes, [(lat, lon), ...]) points along the roads, for David's map
    Uses our own A* (heuristic: straight-line distance / top speed, admissible).
    """
    raise NotImplementedError("Kami: implement with OSMnx graph + own A*")
