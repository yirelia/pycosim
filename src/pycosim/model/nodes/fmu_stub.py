"""FMUStub - distributed proxy node communicating via ZMQ REQ."""

from __future__ import annotations

import logging
from typing import Any

import zmq

from pycosim.data_type import DataType
from pycosim.distributed.protocol import Command, Request, Response
from pycosim.exceptions import DistributedError
from pycosim.model.fmu_proxy import FMUProxy
from pycosim.model.graph_node import GraphNode
from pycosim.model.variable import FMUInput, FMUOutput, Input, Output

logger = logging.getLogger(__name__)


class FMUStub(GraphNode, FMUProxy):
    """Remote FMU proxy - sends commands to a FMUSoul worker via ZMQ."""

    def __init__(self, node_id: str, address: str,
                 inputs: list[Input] | None = None,
                 outputs: list[Output] | None = None):
        super().__init__(node_id, inputs, outputs)
        self.address = address
        self._context: zmq.Context | None = None
        self._socket: zmq.Socket | None = None

    def _send(self, command: Command, **params) -> Response:
        req = Request(command=command, params=params)
        self._socket.send(req.encode())
        resp = Response.decode(self._socket.recv())
        if not resp.success:
            raise DistributedError(
                f"Remote error on '{self.node_id}': {resp.error}")
        return resp

    # --- GraphNode lifecycle ---

    def load(self) -> None:
        self._context = zmq.Context()
        self._socket = self._context.socket(zmq.REQ)
        self._socket.connect(self.address)
        self._send(Command.LOAD)

    def init(self, start_time: float, stop_time: float) -> None:
        self._send(Command.INIT, start_time=start_time, stop_time=stop_time)
        self.pull_outputs()

    def step(self, current_time: float, dt: float) -> bool:
        self.push_inputs()
        resp = self._send(Command.STEP, current_time=current_time, dt=dt)
        self.pull_outputs()
        return resp.data

    def terminate(self) -> None:
        try:
            self._send(Command.TERMINATE)
        except Exception:
            pass
        if self._socket:
            self._socket.close()
        if self._context:
            self._context.term()

    def pull_outputs(self) -> None:
        for out in self.outputs:
            if isinstance(out, FMUOutput):
                resp = self._send(Command.GET, vr=out.vr,
                                  data_type=out.data_type.value)
                out.value = resp.data

    def push_inputs(self) -> None:
        for inp in self.inputs:
            if isinstance(inp, FMUInput):
                self._send(Command.SET, vr=inp.vr, value=inp.value,
                           data_type=inp.data_type.value)

    # --- FMUProxy ---

    def instantiate(self) -> None:
        pass  # Handled by remote soul

    def push(self, vr: int, value: Any, data_type: DataType) -> None:
        self._send(Command.SET, vr=vr, value=value,
                   data_type=data_type.value)

    def pull(self, vr: int, data_type: DataType) -> Any:
        resp = self._send(Command.GET, vr=vr, data_type=data_type.value)
        return resp.data

    def save_state(self) -> None:
        self._send(Command.SAVE_STATE)

    def restore_state(self) -> None:
        self._send(Command.RESTORE_STATE)
