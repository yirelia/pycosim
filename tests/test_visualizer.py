"""Tests for Visualizer."""

import csv
import tempfile
from pathlib import Path

import pytest

from pycosim.engine.visualizer import list_variables, load_csv, plot


@pytest.fixture
def sample_csv(tmp_path):
    csv_path = tmp_path / "results.csv"
    with open(csv_path, "w", newline="") as f:
        writer = csv.writer(f)
        writer.writerow(["time", "Plant.y", "Controller.y"])
        for i in range(11):
            t = i * 0.1
            writer.writerow([t, t * 2.0, t * 3.0])
    return csv_path


def test_load_csv(sample_csv):
    headers, rows = load_csv(sample_csv)
    assert headers == ["time", "Plant.y", "Controller.y"]
    assert len(rows) == 11
    assert rows[0] == [0.0, 0.0, 0.0]
    assert rows[10][0] == pytest.approx(1.0)


def test_list_variables(sample_csv):
    variables = list_variables(sample_csv)
    assert variables == ["Plant.y", "Controller.y"]


def test_load_csv_missing_file():
    with pytest.raises(FileNotFoundError):
        load_csv("/nonexistent/path.csv")


def test_plot_save_to_file(sample_csv, tmp_path):
    out_path = tmp_path / "figure.png"
    plot(sample_csv, output=str(out_path), title="Test")
    assert out_path.exists()
    assert out_path.stat().st_size > 0


def test_plot_selected_vars(sample_csv, tmp_path):
    out_path = tmp_path / "selected.png"
    plot(sample_csv, variables=["Plant.y"], output=str(out_path))
    assert out_path.exists()


def test_plot_subplots(sample_csv, tmp_path):
    out_path = tmp_path / "subplots.png"
    plot(sample_csv, output=str(out_path), subplots=True)
    assert out_path.exists()
