"""Tests for DataType enum."""

from pycosim.data_type import DataType


def test_data_type_values():
    assert DataType.REAL.value == "Real"
    assert DataType.INTEGER.value == "Integer"
    assert DataType.BOOLEAN.value == "Boolean"
    assert DataType.STRING.value == "String"


def test_default_values():
    assert DataType.REAL.default_value == 0.0
    assert DataType.INTEGER.default_value == 0
    assert DataType.BOOLEAN.default_value is False
    assert DataType.STRING.default_value == ""


def test_from_string():
    assert DataType("Real") == DataType.REAL
    assert DataType("Integer") == DataType.INTEGER
