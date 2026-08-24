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
GITHUB_TAP_SKILL = ROOT / "skills" / "emotion-engine"
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

    def assert_installer_preserves_v2_state(self, package_dir):
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            state_file = tmp_path / "state" / "emotion-state.json"
            state_file.parent.mkdir(parents=True)
            legacy = {
                "_schema": "emotion-engine-state/v2",
                "enabled": True,
                "runtime_mode": "light",
                "boundary_state": {"last_boundary": "preserve me"},
            }
            state_file.write_text(json.dumps(legacy, indent=2) + "\n", encoding="utf-8")
            before = state_file.read_bytes()
            env = os.environ.copy()
            env.update({
                "HERMES_SKILL_DEST": str(tmp_path / "installed" / "emotion-engine"),
                "HERMES_EMOTION_STATE": str(state_file),
                "PYTHONDONTWRITEBYTECODE": "1",
            })

            installed = subprocess.run(
                ["sh", str(package_dir / "install.sh")],
                cwd=str(package_dir),
                env=env,
                text=True,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                check=True,
            )

            self.assertEqual(state_file.read_bytes(), before)
            self.assertIn('"status": "migration_required"', installed.stdout)
            self.assertIn("migrate_state", installed.stdout)
            self.assertIn("--apply", installed.stdout)
            self.assertIn("activation is pending", installed.stdout)

    def test_package_contains_required_files(self):
        self.assertTrue((HERMES_SKILL / "SKILL.md").exists())
        self.assertTrue((HERMES_SKILL / "README.md").exists())
        self.assertTrue((HERMES_SKILL / "install.sh").exists())
        self.assertTrue(WRAPPER.exists())
        self.assertIn("activation_check", (HERMES_SKILL / "install.sh").read_text())

    def test_wrapper_initializes_and_reports_status(self):
        with tempfile.TemporaryDirectory() as tmp:
            state_file = Path(tmp) / "emotion-state.json"

            self.run_wrapper(state_file, "configure", "--style", "warm but clearly bounded")
            raw_status = self.run_wrapper(state_file, "status", "--raw")
            payload = json.loads(raw_status)

            self.assertTrue(payload["enabled"])
            self.assertIn("emotion", payload)
            self.assertIn("trust", payload)
            self.assertEqual(payload["_schema"], "emotion-engine-state/v3")

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
            self.assertIn("emotion-engine/spec/emotion-state.schema.json", names)
            self.assertIn("emotion-engine/emotion-state-template.json", names)
            self.assertIn("emotion-engine/LICENSE", names)
            with tempfile.TemporaryDirectory() as tmp:
                with zipfile.ZipFile(output) as package:
                    package.extractall(tmp)
                package_dir = Path(tmp) / "emotion-engine"
                self.assertEqual(
                    (package_dir / "install.sh").read_bytes(),
                    (GITHUB_TAP_SKILL / "install.sh").read_bytes(),
                )
                self.assertEqual(
                    (package_dir / "scripts" / "hermes_emotion.sh").read_bytes(),
                    (GITHUB_TAP_SKILL / "scripts" / "hermes_emotion.sh").read_bytes(),
                )
                self.assert_installer_preserves_v2_state(package_dir)
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
            self.assertTrue((output / "spec" / "emotion-state.schema.json").exists())
            self.assertTrue((output / "emotion-state-template.json").exists())
            self.assertTrue((output / "LICENSE").exists())
            self.assertEqual(
                (output / "install.sh").read_bytes(),
                (GITHUB_TAP_SKILL / "install.sh").read_bytes(),
            )
            self.assertEqual(
                (output / "scripts" / "hermes_emotion.sh").read_bytes(),
                (GITHUB_TAP_SKILL / "scripts" / "hermes_emotion.sh").read_bytes(),
            )
            self.assertNotIn("../../..", (output / "install.sh").read_text())
            self.assertNotIn("../../..", (output / "scripts" / "hermes_emotion.sh").read_text())
            self.assert_installer_preserves_v2_state(output)

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

            self.assertEqual(payload["_schema"], "emotion-engine-state/v3")
            self.assertTrue(payload["enabled"])
        finally:
            if output.exists():
                shutil.rmtree(output)

    def test_github_tap_skill_is_self_contained(self):
        self.assertTrue((GITHUB_TAP_SKILL / "SKILL.md").exists())
        self.assertTrue((GITHUB_TAP_SKILL / "README.md").exists())
        self.assertTrue((GITHUB_TAP_SKILL / "install.sh").exists())
        self.assertTrue((GITHUB_TAP_SKILL / "scripts" / "hermes_emotion.sh").exists())
        self.assertTrue((GITHUB_TAP_SKILL / "scripts" / "emotion_engine_utils.py").exists())
        self.assertTrue((GITHUB_TAP_SKILL / "spec" / "emotion-state.schema.json").exists())
        self.assertTrue((GITHUB_TAP_SKILL / "emotion-state-template.json").exists())
        self.assertTrue((GITHUB_TAP_SKILL / "LICENSE").exists())
        self.assertNotIn("../../..", (GITHUB_TAP_SKILL / "install.sh").read_text())
        self.assertNotIn("../../..", (GITHUB_TAP_SKILL / "scripts" / "hermes_emotion.sh").read_text())

        with tempfile.TemporaryDirectory() as tmp:
            state_file = Path(tmp) / "emotion-state.json"
            env = os.environ.copy()
            env["HERMES_EMOTION_STATE"] = str(state_file)
            result = subprocess.run(
                [str(GITHUB_TAP_SKILL / "scripts" / "hermes_emotion.sh"), "status", "--raw"],
                cwd=str(GITHUB_TAP_SKILL),
                env=env,
                text=True,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                check=True,
            )
            payload = json.loads(result.stdout)

        self.assertEqual(payload["_schema"], "emotion-engine-state/v3")
        self.assertTrue(payload["enabled"])


if __name__ == "__main__":
    unittest.main()
