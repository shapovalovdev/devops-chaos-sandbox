import sys
from pathlib import Path
from unittest.mock import patch, MagicMock
import datetime
import pytest

# Ensure chaos_scheduler is importable regardless of current working directory
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import chaos_scheduler


class MockDatetime(datetime.datetime):
    """Subclass of datetime.datetime to allow mocking datetime.now()."""
    target_now = datetime.datetime(2026, 8, 15, 14, 0)

    @classmethod
    def now(cls, tz=None):
        return cls.target_now


class TestIsInsideSlot:
    """Unit tests for time checking logic in is_inside_slot()."""

    @pytest.mark.parametrize(
        "year,month,day,hour,minute,expected",
        [
            # Saturday inside slot (12:00 - 18:00)
            (2026, 8, 15, 12, 0, True),    # Sat 12:00 (Start boundary)
            (2026, 8, 15, 14, 30, True),   # Sat 14:30
            (2026, 8, 15, 17, 59, True),   # Sat 17:59 (End boundary inside)
            # Sunday inside slot (12:00 - 18:00)
            (2026, 8, 16, 12, 0, True),    # Sun 12:00 (Start boundary)
            (2026, 8, 16, 15, 0, True),    # Sun 15:00
            (2026, 8, 16, 17, 59, True),   # Sun 17:59 (End boundary inside)
            # Outside allowed days
            (2026, 8, 12, 14, 0, False),   # Wed 14:00 (Wednesday)
            (2026, 8, 10, 14, 0, False),   # Mon 14:00 (Monday)
            (2026, 8, 14, 14, 0, False),   # Fri 14:00 (Friday)
            # Outside allowed hours on allowed days
            (2026, 8, 15, 11, 59, False),  # Sat 11:59 (Before start hour)
            (2026, 8, 15, 18, 0, False),   # Sat 18:00 (At end hour boundary)
            (2026, 8, 15, 20, 0, False),   # Sat 20:00 (After end hour)
            (2026, 8, 16, 11, 59, False),  # Sun 11:59 (Before start hour)
            (2026, 8, 16, 18, 0, False),   # Sun 18:00 (At end hour boundary)
        ],
    )
    def test_is_inside_slot_time_checks(
        self, year, month, day, hour, minute, expected, monkeypatch
    ):
        monkeypatch.delenv("FORCE_CHAOS", raising=False)
        MockDatetime.target_now = datetime.datetime(year, month, day, hour, minute)
        with patch("chaos_scheduler.datetime.datetime", MockDatetime):
            assert chaos_scheduler.is_inside_slot() == expected

    def test_force_chaos_override(self, monkeypatch):
        # Wednesday 14:00 is outside slot
        MockDatetime.target_now = datetime.datetime(2026, 8, 12, 14, 0)
        monkeypatch.setenv("FORCE_CHAOS", "1")
        with patch("chaos_scheduler.datetime.datetime", MockDatetime):
            assert chaos_scheduler.is_inside_slot() is True

    def test_force_chaos_disabled(self, monkeypatch):
        # Wednesday 14:00 with FORCE_CHAOS set to 0
        MockDatetime.target_now = datetime.datetime(2026, 8, 12, 14, 0)
        monkeypatch.setenv("FORCE_CHAOS", "0")
        with patch("chaos_scheduler.datetime.datetime", MockDatetime):
            assert chaos_scheduler.is_inside_slot() is False


class TestMainExecution:
    """Unit tests for main() execution and subprocess invocation."""

    @patch("chaos_scheduler.subprocess.run")
    def test_main_invokes_subprocess_inside_slot(
        self, mock_subprocess_run, monkeypatch
    ):
        monkeypatch.delenv("FORCE_CHAOS", raising=False)
        # Saturday 14:00 (inside slot)
        MockDatetime.target_now = datetime.datetime(2026, 8, 15, 14, 0)

        # Configure mock subprocess return value
        mock_result = MagicMock()
        mock_result.returncode = 0
        mock_result.stdout = "Scenario executed successfully"
        mock_result.stderr = ""
        mock_subprocess_run.return_value = mock_result

        with patch("chaos_scheduler.datetime.datetime", MockDatetime):
            chaos_scheduler.main()

        # Verify subprocess.run was called once
        mock_subprocess_run.assert_called_once()
        args, kwargs = mock_subprocess_run.call_args

        # Verify command argument is a valid script path ending in .sh
        executed_script = args[0][0]
        assert executed_script.endswith(".sh")
        assert kwargs.get("stdout") == chaos_scheduler.subprocess.PIPE
        assert kwargs.get("stderr") == chaos_scheduler.subprocess.PIPE
        assert kwargs.get("text") is True
        assert kwargs.get("timeout") == 30

    @patch("chaos_scheduler.subprocess.run")
    def test_main_does_not_invoke_subprocess_outside_slot(
        self, mock_subprocess_run, monkeypatch
    ):
        monkeypatch.delenv("FORCE_CHAOS", raising=False)
        # Wednesday 14:00 (outside slot)
        MockDatetime.target_now = datetime.datetime(2026, 8, 12, 14, 0)

        # Outside slot, main() exits early with status 0
        with pytest.raises(SystemExit) as exc_info:
            with patch("chaos_scheduler.datetime.datetime", MockDatetime):
                chaos_scheduler.main()

        assert exc_info.value.code == 0
        mock_subprocess_run.assert_not_called()

    @patch("chaos_scheduler.subprocess.run")
    def test_main_invokes_subprocess_when_force_chaos_set_outside_slot(
        self, mock_subprocess_run, monkeypatch
    ):
        # Wednesday 14:00 (outside slot, but FORCE_CHAOS=1)
        MockDatetime.target_now = datetime.datetime(2026, 8, 12, 14, 0)
        monkeypatch.setenv("FORCE_CHAOS", "1")

        mock_result = MagicMock()
        mock_result.returncode = 0
        mock_result.stdout = "Forced scenario run"
        mock_result.stderr = ""
        mock_subprocess_run.return_value = mock_result

        with patch("chaos_scheduler.datetime.datetime", MockDatetime):
            chaos_scheduler.main()

        mock_subprocess_run.assert_called_once()

    @patch("chaos_scheduler.subprocess.run")
    @patch("chaos_scheduler.get_scenarios")
    def test_main_handles_no_scenarios(
        self, mock_get_scenarios, mock_subprocess_run, monkeypatch
    ):
        monkeypatch.delenv("FORCE_CHAOS", raising=False)
        MockDatetime.target_now = datetime.datetime(2026, 8, 15, 14, 0)
        mock_get_scenarios.return_value = []

        with pytest.raises(SystemExit) as exc_info:
            with patch("chaos_scheduler.datetime.datetime", MockDatetime):
                chaos_scheduler.main()

        assert exc_info.value.code == 0
        mock_subprocess_run.assert_not_called()


class TestGetScenarios:
    """Unit tests for get_scenarios helper function."""

    def test_get_scenarios_returns_scripts(self):
        scenarios = chaos_scheduler.get_scenarios()
        assert isinstance(scenarios, list)
        assert len(scenarios) > 0
        for s in scenarios:
            assert isinstance(s, Path)
            assert s.suffix == ".sh"
