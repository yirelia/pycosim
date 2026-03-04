"""Tests for Stepper hierarchy."""

from pycosim.engine.steppers.constant import ConstantStepper
from pycosim.engine.steppers.euler import EulerStepper
from pycosim.engine.steppers.adams_bashforth import AdamsBashforthStepper
from pycosim.model.settings import StepperSettings


def test_constant_stepper():
    settings = StepperSettings(step_size=0.1)
    stepper = ConstantStepper(settings)

    assert stepper.next_step_size(0.0) == 0.1
    assert stepper.next_step_size(0.5) == 0.1
    assert not stepper.should_rollback([0.01, 0.02])


def test_euler_stepper():
    settings = StepperSettings(
        method="euler", step_size=0.1, min_step=0.01,
        max_step=1.0, safety_factor=0.9,
    )
    stepper = EulerStepper(settings)

    dt = stepper.next_step_size(0.0)
    assert dt == 0.1  # No errors yet, keep step


def test_adams_bashforth_stepper():
    settings = StepperSettings(
        method="adams_bashforth", step_size=0.1, min_step=0.01,
        max_step=1.0, safety_factor=0.9, order=3,
    )
    stepper = AdamsBashforthStepper(settings)

    dt = stepper.next_step_size(0.0)
    assert dt == 0.1
    assert not stepper.should_rollback([])
