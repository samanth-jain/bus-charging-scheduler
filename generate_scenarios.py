import json
import os

# Create data directory
os.makedirs("data", exist_ok=True)

# Shared base schema
base_network = {
    "global_parameters": {"battery_range_km": 240, "charge_time_to_full_minutes": 25, "speed_km_per_hour": 60},
    "network": {
        "stations": [
            {"id": "BLR", "name": "Bengaluru", "type": "terminal", "chargers": 999},
            {"id": "STN_A", "name": "A", "type": "transit", "chargers": 1},
            {"id": "STN_B", "name": "B", "type": "transit", "chargers": 1},
            {"id": "STN_C", "name": "C", "type": "transit", "chargers": 1},
            {"id": "STN_D", "name": "D", "type": "transit", "chargers": 1},
            {"id": "KOC", "name": "Kochi", "type": "terminal", "chargers": 999}
        ],
        "routes": [
            {"route_id": "BLR_KOC", "direction": "outbound", "path": [
                {"from": "BLR", "to": "STN_A", "distance_km": 100}, {"from": "STN_A", "to": "STN_B", "distance_km": 120},
                {"from": "STN_B", "to": "STN_C", "distance_km": 100}, {"from": "STN_C", "to": "STN_D", "distance_km": 120},
                {"from": "STN_D", "to": "KOC", "distance_km": 100}]},
            {"route_id": "KOC_BLR", "direction": "inbound", "path": [
                {"from": "KOC", "to": "STN_D", "distance_km": 100}, {"from": "STN_D", "to": "STN_C", "distance_km": 120},
                {"from": "STN_C", "to": "STN_B", "distance_km": 100}, {"from": "STN_B", "to": "STN_A", "distance_km": 120},
                {"from": "STN_A", "to": "BLR", "distance_km": 100}]}
        ]
    }
}

def time_to_mins(t_str):
    h, m = map(int, t_str.split(':'))
    return h * 60 + m

def build_scenario(file_name, name, desc, departures_raw, weights={"individual_wait": 1.0, "operator_grouping": 1.0, "overall_time": 1.0}):
    scenario = {
        "metadata": {"scenario_id": file_name, "name": name, "description": desc},
        **base_network,
        "weights": weights,
        "departures": []
    }
    for r in departures_raw:
        scenario["departures"].append({
            "bus_id": r[0], "operator": r[1], 
            # "route_id": "BLR_KOC" if "Bengaluru" in r[2] and "Kochi" in r[2] else "KOC_BLR", 
            "route_id": "BLR_KOC" if r[2].startswith("Bengaluru") else "KOC_BLR",
            "departure_time_mins": time_to_mins(r[3])
        })
    with open(f"data/{file_name}.json", "w") as f:
        json.dump(scenario, f, indent=2)

# SCENARIO 1
s1_raw = [
    ("bus-BK-01", "kpn", "Bengaluru Kochi", "19:00"), ("bus-BK-02", "freshbus", "Bengaluru Kochi", "19:15"),
    ("bus-BK-03", "flixbus", "Bengaluru Kochi", "19:30"), ("bus-BK-04", "kpn", "Bengaluru Kochi", "19:45"),
    ("bus-BK-05", "freshbus", "Bengaluru Kochi", "20:00"), ("bus-BK-06", "flixbus", "Bengaluru Kochi", "20:15"),
    ("bus-BK-07", "kpn", "Bengaluru Kochi", "20:30"), ("bus-BK-08", "freshbus", "Bengaluru Kochi", "20:45"),
    ("bus-BK-09", "flixbus", "Bengaluru Kochi", "21:00"), ("bus-BK-10", "kpn", "Bengaluru Kochi", "21:15"),
    ("bus-KB-01", "freshbus", "Kochi Bengaluru", "19:00"), ("bus-KB-02", "flixbus", "Kochi Bengaluru", "19:15"),
    ("bus-KB-03", "kpn", "Kochi Bengaluru", "19:30"), ("bus-KB-04", "freshbus", "Kochi Bengaluru", "19:45"),
    ("bus-KB-05", "flixbus", "Kochi Bengaluru", "20:00"), ("bus-KB-06", "kpn", "Kochi Bengaluru", "20:15"),
    ("bus-KB-07", "freshbus", "Kochi Bengaluru", "20:30"), ("bus-KB-08", "flixbus", "Kochi Bengaluru", "20:45"),
    ("bus-KB-09", "kpn", "Kochi Bengaluru", "21:00"), ("bus-KB-10", "freshbus", "Kochi Bengaluru", "21:15")
]
build_scenario("scenario_1", "Even Spacing", "15 minute intervals.", s1_raw)

# SCENARIO 2
s2_raw = [
    ("bus-BK-01", "kpn", "Bengaluru Kochi", "19:00"), ("bus-BK-02", "freshbus", "Bengaluru Kochi", "19:08"),
    ("bus-BK-03", "flixbus", "Bengaluru Kochi", "19:16"), ("bus-BK-04", "kpn", "Bengaluru Kochi", "19:24"),
    ("bus-BK-05", "freshbus", "Bengaluru Kochi", "19:32"), ("bus-BK-06", "flixbus", "Bengaluru Kochi", "19:40"),
    ("bus-BK-07", "kpn", "Bengaluru Kochi", "19:48"), ("bus-BK-08", "freshbus", "Bengaluru Kochi", "20:03"),
    ("bus-BK-09", "flixbus", "Bengaluru Kochi", "20:18"), ("bus-BK-10", "kpn", "Bengaluru Kochi", "20:33"),
    ("bus-KB-01", "freshbus", "Kochi Bengaluru", "19:00"), ("bus-KB-02", "flixbus", "Kochi Bengaluru", "19:08"),
    ("bus-KB-03", "kpn", "Kochi Bengaluru", "19:16"), ("bus-KB-04", "freshbus", "Kochi Bengaluru", "19:24"),
    ("bus-KB-05", "flixbus", "Kochi Bengaluru", "19:32"), ("bus-KB-06", "kpn", "Kochi Bengaluru", "19:40"),
    ("bus-KB-07", "freshbus", "Kochi Bengaluru", "19:48"), ("bus-KB-08", "flixbus", "Kochi Bengaluru", "20:03"),
    ("bus-KB-09", "kpn", "Kochi Bengaluru", "20:18"), ("bus-KB-10", "freshbus", "Kochi Bengaluru", "20:33")
]
build_scenario("scenario_2", "Bunched Start", "Heavy early contention.", s2_raw)

# SCENARIO 3
s3_raw = [
    ("bus-BK-01", "kpn", "Bengaluru Kochi", "19:00"), ("bus-BK-02", "freshbus", "Bengaluru Kochi", "19:15"),
    ("bus-BK-03", "flixbus", "Bengaluru Kochi", "19:30"), ("bus-BK-04", "kpn", "Bengaluru Kochi", "19:45"),
    ("bus-BK-05", "freshbus", "Bengaluru Kochi", "20:00"), ("bus-BK-06", "flixbus", "Bengaluru Kochi", "20:15"),
    ("bus-BK-07", "kpn", "Bengaluru Kochi", "20:30"), ("bus-BK-08", "freshbus", "Bengaluru Kochi", "20:45"),
    ("bus-BK-09", "flixbus", "Bengaluru Kochi", "21:00"), ("bus-BK-10", "kpn", "Bengaluru Kochi", "21:15"),
    ("bus-KB-01", "freshbus", "Kochi Bengaluru", "19:00"), ("bus-KB-02", "flixbus", "Kochi Bengaluru", "19:35"),
    ("bus-KB-03", "kpn", "Kochi Bengaluru", "20:10"), ("bus-KB-04", "freshbus", "Kochi Bengaluru", "20:45")
]
build_scenario("scenario_3", "Asymmetric Load", "10 outbound, 4 inbound.", s3_raw)

# SCENARIO 4
s4_raw = [
    ("bus-BK-01", "kpn", "Bengaluru Kochi", "19:00"), ("bus-BK-02", "kpn", "Bengaluru Kochi", "19:15"),
    ("bus-BK-03", "kpn", "Bengaluru Kochi", "19:30"), ("bus-BK-04", "kpn", "Bengaluru Kochi", "19:45"),
    ("bus-BK-05", "kpn", "Bengaluru Kochi", "20:00"), ("bus-BK-06", "kpn", "Bengaluru Kochi", "20:15"),
    ("bus-BK-07", "kpn", "Bengaluru Kochi", "20:30"), ("bus-BK-08", "kpn", "Bengaluru Kochi", "20:45"),
    ("bus-BK-09", "freshbus", "Bengaluru Kochi", "21:00"), ("bus-BK-10", "flixbus", "Bengaluru Kochi", "21:15"),
    ("bus-KB-01", "freshbus", "Kochi Bengaluru", "19:00"), ("bus-KB-02", "flixbus", "Kochi Bengaluru", "19:15"),
    ("bus-KB-03", "kpn", "Kochi Bengaluru", "19:30"), ("bus-KB-04", "freshbus", "Kochi Bengaluru", "19:45"),
    ("bus-KB-05", "flixbus", "Kochi Bengaluru", "20:00"), ("bus-KB-06", "kpn", "Kochi Bengaluru", "20:15"),
    ("bus-KB-07", "freshbus", "Kochi Bengaluru", "20:30"), ("bus-KB-08", "flixbus", "Kochi Bengaluru", "20:45"),
    ("bus-KB-09", "kpn", "Kochi Bengaluru", "21:00"), ("bus-KB-10", "freshbus", "Kochi Bengaluru", "21:15")
]
build_scenario("scenario_4", "Operator-Heavy", "KPN dominates.", s4_raw, weights={"individual_wait": 1.0, "operator_grouping": 2.0, "overall_time": 1.0})

# SCENARIO 5
s5_raw = [
    ("bus-BK-01", "kpn", "Bengaluru Kochi", "19:00"), ("bus-BK-02", "freshbus", "Bengaluru Kochi", "19:08"),
    ("bus-BK-03", "flixbus", "Bengaluru Kochi", "19:16"), ("bus-BK-04", "kpn", "Bengaluru Kochi", "19:24"),
    ("bus-BK-05", "freshbus", "Bengaluru Kochi", "19:32"), ("bus-BK-06", "flixbus", "Bengaluru Kochi", "19:40"),
    ("bus-BK-07", "kpn", "Bengaluru Kochi", "19:48"), ("bus-BK-08", "freshbus", "Bengaluru Kochi", "19:56"),
    ("bus-BK-09", "flixbus", "Bengaluru Kochi", "20:04"), ("bus-BK-10", "kpn", "Bengaluru Kochi", "20:12"),
    ("bus-KB-01", "freshbus", "Kochi Bengaluru", "19:00"), ("bus-KB-02", "flixbus", "Kochi Bengaluru", "19:08"),
    ("bus-KB-03", "kpn", "Kochi Bengaluru", "19:16"), ("bus-KB-04", "freshbus", "Kochi Bengaluru", "19:24"),
    ("bus-KB-05", "flixbus", "Kochi Bengaluru", "19:32"), ("bus-KB-06", "kpn", "Kochi Bengaluru", "19:40"),
    ("bus-KB-07", "freshbus", "Kochi Bengaluru", "19:48"), ("bus-KB-08", "flixbus", "Kochi Bengaluru", "19:56"),
    ("bus-KB-09", "kpn", "Kochi Bengaluru", "20:04"), ("bus-KB-10", "freshbus", "Kochi Bengaluru", "20:12")
]
build_scenario("scenario_5", "Worst Case Convergence", "Maximum contention.", s5_raw)

print("Scenarios generated in ./data/ directory.")