import json
import os
import subprocess
import tempfile
import unittest
import zipfile
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
PI_INTEGRATION = ROOT / "integrations" / "pi"
PI_SKILL = PI_INTEGRATION / "emotion-engine"
WRAPPER = PI_SKILL / "scripts" / "pi_emotion.sh"


class PiIntegrationTest(unittest.TestCase):
    def run_wrapper(self, state_file, *args, cwd=None):
        env = os.environ.copy()
        env["PI_EMOTION_STATE"] = str(state_file)
        env["PYTHONDONTWRITEBYTECODE"] = "1"
        result = subprocess.run(
            ["sh", str(WRAPPER), *args],
            cwd=str(cwd or PI_SKILL),
            env=env,
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            check=True,
        )
        return result.stdout

    def test_pi_package_manifest_exposes_only_pi_skill(self):
        manifest = json.loads((ROOT / "package.json").read_text())

        self.assertIn("pi-package", manifest["keywords"])
        self.assertEqual(
            manifest["pi"]["skills"],
            ["./integrations/pi/emotion-engine"],
        )

    def test_package_contains_agent_skill_files(self):
        skill_text = (PI_SKILL / "SKILL.md").read_text()

        self.assertTrue((PI_SKILL / "README.md").exists())
        self.assertTrue((PI_SKILL / "install.sh").exists())
        self.assertTrue(WRAPPER.exists())
        self.assertIn("name: emotion-engine", skill_text)
        self.assertIn("description:", skill_text)
        self.assertIn("<skill-directory>/scripts/pi_emotion.sh", skill_text)

    def test_wrapper_initializes_and_reports_status(self):
        with tempfile.TemporaryDirectory() as tmp:
            state_file = Path(tmp) / "emotion-state.json"

            self.run_wrapper(
                state_file,
                "configure",
                "--style",
                "warm but clearly bounded",
            )
            raw_status = self.run_wrapper(state_file, "status", "--raw")
            payload = json.loads(raw_status)

            self.assertTrue(payload["enabled"])
            self.assertIn("emotion", payload)
            self.assertIn("trust", payload)
            self.assertEqual(payload["_schema"], "emotion-engine-state/v2")

    def test_wrapper_uses_project_local_pi_state(self):
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            project = tmp_path / "project"
            nested = project / "src" / "feature"
            home = tmp_path / "home"
            (project / ".pi").mkdir(parents=True)
            nested.mkdir(parents=True)
            home.mkdir()
            env = os.environ.copy()
            env.pop("PI_EMOTION_STATE", None)
            env.pop("PI_PROJECT_DIR", None)
            env["HOME"] = str(home)
            env["PYTHONDONTWRITEBYTECODE"] = "1"

            state_path = subprocess.run(
                ["sh", str(WRAPPER), "where"],
                cwd=str(nested),
                env=env,
                text=True,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                check=True,
            ).stdout.strip()

            self.assertEqual(
                Path(state_path).resolve(),
                (project / ".emotion-engine" / "pi-state.json").resolve(),
            )

    def test_installer_creates_user_skill_and_preserves_existing_state(self):
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            home = tmp_path / "home"
            state_file = (
                home / ".pi" / "agent" / "emotion-engine" / "emotion-state.json"
            )
            env = os.environ.copy()
            env.pop("PI_SKILLS_DIR", None)
            env.pop("PI_SKILL_DEST", None)
            env.pop("PI_EMOTION_STATE", None)
            env["HOME"] = str(home)
            env["PYTHONDONTWRITEBYTECODE"] = "1"

            subprocess.run(
                ["sh", str(PI_SKILL / "install.sh")],
                cwd=str(PI_SKILL),
                env=env,
                text=True,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                check=True,
            )

            installed = home / ".pi" / "agent" / "skills" / "emotion-engine"
            original_state = state_file.read_bytes()

            subprocess.run(
                ["sh", str(PI_SKILL / "install.sh")],
                cwd=str(PI_SKILL),
                env=env,
                text=True,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                check=True,
            )

            self.assertTrue((installed / "SKILL.md").exists())
            self.assertTrue((installed / "scripts" / "pi_emotion.sh").exists())
            self.assertTrue(
                (installed / "scripts" / "emotion_engine_utils.py").exists()
            )
            self.assertTrue(
                (installed / "spec" / "emotion-state.schema.json").exists()
            )
            self.assertEqual(state_file.read_bytes(), original_state)

    def test_package_script_builds_installable_self_contained_zip(self):
        output = PI_INTEGRATION / "emotion-engine-pi-skill.zip"
        if output.exists():
            output.unlink()

        try:
            subprocess.run(
                ["sh", str(PI_INTEGRATION / "package_pi_skill.sh")],
                cwd=str(ROOT),
                text=True,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                check=True,
            )

            with zipfile.ZipFile(output) as package:
                names = set(package.namelist())
                with tempfile.TemporaryDirectory() as tmp:
                    tmp_path = Path(tmp)
                    package.extractall(tmp_path / "unzip")
                    unpacked = tmp_path / "unzip" / "emotion-engine"
                    state_file = tmp_path / "state" / "emotion-state.json"
                    env = os.environ.copy()
                    env["PI_SKILLS_DIR"] = str(tmp_path / "skills")
                    env["PI_EMOTION_STATE"] = str(state_file)
                    env["PYTHONDONTWRITEBYTECODE"] = "1"

                    subprocess.run(
                        ["sh", str(unpacked / "install.sh")],
                        cwd=str(unpacked),
                        env=env,
                        text=True,
                        stdout=subprocess.PIPE,
                        stderr=subprocess.PIPE,
                        check=True,
                    )

                    installed = tmp_path / "skills" / "emotion-engine"
                    raw_status = subprocess.run(
                        [
                            "sh",
                            str(installed / "scripts" / "pi_emotion.sh"),
                            "status",
                            "--raw",
                        ],
                        cwd=str(installed),
                        env=env,
                        text=True,
                        stdout=subprocess.PIPE,
                        stderr=subprocess.PIPE,
                        check=True,
                    ).stdout
                    self.assertEqual(
                        json.loads(raw_status)["_schema"],
                        "emotion-engine-state/v2",
                    )

            self.assertIn("emotion-engine/SKILL.md", names)
            self.assertIn("emotion-engine/install.sh", names)
            self.assertIn("emotion-engine/scripts/pi_emotion.sh", names)
            self.assertIn(
                "emotion-engine/scripts/emotion_engine_utils.py",
                names,
            )
            self.assertIn(
                "emotion-engine/spec/emotion-state.schema.json",
                names,
            )
            self.assertIn("emotion-engine/emotion-state-template.json", names)
            self.assertIn("emotion-engine/LICENSE", names)
        finally:
            if output.exists():
                output.unlink()


if __name__ == "__main__":
    unittest.main()
