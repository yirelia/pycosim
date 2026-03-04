"""Tests for config loader."""

import json
import tempfile
from pathlib import Path

import pytest

from pycosim.config.loader import load_graph
from pycosim.exceptions import ConfigError


def test_load_operator_config():
    """Load a config with operator nodes (no real FMU files needed)."""
    config = {
        "settings": {
            "start_time": 0.0,
            "stop_time": 1.0,
            "stepper": {"method": "constant", "step_size": 0.1},
        },
        "nodes": [
            {
                "type": "operator",
                "operator_type": "gain",
                "id": "Gain1",
                "value": 2.5,
                "inputs": [{"id": "input", "type": "Real"}],
            },
            {
                "type": "operator",
                "operator_type": "offset",
                "id": "Offset1",
                "value": 10.0,
                "inputs": [{"id": "input", "type": "Real"}],
            },
        ],
        "arrows": [
            {"from": "Gain1.output", "to": "Offset1.input"},
        ],
        "export": {"folder": "/tmp/test_output", "prefix": "test"},
    }

    with tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False) as f:
        json.dump(config, f)
        f.flush()

        graph = load_graph(f.name)
        assert len(graph.nodes) == 2
        assert len(graph.arrows) == 1
        assert graph.settings.stepper.step_size == 0.1


def test_missing_config_file():
    with pytest.raises(ConfigError):
        load_graph("/nonexistent/path.json")
