import json
import os
import subprocess
import tempfile
import unittest
import zipfile
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
CLAUDE_SKILL = ROOT / "integrations" / "claude-skill" / "emotion-engine"
CLAUDE_INTEGRATION = ROOT / "integrations" / "claude-skill"
WRAPPER = CLAUDE_SKILL / "scripts" / "claude_emotion.sh"


class ClaudeSkillIntegrationTest(unittest.TestCase):
    def run_wrapper(self, state_file, *args):
        env = os.environ.copy()
        env["CLAUDE_EMOTION_STATE"] = str(state_file)
        result = subprocess.run(
            [str(WRAPPER), *args],
            cwd=str(CLAUDE_SKILL),
            env=env,
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            check=True,
        )
        return result.stdout

    def test_package_contains_required_files(self):
        self.assertTrue((CLAUDE_SKILL / "SKILL.md").exists())
        self.assertTrue((CLAUDE_SKILL / "README.md").exists())
        self.assertTrue((CLAUDE_SKILL / "install.sh").exists())
        self.assertTrue(WRAPPER.exists())

    def test_wrapper_initializes_and_reports_status(self):
        with tempfile.TemporaryDirectory() as tmp:
            state_file = Path(tmp) / "emotion-state.json"

            self.run_wrapper(state_file, "configure", "--style", "warm but clearly bounded")
            raw_status = self.run_wrapper(state_file, "status", "--raw")
            payload = json.loads(raw_status)

            self.assertTrue(payload["enabled"])
            self.assertIn("emotion", payload)
            self.assertIn("trust", payload)
            self.assertEqual(payload["_schema"], "emotion-engine-state/v2")

    def test_package_script_builds_self_contained_zip(self):
        output = CLAUDE_INTEGRATION / "emotion-engine-claude-skill.zip"
        if output.exists():
            output.unlink()

        try:
            subprocess.run(
                ["sh", str(CLAUDE_INTEGRATION / "package_claude_skill.sh")],
                cwd=str(ROOT),
                text=True,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                check=True,
            )

            with zipfile.ZipFile(output) as package:
                names = set(package.namelist())

            self.assertIn("emotion-engine/SKILL.md", names)
            self.assertIn("emotion-engine/install.sh", names)
            self.assertIn("emotion-engine/scripts/claude_emotion.sh", names)
            self.assertIn("emotion-engine/scripts/emotion_engine_utils.py", names)
            self.assertIn("emotion-engine/emotion-state-template.json", names)
            self.assertIn("emotion-engine/LICENSE", names)
        finally:
            if output.exists():
                output.unlink()


if __name__ == "__main__":
    unittest.main()
