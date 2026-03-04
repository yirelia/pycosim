"""Tests for CoInitializer."""

from pycosim.data_type import DataType
from pycosim.engine.co_initializer import CoInitializer
from pycosim.model.arrow import Arrow
from pycosim.model.graph import Graph
from pycosim.model.settings import RuntimeSettings
from pycosim.model.variable import Input, Output
from tests.conftest import MockFMUNode


def test_no_algebraic_loop():
    """Linear graph should detect no loops."""
    node_a = MockFMUNode("A", outputs=[Output(id="y", data_type=DataType.REAL)])
    node_b = MockFMUNode("B", inputs=[Input(id="u", data_type=DataType.REAL)])
    arrow = Arrow(from_output=node_a.outputs[0], to_input=node_b.inputs[0])

    graph = Graph(settings=RuntimeSettings(), nodes=[node_a, node_b], arrows=[arrow])
    co_init = CoInitializer(graph)
    co_init.solve()  # Should not raise


def test_scc_detection():
    """Circular connection should be detected as SCC."""
    node_a = MockFMUNode(
        "A",
        inputs=[Input(id="u", data_type=DataType.REAL)],
        outputs=[Output(id="y", data_type=DataType.REAL, value=1.0)],
    )
    node_b = MockFMUNode(
        "B",
        inputs=[Input(id="u", data_type=DataType.REAL)],
        outputs=[Output(id="y", data_type=DataType.REAL, value=1.0)],
    )
    arrows = [
        Arrow(from_output=node_a.outputs[0], to_input=node_b.inputs[0]),
        Arrow(from_output=node_b.outputs[0], to_input=node_a.inputs[0]),
    ]

    graph = Graph(settings=RuntimeSettings(), nodes=[node_a, node_b], arrows=arrows)
    co_init = CoInitializer(graph)
    sccs = co_init._find_sccs()
    loops = [s for s in sccs if len(s) > 1]
    assert len(loops) == 1
