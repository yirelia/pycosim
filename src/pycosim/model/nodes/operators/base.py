"""Operator ABC - mathematical operation nodes."""

from __future__ import annotations

from abc import abstractmethod

from pycosim.data_type import DataType
from pycosim.model.graph_node import GraphNode
from pycosim.model.variable import Input, OperatorOutput


class Operator(GraphNode):
    """Abstract base for mathematical operator nodes."""

    def __init__(self, node_id: str, inputs: list[Input] | None = None,
                 outputs: list[OperatorOutput] | None = None):
        super().__init__(node_id, inputs, outputs)

    def load(self) -> None:
        pass

    def init(self, start_time: float, stop_time: float) -> None:
        self._bind_compute()

    def step(self, current_time: float, dt: float) -> bool:
        self._compute()
        return True

    def terminate(self) -> None:
        pass

    @abstractmethod
    def _compute(self) -> None:
        """Compute output values from inputs."""

    def _bind_compute(self) -> None:
        """Bind compute function to operator outputs for lazy evaluation."""
        for out in self.outputs:
            if isinstance(out, OperatorOutput):
                out.compute_fn = self._compute
