"""FMULocal - local FMU execution via fmpy."""

from __future__ import annotations

import logging
from typing import Any

import fmpy
from fmpy import read_model_description
from fmpy.fmi2 import FMU2Slave

from pycosim.data_type import DataType
from pycosim.exceptions import FMUError
from pycosim.model.fmu_proxy import FMUProxy
from pycosim.model.graph_node import GraphNode
from pycosim.model.variable import FMUInput, FMUOutput, Input, Output

logger = logging.getLogger(__name__)


class FMULocal(GraphNode, FMUProxy):
    """Graph node that wraps a local FMU via fmpy."""

    def __init__(self, node_id: str, fmu_path: str,
                 inputs: list[Input] | None = None,
                 outputs: list[Output] | None = None,
                 before_init_values: dict[str, Any] | None = None):
        super().__init__(node_id, inputs, outputs)
        self.fmu_path = fmu_path
        self.before_init_values = before_init_values or {}
        self._model_description = None
        self._unzip_dir: str | None = None
        self._fmu: FMU2Slave | None = None
        self._saved_state = None
        self._vr_map: dict[str, int] = {}  # name -> value_reference

    # --- GraphNode lifecycle ---

    def load(self) -> None:
        try:
            self._unzip_dir = fmpy.extract(self.fmu_path)
            self._model_description = read_model_description(self.fmu_path)
            for var in self._model_description.modelVariables:
                self._vr_map[var.name] = var.valueReference
            self._resolve_value_references()
            logger.info("Loaded FMU '%s' from %s", self.node_id, self.fmu_path)
        except Exception as e:
            raise FMUError(f"Failed to load FMU '{self.node_id}': {e}") from e

    def init(self, start_time: float, stop_time: float) -> None:
        self.instantiate()
        self._apply_before_init_values()
        self._init(start_time, stop_time)
        self.pull_outputs()

    def step(self, current_time: float, dt: float) -> bool:
        return self._step(current_time, dt)

    def terminate(self) -> None:
        self._terminate()

    def pull_outputs(self) -> None:
        for out in self.outputs:
            if isinstance(out, FMUOutput):
                out.pull(self)

    def push_inputs(self) -> None:
        for inp in self.inputs:
            if isinstance(inp, FMUInput):
                inp.push(self, inp.value)

    # --- FMUProxy implementation ---

    def instantiate(self) -> None:
        try:
            fmi_type = self._detect_fmi_type()
            if fmi_type == "fmi2":
                self._fmu = FMU2Slave(
                    guid=self._model_description.guid,
                    unzipDirectory=self._unzip_dir,
                    modelIdentifier=self._model_description.coSimulation.modelIdentifier,
                )
                self._fmu.instantiate()
            else:
                raise FMUError(f"Unsupported FMI type: {fmi_type}")
        except FMUError:
            raise
        except Exception as e:
            raise FMUError(f"Failed to instantiate FMU '{self.node_id}': {e}") from e

    def _init(self, start_time: float, stop_time: float) -> None:
        self._fmu.setupExperiment(startTime=start_time, stopTime=stop_time)
        self._fmu.enterInitializationMode()
        self._fmu.exitInitializationMode()

    def _step(self, current_time: float, dt: float) -> bool:
        try:
            self.push_inputs()
            status = self._fmu.doStep(
                currentCommunicationPoint=current_time,
                communicationStepSize=dt,
            )
            logger.debug("FMU status is '%s'", status)
        except Exception as e:
            logger.exception("FMU '%s' step raised exception at t=%f dt=%f: %s",
                             self.node_id, current_time, dt, e)
            return False

        try:
            self.pull_outputs()
        except Exception as e:
            # Pulling outputs failed — log and treat as step failure
            logger.exception("FMU '%s' failed to pull outputs at t=%f dt=%f: %s",
                             self.node_id, current_time, dt, e)
            return False

        # Robustly interpret doStep return values:
        # - fmpy.FMU2Slave.doStep commonly returns None on success
        # - Some FMUs or wrappers may return bool or int

        if status is None:
            success = True
        elif isinstance(status, bool):
            success = status
        elif isinstance(status, int):
            success = (status == 0)
        else:
            logger.debug("FMU '%s' doStep returned unexpected status type %s: %r",
                         self.node_id, type(status).__name__, status)
            success = True

        if not success:
            logger.error("FMU '%s' doStep returned non-success status %r at t=%f dt=%f",
                         self.node_id, status, current_time, dt)

        return success

    def _terminate(self) -> None:
        if self._fmu is not None:
            try:
                self._fmu.terminate()
                self._fmu.freeInstance()
            except Exception:
                pass
            self._fmu = None
        if self._unzip_dir is not None:
            try:
                fmpy.util.cleanup(self._unzip_dir)
            except Exception:
                pass

    def push(self, vr: int, value: Any, data_type: DataType) -> None:
        if data_type == DataType.REAL:
            self._fmu.setReal([vr], [float(value)])
        elif data_type == DataType.INTEGER:
            self._fmu.setInteger([vr], [int(value)])
        elif data_type == DataType.BOOLEAN:
            self._fmu.setBoolean([vr], [bool(value)])
        elif data_type == DataType.STRING:
            self._fmu.setString([vr], [str(value)])

    def pull(self, vr: int, data_type: DataType) -> Any:
        if data_type == DataType.REAL:
            return self._fmu.getReal([vr])[0]
        elif data_type == DataType.INTEGER:
            return self._fmu.getInteger([vr])[0]
        elif data_type == DataType.BOOLEAN:
            return self._fmu.getBoolean([vr])[0]
        elif data_type == DataType.STRING:
            return self._fmu.getString([vr])[0]

    def save_state(self) -> None:
        try:
            self._saved_state = self._fmu.getFMUstate()
        except Exception:
            logger.warning("FMU '%s' does not support state save", self.node_id)

    def restore_state(self) -> None:
        if self._saved_state is not None:
            self._fmu.setFMUstate(self._saved_state)

    # --- Internal helpers ---

    def _detect_fmi_type(self) -> str:
        if self._model_description.coSimulation is not None:
            return "fmi2"
        raise FMUError(f"FMU '{self.node_id}' has no CoSimulation interface")

    def _resolve_value_references(self) -> None:
        """Map FMUInput/FMUOutput variable references from model description."""
        for inp in self.inputs:
            if isinstance(inp, FMUInput) and inp.vr == 0 and inp.id in self._vr_map:
                inp.vr = self._vr_map[inp.id]
        for out in self.outputs:
            if isinstance(out, FMUOutput) and out.vr == 0 and out.id in self._vr_map:
                out.vr = self._vr_map[out.id]

    def _apply_before_init_values(self) -> None:
        for name, value in self.before_init_values.items():
            if name in self._vr_map:
                vr = self._vr_map[name]
                self.push(vr, value, DataType.REAL)
