"""Visualizer - plot simulation results from CSV."""

from __future__ import annotations

import csv
import logging
from pathlib import Path

import matplotlib.pyplot as plt

logger = logging.getLogger(__name__)


def load_csv(csv_path: str | Path) -> tuple[list[str], list[list[float]]]:
    """Load a CSV results file. Returns (headers, rows)."""
    path = Path(csv_path)
    if not path.exists():
        raise FileNotFoundError(f"CSV file not found: {path}")

    with open(path) as f:
        reader = csv.reader(f)
        headers = next(reader)
        rows = []
        for row in reader:
            rows.append([float(v) if v != "" else float("nan") for v in row])

    return headers, rows


def list_variables(csv_path: str | Path) -> list[str]:
    """List all variable names in a CSV results file (excluding 'time')."""
    headers, _ = load_csv(csv_path)
    return [h for h in headers if h != "time"]


def plot(
    csv_path: str | Path,
    variables: list[str] | None = None,
    output: str | None = None,
    title: str | None = None,
    subplots: bool = False,
) -> None:
    """Plot simulation results.

    Args:
        csv_path: Path to the CSV results file.
        variables: Variable names to plot. None means all.
        output: Save figure to this path instead of showing interactively.
        title: Figure title.
        subplots: If True, each variable gets its own subplot.
    """
    headers, rows = load_csv(csv_path)
    if not rows:
        logger.warning("CSV file is empty: %s", csv_path)
        return

    col_map = {h: i for i, h in enumerate(headers)}
    time = [row[col_map["time"]] for row in rows]

    # Resolve which variables to plot
    all_vars = [h for h in headers if h != "time"]
    if variables:
        plot_vars = []
        for v in variables:
            if v in col_map:
                plot_vars.append(v)
            else:
                logger.warning("Variable '%s' not found in CSV, skipping", v)
        if not plot_vars:
            logger.error("No valid variables to plot")
            return
    else:
        plot_vars = all_vars

    if subplots and len(plot_vars) > 1:
        fig, axes = plt.subplots(len(plot_vars), 1, sharex=True,
                                 figsize=(10, 3 * len(plot_vars)))
        if len(plot_vars) == 1:
            axes = [axes]
        for ax, var in zip(axes, plot_vars):
            col_idx = col_map[var]
            values = [row[col_idx] for row in rows]
            ax.plot(time, values)
            ax.set_ylabel(var)
            ax.grid(True, alpha=0.3)
        axes[-1].set_xlabel("Time (s)")
        if title:
            fig.suptitle(title)
    else:
        fig, ax = plt.subplots(figsize=(10, 6))
        for var in plot_vars:
            col_idx = col_map[var]
            values = [row[col_idx] for row in rows]
            ax.plot(time, values, label=var)
        ax.set_xlabel("Time (s)")
        ax.set_ylabel("Value")
        ax.legend()
        ax.grid(True, alpha=0.3)
        if title:
            ax.set_title(title)

    plt.tight_layout()

    if output:
        out_path = Path(output)
        out_path.parent.mkdir(parents=True, exist_ok=True)
        fig.savefig(out_path, dpi=150)
        logger.info("Figure saved to %s", out_path)
        plt.close(fig)
    else:
        plt.show()
