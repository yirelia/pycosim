"""JSON configuration loader - builds a runtime Graph from config."""

from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import Any

from pycosim.data_type import DataType
from pycosim.exceptions import ConfigError
from pycosim.model.arrow import Arrow
from pycosim.model.graph import Graph
from pycosim.model.graph_node import GraphNode
from pycosim.model.nodes.external_input import ExternalInput
from pycosim.model.nodes.external_output import ExternalOutput
from pycosim.model.nodes.fmu_local import FMULocal
from pycosim.model.nodes.operators.adder import Adder
from pycosim.model.nodes.operators.gain import Gain
from pycosim.model.nodes.operators.multiplier import Multiplier
from pycosim.model.nodes.operators.offset import Offset
from pycosim.model.settings import (
    CoInitSettings,
    ExportConfig,
    RuntimeSettings,
    StepperSettings,
    ZMQSettings,
)
from pycosim.model.variable import FMUInput, FMUOutput, Input, Output

logger = logging.getLogger(__name__)

_OPERATOR_MAP = {
    "adder": Adder,
    "multiplier": Multiplier,
    "gain": Gain,
    "offset": Offset,
}


def load_graph(config_path: str | Path) -> Graph:
    """Load a simulation graph from a JSON configuration file."""
    path = Path(config_path)
    if not path.exists():
        raise ConfigError(f"Config file not found: {path}")

    with open(path) as f:
        raw = json.load(f)

    settings = _parse_settings(raw.get("settings", {}))
    nodes = _parse_nodes(raw.get("nodes", []), path.parent)
    arrows = _parse_arrows(raw.get("arrows", []), nodes)
    export = _parse_export(raw.get("export", {}))

    graph = Graph(settings=settings, nodes=nodes, arrows=arrows, export=export)
    logger.info("Loaded graph with %d nodes and %d arrows", len(nodes), len(arrows))
    return graph


def _parse_settings(raw: dict) -> RuntimeSettings:
    co_init = CoInitSettings(**raw.get("co_initialization", {}))
    stepper = StepperSettings(**raw.get("stepper", {}))
    zmq = ZMQSettings(**raw.get("zmq", {}))
    return RuntimeSettings(
        start_time=raw.get("start_time", 0.0),
        stop_time=raw.get("stop_time", 10.0),
        co_initialization=co_init,
        stepper=stepper,
        zmq=zmq,
    )


def _parse_nodes(raw_nodes: list[dict], base_dir: Path) -> list[GraphNode]:
    nodes = []
    for raw in raw_nodes:
        node_type = raw.get("type", "fmu")
        node_id = raw["id"]

        if node_type == "fmu":
            nodes.append(_build_fmu_node(raw, base_dir))
        elif node_type == "operator":
            nodes.append(_build_operator_node(raw))
        elif node_type == "external_input":
            outputs = _parse_outputs(raw.get("outputs", []))
            nodes.append(ExternalInput(node_id, outputs=outputs))
        elif node_type == "external_output":
            inputs = _parse_inputs(raw.get("inputs", []))
            nodes.append(ExternalOutput(node_id, inputs=inputs))
        else:
            raise ConfigError(f"Unknown node type: {node_type}")

    return nodes


def _build_fmu_node(raw: dict, base_dir: Path) -> FMULocal:
    node_id = raw["id"]
    fmu_path = str(base_dir / raw["path"])
    inputs = _parse_fmu_inputs(raw.get("inputs", []))
    outputs = _parse_fmu_outputs(raw.get("outputs", []))
    before_init = {}
    for item in raw.get("before_init_values", []):
        before_init[item["name"]] = item["value"]
    return FMULocal(node_id, fmu_path, inputs=inputs, outputs=outputs,
                    before_init_values=before_init)


def _build_operator_node(raw: dict) -> GraphNode:
    node_id = raw["id"]
    op_type = raw.get("operator_type", "gain")
    inputs = _parse_inputs(raw.get("inputs", []))

    cls = _OPERATOR_MAP.get(op_type)
    if cls is None:
        raise ConfigError(f"Unknown operator type: {op_type}")

    if op_type == "gain":
        return cls(node_id, gain=raw.get("value", 1.0), inputs=inputs)
    elif op_type == "offset":
        return cls(node_id, offset=raw.get("value", 0.0), inputs=inputs)
    else:
        return cls(node_id, inputs=inputs)


def _parse_inputs(raw_inputs: list[dict]) -> list[Input]:
    return [Input(id=r["id"], data_type=DataType(r.get("type", "Real")))
            for r in raw_inputs]


def _parse_outputs(raw_outputs: list[dict]) -> list[Output]:
    return [Output(id=r["id"], data_type=DataType(r.get("type", "Real")))
            for r in raw_outputs]


def _parse_fmu_inputs(raw_inputs: list[dict]) -> list[FMUInput]:
    return [FMUInput(id=r["id"], data_type=DataType(r.get("type", "Real")))
            for r in raw_inputs]


def _parse_fmu_outputs(raw_outputs: list[dict]) -> list[FMUOutput]:
    return [FMUOutput(id=r["id"], data_type=DataType(r.get("type", "Real")))
            for r in raw_outputs]


def _parse_arrows(raw_arrows: list[dict], nodes: list[GraphNode]) -> list[Arrow]:
    node_map = {n.node_id: n for n in nodes}
    arrows = []
    for raw in raw_arrows:
        from_parts = raw["from"].split(".")
        to_parts = raw["to"].split(".")
        if len(from_parts) != 2 or len(to_parts) != 2:
            raise ConfigError(f"Arrow spec must be 'NodeId.VarId', got: {raw}")

        from_node = node_map.get(from_parts[0])
        to_node = node_map.get(to_parts[0])
        if from_node is None:
            raise ConfigError(f"Arrow source node not found: {from_parts[0]}")
        if to_node is None:
            raise ConfigError(f"Arrow target node not found: {to_parts[0]}")

        from_output = from_node.get_output(from_parts[1])
        to_input = to_node.get_input(to_parts[1])
        arrows.append(Arrow(from_output=from_output, to_input=to_input))

    return arrows


def _parse_export(raw: dict) -> ExportConfig:
    return ExportConfig(
        folder=raw.get("folder", "./output"),
        prefix=raw.get("prefix", "results"),
        variables=raw.get("variables", ["all"]),
    )
