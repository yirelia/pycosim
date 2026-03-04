"""EulerStepper - first-order adaptive step size."""

from __future__ import annotations

from pycosim.engine.steppers.base import Stepper
from pycosim.model.settings import StepperSettings


class EulerStepper(Stepper):
    """First-order error estimation with adaptive step size."""

    def __init__(self, settings: StepperSettings):
        super().__init__(settings)
        self._prev_outputs: dict[str, float] = {}
        self._prev_prev_outputs: dict[str, float] = {}

    def next_step_size(self, current_time: float, errors: list[float] | None = None) -> float:
        if errors is None or len(errors) == 0:
            return self.step_size

        max_error = max(abs(e) for e in errors) if errors else 0.0
        if max_error < 1e-15:
            new_dt = min(self.step_size * 2.0, self.settings.max_step)
        else:
            # First-order: dt_new = safety * dt * (tol / error)
            ratio = self.settings.stepper.step_size / max_error if hasattr(self.settings, 'stepper') else 1.0 / max_error
            new_dt = self.settings.safety_factor * self.step_size * min(ratio, 2.0)

        new_dt = max(self.settings.min_step, min(new_dt, self.settings.max_step))
        self.step_size = new_dt
        return new_dt

    def should_rollback(self, errors: list[float]) -> bool:
        if not errors:
            return False
        max_error = max(abs(e) for e in errors)
        # Rollback if error exceeds tolerance by factor of 10
        return max_error > self.settings.step_size * 10
