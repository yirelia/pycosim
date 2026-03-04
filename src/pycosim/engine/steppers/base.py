"""Stepper ABC - time step size strategy."""

from __future__ import annotations

from abc import ABC, abstractmethod

from pycosim.model.settings import StepperSettings


class Stepper(ABC):
    """Abstract base for step size strategies."""

    def __init__(self, settings: StepperSettings):
        self.settings = settings
        self.step_size = settings.step_size

    @abstractmethod
    def next_step_size(self, current_time: float, errors: list[float] | None = None) -> float:
        """Compute the next step size."""

    @abstractmethod
    def should_rollback(self, errors: list[float]) -> bool:
        """Determine if the current step should be rolled back."""
