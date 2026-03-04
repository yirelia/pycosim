"""FMI variable data types."""

from enum import Enum


class DataType(Enum):
    REAL = "Real"
    INTEGER = "Integer"
    BOOLEAN = "Boolean"
    STRING = "String"

    @property
    def default_value(self):
        return {
            DataType.REAL: 0.0,
            DataType.INTEGER: 0,
            DataType.BOOLEAN: False,
            DataType.STRING: "",
        }[self]
