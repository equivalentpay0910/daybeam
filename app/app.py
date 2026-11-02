"""OWNER: David. Streamlit app.  Run from the repo root:  streamlit run app/app.py"""
import hashlib
import sys, pathlib
import traceback

sys.path.append(str(pathlib.Path(__file__).resolve().parents[1]))  # lets the app import core/, agent/, tools/
from core.schemas import PlanResult
from core.schemas import Plan
from core.schemas import PlannedStop
import pandas as pd

import folium
from folium.plugins import AntPath
from folium.plugins import BeautifyIcon
from folium.plugins import MarkerCluster
import streamlit as st
from streamlit_folium import st_folium

def main():
    if "map" not in st.session_state:
        stops : list[PlannedStop] = []
        stops.append(PlannedStop(stop_id="-1", place_id="P_home_01"))
        stops.append(PlannedStop(stop_id="-1", place_id="P_market_01"))
        stops.append(PlannedStop(stop_id="-1", place_id="P_library_01"))
        stops.append(PlannedStop(stop_id="-1", place_id="P_rest_01"))
        stops.append(PlannedStop(stop_id="-1", place_id="P_home_01"))
        plan = Plan(task_id="-1", stops=stops) #task_id is -1 because this is filler data and the app does not need to read the task id after the agent has already made a plan
        planResult = PlanResult(plan=plan, method="one_shot")
        st.session_state["map"] = build_route_map(planResult, "data/places_sample.csv")
    
    st.set_page_config(page_title="DayBeam", page_icon="☀️", layout="wide")
    st.title("DayBeam")
    st.caption("Plan your day in San José with AI search")

    request = st.text_area("What do you want to do?",
                        "Farmers market before noon, lunch under $20, library by 3, home by 6.")
    method = st.selectbox("Planner", ["one_shot", "react", "beam"])

    if st.button("Plan my day"):
        st.info("Placeholder: connect to agent.planner.plan() once it works (target Oct 31).")

    mapPlaceholder = st.empty()
    with mapPlaceholder:
        st_folium(st.session_state["map"], width=900, height=500, key="daybeam_map", returned_objects=[])

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

def build_route_map(planResult : PlanResult, csvName : str):
    """Creates a list of coordinates to path through and a marker cluster to group markers."""
    try:
        routeIds = [plannedStop.place_id for plannedStop in planResult.plan.stops]
        df = pd.read_csv(csvName).dropna(subset=['id', 'name', 'category', 'lat', 'lon'])
        coordinatePath : list[list[int]] = []
        markerCluster : MarkerCluster =  MarkerCluster()
        counter = 1
        for routeId in routeIds:
            check_stop(df, routeId, markerCluster, coordinatePath, counter)
            counter += 1
        return build_map(markerCluster, coordinatePath)
    except Exception as e:
        st.error(e)
        traceback.print_exc()

def check_stop(df : pd.DataFrame, routeId : int, markerCluster : MarkerCluster, coordinatePath : list[list[int]], counter):
    """Checks if a node exists in the given csv. Skips if there is none. If there is at least one, grabs the first one and makes a marker to add to the cluster."""
    try:
        filteredDf = df[df["id"]==routeId]
        if len(filteredDf) > 0:
            place = filteredDf.iloc[0]
            color = hex(place.category)
            coordinates = [place["lat"], place["lon"]]
            folium.Marker(list(coordinates), 
                            tooltip=place["name"],
                            icon=BeautifyIcon(border_color = color, 
                                            text_color = color, 
                                            number = counter, 
                                            inner_icon_style="margin:auto; padding-left:5px; padding-right:5px; width: fit-content;",
                                            icon_shape = "marker"
                                            )
                            ).add_to(markerCluster)
            coordinatePath.append(list(coordinates))
    except Exception as e:
        st.error(e)
        traceback.print_exc()

def build_map(markerCluster : MarkerCluster, coordinatePath : list[list[int]]):
    """Builds the map, given a path of coordinates and a marker cluster."""
    m = folium.Map(location=[37.3352, -121.8811], zoom_start=14)  # SJSU
    if len(coordinatePath) > 0:
        m = folium.Map()
        AntPath(locations=[coordinatePath],
        color="#527DFF",
        pulse_color="#CFE2FF",
        delay=1000,
        ).add_to(m)
        markerCluster.add_to(m)
        m.fit_bounds(coordinatePath)
    return m

if __name__ == "__main__":
    main()