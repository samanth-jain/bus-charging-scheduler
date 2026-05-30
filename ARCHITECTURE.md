# ARCHITECTURE


## 1. Core Scheduling Approach

The scheduling engine is built using a **Discrete Event Simulation (DES)** paradigm implemented with Python's native `heapq` module. 

### Why Discrete Event Simulation?
Alternative approaches, such as step-by-step time-slicing (e.g., checking system state every minute) or pure static mathematical optimization (e.g., Mixed-Integer Linear Programming), present trade-offs:
* **Time-slicing** introduces unnecessary computational overhead during periods of low activity and can miss critical events if the time step is too large.
* **Pure static optimization** can become highly complex and computationally expensive as network constraints, dynamic priorities, and rules scale.

A Discrete Event Simulation offers several practical advantages:
* **Asynchronous Time Steps:** Time advances directly to the next critical event (arrival, departure, charge completion), optimizing performance even for long simulation windows.
* **Exact Time Resolution:** Events occur at precise, realistic intervals (e.g., exact travel or charge duration) without rounding errors introduced by fixed-interval steps.
* **Logical Separation:** Each event handler only needs to transition the state of the system for its own event type, simplifying debugging and updates.

### Dynamic Look-Ahead Routing Policy:

- It is assumed that a bus evaluates network topology dynamically rather than using hardcoded battery percentages.
- A bus will opportunistically charge if a charger is free AND its current battery is insufficient to bypass the *next* sequential station ($Battery Range < Distance_1 + Distance_2$). This leapfrog heuristic optimally distributes fleet charging to prevent bottlenecking at deeper stations.
- It is Route-Agnostic: Whether the stations are 10 km apart or 200 km apart, the bus mathematically guarantees it won't willingly drive into a bottleneck if it doesn't have the range to escape it.
- It Self-Corrects for Battery Tech: If we change `battery_range_km: 240` to `500` in the JSON, we don't have to rethink our percentages. The bus will naturally realize that $500 \text{ km}$ is much greater than $D_1 + D_2$ and will confidently skip the station, optimizing for speed.

---

## 2. Data Structure Design

The system relies on a schema design that separates **static configurations**, **dynamic simulation states**, and **simulation output**.

### Configuration Payload Schema
All physical parameters, topological layouts, and operational weights are represented in a single, hierarchical JSON format. This structure is designed to keep the engine configuration-driven:

```json
{
  "metadata": {
    "scenario_id": "scenario_1",
    "name": "Even Spacing"
  },
  "global_parameters": {
    "battery_range_km": 240,
    "charge_time_to_full_minutes": 25,
    "speed_km_per_hour": 60
  },
  "weights": {
    "individual_wait": 1.0,
    "operator_grouping": 1.0,
    "overall_time": 1.0
  },
  "network": {
    "stations": [
      {"id": "BLR", "name": "Bengaluru", "type": "terminal", "chargers": 999},
      {"id": "STN_A", "name": "A", "type": "transit", "chargers": 1}
    ],
    "routes": [
      {
        "route_id": "BLR_KOC",
        "direction": "outbound",
        "path": [
          {"from": "BLR", "to": "STN_A", "distance_km": 100}
        ]
      }
    ]
  },
  "departures": [
    {
      "bus_id": "bus-BK-01",
      "operator": "kpn",
      "route_id": "BLR_KOC",
      "departure_time_mins": 1140
    }
  ]
}

```

### In-Memory Entities

During execution, internal states are managed via structured Dataclasses:

* **`Bus`**: Tracks properties such as current battery range, route progress index, wait times, and queue timestamps.
* **`Station`**: Tracks physical assets (number of total chargers, chargers currently active) and manages the queue of waiting buses.

---

## 3. How weights work

When multiple buses are waiting in a station's queue, the scheduler determines the charging sequence by selecting the bus with the highest priority score. 

The priority score is calculated using three terms, each multiplied by its respective weight:

$$\text{Priority Score} = (w_{\text{individual\_wait}} \times \text{WaitTime}) + (w_{\text{operator\_grouping}} \times \text{TimeSinceOpCharged}) + (w_{\text{overall\_time}} \times \text{TotalTripTime})$$

Here is an explanation of how each term behaves and how adjusting its weight alters the behavior of the fleet.

### 1. Individual Wait Weight ($w_{\text{individual\_wait}}$)

* **Associated Metric:** $\text{WaitTime} = \text{CurrentTime} - \text{QueueJoinTime}$
* **What it measures:** The duration (in minutes) a bus has been stationary in the queue at the current station.
* **How it affects the score:** This value increases linearly by $+1$ for every minute a bus sits waiting. 
* **Operational Impact:**
  * **High Weight:** Forces the queue to behave like a strict **First-In, First-Out (FIFO)** system. The bus that arrived first will almost always be charged first, regardless of its operator or departure time.
  * **Low Weight:** Allows other scheduling factors (like helping late-running buses or maintaining operator fairness) to override the arrival order.


### 2. Operator Grouping Weight ($w_{\text{operator\_grouping}}$)

* **Associated Metric:** $\text{TimeSinceOpCharged} = \text{CurrentTime} - \text{LastChargeTimeByOperator}$
* **What it measures:** The elapsed time since any bus belonging to the same operator (e.g., KPN, Freshbus, or Flixbus) last initiated a charge.
* **How it affects the score:** 
  * If an operator's bus has just started charging, this value resets to $0$ for all other waiting buses of that same operator, reducing their priority.
  * If an operator has not charged any bus for a long time, this value grows, increasing the priority of its waiting buses.
* **Operational Impact:**
  * **High Weight:** Promotes **round-robin interleaving** among operators (e.g., KPN $\rightarrow$ Freshbus $\rightarrow$ Flixbus $\rightarrow$ KPN). It prevents a dominant operator with a large fleet from **monopolizing** a station and blocking smaller competitors.
  * **Low Weight:** Allows batching. If one operator has several buses arrive together, they may charge back-to-back, leaving other operators waiting.


### 3. Overall Time Weight ($w_{\text{overall\_time}}$)

* **Associated Metric:** $\text{TotalTripTime} = \text{CurrentTime} - \text{DepartureTime}$
* **What it measures:** The total time elapsed since the bus departed its original terminal (Bengaluru or Kochi).
* **How it affects the score:** Buses that started their journeys earlier will have a higher baseline score than buses that departed recently.
* **Operational Impact:**
  * **High Weight:** Acts as an **Earliest Departure First (EDF)** priority. It favors late-running buses or those further along their journey to prevent compounding delays on long trips.
  * **Low Weight:** The scheduler ignores how long a bus has been on the road, treating a bus that has traveled 400 km the same as one that has just departed its origin.


### Operational Scenarios: The Trade-Offs

When these weights interact, the scheduler balances competing operational goals:

| Tuning Strategy | Primary Behavior | Trade-Off |
| :--- | :--- | :--- |
| **High $w_{\text{individual\_wait}}$** | Strict FIFO fairness at each station. | A bus on a long-distance, tight schedule may be held up by a recently departed local bus that arrived minutes earlier. |
| **High $w_{\text{operator\_grouping}}$** | Balanced charger sharing among competitors. | A bus may be bypassed in the queue by a competitor's bus that arrived later, simply because its own operator recently used a charger. |
| **High $w_{\text{overall\_time}}$** | Minimizes compounding delays across the network. | Buses that departed recently may experience longer wait times at transit stations as older, long-distance buses are prioritized. |

---

## 4. Anticipated Future Changes & Structural Flexibility

The schema and engine are designed to handle common real-world changes without requiring structural modifications to the core code.

### Case A: Adding New Stations or Changing Segment Distances

* **Design Solution:** The route topology is modeled as an ordered list of nodes and segment distances in the JSON payload.
* **Code Impact:** **No code change required.** The scheduler determines node transitions dynamically using segment data. Updating a distance or adding a station only requires modifying the scenario JSON.

### Case B: Scaling Charger Quantities per Station

* **Design Solution:** Station capacities are defined by the `total_chargers` attribute in the JSON configuration.
* **Code Impact:** **No code change required.** The simulation logic uses `station.total_chargers` to evaluate queue admission. A station can scale from 1 charger to multiple units through configuration changes alone.

### Case C: Introducing Mixed Fleet Characteristics (e.g., Different Battery Ranges or Speeds)

* **Design Solution:** Buses can be extended with optional properties inside the JSON representation.
* **Code Impact:** Highly contained. The global parameters can be moved to properties of individual `Bus` instances:
```python
# Instead of: self.max_battery = self.params["battery_range_km"]
# Use: bus.battery_range = departure_data.get("battery_range_km", default_range)

```



### Case D: Multiple Routes and Bidirectional Traffic

* **Design Solution:** Network routes are mapped via unique `route_id` descriptors in JSON. Stations represent globally shared resources.
* **Code Impact:** **No code change required.** The scheduling engine processes bus events along distinct, arbitrary paths. Resource contention at shared stations is resolved globally using the event queue, supporting complex topologies out of the box.

---

## 4. Operational Customizations (Code Examples)

### Modifying Weights (Code Example)

Weights are stored inside the `self.weights` dictionary. You can adjust priorities or expose them to an external UI (such as Streamlit sliders) before executing the simulation:

```python
# scheduler_override.py
def run_custom_simulation(scenario_data, override_weights):
    # Overwrite the weights from UI inputs
    scenario_data["weights"] = override_weights
    
    # Initialize and execute
    simulation = SchedulerSimulation(scenario_data)
    bus_logs, station_logs = simulation.run()
    return bus_logs, station_logs

```

### Implementing a New Soft Rule (Code Example)

Suppose a new requirement asks to prioritize buses that have a low battery level upon arriving at the station. We can integrate a new soft rule, "Battery Level Priority", into the queue scoring system:

```python
# Inside scheduler.py -> SchedulerSimulation class

def _score_bus(self, bus: Bus, current_time: int) -> float:
    wait_time = current_time - bus.queue_join_time
    last_op_charge = self.last_charge_time_by_operator.get(bus.operator, bus.departure_time)
    time_since_op_charged = current_time - last_op_charge
    total_trip_time = current_time - bus.departure_time
    
    # New Metric: Higher priority score for lower battery range remaining
    # Normalizing battery deficit: (max_battery - current_battery)
    battery_deficit = self.max_battery - bus.battery_km
    
    # Fetch weight parameter (defaults to 0.0 if not defined in configuration)
    battery_weight = self.weights.get("battery_depletion_priority", 0.0)
    
    return (self.weights["individual_wait"] * wait_time) + \
           (self.weights["operator_grouping"] * time_since_op_charged) + \
           (self.weights["overall_time"] * total_trip_time) + \
           (battery_weight * battery_deficit)

```

### Implementing a New Hard Rule (Code Example)

Suppose a new hard rule is introduced: "No bus may enter a charging station queue if the current queue size exceeds 3 buses, unless its remaining battery is critical (less than 100 km)." We can implement this inside the arrival handler:

```python
# Inside scheduler.py -> SchedulerSimulation class

def _handle_arrive(self, bus: Bus, node_id: str, current_time: int):
    route = self.routes[bus.route_id]
    prev_distance = route[bus.current_node_index - 1][1]
    bus.battery_km -= prev_distance
    
    if bus.current_node_index == len(route) - 1:
        self.bus_logs.append({"bus_id": bus.id, "event": "ARRIVE_DEST", "node": node_id, "time": current_time, "wait": 0})
        return

    distance_to_next = route[bus.current_node_index][1]
    station = self.stations[node_id]

    # Dynamic Two-Node Look-Ahead calculation
    if bus.current_node_index + 1 < len(route) - 1:
        distance_after_next = route[bus.current_node_index + 1][1]
    else:
        distance_after_next = 0 
    dynamic_threshold_km = distance_to_next + distance_after_next

    # Standard decision criteria
    must_charge = bus.battery_km < distance_to_next
    should_charge = (station.chargers_in_use < station.total_chargers and bus.battery_km < dynamic_threshold_km)
    
    # Evaluation of the new Hard Rule
    if (must_charge or should_charge):
        # Apply the new hard constraint
        queue_is_congested = len(station.queue) >= 3
        battery_is_safe = bus.battery_km >= 100
        
        if queue_is_congested and battery_is_safe and not must_charge:
            # Bypass charging because the queue is long and battery levels are safe
            self._bypass_station(bus, distance_to_next, current_time)
        else:
            # Join queue normally
            bus.queue_join_time = current_time
            station.queue.append(bus)
            self._evaluate_queue(station, current_time)
    else:
        self._bypass_station(bus, distance_to_next, current_time)

def _bypass_station(self, bus: Bus, distance_to_next: int, current_time: int):
    route = self.routes[bus.route_id]
    travel_time = int(distance_to_next / self.speed)
    next_node = route[bus.current_node_index + 1][0]
    bus.current_node_index += 1
    heapq.heappush(self.events, (current_time + travel_time, "ARRIVE_NODE", bus.id, next_node))

```

---

### 5. System Assumptions

For modeling clarity and simulation consistency, the following assumptions are applied to the physical and operational model:

1. **Dynamic Look-Ahead Routing Policy:** It is assumed that a bus evaluates network topology dynamically rather than using hardcoded battery percentages. A bus will opportunistically charge if a charger is free AND its current battery is insufficient to bypass the *next* sequential station ($Battery < Distance_1 + Distance_2$). This leapfrog heuristic optimally distributes fleet charging to prevent bottlenecking at deeper stations.
2. **Uniform Speed:** Buses maintain a constant speed of 60 km/h. Dynamic traffic variations, delays, and acceleration or deceleration phases are not modeled.
3. **Deterministic Charging Profiles:** Charging time is modeled as a fixed 25-minute block to restore batteries from any state of charge to 100%. Linear or non-linear charging curves are omitted.
4. **Instantaneous Terminal Charging:** Chargers at Bengaluru (BLR) and Kochi (KOC) terminals are assumed to be abundant, charging departing buses instantaneously prior to departure.
5. **Perfect State Measurement:** Measurement of battery depletion is modeled as strictly linear (1 km of travel equates to exactly 1 km of battery capacity loss).
6. **Station Navigation:** Docking, parking, and maneuvering times within the charging stations are assumed to take 0 minutes.

```

```