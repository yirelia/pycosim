"""ZMQ protocol messages for distributed simulation."""

from __future__ import annotations

import json
from dataclasses import asdict, dataclass, field
from enum import Enum
from typing import Any


class Command(str, Enum):
    LOAD = "load"
    INIT = "init"
    STEP = "step"
    GET = "get"
    SET = "set"
    SAVE_STATE = "save_state"
    RESTORE_STATE = "restore_state"
    TERMINATE = "terminate"


@dataclass
class Request:
    command: Command
    params: dict[str, Any] = field(default_factory=dict)

    def encode(self) -> bytes:
        return json.dumps({"command": self.command.value, "params": self.params}).encode()

    @classmethod
    def decode(cls, data: bytes) -> Request:
        raw = json.loads(data)
        return cls(command=Command(raw["command"]), params=raw.get("params", {}))


@dataclass
class Response:
    success: bool
    data: Any = None
    error: str | None = None

    def encode(self) -> bytes:
        return json.dumps({"success": self.success, "data": self.data,
                           "error": self.error}).encode()

    @classmethod
    def decode(cls, data: bytes) -> Response:
        raw = json.loads(data)
        return cls(success=raw["success"], data=raw.get("data"),
                   error=raw.get("error"))
