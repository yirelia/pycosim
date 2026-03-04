"""Tests for Iterator."""

from pycosim.data_type import DataType
from pycosim.engine.iterator import Iterator
from pycosim.model.arrow import Arrow
from pycosim.model.variable import FMUInput, FMUOutput, Input, Output
from tests.conftest import MockFMUNode


def _make_two_node_graph():
    """Create two mock nodes connected by an arrow."""
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
    return [node_a, node_b], [arrow]


def test_sequential_iterate():
    nodes, arrows = _make_two_node_graph()
    for n in nodes:
        n.load()
        n.init(0.0, 10.0)

    nodes[0].inputs[0].value = 3.0

    it = Iterator(nodes, arrows, parallel=False)
    success = it.iterate(0.0, 0.1)
    assert success

    # After iterate: A's output transferred to B's input
    assert nodes[1].inputs[0].value == nodes[0].outputs[0].value


def test_parallel_iterate():
    nodes, arrows = _make_two_node_graph()
    for n in nodes:
        n.load()
        n.init(0.0, 10.0)

    nodes[0].inputs[0].value = 3.0

    it = Iterator(nodes, arrows, parallel=True, max_workers=2)
    success = it.iterate(0.0, 0.1)
    assert success
