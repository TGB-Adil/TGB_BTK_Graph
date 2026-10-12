from dataclasses import dataclass, field
from typing import Any
from uuid import uuid4

@dataclass
class Edge:
    edge_id: str = field(default_factory=lambda: str(uuid4()))
    source: str = ""
    target: str = ""

    customer_orders: list[str] = field(default_factory=list)
    orders: list[dict[str, Any]] = field(default_factory=list)

    loading_meter_planned: float = 0.0
    weight_total_planned: float = 0.0

    attributes: dict[str, Any] = field(default_factory=dict)