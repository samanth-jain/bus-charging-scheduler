import streamlit as st
import json
import os
import copy
import logging
import traceback
import pandas as pd
from scheduler import SchedulerSimulation

# --- CONFIGURATION ---
st.set_page_config(page_title="EV Fleet Scheduler", page_icon="🔋", layout="wide")

def load_scenarios():
    scenarios = {}
    if not os.path.exists("data"):
        return scenarios
    for file in sorted(os.listdir("data")):
        if file.endswith(".json"):
            with open(os.path.join("data", file), "r") as f:
                data = json.load(f)
                scenarios[data["metadata"]["name"]] = data
    return scenarios

def mins_to_time(mins):
    h = (mins // 60) % 24 # Handle next-day rollovers
    m = mins % 60
    return f"{h:02d}:{m:02d}"

# --- DATA LOADING ---
scenarios = load_scenarios()
if not scenarios:
    st.error("No scenarios found! Please run `python generate_scenarios.py` first.")
    st.stop()

# --- SIDEBAR CONTROLS ---
with st.sidebar:
    st.title("🔋 EV Fleet Scheduler")
    st.markdown("Select a scenario to run the simulation and view the optimized charging plan.")
    selected_name = st.selectbox("Scenario", list(scenarios.keys()), key="selected_scenario")
    scenario_data = copy.deepcopy(scenarios[selected_name])

    if st.session_state.get("last_selected_scenario") != selected_name:
        for key, default_value in scenario_data["weights"].items():
            st.session_state[f"weight_{key}"] = float(default_value)
        st.session_state["last_selected_scenario"] = selected_name

    # If a reset was requested (from the previous run), apply defaults now
    if st.session_state.get("do_reset"):
        for key, default_value in scenarios[selected_name]["weights"].items():
            st.session_state[f"weight_{key}"] = float(default_value)
        st.session_state["do_reset"] = False

    st.markdown("---")
    st.markdown("### Scenario Weights")
    weight_values = {}
    for key, default_value in scenario_data["weights"].items():
        slider_label = key.replace("_", " ").title()
        slider_key = f"weight_{key}"
        if slider_key not in st.session_state:
            st.session_state[slider_key] = float(default_value)

        weight_values[key] = st.slider(
            slider_label,
            min_value=0.0,
            max_value=5.0,
            step=0.1,
            format="%.1f",
            key=slider_key
        )

    def _request_reset():
        st.session_state["do_reset"] = True

    st.button("Reset Weights to Scenario Defaults", on_click=_request_reset)

    # Update scenario weights based on UI controls before simulation
    scenario_data["weights"].update(weight_values)

    st.info("**Active weights will be applied when the simulation starts.**")

# --- RUN SIMULATION ---
logger = logging.getLogger("ev_fleet_app")

try:
    sim = SchedulerSimulation(scenario_data)
    bus_logs, station_logs = sim.run()
except Exception as e:
    # Log and display the traceback in the Streamlit UI for debugging
    logger.exception("Simulation failed: %s", e)
    st.error(f"Simulation failed: {e}")
    st.text(traceback.format_exc())


# --- DATA PROCESSING FOR UI ---
# Map buses to operators using the input JSON
bus_op_map = {d["bus_id"]: d["operator"] for d in scenario_data["departures"]}

bus_stats = []
for bus_id in sorted(set([l["bus_id"] for l in bus_logs])):
    logs = [l for l in bus_logs if l["bus_id"] == bus_id]
    operator = bus_op_map.get(bus_id, "Unknown").capitalize()
    
    depart_log = next((l for l in logs if l["event"] == "DEPART"), None)
    arrive_log = next((l for l in logs if l["event"] == "ARRIVE_DEST"), None)
    
    depart_time = depart_log["time"] if depart_log else 0
    arrive_time = arrive_log["time"] if arrive_log else 0
    trip_time = arrive_time - depart_time
    total_wait = sum(l.get("wait", 0) for l in logs if l["event"] == "CHARGE")
    
    # Build a readable timeline
    timeline = []
    for log in logs:
        if log["event"] == "DEPART": 
            timeline.append(f"Depart {log['node']} ({mins_to_time(log['time'])})")
        elif log["event"] == "CHARGE": 
            timeline.append(f"Charge {log['node']} ({log['wait']}m wait)")
        elif log["event"] == "ARRIVE_DEST": 
            timeline.append(f"Arrive {log['node']} ({mins_to_time(log['time'])})")
            
    bus_stats.append({
        "Bus ID": bus_id,
        "Operator": operator,
        "Departure": mins_to_time(depart_time),
        "Arrival": mins_to_time(arrive_time),
        "Trip Duration (m)": trip_time,
        "Total Wait (m)": total_wait,
        "Timeline": " ➔ ".join(timeline)
    })

df_bus = pd.DataFrame(bus_stats)

# --- MAIN UI LAYOUT ---
st.title(f"Scenario: {selected_name}")
st.write(scenario_data["metadata"]["description"])

# Create UI Tabs
tab_dash, tab_bus, tab_stn, tab_raw = st.tabs([
    "📊 Fleet & Operator Dashboard", 
    "🚌 Per-Bus Timetable", 
    "⚡ Station Activity", 
    "⚙️ Raw Config"
])

# --- TAB 1: DASHBOARD & OPERATORS ---
with tab_dash:
    st.subheader("Network Metrics")
    m1, m2, m3, m4 = st.columns(4)
    m1.metric("Total Buses Processed", len(df_bus))
    m2.metric("Avg Network Wait Time", f"{df_bus['Total Wait (m)'].mean():.1f} mins")
    m3.metric("Max Wait Time (Single Bus)", f"{df_bus['Total Wait (m)'].max()} mins")
    m4.metric("Avg Trip Duration", f"{df_bus['Trip Duration (m)'].mean():.0f} mins")

    st.markdown("---")
    st.subheader("Operator Fleet Comparison")
    
    # Aggregate data by Operator
    if not df_bus.empty:
        df_ops = df_bus.groupby("Operator").agg(
            Fleet_Size=("Bus ID", "count"),
            Avg_Wait_Mins=("Total Wait (m)", "mean"),
            Max_Wait_Mins=("Total Wait (m)", "max"),
            Total_Wait_Mins=("Total Wait (m)", "sum"),
            Avg_Trip_Mins=("Trip Duration (m)", "mean")
        ).reset_index()
        
        # Round the floats for cleaner display
        df_ops["Avg_Wait_Mins"] = df_ops["Avg_Wait_Mins"].round(1)
        df_ops["Avg_Trip_Mins"] = df_ops["Avg_Trip_Mins"].round(1)
        df_ops["Total_Wait_Mins"] = df_ops["Total_Wait_Mins"].astype(int)
        
        col_chart1, col_chart2, col_table = st.columns([1, 1, 1.5])
        
        with col_chart1:
            st.markdown("**Average Wait Time by Operator**")
            st.bar_chart(df_ops, x="Operator", y="Avg_Wait_Mins", use_container_width=True)

        with col_chart2:
            st.markdown("**Total Wait Time by Operator**")
            st.bar_chart(df_ops, x="Operator", y="Total_Wait_Mins", use_container_width=True)
            
        with col_table:
            st.markdown("**Operator Breakdown Matrix**")
            st.dataframe(
                df_ops.rename(columns={
                    "Fleet_Size": "Total Buses", 
                    "Avg_Wait_Mins": "Avg Wait (m)",
                    "Max_Wait_Mins": "Max Wait (m)", 
                    "Total_Wait_Mins": "Total Wait (m)",
                    "Avg_Trip_Mins": "Avg Trip Time (m)"
                }),
                use_container_width=True, 
                hide_index=True
            )

# --- TAB 2: PER-BUS TIMETABLE ---
with tab_bus:
    st.subheader("Detailed Bus Logs")
    # Display the full dataframe, formatted nicely
    st.dataframe(df_bus, use_container_width=True, hide_index=True)

# --- TAB 3: PER-STATION ACTIVITY ---
with tab_stn:
    st.subheader("Charger Utilization Order")
    col1, col2, col3, col4 = st.columns(4)
    stations = ["STN_A", "STN_B", "STN_C", "STN_D"]
    cols = [col1, col2, col3, col4]

    for i, stn in enumerate(stations):
        with cols[i]:
            st.markdown(f"**Station {stn[-1]}**")
            stn_data = [l for l in station_logs if l["node"] == stn]
            if not stn_data:
                st.info("No buses charged here.")
                continue
                
            df_s = pd.DataFrame(stn_data)
            # Map operator into the station view too
            df_s["Operator"] = df_s["bus_id"].map(lambda x: bus_op_map.get(x, "Unknown").capitalize())
            df_s["Arrived"] = df_s["arrive"].apply(mins_to_time)
            df_s["Charged"] = df_s["start"].apply(mins_to_time)
            df_s["Wait"] = df_s["wait"]
            
            df_display = df_s[["bus_id", "Operator", "Arrived", "Wait", "Charged"]]
            df_display.columns = ["Bus", "Operator", "Arrived", "Wait (m)", "Start Charge"]
            st.dataframe(df_display, hide_index=True)

# --- TAB 4: RAW DATA ---
with tab_raw:
    st.subheader("Scenario JSON Payload")
    st.markdown("This validates that the simulation is purely data-driven.")
    st.json(scenario_data)