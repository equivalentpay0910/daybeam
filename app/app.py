"""OWNER: David. Streamlit app.  Run from the repo root:  streamlit run app/app.py"""
from datetime import time
import hashlib, heapq, pathlib, sys, traceback
from itertools import count
from typing import Literal
from collections import defaultdict, deque

sys.path.append(str(pathlib.Path(__file__).resolve().parents[1]))  # lets the app import core/, agent/, tools/
from agent.planner import plan
from core.schemas import Plan, PlannedStop, PlanResult, SearchNode, StopRequest, Task
import pandas as pd
import numpy as np

import folium
from folium.plugins import AntPath, MarkerCluster
from folium import DivIcon
import streamlit as st
from streamlit_folium import st_folium
import graphviz

def main():
    """The main method of the class. Can be treated like the blueprint for the webpage itself."""
    initialize_state_if_not_already()
    
    st.set_page_config(page_title="DayBeam", page_icon="☀️", layout="wide")
    st.title("DayBeam")
    st.caption("Plan your day in San José with AI search")

    st.divider()

    tabDisplay, tabCreate = st.tabs(["Display", "Create"], key="active_tab", on_change="rerun")

    with tabCreate:
        enable_tab_create()
    with tabDisplay:
        enable_tab_display()

def initialize_state_if_not_already():
    """Initializes variables that are never deleted: overridden, maybe, but never deleted."""
    if "initialized" not in st.session_state:
        st.session_state["search_map_stops"] = []
        st.session_state["df"] = pd.read_csv("data/places.csv").dropna()
        st.session_state["plan_result"] = get_default_map_show_iterate(20)
        st.session_state["display_maps"] = []
        iteration = 0
        finished = False
        while(not finished):
            finished = iterate_history(iteration, 1.2, 5)
            iteration += 1
        st.session_state["active_tab"] = "Display"
        st.session_state["stop_counter"] = count()
        st.session_state["selected_stops"] = {}
        st.session_state["time_d_e"] = time(0, 0)
        st.session_state["time_d_l"] = time(23, 59)
        st.session_state["initialized"] = True

def enable_tab_create():
    """Displays the create tab"""
    request = st.text_area("What do you want to do?",
                        "Farmers market before noon, lunch under $20, library by 3, home by 6.")
    
    startTime, endTime = make_day_frame()
    budget, drive = make_budget_and_drive()
    start, end = make_start_end_locations()
    method, seed, beamWidth = make_method_info()
    colFixeds, colFlexibles = st.columns(2)
    with colFixeds:
        make_fixeds()
    with colFlexibles:
        make_flexibles()
    
    generate_stop_forms()

    if st.button("Plan my day", on_click=switch_to_display):
        try:
            task = Task(id="-1", 
                request_text=request, 
                start_place_id=start, 
                end_place_id=end, 
                day_start=startTime.strftime("%H:%M"),
                day_end=endTime.strftime("%H:%M"),
                budget_usd=round(budget, 2),
                max_drive_min=drive,
                stops=list(st.session_state["selected_stops"].values())) # id -1 is a placeholder value. Will be replaced with the clean task method from Kami
            # call method from Kami to clean the task here
            planResult = plan(task=task, method=method, seed=seed, beam_width=beamWidth)
            if planResult:
                st.session_state["plan_result"] = planResult
                st.session_state["display_maps"] = []
                iteration = 0
                finished = False
                while(not finished):
                    finished = iterate_history(iteration, 1.2, 5)
                    iteration += 1
                st.rerun()
        
        except Exception as e:
            st.error(e)
            traceback.print_exc()
    
    st.subheader("Stops Map")
    st_folium(build_stops_map(list(st.session_state["selected_stops"].values()), start, end), 
            width=900, height=500, 
            key=f"daybeam_search_map", 
            returned_objects=[]
    )

def enable_tab_display():
    """Displays the display tab"""
    try:
        if(len(st.session_state["display_maps"])-1>0):
            mapSlider = st.slider("Select search state from sample",
                            min_value=0,
                            max_value=len(st.session_state["display_maps"])-1,
                            value=len(st.session_state["display_maps"])-1
            )
        else:
            mapSlider = 0
        currData = st.session_state["display_maps"][mapSlider]
        match currData["type"]:
            case "route":
                currMap = build_map_animated_route(currData["stops"])
            case "potential":
                currMap = build_potential_routes_map(currData["nodes"])
            case _:
                currMap = folium.Map(location=[37.3352, -121.8811], zoom_start=14)

        st.subheader("Route Map")
        st_folium(currMap, 
                width=900, height=500, 
                key=f"daybeam_display_map_{mapSlider}", 
                returned_objects=[]
        )

        st.subheader("Search Tree")
        if "plan_result" in st.session_state and st.session_state["plan_result"].search_log:
            tree_graph = build_search_tree_graph(st.session_state["plan_result"])
            st.graphviz_chart(tree_graph, width='content')
    except Exception as e:
        st.error(e)
        traceback.print_exc()

def make_method_info():
    method = st.selectbox("Planner", ["one_shot", "react", "beam"])
    if method == "beam":
        colSeed, colBeamWidth = st.columns(2)
        with colSeed:
            seed = st.number_input(
                "Enter agent seed",
                min_value=0,
                step=1,
                key="seed"
            )
        with colBeamWidth:
            beamWidth = st.number_input(
                "Enter beam width",
                min_value=1,
                value = 3,
                step=1,
                key="beamWidth"
            )
        return method, seed, beamWidth
    seed = st.number_input(
        "Enter agent seed",
        min_value=0,
        step=1,
        key="seed"
    )
    return method, seed, 3

def make_day_frame():
    """Creates two time inputs to bound the day"""
    colEarly, colLate = st.columns(2)
    with colEarly:
        startTime = st.time_input("Start of Day", 
                    key="time_d_e", 
                    on_change=update_order_time_border)
    with colLate:
        endTime = st.time_input("End of day", 
                    key="time_d_l",
                    on_change=update_order_time_border)
    return startTime, endTime

def make_budget_and_drive():
    """Creates a form to fill out budget and driving time. Organized as such because neither field needs to take up a whole row."""
    colBudget, colDrive = st.columns(2)
    with colBudget:
        budget = st.number_input(
            "Enter budget (USD)",
            min_value=0.0,
            step=0.01,
            format="%.2f",
            key="budget"
        )
    with colDrive:
        drive = st.number_input(
            "Enter driving time (minutes)",
            min_value=0.0,
            step=1.0,
            key="drive"
        )
    return budget, drive

def make_start_end_locations():
    """Creates two select boxes to select starting and end locations"""
    colStart, colEnd = st.columns(2)
    with colStart:
        start = st.selectbox(
        "Starting location:",
        options=st.session_state["df"]["id"],
        format_func=lambda x: st.session_state["df"].loc[st.session_state["df"]["id"]==x, "name"].values[0],
        key="select_start"
        )

    with colEnd:
        end = st.selectbox(
        "Ending location:",
        options=st.session_state["df"]["id"],
        format_func=lambda x: st.session_state["df"].loc[st.session_state["df"]["id"]==x, "name"].values[0],
        key="select_end"
        )
    return (start, end)

def make_fixeds():
    """Creates a selectbox to add specific stop locations. Multiple of the same stop location can be added."""
    st.selectbox(
    "Choose your desired stops locations:",
    index=None,
    options=st.session_state["df"]["id"],
    format_func=lambda x: st.session_state["df"].loc[st.session_state["df"]["id"]==x, "name"].values[0],
    placeholder="Type to search or select stop locations...",
    key="select_fixed",
    on_change=add_stop,
    args=("fixed", "select_fixed")
    )

def make_flexibles():
    """Creates a selectbox to add stop categories. Multiple of the same stop category can be added."""
    st.selectbox(
        "Choose your desired stop categories:",
        index=None,
        options=st.session_state["df"]["category"].unique(),
        placeholder="Type to search or select stop categories...",
        key="select_flexible",
        on_change=add_stop,
        args=("flexible", "select_flexible")
    )

def generate_stop_forms():
    """Creates expandable forms for each selected stop"""
    for selected_stop_id in list(st.session_state["selected_stops"].keys()):
        try:
            selected_stop = st.session_state["selected_stops"][selected_stop_id]
            if f"time_e_{selected_stop_id}" not in st.session_state:
                st.session_state[f"time_e_{selected_stop_id}"] = None
            if f"time_l_{selected_stop_id}" not in st.session_state:
                st.session_state[f"time_l_{selected_stop_id}"] = None
            if f"dur_{selected_stop_id}" not in st.session_state:
                st.session_state[f"dur_{selected_stop_id}"] = 30

            if selected_stop.kind == "flexible":
                name = selected_stop.category
            else:
                filteredDf = st.session_state["df"][st.session_state["df"]["id"] == selected_stop.place_id]["name"]
                if len(filteredDf) > 0:
                    name = filteredDf.iloc[0]
                else:
                    continue
            with st.expander(f"Add details for {name}"):
                colEarly, colLate = st.columns(2)
                with colEarly:
                    st.time_input("Earliest Acceptable Arrival Time", 
                                                    key=f"time_e_{selected_stop_id}", 
                                                    on_change=update_order_time, 
                                                    args=(f"time_e_{selected_stop.id}", f"time_l_{selected_stop_id}", selected_stop_id))
                with colLate:
                    st.time_input("Latest Acceptable Arrival Time", 
                                                key=f"time_l_{selected_stop_id}",
                                                on_change=update_order_time, 
                                                args=(f"time_e_{selected_stop_id}", f"time_l_{selected_stop_id}", selected_stop_id))
                colDur, colBud = st.columns(2)
                with colDur:
                    st.number_input("Duration (minutes)", 
                                            min_value=0, 
                                            step=5, 
                                            key=f"dur_{selected_stop_id}",
                                            on_change=update_duration, 
                                            args=(f"dur_{selected_stop_id}", selected_stop_id))
                with colBud:
                    st.number_input(
                        "Enter budget (USD)",
                        min_value=0.0,
                        step=0.01,
                        format="%.2f",
                        key=f"budget_{selected_stop_id}",
                        on_change=update_budget,
                        args=(f"dur_{selected_stop_id}", selected_stop_id)
                    )
                if st.button("Remove stop",
                    key=f"button_remove_{selected_stop_id}"):
                    del st.session_state["selected_stops"][selected_stop_id]
                    del st.session_state[f"time_e_{selected_stop_id}"]
                    del st.session_state[f"time_l_{selected_stop_id}"]
                    del st.session_state[f"dur_{selected_stop_id}"]
                    del st.session_state[f"button_remove_{selected_stop_id}"]
                    st.rerun()
        except Exception as e:
            st.error(e)
            traceback.print_exc()

def add_stop(kind : Literal["fixed", "flexible"], inputKey : str):
    """Creates a stop and adds it to the selected stops dictionary"""
    try:
        if st.session_state[inputKey]:
            stopId = f"s{next(st.session_state['stop_counter'])}"
            windowStrings = (st.session_state["time_d_e"].strftime("%H:%M"), 
                           st.session_state["time_d_l"].strftime("%H:%M"))
            if kind == "flexible":
                st.session_state["selected_stops"][stopId] = StopRequest(id=stopId, kind=kind, category=st.session_state[inputKey], window=windowStrings)
            else:
                st.session_state["selected_stops"][stopId] = StopRequest(id=stopId, kind=kind, place_id=st.session_state[inputKey], window=windowStrings)
            st.session_state[inputKey] = None
    except Exception as e:
        st.error(e)
        traceback.print_exc()

def switch_to_display():
    """Switches tab to display"""
    st.session_state["active_tab"] = "Display"

def switch_to_create():
    """Switches tab to create"""
    st.session_state["active_tab"] = "Create"

def update_order_time_border():
    """Connects both the day start and day end and sets boundaries for all stops"""
    if st.session_state["time_d_e"] > st.session_state["time_d_l"]:
        st.session_state["time_d_e"], st.session_state["time_d_l"] = st.session_state["time_d_l"], st.session_state["time_d_e"]
    for selected_stop_id in list(st.session_state["selected_stops"].keys()):
        update_order_time(f"time_e_{selected_stop_id}", f"time_l_{selected_stop_id}", selected_stop_id)

def update_order_time(earlierKey : str, laterKey : str, stopId : str):
    """Validates and updates stop time"""
    if st.session_state[earlierKey]:
        validate_time(earlierKey)
        if st.session_state[laterKey]:
            validate_time(laterKey)
            if st.session_state[earlierKey] > st.session_state[laterKey]:
                st.session_state[earlierKey], st.session_state[laterKey] = st.session_state[laterKey], st.session_state[earlierKey]
            st.session_state["selected_stops"][stopId].window = (st.session_state[earlierKey].strftime("%H:%M"), st.session_state[laterKey].strftime("%H:%M"))
        else:
            st.session_state["selected_stops"][stopId].window = (st.session_state[earlierKey].strftime("%H:%M"), st.session_state["time_d_l"].strftime("%H:%M"))
    else:
        if st.session_state[laterKey]:
            validate_time(laterKey)
            st.session_state[laterKey] = min(st.session_state[laterKey], st.session_state["time_d_l"])
            st.session_state["selected_stops"][stopId].window = (st.session_state["time_d_e"].strftime("%H:%M"), st.session_state[laterKey].strftime("%H:%M"))
        else:
            st.session_state["selected_stops"][stopId].window = (st.session_state["time_d_e"].strftime("%H:%M"), st.session_state["time_d_l"].strftime("%H:%M"))

def validate_time(key : str):
    """Ensures that the value of any particular time element is within the min and max. Sets it to the boundary if out of bounds."""
    if st.session_state[key]:
        st.session_state[key] = min(max(st.session_state[key], st.session_state["time_d_e"]), st.session_state["time_d_l"])

def update_duration(key : str, stopId : str):
    """Connects the duration field to the stop request duration variable"""
    st.session_state["selected_stops"][stopId].duration_min = st.session_state[key]

def update_budget(key : str, stopId : str):
    """Connects the budget field to the stop request budget variable"""
    st.session_state["selected_stops"][stopId].max_price_usd = st.session_state[key]

def calculate_index(iteration : int, growthBase : float, batchSize : int):
    """Calculates the next index based on an exponential sum."""
    return round((1-pow(growthBase, iteration+1))/(1-growthBase))+(batchSize*(iteration))-1

def get_default_map_show_iterate(size : int = 20):
    """Generates a randomized map using the four placeholder ids."""
    stops : list[PlannedStop] = []
    stopsCategory = [PlannedStop(stop_id="-1", place_id=id) for id in st.session_state["df"]["id"].tolist()]
    stops = stops + list(np.random.choice(stopsCategory, size))
    rng = np.random.default_rng()
    scores = rng.integers(low=0, high=10, size=size)
    plan = Plan(task_id="-1", stops=stops) #task_id is -1 because this is filler data and the app does not need to read the task id after the agent has already made a plan
    planResult = PlanResult(plan=plan, method="one_shot")
    last = 0 # cannot be none because last references curr+2
    counter = count(start=1)
    num = next(counter)
    planResult.search_log.append(SearchNode(node_id=num, depth=0, 
                partial_plan=[], 
                score=0, kept = True))

    parentDict = dict()
    
    for i in range(size):
        curr = next(counter)
        if i>0:
            parents = rng.integers(low=last, high=curr, size=round(pow(1.3, i+1)))
            keptList = np.random.choice([True, False], size=round(pow(1.3, i+1)), p=[0.8, 0.2])
            for j in range(round(pow(1.3, i+1))):
                if parentDict[parents[j]].kept:
                    kept = keptList[j]
                else:
                    kept = False
                num = next(counter)
                node = SearchNode(node_id=num, depth=i+1, 
                                partial_plan=[stops[0]]+[stop for stop in np.random.choice(stopsCategory, size=i+1)], 
                                score=sum(scores[:i+1])+rng.integers(low=0, high=10),
                                parent_id=parents[j], kept=kept)
                planResult.search_log.append(node)
                parentDict[num] = node

            num = next(counter)
            node = SearchNode(node_id=num, depth=i+1, partial_plan=stops[:i+1], score=sum(scores[:i+1]), parent_id=curr-1)
            planResult.search_log.append(node)
            parentDict[num] = node
        else:
            keptList = np.random.choice([True, False], size=round(pow(1.3, i+1)))
            for j in range(round(pow(1.3, i+1))):
                num = next(counter)
                node = SearchNode(node_id=num, depth=i+1, 
                                    partial_plan=[stops[0]]+[stop for stop in np.random.choice(stopsCategory, size=i+1)], 
                                    score=sum(scores[:i+1])+rng.integers(low=0, high=10),
                                    parent_id=1, kept=keptList[j])
                planResult.search_log.append(node)
                parentDict[num] = node

            num = next(counter)
            node = SearchNode(node_id=num, depth=i+1, partial_plan=stops[:i+1], score=sum(scores[:i+1]), parent_id=1)
            planResult.search_log.append(node)
            parentDict[num] = node
        last = curr+1
    return planResult

def iterate_history(iteration : int, growth_base : float, batch_size : int):
    """Performs one iteration on search history. Exponential indexing to prevent drawing too many maps. Returns False if there can be another iteration and True if all iterations are done."""
    planResult = st.session_state["plan_result"]
    startingIndex = calculate_index(iteration, growth_base, batch_size)
    searchLog : list[SearchNode] = planResult.search_log
    if len(searchLog)-1 < startingIndex:
        if planResult.plan:
            st.session_state["display_maps"].append({
                "type": "route", 
                "stops": planResult.plan.stops
            })
        else:
            st.session_state["display_maps"].append({"type": "blank"})
        return True
    if searchLog[startingIndex].score is not None:
        endingIndex = min(calculate_index(iteration+1, growth_base, batch_size), len(searchLog))
        topFiveNodes : list[SearchNode] = heapq.nlargest(5, searchLog[startingIndex : endingIndex], key=lambda node: node.score)
    else:
        topFiveNodes : list[SearchNode] = searchLog[startingIndex : min(startingIndex+5, len(searchLog))]
    st.session_state["display_maps"].append({
        "type": "potential", 
        "nodes": topFiveNodes
    })
    return False
    
def build_potential_routes_map(routes : list[SearchNode]):
    """Builds a map containing multiple routes. The limit is five because there are five different colors."""
    minLat = None
    minLon = None
    maxLat = None
    maxLon = None
    lines : list[folium.PolyLine] = []
    for route, color in zip(routes, ["red", "blue", "green", "orange", "yellow"]):
        try:
            routeDict = build_route(route.partial_plan, color)
            if routeDict is None:
                continue
            lines.append(routeDict["line"])
            if minLat: # if minLat is not none, then there is at least one coordinate, so everything else is not None
                minLat = min(minLat, routeDict["minLat"])
                minLon = min(minLon, routeDict["minLon"])
                maxLat = max(maxLat, routeDict["maxLat"])
                maxLon = max(maxLon, routeDict["maxLon"])
            else:
                minLat = routeDict["minLat"]
                minLon = routeDict["minLon"]
                maxLat = routeDict["maxLat"]
                maxLon = routeDict["maxLon"]
        except Exception as e:
            st.error(e)
            traceback.print_exc()
    m = folium.Map(location=[37.3352, -121.8811], zoom_start=14)  # SJSU
    if minLat:
        m = folium.Map()
        for line in lines:
            line.add_to(m)
        m.fit_bounds([[minLat, minLon], [maxLat, maxLon]])
    return m

def build_route(plannedStops : list[PlannedStop], color : str):
    """Creates a route containing a list of coordinates to path through."""
    placeIds = [plannedStop.place_id for plannedStop in plannedStops]
    coordinatePath : list[tuple[int]] = []
    for placeId in placeIds:
        check_place(placeId, coordinatePath)
    lat = [coordinate[0] for coordinate in coordinatePath]
    lon = [coordinate[1] for coordinate in coordinatePath]
    if not coordinatePath or len(coordinatePath)==0:
        return None
    return {"line":folium.PolyLine(
        locations=coordinatePath,
        color=color,
        weight=2
    ), "minLat": min(lat)
    , "minLon": min(lon)
    , "maxLat": max(lat)
    , "maxLon": max(lon)
    }

def build_map_animated_route(plannedStops : list[PlannedStop]):
    """Creates map containing a list of coordinates to path through and a marker cluster to group markers."""
    try:
        placeIds = [plannedStop.place_id for plannedStop in plannedStops]
        coordinatePath : list[tuple[int]] = []
        markerCluster : MarkerCluster =  MarkerCluster()
        counter = count(start=1)
        for placeId in placeIds:
            check_place(placeId, coordinatePath, counter=counter, markerCluster=markerCluster)
        return build_map(markerCluster, coordinatePath, True)
    except Exception as e:
        st.error(e)
        traceback.print_exc()

def build_stops_map(stops : list[StopRequest], start : str, end : str):
    """Creates map containing a list of coordinates to path through and a marker cluster to group markers."""
    try:
        coordinatePath : list[tuple[int]] = []
        markerCluster : MarkerCluster =  MarkerCluster()
        counter = count(start=1)
        check_special_place(coordinatePath, "★", markerCluster, "#91FFB8", st.session_state["select_start"], "Starting location")
        for stop in stops:
            check_stop(stop, coordinatePath, counter=counter, markerCluster=markerCluster)
        check_special_place(coordinatePath, "★", markerCluster, "#FF919E", st.session_state["select_end"], "Ending location")
        return build_map(markerCluster, coordinatePath, route=False)
    except Exception as e:
        st.error(e)
        traceback.print_exc()

def check_place(placeId : str, coordinatePath : list[tuple[int]], counter : count = None, markerCluster : MarkerCluster = None):
    """Adds all places of a particular placeId (usually returns one or zero) to a coordinate path. If a markercluster is provided, adds them to the marker cluster."""
    try:
        filteredDf = st.session_state["df"][st.session_state["df"]["id"]==placeId]
        for i, row in filteredDf.iterrows():
            color = hex(row.category)
            coordinates = (row["lat"], row["lon"])
            if markerCluster and counter:
                markerHtml = marker_html(color, str(next(counter)))
                folium.Marker(coordinates, 
                                tooltip=row["name"],
                                sticky=True,
                                icon=DivIcon(
                                    html=markerHtml,
                                    icon_size=(0, 0),
                                    icon_anchor=(0, 0)
                                )
                                ).add_to(markerCluster)
            coordinatePath.append(coordinates)
    except Exception as e:
        st.error(e)
        traceback.print_exc()
        
def check_stop(stop : StopRequest, coordinatePath : list[tuple[int]], counter : count = None, markerCluster : MarkerCluster = None):
    """Adds all places of a particular placeId (usually returns one or zero) or stop category to a coordinate path. If a markercluster is provided, adds them to the marker cluster."""
    try:
        color = hex(stop.kind)
        if stop.kind == "fixed":
            filteredDf = st.session_state["df"][st.session_state["df"]["id"]==stop.place_id]
            tooltipKey = "name"
        else:
            filteredDf = st.session_state["df"][st.session_state["df"]["category"]==stop.category]
            tooltipKey = "category"
        for i, row in filteredDf.iterrows():
            coordinates = (row["lat"], row["lon"])
            if markerCluster and counter:
                window = f"{stop.window[0]}-{stop.window[1]}"
                markerHtml = marker_html(color, str(next(counter)))
                popupHtml = f'<div style="white-space: nowrap;">Arrival Window: {escape(str(window))}<br>Duration: {escape(str(stop.duration_min))}</div>'
                folium.Marker(coordinates, 
                                popup=folium.Popup(popupHtml, max_width=500),
                                tooltip=row[tooltipKey],
                                sticky=True,
                                icon=DivIcon(
                                    html=markerHtml,
                                    icon_size=(0, 0),
                                    icon_anchor=(0, 0)
                                )
                                ).add_to(markerCluster)
            coordinatePath.append(coordinates)
    except Exception as e:
        st.error(e)
        traceback.print_exc()

def check_special_place(coordinatePath : list[tuple[int]], iconText : str, markerCluster : MarkerCluster, color : str, placeId : str, tooltip : str):
    """Adds a specially customized marker"""
    try:
        filteredDf = st.session_state["df"][st.session_state["df"]["id"]==placeId]
        if len(filteredDf)>0:
            place = filteredDf.iloc[0]
            coordinates = (place["lat"], place["lon"])
            markerHtml = marker_html(color, iconText)
            popupHtml = f'<div style="white-space: nowrap;">{escape(place["name"])}</div>'
            folium.Marker(coordinates,
                            popup=folium.Popup(popupHtml, max_width=500),
                            tooltip=tooltip,
                            sticky=True,
                            icon=DivIcon(
                                html=markerHtml,
                                icon_size=(0, 0),
                                icon_anchor=(0, 0)
                            )
                            ).add_to(markerCluster)
            coordinatePath.append(coordinates)
    except Exception as e:
        st.error(e)
        traceback.print_exc()

def marker_html(color : str, text : str):
    """Creates a custom marker that automatically scales with content."""
    color = escape(color)
    text = escape(text)
    return f"""
<div style="display: flex; flex-direction: column; align-items: center; width: max-content; transform: translate(-50%, -100%); filter: drop-shadow(0px 3px 2px rgba(0,0,0,0.3));">
    <div style="
        background-color: white;
        border: 2px solid {color};
        color: {color};
        border-radius: 12px;
        padding: 2px 8px;
        font-weight: bold;
        font-family: sans-serif;
        position: relative;
        z-index: 2;
        white-space: nowrap;
    ">
        {text}
    </div>
    <div style="
        width: 10px;
        height: 10px;
        background-color: white;
        border-bottom: 2px solid {color};
        border-right: 2px solid {color};
        transform: rotate(45deg);
        margin-top: -6px;
        z-index: 1;
    "></div>
</div>
"""

def build_map(markerCluster : MarkerCluster, coordinatePath : list[tuple[int]], route : bool):
    """Builds the map, given a path of coordinates and a marker cluster."""
    m = folium.Map(location=[37.3352, -121.8811], zoom_start=14)  # SJSU
    if len(coordinatePath) > 0:
        m = folium.Map()
        if route and coordinatePath and len(coordinatePath)>0:
            AntPath(locations=coordinatePath,
            color="#527DFF",
            pulse_color="#CFE2FF",
            delay=1000,
            ).add_to(m)
        markerCluster.add_to(m)
        m.fit_bounds(coordinatePath)
    return m

def build_search_tree_graph(plan_result: PlanResult):
    """Creates a search tree, clustering pruned nodes."""
    graph = graphviz.Digraph(
        graph_attr={'rankdir': 'LR'}, 
        node_attr={'shape': 'box', 'style': 'filled', 'fontname': 'Helvetica'}
    )
    
    parentDict = dict()
    nodeIds = {node.node_id for node in plan_result.search_log}
    
    for node in plan_result.search_log:
        if node.parent_id is not None and node.parent_id not in nodeIds:
            continue
        if node.parent_id not in parentDict:
            parentDict[node.parent_id] = {True: [], False: []}
        parentDict[node.parent_id][node.kept].append(node)
        
    queue = deque([None]) 

    while queue:
        currentParent = queue.popleft()

        if currentParent not in parentDict:
            continue

        for node in parentDict[currentParent][True]:
            label = f"Node: {node.node_id}\nDepth: {node.depth}\nStops: {len(node.partial_plan)}"
            if node.score:
                label+="\nScore: {node.score}"
            graph.node(str(node.node_id), label=label, fillcolor="lightblue", fontcolor="black")

            if currentParent is not None:
                graph.edge(str(currentParent), str(node.node_id))

            queue.append(node.node_id)

        unkept = parentDict[currentParent][False]
        if len(parentDict[currentParent][False]) > 3:
            parentDict[currentParent][False].sort(key=lambda x: (x.score is None, x.score))
            unkept = parentDict[currentParent][False][:2]
            left = len(parentDict[currentParent][False])-2
            graph.node(
                f"cluster{currentParent}", 
                label=f"+{left}\npruned", 
                shape="circle", 
                style="filled,dashed", 
                fillcolor="whitesmoke", 
                fontcolor="grey"
            )
            graph.edge(str(currentParent), f"cluster{currentParent}", style="dashed", color="grey")

        for node in unkept:
            label = f"Node: {node.node_id}\nDepth: {node.depth}\nStops: {len(node.partial_plan)}"
            if node.score:
                label+="\nScore: {node.score}"
            graph.node(str(node.node_id), label=label, fillcolor="lightgrey", fontcolor="grey")

            if currentParent is not None:
                graph.edge(str(currentParent), str(node.node_id))
            
    return graph

def hex(text : str):
    """Converts string to a sha256 hash and turns the hash into values of red, green, and blue for hexadecimal formatting"""
    hashObject = hashlib.sha256(text.encode("utf-8"))
    hashBytes = hashObject.digest()
    red = map_raw_to_range(hashBytes[0], 0, 230)
    green = map_raw_to_range(hashBytes[1], 0, 230)
    blue = map_raw_to_range(hashBytes[2], 0, 230)
    return f"#{red:02x}{green:02x}{blue:02x}"

def map_raw_to_range(val : bytes, min : int, max: int):
    """Converts a value between 0-255 into part of a hexadecimal"""
    return int((val/255.0)*(max-min)+min)

def escape(text : str):
    """Transforms a string into html-safe text"""
    if not text:
        return ""
    return text.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;").replace("\"", "&quot;").replace("'", "&#39;")

if __name__ == "__main__":
    main()