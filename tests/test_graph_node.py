"""Tests for GraphNode and MockFMUNode."""

import pytest

from pycosim.data_type import DataType
from pycosim.model.variable import FMUInput, FMUOutput, Input
from tests.conftest import MockFMUNode


def test_mock_node_lifecycle():
    inputs = [FMUInput(id="u", data_type=DataType.REAL, vr=1)]
    outputs = [FMUOutput(id="y", data_type=DataType.REAL, vr=101)]
    node = MockFMUNode("test", inputs=inputs, outputs=outputs)

    node.load()
    assert node._loaded

    node.init(0.0, 10.0)
    assert node._initialized

    node.inputs[0].value = 5.0
    success = node.step(0.0, 0.1)
    assert success
    assert node.outputs[0].value == 10.0  # mock doubles input

    node.terminate()


def test_get_input_output():
    node = MockFMUNode("n1",
                       inputs=[Input(id="a", data_type=DataType.REAL)],
                       outputs=[])
    assert node.get_input("a").id == "a"

    with pytest.raises(KeyError):
        node.get_input("nonexistent")


def test_save_restore():
    inputs = [FMUInput(id="u", data_type=DataType.REAL, vr=1)]
    outputs = [FMUOutput(id="y", data_type=DataType.REAL, vr=101)]
    node = MockFMUNode("test", inputs=inputs, outputs=outputs)

    node.load()
    node.init(0.0, 10.0)
    node.inputs[0].value = 5.0
    node.step(0.0, 0.1)

    node.save_state()
    original_value = node.proxy._values.copy()

    node.inputs[0].value = 99.0
    node.step(0.1, 0.1)

    node.restore_state()
    assert node.proxy._values == original_value
