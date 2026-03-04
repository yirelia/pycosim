"""ExternalInput - node providing external values to the graph."""

from __future__ import annotations

from pycosim.model.graph_node import GraphNode
from pycosim.model.variable import Output


class ExternalInput(GraphNode):
    """Provides externally set values as outputs to the simulation graph."""

    def __init__(self, node_id: str, outputs: list[Output] | None = None):
        super().__init__(node_id, inputs=[], outputs=outputs)

    def load(self) -> None:
        pass

    def init(self, start_time: float, stop_time: float) -> None:
        pass

    def step(self, current_time: float, dt: float) -> bool:
        return True

    def terminate(self) -> None:
        pass
