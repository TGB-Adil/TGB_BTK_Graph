
from dataclasses import dataclass, field
from uuid import uuid4

from models.node import Node
from models.edge import Edge


@dataclass
class Graph:
    layer: str
    graph_id: str = field(default_factory=lambda: str(uuid4()))

    nodes: dict[str, Node] = field(default_factory=dict)
    edges: dict[tuple[str, str], Edge] = field(default_factory=dict)

    def add_node(self, node: Node) -> Node:
        # The area seal is the lookup key, not the random UUID.
        self.nodes.setdefault(node.area_seal, node)
        return self.nodes[node.area_seal]

    def add_edge(self, edge: Edge) -> Edge:
        key = (edge.source, edge.target)

        if key not in self.edges:
            self.edges[key] = edge

        return self.edges[key]