import os
import sys
import json
import pytest
from unittest.mock import patch, MagicMock, call

# Ensure mock environment variables are set before importing chaos_alerts
os.environ.setdefault("TELEGRAM_BOT_TOKEN", "mock_token_123")
os.environ.setdefault("TELEGRAM_CHAT_ID", "mock_chat_999")
os.environ.setdefault("TARGET_APP_URL", "http://example.com/health")

# Ensure parent directory is in sys.path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

import chaos_alerts


@pytest.fixture(autouse=True)
def mock_env_vars(monkeypatch):
    """Fixture to ensure mocked environment variables and module attributes are set for each test."""
    monkeypatch.setenv("TELEGRAM_BOT_TOKEN", "mock_token_123")
    monkeypatch.setenv("TELEGRAM_CHAT_ID", "mock_chat_999")
    monkeypatch.setenv("TARGET_APP_URL", "http://example.com/health")
    monkeypatch.setattr(chaos_alerts, "TELEGRAM_BOT_TOKEN", "mock_token_123")
    monkeypatch.setattr(chaos_alerts, "TELEGRAM_CHAT_ID", "mock_chat_999")
    monkeypatch.setattr(chaos_alerts, "TARGET_APP_URL", "http://example.com/health")


class TestValidateEnv:
    def test_validate_env_success(self):
        """validate_env should complete without exiting when all env vars are present."""
        chaos_alerts.validate_env()

    @pytest.mark.parametrize("missing_var", ["TELEGRAM_BOT_TOKEN", "TELEGRAM_CHAT_ID", "TARGET_APP_URL"])
    def test_validate_env_missing_vars(self, monkeypatch, missing_var):
        """validate_env should exit with code 1 if any env var is missing."""
        monkeypatch.setattr(chaos_alerts, missing_var, None)
        with pytest.raises(SystemExit) as exc_info:
            chaos_alerts.validate_env()
        assert exc_info.value.code == 1


class TestSendTelegramMessage:
    @patch("urllib.request.urlopen")
    def test_send_telegram_message_success(self, mock_urlopen):
        """Test sending Telegram notification successfully."""
        mock_response = MagicMock()
        mock_response.read.return_value = b'{"ok": true}'
        mock_response.__enter__.return_value = mock_response
        mock_urlopen.return_value = mock_response

        res = chaos_alerts.send_telegram_message("Test Alert Message")

        assert res == b'{"ok": true}'
        mock_urlopen.assert_called_once()
        req_arg = mock_urlopen.call_args[0][0]
        assert req_arg.full_url == "https://api.telegram.org/botmock_token_123/sendMessage"
        assert req_arg.headers["Content-type"] == "application/json"

        body = json.loads(req_arg.data.decode("utf-8"))
        assert body["chat_id"] == "mock_chat_999"
        assert body["text"] == "Test Alert Message"
        assert body["parse_mode"] == "Markdown"

    @patch("urllib.request.urlopen")
    def test_send_telegram_message_failure(self, mock_urlopen):
        """Test exception handling during Telegram message sending."""
        mock_urlopen.side_effect = Exception("Network unreachable")

        res = chaos_alerts.send_telegram_message("Test Fail Message")
        assert res is None


class TestCheckAppHealth:
    @patch("urllib.request.urlopen")
    def test_check_app_health_200_ok(self, mock_urlopen):
        """Test check_app_health returning status code 200."""
        mock_response = MagicMock()
        mock_response.getcode.return_value = 200
        mock_response.__enter__.return_value = mock_response
        mock_urlopen.return_value = mock_response

        healthy, msg = chaos_alerts.check_app_health()
        assert healthy is True
        assert msg == "Status: 200"

        mock_urlopen.assert_called_once()
        req_arg = mock_urlopen.call_args[0][0]
        assert req_arg.full_url == "http://example.com/health"
        assert req_arg.headers["User-agent"] == "ChaosSandboxAlertMonitor/1.0"

    @patch("urllib.request.urlopen")
    def test_check_app_health_non_200(self, mock_urlopen):
        """Test check_app_health returning non-200 status code."""
        mock_response = MagicMock()
        mock_response.getcode.return_value = 503
        mock_response.__enter__.return_value = mock_response
        mock_urlopen.return_value = mock_response

        healthy, msg = chaos_alerts.check_app_health()
        assert healthy is False
        assert msg == "Non-200 Status: 503"

    @patch("urllib.request.urlopen")
    def test_check_app_health_exception(self, mock_urlopen):
        """Test check_app_health handling network exceptions."""
        mock_urlopen.side_effect = Exception("Connection Refused")

        healthy, msg = chaos_alerts.check_app_health()
        assert healthy is False
        assert msg == "Exception: Connection Refused"


class TestStateTransitions:
    @patch("chaos_alerts.send_telegram_message")
    @patch("chaos_alerts.check_app_health")
    @patch("chaos_alerts.validate_env")
    @patch("time.sleep")
    def test_state_transition_healthy_down_healthy(
        self, mock_sleep, mock_validate_env, mock_check_health, mock_send_telegram
    ):
        """
        Test daemon state transitions: Healthy -> Down -> Down (no duplicate message) -> Healthy -> Exit.
        Verifies alerts are sent on state transitions only.
        """
        mock_check_health.side_effect = [
            (True, "Status: 200"),            # 1. Initially Healthy
            (False, "Non-200 Status: 500"),   # 2. Transition: Healthy -> Down (Alert triggered)
            (False, "Non-200 Status: 500"),   # 3. Remains Down (No duplicate alert)
            (True, "Status: 200"),            # 4. Transition: Down -> Healthy (Recovery triggered)
        ]

        # Interrupt loop after 4th sleep call
        mock_sleep.side_effect = [None, None, None, KeyboardInterrupt]

        with pytest.raises(KeyboardInterrupt):
            chaos_alerts.main()

        mock_validate_env.assert_called_once()
        assert mock_send_telegram.call_count == 2

        first_msg = mock_send_telegram.call_args_list[0][0][0]
        second_msg = mock_send_telegram.call_args_list[1][0][0]

        assert "DOWNTIME ALERT" in first_msg
        assert "UNREACHABLE" in first_msg
        assert "Non-200 Status: 500" in first_msg

        assert "RECOVERY ALERT" in second_msg
        assert "healthy again" in second_msg

    @patch("urllib.request.urlopen")
    @patch("time.sleep")
    def test_end_to_end_state_transition_with_urlopen_mock(self, mock_sleep, mock_urlopen):
        """
        End-to-end test of main loop using mocked urllib.request.urlopen.
        Simulates Healthy -> Down -> Healthy sequence directly through urlopen.
        """
        mock_resp_200 = MagicMock()
        mock_resp_200.getcode.return_value = 200
        mock_resp_200.read.return_value = b'{"ok": true}'
        mock_resp_200.__enter__.return_value = mock_resp_200

        mock_resp_500 = MagicMock()
        mock_resp_500.getcode.return_value = 500
        mock_resp_500.__enter__.return_value = mock_resp_500

        mock_urlopen.side_effect = [
            mock_resp_200,  # 1. Health check (Healthy)
            mock_resp_500,  # 2. Health check (Down)
            mock_resp_200,  # 2. Telegram alert send
            mock_resp_500,  # 3. Health check (Down, repeat)
            mock_resp_200,  # 4. Health check (Healthy)
            mock_resp_200,  # 4. Telegram recovery send
        ]

        mock_sleep.side_effect = [None, None, None, KeyboardInterrupt]

        with pytest.raises(KeyboardInterrupt):
            chaos_alerts.main()

        assert mock_urlopen.call_count == 6
