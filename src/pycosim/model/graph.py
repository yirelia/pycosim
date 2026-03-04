"""Runtime simulation graph (immutable after construction)."""

from __future__ import annotations

from dataclasses import dataclass, field

from pycosim.model.arrow import Arrow
from pycosim.model.graph_node import GraphNode
from pycosim.model.settings import ExportConfig, RuntimeSettings


@dataclass
class Graph:
    """Immutable runtime simulation graph."""

    settings: RuntimeSettings
    nodes: list[GraphNode] = field(default_factory=list)
    arrows: list[Arrow] = field(default_factory=list)
    export: ExportConfig = field(default_factory=ExportConfig)

    def get_node(self, node_id: str) -> GraphNode:
        for node in self.nodes:
            if node.node_id == node_id:
                return node
        raise KeyError(f"No node '{node_id}' in graph")
