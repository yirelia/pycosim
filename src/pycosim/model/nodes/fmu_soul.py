"""FMUSoul - distributed worker wrapping FMULocal with ZMQ REP."""

from __future__ import annotations

import logging

import zmq

from pycosim.data_type import DataType
from pycosim.distributed.protocol import Command, Request, Response
from pycosim.model.nodes.fmu_local import FMULocal

logger = logging.getLogger(__name__)


class FMUSoul:
    """Worker-side FMU wrapper that listens for commands via ZMQ REP."""

    def __init__(self, fmu_local: FMULocal, bind_address: str):
        self.fmu = fmu_local
        self.bind_address = bind_address
        self._context: zmq.Context | None = None
        self._socket: zmq.Socket | None = None
        self._running = False

    def start(self) -> None:
        self._context = zmq.Context()
        self._socket = self._context.socket(zmq.REP)
        self._socket.bind(self.bind_address)
        self._running = True
        logger.info("FMUSoul '%s' listening on %s",
                     self.fmu.node_id, self.bind_address)

    def serve_forever(self) -> None:
        """Main loop: receive requests, dispatch, send responses."""
        self.start()
        try:
            while self._running:
                data = self._socket.recv()
                req = Request.decode(data)
                resp = self._dispatch(req)
                self._socket.send(resp.encode())
        finally:
            self.stop()

    def stop(self) -> None:
        self._running = False
        if self._socket:
            self._socket.close()
        if self._context:
            self._context.term()

    def _dispatch(self, req: Request) -> Response:
        try:
            cmd = req.command
            p = req.params

            if cmd == Command.LOAD:
                self.fmu.load()
                return Response(success=True)

            elif cmd == Command.INIT:
                self.fmu.init(p["start_time"], p["stop_time"])
                return Response(success=True)

            elif cmd == Command.STEP:
                result = self.fmu.step(p["current_time"], p["dt"])
                return Response(success=True, data=result)

            elif cmd == Command.GET:
                value = self.fmu.pull(p["vr"], DataType(p["data_type"]))
                return Response(success=True, data=value)

            elif cmd == Command.SET:
                self.fmu.push(p["vr"], p["value"], DataType(p["data_type"]))
                return Response(success=True)

            elif cmd == Command.SAVE_STATE:
                self.fmu.save_state()
                return Response(success=True)

            elif cmd == Command.RESTORE_STATE:
                self.fmu.restore_state()
                return Response(success=True)

            elif cmd == Command.TERMINATE:
                self.fmu.terminate()
                self._running = False
                return Response(success=True)

            else:
                return Response(success=False, error=f"Unknown command: {cmd}")

        except Exception as e:
            logger.exception("Error handling %s", req.command)
            return Response(success=False, error=str(e))
