"""PyCosim exception hierarchy."""


class PyCosimError(Exception):
    """Base exception for all PyCosim errors."""


class ConfigError(PyCosimError):
    """Invalid simulation configuration."""


class SimulationError(PyCosimError):
    """Error during simulation execution."""


class FMUError(PyCosimError):
    """Error in FMU operations (load/init/step)."""


class CoInitError(PyCosimError):
    """Co-initialization (algebraic loop) solver failed."""


class StepError(SimulationError):
    """Step execution failed (divergence, NaN, etc.)."""


class DistributedError(PyCosimError):
    """Distributed communication error."""
