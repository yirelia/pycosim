"""Exporter - writes simulation results to CSV."""

from __future__ import annotations

import csv
import logging
from pathlib import Path
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from pycosim.model.graph import Graph
    from pycosim.model.graph_node import GraphNode

logger = logging.getLogger(__name__)


class Exporter:
    """Exports simulation time series data to CSV files."""

    def __init__(self, graph: Graph):
        self.graph = graph
        self._file = None
        self._writer = None
        self._headers: list[str] = []
        self._var_accessors: list[tuple[GraphNode, str]] = []

    def open(self) -> None:
        export = self.graph.export
        out_dir = Path(export.folder)
        out_dir.mkdir(parents=True, exist_ok=True)
        out_path = out_dir / f"{export.prefix}.csv"

        self._build_columns()

        self._file = open(out_path, "w", newline="")
        self._writer = csv.writer(self._file)
        self._writer.writerow(self._headers)
        logger.info("Exporting to %s", out_path)

    def record(self, time: float) -> None:
        if self._writer is None:
            return
        row = [time]
        for node, var_id in self._var_accessors:
            try:
                var = node.get_output(var_id)
                row.append(var.value)
            except KeyError:
                try:
                    var = node.get_input(var_id)
                    row.append(var.value)
                except KeyError:
                    row.append("")
        self._writer.writerow(row)

    def close(self) -> None:
        if self._file is not None:
            self._file.close()
            self._file = None
            self._writer = None

    def _build_columns(self) -> None:
        self._headers = ["time"]
        self._var_accessors = []
        export_vars = self.graph.export.variables

        for node in self.graph.nodes:
            if "all" in export_vars:
                for out in node.outputs:
                    col_name = f"{node.node_id}.{out.id}"
                    self._headers.append(col_name)
                    self._var_accessors.append((node, out.id))
            else:
                for spec in export_vars:
                    parts = spec.split(".")
                    if len(parts) == 2 and parts[0] == node.node_id:
                        self._headers.append(spec)
                        self._var_accessors.append((node, parts[1]))
