import json
import os
import subprocess
import tempfile
import unittest
import zipfile
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
OPENCLAW_INTEGRATION = ROOT / "integrations" / "openclaw"
OPENCLAW_SKILL = ROOT / "integrations" / "openclaw" / "emotion-engine"
INSTALLER = OPENCLAW_SKILL / "install.sh"


class OpenClawIntegrationTest(unittest.TestCase):
    def test_package_contains_required_files(self):
        self.assertTrue((OPENCLAW_SKILL / "SKILL.md").exists())
        self.assertTrue((OPENCLAW_SKILL / "README.md").exists())
        self.assertTrue(INSTALLER.exists())

    def test_installer_creates_workspace_skill_and_state(self):
        with tempfile.TemporaryDirectory() as tmp:
            workspace = Path(tmp) / "workspace"
            env = os.environ.copy()
            env["OPENCLAW_WORKSPACE"] = str(workspace)

            subprocess.run(
                [str(INSTALLER)],
                cwd=str(OPENCLAW_SKILL),
                env=env,
                text=True,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                check=True,
            )

            installed = workspace / "skills" / "emotion-engine"
            state_file = workspace / "emotion-state.json"
            self.assertTrue((installed / "SKILL.md").exists())
            self.assertTrue((installed / "install.sh").exists())
            self.assertTrue((installed / "scripts" / "emotion_engine_utils.py").exists())
            self.assertTrue((installed / "spec" / "emotion-state.schema.json").exists())

            with state_file.open() as f:
                state = json.load(f)
            self.assertEqual(state["_schema"], "emotion-engine-state/v2")

    def test_package_script_builds_self_contained_zip(self):
        output = OPENCLAW_INTEGRATION / "emotion-engine-openclaw-skill.zip"
        if output.exists():
            output.unlink()

        try:
            subprocess.run(
                ["sh", str(OPENCLAW_INTEGRATION / "package_openclaw_skill.sh")],
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
            self.assertIn("emotion-engine/scripts/emotion_engine_utils.py", names)
            self.assertIn("emotion-engine/spec/emotion-state.schema.json", names)
            self.assertIn("emotion-engine/emotion-state-template.json", names)
            self.assertIn("emotion-engine/LICENSE", names)
        finally:
            if output.exists():
                output.unlink()


if __name__ == "__main__":
    unittest.main()
