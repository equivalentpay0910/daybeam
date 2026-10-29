
# Tests our A* routing algorithm against NetworkX.
# Checks that both algorithms find the same shortest driving time
# and that the returned path has the correct start and end nodes.

import networkx as nx
import pytest

from tools.routing import load_road_network, astar_search


@pytest.fixture(scope="module")
def road_graph():
    # Load the road network once for all tests in this file
    return load_road_network()


def test_astar_matches_networkx(road_graph):
    # Select two different intersections from the road network
    nodes = list(road_graph.nodes)
    start = nodes[0]
    goal = nodes[100]

    # Calculate the shortest driving time using our A*
    path, our_time = astar_search(road_graph, start, goal)

    # Calculate the shortest driving time using NetworkX
    expected_time = nx.shortest_path_length(
        road_graph, start, goal, weight="travel_time"
    )

    # Compare both travel times
    assert our_time == pytest.approx(expected_time, abs=0.001)

    # Check the first and last nodes of the returned route
    assert path[0] == start
    assert path[-1] == goal




"""
Next Function:
Allows pytest to run the same test with several different inputs. 
Instead of writing five nearly identical tests, we specify five start-goal pairs.
Each pair becomes a separate test case.
Tests A* on several different routes to make sure it returns the same shortest driving time as NetworkX.
"""

@pytest.mark.parametrize("start_index, goal_index", [
    (0, 50),
    (10, 150),
    (20, 200),
    (100, 300),
    (250, 500),
])
def test_astar_multiple_routes(road_graph, start_index, goal_index):
    nodes = list(road_graph.nodes)

    start = nodes[start_index]
    goal = nodes[goal_index]

    # Run our A* algorithm
    path, our_time = astar_search(road_graph, start, goal)

    # Compare against NetworkX shortest travel time
    expected_time = nx.shortest_path_length(
        road_graph, start, goal, weight="travel_time"
    )

    assert our_time == pytest.approx(expected_time, abs=0.001)
    assert path[0] == start
    assert path[-1] == goal
