"""Iterator - orchestrates node stepping with optional parallelism."""

from __future__ import annotations

import logging
from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from pycosim.model.arrow import Arrow
    from pycosim.model.graph_node import GraphNode

logger = logging.getLogger(__name__)


class Iterator:
    """BSP-style iterator: parallel step → barrier → sequential exchange."""

    def __init__(self, nodes: list[GraphNode], arrows: list[Arrow],
                 parallel: bool = False, max_workers: int | None = None):
        self.nodes = nodes
        self.arrows = arrows
        self.parallel = parallel
        self.max_workers = max_workers

    def iterate(self, current_time: float, dt: float) -> bool:
        """Execute one full iteration: step all nodes, then exchange variables."""
        if self.parallel and len(self.nodes) > 1:
            success = self._step_parallel(current_time, dt)
        else:
            success = self._step_sequential(current_time, dt)

        if not success:
            return False

        self._exchange_variables()
        return True

    def save_states(self) -> None:
        for node in self.nodes:
            node.save_state()

    def restore_states(self) -> None:
        for node in self.nodes:
            node.restore_state()

    def _step_sequential(self, current_time: float, dt: float) -> bool:
        for node in self.nodes:
            if not node.step(current_time, dt):
                logger.error("Node '%s' step failed at t=%f", node.node_id, current_time)
                return False
        return True

    def _step_parallel(self, current_time: float, dt: float) -> bool:
        with ThreadPoolExecutor(max_workers=self.max_workers) as executor:
            futures = {
                executor.submit(node.step, current_time, dt): node
                for node in self.nodes
            }
            for future in as_completed(futures):
                node = futures[future]
                try:
                    if not future.result():
                        logger.error("Node '%s' step failed at t=%f",
                                     node.node_id, current_time)
                        return False
                except Exception as e:
                    logger.error("Node '%s' raised: %s", node.node_id, e)
                    return False
        return True

    def _exchange_variables(self) -> None:
        """Transfer values along all arrows (sequential to avoid races)."""
        for arrow in self.arrows:
            arrow.transfer()
