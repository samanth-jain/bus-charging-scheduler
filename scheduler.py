import heapq
import logging
import traceback
from typing import Dict, Any
from models import Bus, Station


class SchedulerSimulation:
    def __init__(self, scenario_data: Dict[str, Any]):
        self.logger = logging.getLogger(self.__class__.__name__)

        try:
            self.weights = scenario_data["weights"]
        except Exception as e:
            self.logger.exception("Failed reading scenario weights: %s", e)
            raise

        self.params = scenario_data["global_parameters"]
        self.max_battery = self.params["battery_range_km"]
        self.speed = self.params["speed_km_per_hour"] / 60.0
        self.charge_time = self.params["charge_time_to_full_minutes"]
        
        self.stations: Dict[str, Station] = {
            s["id"]: Station(id=s["id"], total_chargers=s["chargers"]) 
            for s in scenario_data["network"]["stations"]
        }
        
        # Build route graph from JSON
        self.routes = {}
        for r in scenario_data["network"]["routes"]:
            path = [(n["from"], n["distance_km"]) for n in r["path"]]
            path.append((r["path"][-1]["to"], 0)) # Add destination
            self.routes[r["route_id"]] = path

        self.bus_logs = []
        self.station_logs = []
        self.last_charge_time_by_operator = {}
        self.events = []
        self.buses: Dict[str, Bus] = {}
        
        for dep in scenario_data["departures"]:
            bus = Bus(id=dep["bus_id"], operator=dep["operator"], route_id=dep["route_id"], departure_time=dep["departure_time_mins"])
            self.buses[bus.id] = bus
            heapq.heappush(self.events, (bus.departure_time, "DEPART_ORIGIN", bus.id, self.routes[bus.route_id][0][0]))

        self.logger.info("Initialized SchedulerSimulation: buses=%d events=%d", len(self.buses), len(self.events))

    def run(self):
        while self.events:
            current_time, event_type, bus_id, node_id = heapq.heappop(self.events)
            bus = self.buses.get(bus_id)
            try:
                if not bus:
                    self.logger.warning("Event for unknown bus id %s at time %s: %s", bus_id, current_time, event_type)
                    continue

                if event_type == "DEPART_ORIGIN":
                    self._handle_depart(bus, current_time)
                elif event_type == "ARRIVE_NODE":
                    self._handle_arrive(bus, node_id, current_time)
                elif event_type == "CHARGE_START":
                    self._handle_charge_start(bus, node_id, current_time)
                elif event_type == "CHARGE_FINISH":
                    self._handle_charge_finish(bus, node_id, current_time)
            except Exception as e:
                tb = traceback.format_exc()
                self.logger.exception("Unhandled exception processing event %s for bus %s at %s: %s", event_type, bus_id, current_time, e)
                self.bus_logs.append({
                    "bus_id": bus_id,
                    "event": "ERROR",
                    "node": node_id,
                    "time": current_time,
                    "error": str(e),
                    "traceback": tb,
                })
                continue

        self.logger.info("Simulation finished: %d bus logs, %d station logs", len(self.bus_logs), len(self.station_logs))
        return self.bus_logs, self.station_logs

    def _handle_depart(self, bus: Bus, current_time: int):
        route = self.routes[bus.route_id]
        distance_to_next = route[bus.current_node_index][1]
        travel_time = int(distance_to_next / self.speed)
        next_node = route[bus.current_node_index + 1][0]
        
        bus.current_node_index += 1
        heapq.heappush(self.events, (current_time + travel_time, "ARRIVE_NODE", bus.id, next_node))
        
        self.bus_logs.append({"bus_id": bus.id, "event": "DEPART", "node": route[0][0], "time": current_time, "wait": 0})

    def _handle_arrive(self, bus: Bus, node_id: str, current_time: int):
        """
        Bus arrives at a node. Decide to charge, skip, or finish trip.
        Uses dynamic look-ahead heuristic to avoid traffic jams.
        """
        route = self.routes[bus.route_id]
        
        # Deduct battery based on travel distance from previous node
        prev_distance = route[bus.current_node_index - 1][1]
        bus.battery_km -= prev_distance
        
        # Check if terminal node (Kochi or Bengaluru)
        if bus.current_node_index == len(route) - 1:
            self.bus_logs.append({
                "bus_id": bus.id, "event": "ARRIVE_DEST", 
                "node": node_id, "time": current_time, "wait": 0
            })
            return

        station = self.stations[node_id]

        # --- DYNAMIC TWO-NODE LOOK-AHEAD ROUTING ---
        
        # 1. Distance to the immediate next station
        distance_to_next = route[bus.current_node_index][1]
        
        # 2. Distance to the station AFTER the next one (if it exists)
        if bus.current_node_index + 1 < len(route) - 1:
            distance_after_next = route[bus.current_node_index + 1][1]
        else:
            # If the next stop is the final destination, there is no "after next"
            distance_after_next = 0 
            
        # 3. Calculate dynamic threshold
        dynamic_threshold_km = distance_to_next + distance_after_next

        # 4. Routing Logic
        # Hard rule: Must charge if battery can't reach the immediate next station.
        must_charge = bus.battery_km < distance_to_next
        
        # Soft rule: Charge if charger is free AND we can't reach the station AFTER next.
        # This leapfrogs buses and prevents mass bottlenecks at deep stations.
        should_charge = (
            station.chargers_in_use < station.total_chargers 
            and bus.battery_km < dynamic_threshold_km
        )
        
        if must_charge or should_charge:
            # Join queue and trigger evaluation
            bus.queue_join_time = current_time
            station.queue.append(bus)
            self._evaluate_queue(station, current_time)
        else:
            # Skip charging and proceed to next node
            travel_time = int(distance_to_next / self.speed)
            next_node = route[bus.current_node_index + 1][0]
            
            bus.current_node_index += 1
            heapq.heappush(self.events, (current_time + travel_time, "ARRIVE_NODE", bus.id, next_node))
            
    def _evaluate_queue(self, station: Station, current_time: int):
        if station.chargers_in_use < station.total_chargers and station.queue:
            best_bus = max(station.queue, key=lambda b: self._score_bus(b, current_time))
            station.queue.remove(best_bus)
            station.chargers_in_use += 1
            heapq.heappush(self.events, (current_time, "CHARGE_START", best_bus.id, station.id))

    def _score_bus(self, bus: Bus, current_time: int) -> float:
        wait_time = current_time - bus.queue_join_time
        last_op_charge = self.last_charge_time_by_operator.get(bus.operator, bus.departure_time)
        time_since_op_charged = current_time - last_op_charge
        total_trip_time = current_time - bus.departure_time
        
        return (self.weights["individual_wait"] * wait_time) + \
               (self.weights["operator_grouping"] * time_since_op_charged) + \
               (self.weights["overall_time"] * total_trip_time)

    def _handle_charge_start(self, bus: Bus, node_id: str, current_time: int):
        wait = current_time - bus.queue_join_time
        bus.total_wait_time += wait
        self.last_charge_time_by_operator[bus.operator] = current_time
        
        heapq.heappush(self.events, (current_time + self.charge_time, "CHARGE_FINISH", bus.id, node_id))
        
        log_entry = {"bus_id": bus.id, "event": "CHARGE", "node": node_id, "arrive": bus.queue_join_time, "start": current_time, "wait": wait}
        self.bus_logs.append(log_entry)
        self.station_logs.append(log_entry)

    def _handle_charge_finish(self, bus: Bus, node_id: str, current_time: int):
        station = self.stations[node_id]
        bus.battery_km = self.max_battery
        station.chargers_in_use -= 1
        
        for log in reversed(self.bus_logs):
            if log["bus_id"] == bus.id and log["node"] == node_id and log["event"] == "CHARGE" and "end" not in log:
                log["end"] = current_time
                break
                
        route = self.routes[bus.route_id]
        distance_to_next = route[bus.current_node_index][1]
        travel_time = int(distance_to_next / self.speed)
        next_node = route[bus.current_node_index + 1][0]
        
        bus.current_node_index += 1
        heapq.heappush(self.events, (current_time + travel_time, "ARRIVE_NODE", bus.id, next_node))
        self._evaluate_queue(station, current_time)

