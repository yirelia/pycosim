"""Distributed worker process - hosts an FMUSoul."""

from __future__ import annotations

import logging

from pycosim.model.nodes.fmu_local import FMULocal
from pycosim.model.nodes.fmu_soul import FMUSoul

logger = logging.getLogger(__name__)


class Worker:
    """Standalone worker process hosting an FMU via ZMQ."""

    def __init__(self, fmu_path: str, node_id: str,
                 coordinator_address: str = "tcp://localhost:5555"):
        self.fmu_path = fmu_path
        self.node_id = node_id
        self.coordinator_address = coordinator_address

    def run(self) -> None:
        logger.info("Starting worker for FMU '%s'", self.node_id)
        fmu_local = FMULocal(node_id=self.node_id, fmu_path=self.fmu_path)
        soul = FMUSoul(fmu_local, bind_address=self.coordinator_address)
        soul.serve_forever()
