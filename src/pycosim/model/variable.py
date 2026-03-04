"""Variable hierarchy for simulation graph ports."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from pycosim.data_type import DataType


@dataclass
class Variable:
    """Base variable attached to a graph node."""

    id: str
    data_type: DataType
    value: Any = None

    def __post_init__(self):
        if self.value is None:
            self.value = self.data_type.default_value


@dataclass
class Input(Variable):
    """Input port on a graph node."""
    pass


@dataclass
class Output(Variable):
    """Output port on a graph node."""
    pass


@dataclass
class FMUInput(Input):
    """Input delegating writes to an FMUProxy."""

    vr: int = 0  # FMI value reference

    def push(self, proxy, value: Any) -> None:
        self.value = value
        proxy.push(self.vr, value, self.data_type)


@dataclass
class FMUOutput(Output):
    """Output delegating reads to an FMUProxy."""

    vr: int = 0  # FMI value reference

    def pull(self, proxy) -> Any:
        self.value = proxy.pull(self.vr, self.data_type)
        return self.value


@dataclass
class OperatorOutput(Output):
    """Output computed lazily by an operator node."""

    compute_fn: Any = None  # Callable set by operator

    def pull(self) -> Any:
        if self.compute_fn is not None:
            self.value = self.compute_fn()
        return self.value
