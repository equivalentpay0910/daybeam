"""OWNER: David. Streamlit app.  Run from the repo root:  streamlit run app/app.py"""
import sys, pathlib
sys.path.append(str(pathlib.Path(__file__).resolve().parents[1]))  # lets the app import core/, agent/, tools/

import folium
import streamlit as st
from streamlit_folium import st_folium

st.set_page_config(page_title="DayBeam", page_icon="☀️", layout="wide")
st.title("DayBeam")
st.caption("Plan your day in San José with AI search")

request = st.text_area("What do you want to do?",
                       "Farmers market before noon, lunch under $20, library by 3, home by 6.")
method = st.selectbox("Planner", ["one_shot", "react", "beam"])

if st.button("Plan my day"):
    st.info("Placeholder: connect to agent.planner.plan() once it works (target Oct 31).")

m = folium.Map(location=[37.3352, -121.8811], zoom_start=14)  # SJSU
folium.Marker([37.3352, -121.8811], popup="SJSU").add_to(m)
st_folium(m, width=900, height=500)
