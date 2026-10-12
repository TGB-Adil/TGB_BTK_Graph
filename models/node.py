from dataclasses import dataclass, field
from typing import Any
from uuid import uuid4

@dataclass
class Node:
    node_id: str = field(default_factory=lambda: str(uuid4()))
    # Business identifier from the OAS tables
    area_seal: str = ""
    # Coordinates;
    cx:float | None = None
    cy:float | None = None
    
    # InBound/Outbound Loading meter and and weight 
    inbound_loading_meter: float = 0.0
    outbound_loading_meter: float = 0.0
    
    inbound_weight: float = 0.0
    outbound_weight: float = 0.0
    
    # individual order contributing to node
    inbound_orders : list[dict[str, Any]] = field(default_factory=list)
    outbound_orders : list[dict[str, Any]] = field(default_factory=list)
    
    attributes: dict[str, Any] = field(default_factory=dict)