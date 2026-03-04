"""Iterator - orchestrates node stepping with optional parallelism."""

from __future__ import annotations

import logging
import os
import threading
import time as _time
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
        self._step_count = 0
        self._total_step_time = 0.0
        self._total_exchange_time = 0.0

        # Log execution mode at construction
        if self.parallel and len(self.nodes) > 1:
            effective_workers = max_workers or min(len(nodes), os.cpu_count() or 1)
            logger.info("Iterator: PARALLEL mode, %d nodes, max_workers=%d",
                        len(nodes), effective_workers)
        else:
            reason = "single node" if len(self.nodes) <= 1 else "not requested"
            logger.info("Iterator: SEQUENTIAL mode, %d nodes (%s)",
                        len(nodes), reason)

    def iterate(self, current_time: float, dt: float) -> bool:
        """Execute one full iteration: step all nodes, then exchange variables."""
        t0 = _time.perf_counter()

        if self.parallel and len(self.nodes) > 1:
            success = self._step_parallel(current_time, dt)
        else:
            success = self._step_sequential(current_time, dt)

        t1 = _time.perf_counter()

        if not success:
            return False

        self._exchange_variables()
        t2 = _time.perf_counter()

        self._step_count += 1
        step_ms = (t1 - t0) * 1000
        exch_ms = (t2 - t1) * 1000
        self._total_step_time += step_ms
        self._total_exchange_time += exch_ms

        if logger.isEnabledFor(logging.DEBUG):
            logger.debug("Step %d @ t=%.6f: nodes=%.2fms, exchange=%.2fms",
                         self._step_count, current_time, step_ms, exch_ms)

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
        thread_ids: dict[str, int] = {}

        def _run_node(node):
            tid = threading.current_thread().ident
            thread_ids[node.node_id] = tid
            return node.step(current_time, dt)

        with ThreadPoolExecutor(max_workers=self.max_workers) as executor:
            futures = {
                executor.submit(_run_node, node): node
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

        if logger.isEnabledFor(logging.DEBUG):
            unique_threads = set(thread_ids.values())
            mapping = ", ".join(f"{nid}->T{tid % 10000}"
                                for nid, tid in thread_ids.items())
            logger.debug("Parallel dispatch: %d unique threads [%s]",
                         len(unique_threads), mapping)

        return True

    def _exchange_variables(self) -> None:
        """Transfer values along all arrows (sequential to avoid races)."""
        for arrow in self.arrows:
            arrow.transfer()

    def log_summary(self) -> None:
        """Log performance summary. Call after simulation ends."""
        if self._step_count == 0:
            return
        mode = "PARALLEL" if (self.parallel and len(self.nodes) > 1) else "SEQUENTIAL"
        avg_step = self._total_step_time / self._step_count
        avg_exch = self._total_exchange_time / self._step_count
        logger.info(
            "Iterator summary: mode=%s, steps=%d, "
            "avg_step=%.2fms, avg_exchange=%.2fms, "
            "total=%.1fms",
            mode, self._step_count, avg_step, avg_exch,
            self._total_step_time + self._total_exchange_time,
        )
