"""Arrow: directional connection between an Output and an Input."""

from __future__ import annotations

from dataclasses import dataclass

from pycosim.model.variable import Input, Output


@dataclass
class Arrow:
    """A connection from an output port to an input port."""

    from_output: Output
    to_input: Input

    def transfer(self) -> None:
        """Copy the current output value to the connected input."""
        self.to_input.value = self.from_output.value
