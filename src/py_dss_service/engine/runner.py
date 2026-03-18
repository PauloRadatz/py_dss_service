"""
DSS execution runner.

Uses py-dss-toolkit to run OpenDSS simulations and extract results.
"""

import logging
import tempfile
from pathlib import Path
from typing import Any, Optional

from py_dss_interface import DSS
from py_dss_toolkit import dss_tools

from py_dss_service.common.errors import JobExecutionError
from py_dss_service.common.time import utc_now_iso
from py_dss_service.engine.validation import get_script_lines
from py_dss_service.schemas.job_spec import Action
from py_dss_service.schemas.results import JobResult


class DSSRunner:
    """
    Runner for executing DSS scripts and extracting results using py-dss-toolkit.

    Stage 1: Executes snapshot power flow and extracts circuit summary.
    """

    def __init__(self, logger: Optional[logging.Logger] = None, data_path: Optional[Path] = None):
        """
        Initialize the DSS runner.

        Args:
            logger: Optional logger for execution messages
            data_path: Optional path for DSS data directory (prevents CWD changes)
        """
        self.logger = logger or logging.getLogger(__name__)
        self._dss: Optional[DSS] = None
        self._dss_tools_connected = False
        # Use provided data_path or create a temp directory
        self._data_path = data_path or Path(tempfile.gettempdir()) / "pydss_temp"
        self._data_path.mkdir(parents=True, exist_ok=True)

    def _get_dss(self) -> DSS:
        """Get or create DSS instance with proper data path set."""
        if self._dss is None:
            self._dss = DSS()
            # Set the data path to prevent OpenDSS from changing CWD
            self._dss.dssinterface.datapath = str(self._data_path)
        return self._dss

    def _connect_dss_tools(self, dss: DSS) -> None:
        """Connect DSS instance to dss_tools (only once per instance)."""
        if not self._dss_tools_connected:
            dss_tools.update_dss(dss)
            self._dss_tools_connected = True
            self.logger.debug("Connected DSS instance to dss_tools")

    def _apply_action(self, dss: DSS, action: Action, job_id: str, action_num: int) -> None:
        """
        Apply a single action to the DSS instance.

        Args:
            dss: The DSS instance
            action: The action to apply
            job_id: Job identifier for logging
            action_num: Action number (for logging)

        Raises:
            JobExecutionError: If action type is unknown or execution fails
        """
        try:
            action_type = action.type

            if action_type == "dss_command":
                command = action.command
                dss.text(command)
                self.logger.info(f"[{job_id}] Action {action_num}: DSS command: {command}")

            elif action_type == "add_line_in_vsource":
                add_meter = action.add_meter
                add_monitors = action.add_monitors
                dss_tools.model.add_line_in_vsource(
                    add_meter=add_meter,
                    add_monitors=add_monitors
                )
                self.logger.info(
                    f"[{job_id}] Action {action_num}: [toolkit] Added line in vsource "
                    f"(meter={add_meter}, monitors={add_monitors})"
                )

            else:
                raise JobExecutionError(f"Unknown action type: {action_type}")

        except Exception as e:
            self.logger.error(f"[{job_id}] Error applying action {action_num}: {e}")
            raise JobExecutionError(f"Failed to apply action {action_num} ({action.type}): {e}") from e

    def execute(
        self,
        job_id: str,
        dss_script: str,
        start_time: float,
        actions: list[Action] = None,
    ) -> JobResult:
        """
        Execute a DSS script and return results using py-dss-toolkit.

        Args:
            job_id: The job identifier
            dss_script: The DSS script to execute
            start_time: Start timestamp for execution time calculation
            actions: List of actions to apply after script but before solving

        Returns:
            JobResult with circuit summary and convergence info

        Raises:
            JobExecutionError: If execution fails
        """
        import time

        dss = self._get_dss()
        self._connect_dss_tools(dss)

        if actions is None:
            actions = []

        try:
            # Clear any previous circuit
            self.logger.info(f"[{job_id}] Starting DSS execution")
            dss.text("clear")

            # Execute script lines
            lines = get_script_lines(dss_script)
            self.logger.info(f"[{job_id}] Executing {len(lines)} script lines")

            for i, line in enumerate(lines):
                self.logger.debug(f"[{job_id}] Line {i+1}: {line}")
                dss.text(line)

            # Process actions in order
            if actions:
                self.logger.info(f"[{job_id}] Processing {len(actions)} actions...")
                for i, action in enumerate(actions):
                    self._apply_action(dss, action, job_id, i + 1)

            # Run power flow solution using py-dss-toolkit
            self.logger.info(f"[{job_id}] Running solve_snapshot via py-dss-toolkit")
            dss_tools.simulation.solve_snapshot(max_control_iter=20)

            # Check convergence
            converged = self._check_convergence(dss)
            self.logger.info(f"[{job_id}] Converged: {converged}")

            # Extract ALL results from py-dss-toolkit (run once, save all)
            self.logger.info(f"[{job_id}] Extracting all available results...")
            
            circuit_summary = self._extract_circuit_summary()
            if circuit_summary:
                self.logger.info(f"[{job_id}] Extracted circuit summary ({len(circuit_summary)} quantities)")
            
            voltages_ln = self._extract_voltages_ln()
            if voltages_ln:
                self.logger.info(f"[{job_id}] Extracted line-neutral voltages")
            
            voltages_ll = self._extract_voltages_ll()
            if voltages_ll:
                self.logger.info(f"[{job_id}] Extracted line-line voltages")
            
            currents = self._extract_currents()
            if currents:
                self.logger.info(f"[{job_id}] Extracted currents")
            
            powers = self._extract_powers()
            if powers:
                self.logger.info(f"[{job_id}] Extracted powers")
            
            loading_percent = self._extract_loading_percent()
            if loading_percent:
                self.logger.info(f"[{job_id}] Extracted loading percentages")
            
            violations = self._extract_violations()
            if violations:
                self.logger.info(f"[{job_id}] Extracted violations")

            execution_time = time.time() - start_time

            return JobResult(
                job_id=job_id,
                converged=converged,
                circuit_summary=circuit_summary,
                voltages_ln=voltages_ln,
                completed_at=utc_now_iso(),
                execution_time_seconds=round(execution_time, 3),
                log_file=f"logs/{job_id}.log",
            )

        except Exception as e:
            self.logger.error(f"[{job_id}] Execution failed: {e}")
            raise JobExecutionError(f"DSS execution failed: {e}") from e

    def solve_snapshot(self, job_id: str = "session") -> JobResult:
        """
        Run snapshot power flow on already-loaded circuit and extract results.

        This is used by sessions where the circuit is already loaded.
        Unlike execute(), this does NOT clear or load a script.

        Args:
            job_id: Job/session identifier for logging

        Returns:
            JobResult with simulation results
        """
        import time

        start_time = time.time()
        dss = self._get_dss()
        self._connect_dss_tools(dss)

        try:
            # Run power flow solution using py-dss-toolkit
            self.logger.info(f"[{job_id}] Running solve_snapshot via py-dss-toolkit")
            dss_tools.simulation.solve_snapshot(max_control_iter=20)

            # Check convergence
            converged = self._check_convergence(dss)
            self.logger.info(f"[{job_id}] Converged: {converged}")

            # Extract all results
            circuit_summary = self._extract_circuit_summary()
            voltages_ln = self._extract_voltages_ln()

            execution_time = time.time() - start_time

            return JobResult(
                job_id=job_id,
                simulation_type="snapshot",
                converged=converged,
                circuit_summary=circuit_summary,
                voltages_ln=voltages_ln,
                completed_at=utc_now_iso(),
                execution_time_seconds=round(execution_time, 3),
            )

        except Exception as e:
            self.logger.error(f"[{job_id}] Solve failed: {e}")
            raise JobExecutionError(f"Solve failed: {e}") from e

    def _check_convergence(self, dss: DSS) -> bool:
        """
        Check if the power flow solution converged.

        Best-effort: tries to read solution convergence flag.
        """
        return bool(dss.solution.converged)

    def _extract_circuit_summary(self) -> Optional[dict[str, Any]]:
        """Extract circuit summary as column-oriented records.

        Returns dict like ``{"P feeder (kW)": [...], "Q feeder (kvar)": [...], ...}``.
        """
        try:
            records = dss_tools.results._summary_records
            return records if records else None
        except Exception as e:
            self.logger.warning(f"Error extracting circuit summary: {e}")
        return None

    def _extract_voltages_ln(self) -> Optional[dict[str, Any]]:
        """Extract line-neutral voltages as record dicts.

        Returns ``{"magnitude": {bus: {node: val}}, "angle": {bus: {node: val}}}``.
        """
        try:
            mag = dss_tools.results._voltage_mag_ln_nodes_records
            ang = dss_tools.results._voltage_ang_ln_nodes_records
            if mag:
                return {"magnitude": mag, "angle": ang}
        except Exception as e:
            self.logger.warning(f"Error extracting line-neutral voltages: {e}")
        return None

    def get_model_summary(self) -> Optional[dict[str, Any]]:
        """Get circuit model summary as a plain dict (key → value)."""
        try:
            records = dss_tools.model._summary_model_records
            return records if records else None
        except Exception as e:
            self.logger.warning(f"Error getting model summary: {e}")
        return None

    def get_buses(self) -> Optional[dict[str, Any]]:
        """Get bus data as column-oriented records."""
        try:
            return dss_tools.model._buses_records
        except Exception as e:
            self.logger.warning(f"Error getting buses: {e}")
        return None

    def get_lines(self) -> Optional[dict[str, Any]]:
        """Get line data as column-oriented records."""
        try:
            return dss_tools.model._lines_records
        except Exception as e:
            self.logger.warning(f"Error getting lines: {e}")
        return None

    def get_loads(self) -> Optional[dict[str, Any]]:
        """Get load data as column-oriented records."""
        try:
            return dss_tools.model._loads_records
        except Exception as e:
            self.logger.warning(f"Error getting loads: {e}")
        return None

    def get_segments(self) -> Optional[dict[str, Any]]:
        """Get segment data as column-oriented records."""
        try:
            return dss_tools.model._segments_records
        except Exception as e:
            self.logger.warning(f"Error getting segments: {e}")
        return None

    @staticmethod
    def _record_count(records: Optional[dict[str, list]]) -> int:
        """Number of rows in column-oriented records."""
        if not records:
            return 0
        first_col = next(iter(records.values()), [])
        return len(first_col)

    def extract_model_snapshot(self, job_id: str) -> dict[str, Any]:
        """Extract complete model snapshot for saving with job results.

        Returns a dict suitable for the JobModelSnapshot schema.
        All model data is column-oriented records (straight from py-dss-toolkit).
        """
        dss = self._get_dss()
        circuit_name = dss.circuit.name if dss.circuit.name else "unknown"

        buses = self.get_buses()
        lines = self.get_lines()
        loads = self.get_loads()
        segments = self.get_segments()
        summary = self.get_model_summary()

        return {
            "job_id": job_id,
            "circuit_name": circuit_name,
            "num_buses": self._record_count(buses),
            "num_lines": self._record_count(lines),
            "num_loads": self._record_count(loads),
            "summary": summary,
            "buses": buses,
            "lines": lines,
            "loads": loads,
            "segments": segments,
        }

