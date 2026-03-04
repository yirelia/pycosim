"""ExternalOutput - node receiving values from the graph."""

from __future__ import annotations

from pycosim.model.graph_node import GraphNode
from pycosim.model.variable import Input


class ExternalOutput(GraphNode):
    """Receives values from the simulation graph for external consumption."""

    def __init__(self, node_id: str, inputs: list[Input] | None = None):
        super().__init__(node_id, inputs=inputs, outputs=[])

    def load(self) -> None:
        pass

    def init(self, start_time: float, stop_time: float) -> None:
        pass

    def step(self, current_time: float, dt: float) -> bool:
        return True

    def terminate(self) -> None:
        pass
