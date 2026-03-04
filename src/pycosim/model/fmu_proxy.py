"""FMUProxy ABC - unified abstraction for FMU operations."""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any

from pycosim.data_type import DataType


class FMUProxy(ABC):
    """Abstract interface for FMU operations (local or remote)."""

    @abstractmethod
    def load(self, path: str) -> None:
        """Load the FMU from the given path."""

    @abstractmethod
    def instantiate(self) -> None:
        """Create an FMU instance."""

    @abstractmethod
    def init(self, start_time: float, stop_time: float) -> None:
        """Initialize the FMU instance."""

    @abstractmethod
    def step(self, current_time: float, dt: float) -> bool:
        """Advance the FMU by dt. Returns True on success."""

    @abstractmethod
    def terminate(self) -> None:
        """Terminate and free FMU resources."""

    @abstractmethod
    def push(self, vr: int, value: Any, data_type: DataType) -> None:
        """Set an input variable by value reference."""

    @abstractmethod
    def pull(self, vr: int, data_type: DataType) -> Any:
        """Get an output variable by value reference."""

    @abstractmethod
    def save_state(self) -> None:
        """Save current state for rollback."""

    @abstractmethod
    def restore_state(self) -> None:
        """Restore previously saved state."""

    def derivative_of_io(self, input_vr: int, output_vr: int,
                         delta: float = 1e-6) -> float:
        """Approximate directional derivative d(output)/d(input) via finite difference."""
        original = self.pull(output_vr, DataType.REAL)
        current_input = self.pull(input_vr, DataType.REAL)
        self.push(input_vr, current_input + delta, DataType.REAL)
        perturbed = self.pull(output_vr, DataType.REAL)
        self.push(input_vr, current_input, DataType.REAL)
        return (perturbed - original) / delta

    def derivative_of(self, output_vr: int) -> float:
        """Get the time derivative of an output (if available)."""
        return 0.0
