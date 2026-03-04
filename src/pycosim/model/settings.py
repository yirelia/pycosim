"""Runtime settings for simulation execution."""

from __future__ import annotations

from dataclasses import dataclass, field


@dataclass
class CoInitSettings:
    residuals_tolerance: float = 1e-5
    max_iterations: int = 100


@dataclass
class StepperSettings:
    method: str = "constant"
    step_size: float = 0.1
    min_step: float = 0.01
    max_step: float = 1.0
    safety_factor: float = 0.9
    order: int = 3


@dataclass
class ZMQSettings:
    coordinator_address: str = "tcp://localhost:5555"


@dataclass
class ExportConfig:
    folder: str = "./output"
    prefix: str = "results"
    variables: list[str] = field(default_factory=lambda: ["all"])


@dataclass
class RuntimeSettings:
    start_time: float = 0.0
    stop_time: float = 10.0
    co_initialization: CoInitSettings = field(default_factory=CoInitSettings)
    stepper: StepperSettings = field(default_factory=StepperSettings)
    zmq: ZMQSettings = field(default_factory=ZMQSettings)
