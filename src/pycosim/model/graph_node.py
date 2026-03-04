"""GraphNode ABC - base class for all simulation graph nodes."""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any

from pycosim.model.variable import Input, Output


class GraphNode(ABC):
    """Abstract base for all nodes in the simulation graph."""

    def __init__(self, node_id: str, inputs: list[Input] | None = None,
                 outputs: list[Output] | None = None):
        self.node_id = node_id
        self.inputs: list[Input] = inputs or []
        self.outputs: list[Output] = outputs or []

    def get_input(self, var_id: str) -> Input:
        for inp in self.inputs:
            if inp.id == var_id:
                return inp
        raise KeyError(f"Node '{self.node_id}' has no input '{var_id}'")

    def get_output(self, var_id: str) -> Output:
        for out in self.outputs:
            if out.id == var_id:
                return out
        raise KeyError(f"Node '{self.node_id}' has no output '{var_id}'")

    @abstractmethod
    def load(self) -> None:
        """Phase 1: Load resources."""

    @abstractmethod
    def init(self, start_time: float, stop_time: float) -> None:
        """Phase 2: Initialize the node."""

    @abstractmethod
    def step(self, current_time: float, dt: float) -> bool:
        """Phase 3: Execute one time step. Returns True on success."""

    @abstractmethod
    def terminate(self) -> None:
        """Phase 4: Clean up resources."""

    def save_state(self) -> None:
        """Save state for rollback (no-op by default)."""

    def restore_state(self) -> None:
        """Restore saved state (no-op by default)."""

    def pull_outputs(self) -> None:
        """Refresh all output values from the underlying model."""

    def push_inputs(self) -> None:
        """Write all input values to the underlying model."""

    def __repr__(self) -> str:
        return f"{self.__class__.__name__}('{self.node_id}')"
