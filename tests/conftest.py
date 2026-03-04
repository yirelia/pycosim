"""Shared test fixtures."""

from __future__ import annotations

from typing import Any

import pytest

from pycosim.data_type import DataType
from pycosim.model.fmu_proxy import FMUProxy
from pycosim.model.graph_node import GraphNode
from pycosim.model.variable import FMUInput, FMUOutput, Input, Output


class MockFMUProxy(FMUProxy):
    """Mock FMU for testing without real FMU files."""

    def __init__(self):
        self._values: dict[int, Any] = {}
        self._saved_values: dict[int, Any] = {}
        self._loaded = False
        self._initialized = False
        self._step_count = 0

    def load(self, path: str) -> None:
        self._loaded = True

    def instantiate(self) -> None:
        pass

    def init(self, start_time: float, stop_time: float) -> None:
        self._initialized = True

    def step(self, current_time: float, dt: float) -> bool:
        self._step_count += 1
        # Simple dynamics: output = input * 2.0 for testing
        for vr, val in list(self._values.items()):
            if isinstance(val, (int, float)):
                self._values[vr + 100] = val * 2.0
        return True

    def terminate(self) -> None:
        pass

    def push(self, vr: int, value: Any, data_type: DataType) -> None:
        self._values[vr] = value

    def pull(self, vr: int, data_type: DataType) -> Any:
        return self._values.get(vr, data_type.default_value)

    def save_state(self) -> None:
        self._saved_values = dict(self._values)

    def restore_state(self) -> None:
        self._values = dict(self._saved_values)


class MockFMUNode(GraphNode):
    """Mock graph node wrapping MockFMUProxy for integration tests."""

    def __init__(self, node_id: str, inputs: list[Input] | None = None,
                 outputs: list[Output] | None = None):
        super().__init__(node_id, inputs, outputs)
        self.proxy = MockFMUProxy()
        self._loaded = False
        self._initialized = False

    def load(self) -> None:
        self.proxy.load("")
        self._loaded = True

    def init(self, start_time: float, stop_time: float) -> None:
        self.proxy.init(start_time, stop_time)
        self._initialized = True
        self.pull_outputs()

    def step(self, current_time: float, dt: float) -> bool:
        self.push_inputs()
        result = self.proxy.step(current_time, dt)
        self.pull_outputs()
        return result

    def terminate(self) -> None:
        self.proxy.terminate()

    def pull_outputs(self) -> None:
        for out in self.outputs:
            if isinstance(out, FMUOutput):
                out.value = self.proxy.pull(out.vr, out.data_type)

    def push_inputs(self) -> None:
        for inp in self.inputs:
            if isinstance(inp, FMUInput):
                self.proxy.push(inp.vr, inp.value, inp.data_type)

    def save_state(self) -> None:
        self.proxy.save_state()

    def restore_state(self) -> None:
        self.proxy.restore_state()
