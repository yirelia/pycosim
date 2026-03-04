"""CoInitializer - algebraic loop detection and Newton-Raphson solver."""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING

import numpy as np

from pycosim.exceptions import CoInitError

if TYPE_CHECKING:
    from pycosim.model.arrow import Arrow
    from pycosim.model.graph import Graph
    from pycosim.model.graph_node import GraphNode

logger = logging.getLogger(__name__)


class CoInitializer:
    """Detects algebraic loops (SCCs) and solves them via Newton-Raphson."""

    def __init__(self, graph: Graph):
        self.graph = graph
        self.tolerance = graph.settings.co_initialization.residuals_tolerance
        self.max_iterations = graph.settings.co_initialization.max_iterations

    def solve(self) -> None:
        """Detect SCCs and solve algebraic loops."""
        sccs = self._find_sccs()
        loops = [scc for scc in sccs if len(scc) > 1]
        if not loops:
            logger.info("No algebraic loops detected")
            return

        logger.info("Found %d algebraic loop(s)", len(loops))
        for i, loop in enumerate(loops):
            node_ids = [n.node_id for n in loop]
            logger.info("  Loop %d: %s", i + 1, " → ".join(node_ids))
            self._solve_loop(loop)

    def _find_sccs(self) -> list[list[GraphNode]]:
        """Tarjan's SCC algorithm on the simulation graph."""
        nodes = self.graph.nodes
        node_map = {n.node_id: n for n in nodes}

        # Build adjacency from arrows
        adj: dict[str, list[str]] = {n.node_id: [] for n in nodes}
        for arrow in self.graph.arrows:
            from_node_id = self._find_owner(arrow.from_output, nodes)
            to_node_id = self._find_owner(arrow.to_input, nodes)
            if from_node_id and to_node_id:
                adj[from_node_id].append(to_node_id)

        # Tarjan's
        index_counter = [0]
        stack = []
        on_stack = set()
        indices: dict[str, int] = {}
        lowlinks: dict[str, int] = {}
        result: list[list[GraphNode]] = []

        def strongconnect(v: str):
            indices[v] = index_counter[0]
            lowlinks[v] = index_counter[0]
            index_counter[0] += 1
            stack.append(v)
            on_stack.add(v)

            for w in adj.get(v, []):
                if w not in indices:
                    strongconnect(w)
                    lowlinks[v] = min(lowlinks[v], lowlinks[w])
                elif w in on_stack:
                    lowlinks[v] = min(lowlinks[v], indices[w])

            if lowlinks[v] == indices[v]:
                scc = []
                while True:
                    w = stack.pop()
                    on_stack.discard(w)
                    scc.append(node_map[w])
                    if w == v:
                        break
                result.append(scc)

        for n in nodes:
            if n.node_id not in indices:
                strongconnect(n.node_id)

        return result

    def _solve_loop(self, loop_nodes: list[GraphNode]) -> None:
        """Newton-Raphson iteration to solve an algebraic loop."""
        # Collect arrows within the loop
        loop_ids = {n.node_id for n in loop_nodes}
        loop_arrows = []
        for arrow in self.graph.arrows:
            from_id = self._find_owner(arrow.from_output, loop_nodes)
            to_id = self._find_owner(arrow.to_input, loop_nodes)
            if from_id in loop_ids and to_id in loop_ids:
                loop_arrows.append(arrow)

        if not loop_arrows:
            return

        n = len(loop_arrows)
        for iteration in range(self.max_iterations):
            # Compute residuals: r_i = output_i - input_i (after transfer)
            residuals = np.zeros(n)
            for i, arrow in enumerate(loop_arrows):
                residuals[i] = arrow.from_output.value - arrow.to_input.value

            if np.max(np.abs(residuals)) < self.tolerance:
                logger.info("  Converged in %d iterations", iteration + 1)
                return

            # Build approximate Jacobian via finite differences
            jacobian = np.eye(n)
            delta = 1e-6
            for j, arrow in enumerate(loop_arrows):
                original = arrow.to_input.value
                arrow.to_input.value = original + delta

                # Re-evaluate affected nodes
                to_node_id = self._find_owner(arrow.to_input, loop_nodes)
                for node in loop_nodes:
                    if node.node_id == to_node_id:
                        node.push_inputs()
                        node.pull_outputs()

                for i, a in enumerate(loop_arrows):
                    perturbed_residual = a.from_output.value - a.to_input.value
                    jacobian[i, j] = (perturbed_residual - residuals[i]) / delta

                arrow.to_input.value = original

            # Restore node states
            for node in loop_nodes:
                node.push_inputs()
                node.pull_outputs()

            # Newton step: x_new = x - J^{-1} * r
            try:
                correction = np.linalg.solve(jacobian, residuals)
            except np.linalg.LinAlgError:
                raise CoInitError("Singular Jacobian in algebraic loop solver")

            for i, arrow in enumerate(loop_arrows):
                arrow.to_input.value -= correction[i]

            # Push corrected inputs
            for node in loop_nodes:
                node.push_inputs()
                node.pull_outputs()

        raise CoInitError(
            f"Newton-Raphson did not converge after {self.max_iterations} iterations"
        )

    @staticmethod
    def _find_owner(variable, nodes: list[GraphNode]) -> str | None:
        for node in nodes:
            for v in node.inputs + node.outputs:
                if v is variable:
                    return node.node_id
        return None
