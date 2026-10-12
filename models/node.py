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
    
    # Corner coordinates: x = longitude, y = latitude
    blx_coord: float | None = None  # Bottom-left longitude
    bly_coord: float | None = None  # Bottom-left latitude

    tlx_coord: float | None = None  # Top-left longitude
    tly_coord: float | None = None  # Top-left latitude

    trx_coord: float | None = None  # Top-right longitude
    try_coord: float | None = None  # Top-right latitude

    brx_coord: float | None = None  # Bottom-right longitude
    bry_coord: float | None = None  # Bottom-right latitude

    
    # InBound/Outbound Loading meter and and weight 
    inbound_loading_meter: float = 0.0
    outbound_loading_meter: float = 0.0
    
    inbound_weight: float = 0.0
    outbound_weight: float = 0.0
    
    # individual order contributing to node
    inbound_orders : list[dict[str, Any]] = field(default_factory=list)
    outbound_orders : list[dict[str, Any]] = field(default_factory=list)
    
    attributes: dict[str, Any] = field(default_factory=dict)