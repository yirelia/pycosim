"""ConstantStepper - fixed step size."""

from __future__ import annotations

from pycosim.engine.steppers.base import Stepper
from pycosim.model.settings import StepperSettings


class ConstantStepper(Stepper):
    """Fixed step size - no adaptation."""

    def __init__(self, settings: StepperSettings):
        super().__init__(settings)

    def next_step_size(self, current_time: float, errors: list[float] | None = None) -> float:
        return self.step_size

    def should_rollback(self, errors: list[float]) -> bool:
        return False
