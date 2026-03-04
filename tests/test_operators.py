"""Tests for Operator nodes."""

from pycosim.data_type import DataType
from pycosim.model.nodes.operators.adder import Adder
from pycosim.model.nodes.operators.gain import Gain
from pycosim.model.nodes.operators.multiplier import Multiplier
from pycosim.model.nodes.operators.offset import Offset
from pycosim.model.variable import Input


def test_adder():
    inputs = [
        Input(id="a", data_type=DataType.REAL, value=3.0),
        Input(id="b", data_type=DataType.REAL, value=7.0),
    ]
    adder = Adder("add1", inputs=inputs)
    adder.init(0.0, 10.0)
    adder.step(0.0, 0.1)
    assert adder.outputs[0].value == 10.0


def test_multiplier():
    inputs = [
        Input(id="a", data_type=DataType.REAL, value=3.0),
        Input(id="b", data_type=DataType.REAL, value=4.0),
    ]
    mul = Multiplier("mul1", inputs=inputs)
    mul.init(0.0, 10.0)
    mul.step(0.0, 0.1)
    assert mul.outputs[0].value == 12.0


def test_gain():
    gain = Gain("g1", gain=2.5)
    gain.inputs[0].value = 4.0
    gain.init(0.0, 10.0)
    gain.step(0.0, 0.1)
    assert gain.outputs[0].value == 10.0


def test_offset():
    offset = Offset("off1", offset=3.0)
    offset.inputs[0].value = 7.0
    offset.init(0.0, 10.0)
    offset.step(0.0, 0.1)
    assert offset.outputs[0].value == 10.0
