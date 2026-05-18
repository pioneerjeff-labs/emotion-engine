import json
import os
import shutil
import subprocess
import tempfile
import unittest
import zipfile
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
HERMES_INTEGRATION = ROOT / "integrations" / "hermes"
HERMES_SKILL = HERMES_INTEGRATION / "emotion-engine"
WRAPPER = HERMES_SKILL / "scripts" / "hermes_emotion.sh"


class HermesIntegrationTest(unittest.TestCase):
    def run_wrapper(self, state_file, *args):
        env = os.environ.copy()
        env["HERMES_EMOTION_STATE"] = str(state_file)
        env["PYTHONDONTWRITEBYTECODE"] = "1"
        result = subprocess.run(
            [str(WRAPPER), *args],
            cwd=str(HERMES_SKILL),
            env=env,
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            check=True,
        )
        return result.stdout

    def test_package_contains_required_files(self):
        self.assertTrue((HERMES_SKILL / "SKILL.md").exists())
        self.assertTrue((HERMES_SKILL / "README.md").exists())
        self.assertTrue((HERMES_SKILL / "install.sh").exists())
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
        output = HERMES_INTEGRATION / "emotion-engine-hermes-skill.zip"
        if output.exists():
            output.unlink()

        try:
            subprocess.run(
                ["sh", str(HERMES_INTEGRATION / "package_hermes_skill.sh")],
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
            self.assertIn("emotion-engine/scripts/hermes_emotion.sh", names)
            self.assertIn("emotion-engine/scripts/emotion_engine_utils.py", names)
            self.assertIn("emotion-engine/emotion-state-template.json", names)
            self.assertIn("emotion-engine/LICENSE", names)
        finally:
            if output.exists():
                output.unlink()

    def test_prepare_hermes_hub_skill_builds_self_contained_directory(self):
        output = ROOT / "dist" / "hermes-hub" / "emotion-engine"
        if output.exists():
            shutil.rmtree(output)

        try:
            subprocess.run(
                ["sh", str(HERMES_INTEGRATION / "prepare_hermes_hub_skill.sh")],
                cwd=str(ROOT),
                text=True,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                check=True,
            )

            self.assertTrue((output / "SKILL.md").exists())
            self.assertTrue((output / "README.md").exists())
            self.assertTrue((output / "install.sh").exists())
            self.assertTrue((output / "scripts" / "hermes_emotion.sh").exists())
            self.assertTrue((output / "scripts" / "emotion_engine_utils.py").exists())
            self.assertTrue((output / "emotion-state-template.json").exists())
            self.assertTrue((output / "LICENSE").exists())

            with tempfile.TemporaryDirectory() as tmp:
                state_file = Path(tmp) / "emotion-state.json"
                env = os.environ.copy()
                env["HERMES_EMOTION_STATE"] = str(state_file)
                result = subprocess.run(
                    [str(output / "scripts" / "hermes_emotion.sh"), "status", "--raw"],
                    cwd=str(output),
                    env=env,
                    text=True,
                    stdout=subprocess.PIPE,
                    stderr=subprocess.PIPE,
                    check=True,
                )
                payload = json.loads(result.stdout)

            self.assertEqual(payload["_schema"], "emotion-engine-state/v2")
            self.assertTrue(payload["enabled"])
        finally:
            if output.exists():
                shutil.rmtree(output)


if __name__ == "__main__":
    unittest.main()
