"""Adder operator - sums all inputs."""

from __future__ import annotations

from pycosim.data_type import DataType
from pycosim.model.nodes.operators.base import Operator
from pycosim.model.variable import Input, OperatorOutput


class Adder(Operator):
    """Sums all input values to produce a single output."""

    def __init__(self, node_id: str, inputs: list[Input] | None = None):
        output = OperatorOutput(id="output", data_type=DataType.REAL)
        super().__init__(node_id, inputs, [output])

    def _compute(self) -> None:
        total = sum(inp.value for inp in self.inputs)
        self.outputs[0].value = total
