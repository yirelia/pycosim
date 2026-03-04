"""AdamsBashforthStepper - multi-step adaptive method."""

from __future__ import annotations

from collections import deque

from pycosim.engine.steppers.base import Stepper
from pycosim.model.settings import StepperSettings


class AdamsBashforthStepper(Stepper):
    """Adams-Bashforth multi-step method with adaptive step size."""

    def __init__(self, settings: StepperSettings):
        super().__init__(settings)
        self.order = settings.order
        self._error_history: deque[float] = deque(maxlen=self.order)

    def next_step_size(self, current_time: float, errors: list[float] | None = None) -> float:
        if errors is None or len(errors) == 0:
            return self.step_size

        max_error = max(abs(e) for e in errors)
        self._error_history.append(max_error)

        if max_error < 1e-15:
            new_dt = min(self.step_size * 1.5, self.settings.max_step)
        else:
            # Higher-order: dt_new = safety * dt * (tol / error)^(1/(order+1))
            tol = self.settings.step_size  # Use nominal step as tolerance proxy
            ratio = (tol / max_error) ** (1.0 / (self.order + 1))
            new_dt = self.settings.safety_factor * self.step_size * min(ratio, 2.0)

        new_dt = max(self.settings.min_step, min(new_dt, self.settings.max_step))
        self.step_size = new_dt
        return new_dt

    def should_rollback(self, errors: list[float]) -> bool:
        if not errors:
            return False
        max_error = max(abs(e) for e in errors)
        return max_error > self.settings.step_size * 10
