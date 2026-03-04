"""Tests for GraphExecutor with mock nodes."""

import tempfile
from pathlib import Path

from pycosim.data_type import DataType
from pycosim.engine.graph_executor import GraphExecutor
from pycosim.model.arrow import Arrow
from pycosim.model.graph import Graph
from pycosim.model.settings import ExportConfig, RuntimeSettings, StepperSettings
from pycosim.model.variable import FMUInput, FMUOutput, Input, Output
from tests.conftest import MockFMUNode


def test_full_simulation_lifecycle():
    """Run a 2-node simulation for 1 second with dt=0.5."""
    with tempfile.TemporaryDirectory() as tmp:
        node_a = MockFMUNode(
            "A",
            inputs=[FMUInput(id="u", data_type=DataType.REAL, vr=1)],
            outputs=[FMUOutput(id="y", data_type=DataType.REAL, vr=101)],
        )
        node_b = MockFMUNode(
            "B",
            inputs=[FMUInput(id="u", data_type=DataType.REAL, vr=1)],
            outputs=[FMUOutput(id="y", data_type=DataType.REAL, vr=101)],
        )
        arrow = Arrow(from_output=node_a.outputs[0], to_input=node_b.inputs[0])

        settings = RuntimeSettings(
            start_time=0.0,
            stop_time=1.0,
            stepper=StepperSettings(method="constant", step_size=0.5),
        )
        graph = Graph(
            settings=settings,
            nodes=[node_a, node_b],
            arrows=[arrow],
            export=ExportConfig(folder=tmp, prefix="test_sim"),
        )

        executor = GraphExecutor(graph)
        executor.execute()

        csv_path = Path(tmp) / "test_sim.csv"
        assert csv_path.exists()
        lines = csv_path.read_text().strip().split("\n")
        assert len(lines) == 4  # header + 3 time points (0.0, 0.5, 1.0)
