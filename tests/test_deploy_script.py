"""Static guards for deploy_pi.sh: python -m unittest tests.test_deploy_script.

Runs anywhere (no Flask, SSH, or Pi needed); only reads the script text.
"""
import unittest
from pathlib import Path


class DeployScriptTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.script = (Path(__file__).resolve().parent.parent
                      / "deploy_pi.sh").read_text()
        cls.code = "\n".join(
            line for line in cls.script.splitlines()
            if line.strip() and not line.strip().startswith("#"))

    def test_script_is_bash_clean(self):
        self.assertTrue(self.script.startswith("#!/usr/bin/env bash"))
        self.assertIn("set -euo pipefail", self.script)

    def test_never_uses_delete_or_privilege_escalation(self):
        opts = self.code[self.code.index("RSYNC_OPTS="):]
        opts = opts[:opts.index("\n")]
        self.assertNotIn("--delete", opts)
        for token in ("sudo", "apt install", "pip install",
                      "hailortcli install"):
            self.assertNotIn(token, self.code)

    def test_preserves_pi_live_state(self):
        for pattern in (r"--exclude='\.venv/'", r"--exclude='\.deps/'",
                        r"--exclude='\*\.log'", r"--exclude='\*\.db'",
                        r"--exclude='camera-check\.jpg'",
                        r"--exclude='venv_hailo_rpi5_examples/'"):
            self.assertRegex(self.script, pattern)
        # The tracked example database must never overwrite Pi history.
        self.assertIn("--exclude='*.db'", self.script)
        self.assertIn("--checksum", self.script)

    def test_aborts_while_detection_is_active_unless_forced(self):
        self.assertIn("--force", self.script)
        self.assertRegex(self.script, r"detection is ACTIVE.*--force")

    def test_restart_ignores_docs_only_changes(self):
        block = self.script[self.script.index("RUNTIME_CHANGED=0"):]
        decision = block.split("\n\n")[0]
        self.assertNotIn("docs/", decision)
        self.assertNotIn("README", decision)
        self.assertNotIn("tests/", decision)
        for runtime in (r"app\.py", r"detection\.py", "templates/", "static/"):
            self.assertIn(runtime, decision)


if __name__ == "__main__":
    unittest.main()
