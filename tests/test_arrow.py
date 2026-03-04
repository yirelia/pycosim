"""Tests for Arrow."""

from pycosim.data_type import DataType
from pycosim.model.arrow import Arrow
from pycosim.model.variable import Input, Output


def test_arrow_transfer():
    out = Output(id="y", data_type=DataType.REAL, value=5.0)
    inp = Input(id="u", data_type=DataType.REAL, value=0.0)
    arrow = Arrow(from_output=out, to_input=inp)

    arrow.transfer()
    assert inp.value == 5.0


def test_arrow_transfer_string():
    out = Output(id="s_out", data_type=DataType.STRING, value="hello")
    inp = Input(id="s_in", data_type=DataType.STRING)
    arrow = Arrow(from_output=out, to_input=inp)

    arrow.transfer()
    assert inp.value == "hello"
