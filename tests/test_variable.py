"""Tests for Variable hierarchy."""

from pycosim.data_type import DataType
from pycosim.model.variable import (
    FMUInput, FMUOutput, Input, OperatorOutput, Output, Variable,
)
from tests.conftest import MockFMUProxy


def test_variable_default():
    v = Variable(id="x", data_type=DataType.REAL)
    assert v.value == 0.0

    v2 = Variable(id="s", data_type=DataType.STRING)
    assert v2.value == ""


def test_input_output():
    inp = Input(id="u", data_type=DataType.REAL)
    out = Output(id="y", data_type=DataType.REAL)
    assert inp.value == 0.0
    assert out.value == 0.0


def test_fmu_input_push():
    proxy = MockFMUProxy()
    inp = FMUInput(id="u", data_type=DataType.REAL, vr=1)
    inp.push(proxy, 3.14)
    assert inp.value == 3.14
    assert proxy._values[1] == 3.14


def test_fmu_output_pull():
    proxy = MockFMUProxy()
    proxy._values[2] = 42.0
    out = FMUOutput(id="y", data_type=DataType.REAL, vr=2)
    result = out.pull(proxy)
    assert result == 42.0
    assert out.value == 42.0


def test_operator_output():
    out = OperatorOutput(id="result", data_type=DataType.REAL)
    out.compute_fn = lambda: 99.0
    result = out.pull()
    assert result == 99.0
