"""Gain operator - multiplies input by a constant."""

from __future__ import annotations

from pycosim.data_type import DataType
from pycosim.model.nodes.operators.base import Operator
from pycosim.model.variable import Input, OperatorOutput


class Gain(Operator):
    """Multiplies a single input by a constant gain factor."""

    def __init__(self, node_id: str, gain: float = 1.0,
                 inputs: list[Input] | None = None):
        self.gain = gain
        if inputs is None:
            inputs = [Input(id="input", data_type=DataType.REAL)]
        output = OperatorOutput(id="output", data_type=DataType.REAL)
        super().__init__(node_id, inputs, [output])

    def _compute(self) -> None:
        self.outputs[0].value = self.inputs[0].value * self.gain
