from dataclasses import dataclass, field
from typing import List

@dataclass
class Bus:
    id: str
    operator: str
    route_id: str
    departure_time: int
    battery_km: int = 240
    current_node_index: int = 0
    total_wait_time: int = 0
    queue_join_time: int = 0

@dataclass
class Station:
    id: str
    total_chargers: int
    chargers_in_use: int = 0
    queue: List[Bus] = field(default_factory=list)