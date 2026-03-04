"""GraphExecutor - 4-phase simulation lifecycle orchestrator."""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING

from pycosim.engine.co_initializer import CoInitializer
from pycosim.engine.exporter import Exporter
from pycosim.engine.iterator import Iterator
from pycosim.engine.steppers.adams_bashforth import AdamsBashforthStepper
from pycosim.engine.steppers.base import Stepper
from pycosim.engine.steppers.constant import ConstantStepper
from pycosim.engine.steppers.euler import EulerStepper
from pycosim.exceptions import SimulationError

if TYPE_CHECKING:
    from pycosim.model.graph import Graph

logger = logging.getLogger(__name__)

_STEPPER_MAP = {
    "constant": ConstantStepper,
    "euler": EulerStepper,
    "adams_bashforth": AdamsBashforthStepper,
}


class GraphExecutor:
    """Orchestrates the 4-phase simulation lifecycle."""

    def __init__(self, graph: Graph, parallel: bool = False,
                 max_workers: int | None = None):
        self.graph = graph
        self.parallel = parallel
        self.max_workers = max_workers

    def execute(self) -> None:
        """Run the full simulation: load → init → simulate → terminate."""
        settings = self.graph.settings
        logger.info("=== PyCosim Simulation ===")
        logger.info("Time: [%f, %f], Stepper: %s",
                     settings.start_time, settings.stop_time,
                     settings.stepper.method)

        try:
            self._phase_load()
            self._phase_init()
            self._phase_simulate()
        finally:
            self._phase_terminate()

        logger.info("=== Simulation Complete ===")

    def _phase_load(self) -> None:
        logger.info("--- Phase 1: LOAD ---")
        for node in self.graph.nodes:
            node.load()

    def _phase_init(self) -> None:
        logger.info("--- Phase 2: INIT ---")
        settings = self.graph.settings
        for node in self.graph.nodes:
            node.init(settings.start_time, settings.stop_time)

        # Initial variable exchange
        for arrow in self.graph.arrows:
            arrow.transfer()

        # Co-initialization (algebraic loop solving)
        co_init = CoInitializer(self.graph)
        co_init.solve()

    def _phase_simulate(self) -> None:
        logger.info("--- Phase 3: SIMULATE ---")
        settings = self.graph.settings
        stepper = self._create_stepper()
        iterator = Iterator(
            self.graph.nodes, self.graph.arrows,
            parallel=self.parallel, max_workers=self.max_workers,
        )
        exporter = Exporter(self.graph)
        exporter.open()

        try:
            current_time = settings.start_time
            exporter.record(current_time)

            while current_time < settings.stop_time - 1e-12:
                dt = stepper.next_step_size(current_time)
                # Clamp to stop_time
                if current_time + dt > settings.stop_time:
                    dt = settings.stop_time - current_time

                if dt <= 0:
                    break

                # Save state for possible rollback
                if not isinstance(stepper, ConstantStepper):
                    iterator.save_states()

                success = iterator.iterate(current_time, dt)

                if not success:
                    if not isinstance(stepper, ConstantStepper):
                        iterator.restore_states()
                        # Halve step size and retry
                        stepper.step_size = max(dt / 2, settings.stepper.min_step)
                        continue
                    else:
                        raise SimulationError(
                            f"Step failed at t={current_time} with dt={dt}")

                current_time += dt
                exporter.record(current_time)

                if logger.isEnabledFor(logging.DEBUG):
                    logger.debug("t=%.6f, dt=%.6f", current_time, dt)
        finally:
            iterator.log_summary()
            exporter.close()

    def _phase_terminate(self) -> None:
        logger.info("--- Phase 4: TERMINATE ---")
        for node in self.graph.nodes:
            try:
                node.terminate()
            except Exception as e:
                logger.warning("Error terminating '%s': %s", node.node_id, e)

    def _create_stepper(self) -> Stepper:
        method = self.graph.settings.stepper.method
        cls = _STEPPER_MAP.get(method)
        if cls is None:
            raise SimulationError(f"Unknown stepper method: {method}")
        return cls(self.graph.settings.stepper)
