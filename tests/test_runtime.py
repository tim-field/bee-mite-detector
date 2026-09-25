"""Hardware-independent regression tests: python -m unittest tests.test_runtime."""
import importlib
import os
from pathlib import Path
import signal
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import MagicMock, patch


class RuntimeTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.temp = tempfile.TemporaryDirectory()
        with patch.dict(os.environ, {"BEE_DB_PATH": str(Path(cls.temp.name) / "test.db")}):
            cls.runtime = importlib.import_module("app")

    @classmethod
    def tearDownClass(cls):
        cls.temp.cleanup()

    def setUp(self):
        self.app = self.runtime
        self.app.detection_active = False
        self.app.detection_process = None
        self.app.detection_thread = None
        self.app.last_detection_error = None
        self.client = self.app.app.test_client()

    def test_portable_command(self):
        command = self.app.DETECTION_COMMAND
        self.assertEqual(command[0], sys.executable)
        self.assertEqual(command[1], "-u")
        self.assertTrue(Path(command[2]).is_file())
        self.assertEqual(command[command.index("--input") + 1], "rpi")
        self.assertNotIn("/home/ergi", " ".join(command))

    def test_email_is_disabled_without_explicit_configuration(self):
        from email_service import EmailService
        with patch.dict(os.environ, {}, clear=True), patch("email_service.smtplib.SMTP") as smtp:
            service = EmailService()
            self.assertEqual(service.username, "")
            self.assertEqual(service.password, "")
            self.assertEqual(service.recipient, "")
            self.assertFalse(service.send_session_summary(1, "unused.db"))
            smtp.assert_not_called()

    def test_dashboard_and_status(self):
        self.assertEqual(self.client.get("/").status_code, 200)
        status = self.client.get("/get_stats").get_json()
        self.assertFalse(status["active"])
        self.assertIsNone(status["error"])

    def test_zero_bees_is_not_evidence_of_low_risk(self):
        self.app.detection_stats.update(unique_bees=0, unique_varroa=0, total_frames=10)
        self.app.update_time_series()
        self.assertEqual(self.app.detection_stats["infestation_risk_level"], "Unknown")

    def test_stop_only_signals_owned_group(self):
        process = MagicMock(pid=12345)
        process.poll.return_value = None
        self.app.detection_process = process
        with patch("app.os.killpg") as killpg:
            self.app.terminate_detection()
        killpg.assert_called_once_with(12345, signal.SIGINT)
        process.wait.assert_called_once_with(timeout=3)
        self.assertIsNone(self.app.detection_process)

    def test_stop_escalates_when_needed(self):
        process = MagicMock(pid=12345)
        process.poll.return_value = None
        process.wait.side_effect = [subprocess.TimeoutExpired("test", 3), None]
        self.app.detection_process = process
        with patch("app.os.killpg") as killpg:
            self.app.terminate_detection()
        self.assertEqual([call.args[1] for call in killpg.call_args_list],
                         [signal.SIGINT, signal.SIGTERM])

    def test_start_stop_routes(self):
        thread = MagicMock()
        thread.is_alive.return_value = False
        with patch("app.threading.Thread", return_value=thread), patch("app.time.sleep"):
            self.assertEqual(self.client.post("/start_detection").get_json()["status"], "started")
            self.assertEqual(self.client.post("/start_detection").get_json()["status"], "already_running")
            self.assertEqual(self.client.post("/stop_detection").get_json()["status"], "stopped")
        thread.start.assert_called_once()
        thread.join.assert_called_once()

    def test_startup_failure_clears_active_and_exposes_error(self):
        self.app.detection_active = True
        with patch("app.db"), patch("app.subprocess.Popen", side_effect=OSError("missing runtime")):
            self.app.detection_loop()
        self.assertFalse(self.app.detection_active)
        self.assertIn("missing runtime", self.app.last_detection_error)

    def test_process_uses_merged_stderr_no_shell_and_own_session(self):
        process = MagicMock(pid=12345)
        process.stdout.readline.side_effect = ["model failed\n", ""]
        process.poll.return_value = 1
        process.wait.return_value = 1
        self.app.detection_active = True
        with patch("app.db"), patch("app.subprocess.Popen", return_value=process) as popen:
            self.app.detection_loop()
        options = popen.call_args.kwargs
        self.assertEqual(options["stderr"], subprocess.STDOUT)
        self.assertTrue(options["start_new_session"])
        self.assertFalse(options.get("shell", False))
        self.assertEqual(options["cwd"], self.app.PROJECT_DIR)
        self.assertIn("model failed", self.app.last_detection_error)
        self.assertFalse(self.app.detection_active)


if __name__ == "__main__":
    unittest.main()
