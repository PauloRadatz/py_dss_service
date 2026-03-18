"""Tests for py_dss_service.engine.runner."""

import logging
from unittest.mock import MagicMock, patch, PropertyMock

import pytest

from py_dss_service.common.errors import JobExecutionError
from py_dss_service.engine.runner import DSSRunner
from py_dss_service.schemas.job_spec import DSSCommandAction


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture()
def runner():
    """Create a DSSRunner with mocked DSS and dss_tools."""
    with patch("py_dss_service.engine.runner.DSS") as MockDSS:
        mock_dss_instance = MagicMock()
        MockDSS.return_value = mock_dss_instance
        mock_dss_instance.solution.converged = True
        mock_dss_instance.circuit.name = "test_circuit"
        mock_dss_instance.dssinterface = MagicMock()

        r = DSSRunner(logger=logging.getLogger("test"))
        r._dss = mock_dss_instance
        r._dss_tools_connected = True
        yield r


# ---------------------------------------------------------------------------
# _record_count (static, no mocks needed)
# ---------------------------------------------------------------------------

class TestRecordCount:
    def test_none_returns_zero(self):
        assert DSSRunner._record_count(None) == 0

    def test_empty_dict_returns_zero(self):
        assert DSSRunner._record_count({}) == 0

    def test_column_oriented_records(self):
        records = {"col_a": [1, 2, 3], "col_b": [4, 5, 6]}
        assert DSSRunner._record_count(records) == 3

    def test_single_row(self):
        records = {"x": [10]}
        assert DSSRunner._record_count(records) == 1

    def test_empty_columns(self):
        records = {"x": [], "y": []}
        assert DSSRunner._record_count(records) == 0


# ---------------------------------------------------------------------------
# _extract_circuit_summary
# ---------------------------------------------------------------------------

class TestExtractCircuitSummary:
    @patch("py_dss_service.engine.runner.dss_tools")
    def test_returns_records_when_available(self, mock_dss_tools, runner):
        mock_dss_tools.results._summary_records = {
            "P feeder (kW)": [100.0],
            "Q feeder (kvar)": [50.0],
        }
        result = runner._extract_circuit_summary()
        assert result == {"P feeder (kW)": [100.0], "Q feeder (kvar)": [50.0]}

    @patch("py_dss_service.engine.runner.dss_tools")
    def test_returns_none_when_empty(self, mock_dss_tools, runner):
        mock_dss_tools.results._summary_records = {}
        assert runner._extract_circuit_summary() is None

    @patch("py_dss_service.engine.runner.dss_tools")
    def test_returns_none_when_none(self, mock_dss_tools, runner):
        mock_dss_tools.results._summary_records = None
        assert runner._extract_circuit_summary() is None

    @patch("py_dss_service.engine.runner.dss_tools")
    def test_returns_none_on_exception(self, mock_dss_tools, runner):
        type(mock_dss_tools.results)._summary_records = PropertyMock(
            side_effect=RuntimeError("DSS error")
        )
        assert runner._extract_circuit_summary() is None


# ---------------------------------------------------------------------------
# _extract_voltages_ln
# ---------------------------------------------------------------------------

class TestExtractVoltagesLn:
    @patch("py_dss_service.engine.runner.dss_tools")
    def test_returns_mag_and_angle(self, mock_dss_tools, runner):
        mag = {"bus1": {"1": 1.01, "2": 1.00}}
        ang = {"bus1": {"1": 0.0, "2": -120.0}}
        mock_dss_tools.results._voltage_mag_ln_nodes_records = mag
        mock_dss_tools.results._voltage_ang_ln_nodes_records = ang

        result = runner._extract_voltages_ln()
        assert result == {"magnitude": mag, "angle": ang}

    @patch("py_dss_service.engine.runner.dss_tools")
    def test_returns_none_when_mag_empty(self, mock_dss_tools, runner):
        mock_dss_tools.results._voltage_mag_ln_nodes_records = {}
        mock_dss_tools.results._voltage_ang_ln_nodes_records = {}
        assert runner._extract_voltages_ln() is None

    @patch("py_dss_service.engine.runner.dss_tools")
    def test_returns_none_when_mag_none(self, mock_dss_tools, runner):
        mock_dss_tools.results._voltage_mag_ln_nodes_records = None
        mock_dss_tools.results._voltage_ang_ln_nodes_records = None
        assert runner._extract_voltages_ln() is None

    @patch("py_dss_service.engine.runner.dss_tools")
    def test_returns_none_on_exception(self, mock_dss_tools, runner):
        type(mock_dss_tools.results)._voltage_mag_ln_nodes_records = PropertyMock(
            side_effect=RuntimeError("DSS error")
        )
        assert runner._extract_voltages_ln() is None


# ---------------------------------------------------------------------------
# get_buses / get_lines / get_loads / get_segments
# ---------------------------------------------------------------------------

class TestModelGetters:
    @pytest.mark.parametrize(
        "method_name, record_attr",
        [
            ("get_buses", "_buses_records"),
            ("get_lines", "_lines_records"),
            ("get_loads", "_loads_records"),
            ("get_segments", "_segments_records"),
        ],
    )
    @patch("py_dss_service.engine.runner.dss_tools")
    def test_returns_records_passthrough(self, mock_dss_tools, runner, method_name, record_attr):
        data = {"name": ["a", "b"], "value": [1, 2]}
        setattr(mock_dss_tools.model, record_attr, data)
        result = getattr(runner, method_name)()
        assert result == data

    @pytest.mark.parametrize(
        "method_name, record_attr",
        [
            ("get_buses", "_buses_records"),
            ("get_lines", "_lines_records"),
            ("get_loads", "_loads_records"),
            ("get_segments", "_segments_records"),
        ],
    )
    @patch("py_dss_service.engine.runner.dss_tools")
    def test_returns_none_on_exception(self, mock_dss_tools, runner, method_name, record_attr):
        type(mock_dss_tools.model).__dict__  # ensure model exists
        prop = PropertyMock(side_effect=RuntimeError("DSS error"))
        setattr(type(mock_dss_tools.model), record_attr, prop)
        result = getattr(runner, method_name)()
        assert result is None


# ---------------------------------------------------------------------------
# get_model_summary
# ---------------------------------------------------------------------------

class TestGetModelSummary:
    @patch("py_dss_service.engine.runner.dss_tools")
    def test_returns_dict_when_available(self, mock_dss_tools, runner):
        summary = {"total_buses": 10, "total_lines": 5}
        mock_dss_tools.model._summary_model_records = summary
        assert runner.get_model_summary() == summary

    @patch("py_dss_service.engine.runner.dss_tools")
    def test_returns_none_when_empty(self, mock_dss_tools, runner):
        mock_dss_tools.model._summary_model_records = {}
        assert runner.get_model_summary() is None

    @patch("py_dss_service.engine.runner.dss_tools")
    def test_returns_none_when_none(self, mock_dss_tools, runner):
        mock_dss_tools.model._summary_model_records = None
        assert runner.get_model_summary() is None

    @patch("py_dss_service.engine.runner.dss_tools")
    def test_returns_none_on_exception(self, mock_dss_tools, runner):
        type(mock_dss_tools.model)._summary_model_records = PropertyMock(
            side_effect=RuntimeError("DSS error")
        )
        assert runner.get_model_summary() is None


# ---------------------------------------------------------------------------
# extract_model_snapshot
# ---------------------------------------------------------------------------

class TestExtractModelSnapshot:
    @patch("py_dss_service.engine.runner.dss_tools")
    def test_correct_counts_from_records(self, mock_dss_tools, runner):
        mock_dss_tools.model._buses_records = {"name": ["b1", "b2", "b3"]}
        mock_dss_tools.model._lines_records = {"name": ["l1", "l2"]}
        mock_dss_tools.model._loads_records = {"name": ["ld1"]}
        mock_dss_tools.model._segments_records = {"name": ["s1", "s2"]}
        mock_dss_tools.model._summary_model_records = {"total": 10}

        result = runner.extract_model_snapshot("job-1")

        assert result["job_id"] == "job-1"
        assert result["circuit_name"] == "test_circuit"
        assert result["num_buses"] == 3
        assert result["num_lines"] == 2
        assert result["num_loads"] == 1
        assert result["summary"] == {"total": 10}
        assert result["buses"] == {"name": ["b1", "b2", "b3"]}
        assert result["lines"] == {"name": ["l1", "l2"]}
        assert result["loads"] == {"name": ["ld1"]}
        assert result["segments"] == {"name": ["s1", "s2"]}

    @patch("py_dss_service.engine.runner.dss_tools")
    def test_handles_none_records_gracefully(self, mock_dss_tools, runner):
        mock_dss_tools.model._buses_records = None
        mock_dss_tools.model._lines_records = None
        mock_dss_tools.model._loads_records = None
        mock_dss_tools.model._segments_records = None
        mock_dss_tools.model._summary_model_records = None

        result = runner.extract_model_snapshot("job-2")

        assert result["num_buses"] == 0
        assert result["num_lines"] == 0
        assert result["num_loads"] == 0
        assert result["buses"] is None
        assert result["lines"] is None
        assert result["loads"] is None
        assert result["segments"] is None
        assert result["summary"] is None

    @patch("py_dss_service.engine.runner.dss_tools")
    def test_handles_empty_records(self, mock_dss_tools, runner):
        mock_dss_tools.model._buses_records = {}
        mock_dss_tools.model._lines_records = {}
        mock_dss_tools.model._loads_records = {}
        mock_dss_tools.model._segments_records = {}
        mock_dss_tools.model._summary_model_records = {}

        result = runner.extract_model_snapshot("job-3")

        assert result["num_buses"] == 0
        assert result["num_lines"] == 0
        assert result["num_loads"] == 0


# ---------------------------------------------------------------------------
# _apply_action
# ---------------------------------------------------------------------------

class TestApplyAction:
    def test_dss_command_calls_dss_text(self, runner):
        action = DSSCommandAction(type="dss_command", command="solve")
        runner._apply_action(runner._dss, action, "j1", 1)
        runner._dss.text.assert_called_once_with("solve")

    def test_unknown_action_type_raises_job_execution_error(self, runner):
        action = MagicMock()
        action.type = "unknown_type"
        with pytest.raises(JobExecutionError, match="Unknown action type"):
            runner._apply_action(runner._dss, action, "j1", 1)

    @patch("py_dss_service.engine.runner.dss_tools")
    def test_add_line_in_vsource_action(self, mock_dss_tools, runner):
        from py_dss_service.schemas.job_spec import AddLineInVsourceAction

        action = AddLineInVsourceAction(
            type="add_line_in_vsource", add_meter=True, add_monitors=False
        )
        runner._apply_action(runner._dss, action, "j1", 1)
        mock_dss_tools.model.add_line_in_vsource.assert_called_once_with(
            add_meter=True, add_monitors=False
        )

    def test_dss_command_exception_wraps_as_job_execution_error(self, runner):
        runner._dss.text.side_effect = RuntimeError("COM error")
        action = DSSCommandAction(type="dss_command", command="bad")
        with pytest.raises(JobExecutionError, match="Failed to apply action"):
            runner._apply_action(runner._dss, action, "j1", 1)
