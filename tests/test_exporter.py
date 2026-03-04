"""Tests for Exporter."""

import csv
import tempfile
from pathlib import Path

from pycosim.data_type import DataType
from pycosim.engine.exporter import Exporter
from pycosim.model.arrow import Arrow
from pycosim.model.graph import Graph
from pycosim.model.settings import ExportConfig, RuntimeSettings
from pycosim.model.variable import Output
from tests.conftest import MockFMUNode


def test_exporter_writes_csv():
    with tempfile.TemporaryDirectory() as tmp:
        node = MockFMUNode(
            "N1",
            outputs=[Output(id="y", data_type=DataType.REAL, value=42.0)],
        )
        graph = Graph(
            settings=RuntimeSettings(),
            nodes=[node],
            arrows=[],
            export=ExportConfig(folder=tmp, prefix="test"),
        )

        exp = Exporter(graph)
        exp.open()
        exp.record(0.0)
        exp.record(0.1)
        exp.close()

        csv_path = Path(tmp) / "test.csv"
        assert csv_path.exists()

        with open(csv_path) as f:
            reader = csv.reader(f)
            headers = next(reader)
            assert headers == ["time", "N1.y"]
            row1 = next(reader)
            assert float(row1[0]) == 0.0
            assert float(row1[1]) == 42.0
