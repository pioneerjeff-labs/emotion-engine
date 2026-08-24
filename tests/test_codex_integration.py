import json
import os
import subprocess
import sys
import tempfile
import unittest
import zipfile
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
CODEX_INTEGRATION = ROOT / "integrations" / "codex"
CODEX_SKILL = CODEX_INTEGRATION / "emotion-engine-codex"
WRAPPER = CODEX_SKILL / "scripts" / "codex_emotion.sh"


class CodexIntegrationTest(unittest.TestCase):
    def run_wrapper(self, state_file, *args):
        env = os.environ.copy()
        env["CODEX_EMOTION_STATE"] = str(state_file)
        env["PYTHONDONTWRITEBYTECODE"] = "1"
        result = subprocess.run(
            [str(WRAPPER), *args],
            cwd=str(CODEX_SKILL),
            env=env,
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            check=True,
        )
        return result.stdout

    def test_package_contains_required_files(self):
        self.assertTrue((CODEX_SKILL / "SKILL.md").exists())
        self.assertTrue((CODEX_SKILL / "README.md").exists())
        self.assertTrue((CODEX_SKILL / "install.sh").exists())
        self.assertTrue(WRAPPER.exists())
        self.assertTrue((CODEX_SKILL / "scripts" / "nora_demo.py").exists())

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

    def test_nora_demo_generates_isolated_reply_prompt(self):
        with tempfile.TemporaryDirectory() as tmp:
            state_file = Path(tmp) / "emotion-state.json"

            prompt = self.run_wrapper(
                state_file,
                "nora-demo",
                "--packet",
                "low",
                "--reply-prompt",
            )

        self.assertIn("Packet: Emotion Engine / low trust", prompt)
        self.assertIn("Emotion Engine state:", prompt)
        self.assertIn("Output only Nora's reply in Chinese.", prompt)

    def test_wrapper_forwards_record_policy(self):
        with tempfile.TemporaryDirectory() as tmp:
            state_file = Path(tmp) / "emotion-state.json"

            output = self.run_wrapper(
                state_file,
                "record_policy",
                "--mode",
                "light",
                "--context",
                "milestone",
                "that migration was handled well",
            )

        payload = json.loads(output)
        self.assertEqual(payload["mode"], "light")
        self.assertEqual(payload["decision"], "respond_only")
        self.assertEqual(payload["reason"], "work_checkpoint")
        self.assertIn("reply_bias", payload)
        self.assertIn("milestone", payload["context"])

    def test_installer_creates_user_skill_and_state(self):
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            skills_dir = tmp_path / "skills"
            state_file = tmp_path / "state" / "emotion-state.json"
            env = os.environ.copy()
            env["CODEX_SKILLS_DIR"] = str(skills_dir)
            env["CODEX_EMOTION_STATE"] = str(state_file)
            env["PYTHONDONTWRITEBYTECODE"] = "1"

            result = subprocess.run(
                ["sh", str(CODEX_SKILL / "install.sh")],
                cwd=str(CODEX_SKILL),
                env=env,
                text=True,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                check=True,
            )

            installed = skills_dir / "emotion-engine-codex"
            self.assertTrue((installed / "SKILL.md").exists())
            self.assertTrue((installed / "scripts" / "codex_emotion.sh").exists())
            self.assertTrue((installed / "scripts" / "emotion_engine_utils.py").exists())
            self.assertTrue((installed / "scripts" / "emotion_engine_mcp.py").exists())
            self.assertTrue((installed / "scripts" / "register_mcp_client.py").exists())
            self.assertTrue((installed / "spec" / "emotion-state.schema.json").exists())
            self.assertTrue(state_file.exists())
            self.assertIn('"status": "identity_binding_required"', result.stdout)
            self.assertIn("bind_identity", result.stdout)

            raw_status = subprocess.run(
                [str(installed / "scripts" / "codex_emotion.sh"), "status", "--raw"],
                cwd=str(installed),
                env=env,
                text=True,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                check=True,
            ).stdout
            self.assertEqual(json.loads(raw_status)["_schema"], "emotion-engine-state/v3")

            listed = subprocess.run(
                [sys.executable, str(installed / "scripts" / "emotion_engine_mcp.py"), "--state", str(state_file)],
                input=json.dumps({"jsonrpc": "2.0", "id": 1, "method": "tools/list"}) + "\n",
                text=True,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                check=True,
            ).stdout
            tool_names = {tool["name"] for tool in json.loads(listed)["result"]["tools"]}
            self.assertIn("emotion_engine_record_policy", tool_names)
            self.assertNotIn("emotion_engine_repair", tool_names)

    def test_installer_defaults_to_agents_skills_without_existing_codex_dir(self):
        with tempfile.TemporaryDirectory() as tmp:
            home = Path(tmp) / "home"
            env = os.environ.copy()
            env.pop("CODEX_SKILLS_DIR", None)
            env.pop("CODEX_EMOTION_STATE", None)
            env["HOME"] = str(home)
            env["PYTHONDONTWRITEBYTECODE"] = "1"

            subprocess.run(
                ["sh", str(CODEX_SKILL / "install.sh")],
                cwd=str(CODEX_SKILL),
                env=env,
                text=True,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                check=True,
            )

            installed = home / ".agents" / "skills" / "emotion-engine-codex"
            state_file = home / ".agents" / "emotion-engine" / "emotion-state.json"
            self.assertTrue((installed / "SKILL.md").exists())
            self.assertTrue(state_file.exists())

            raw_status = subprocess.run(
                [str(installed / "scripts" / "codex_emotion.sh"), "status", "--raw"],
                cwd=str(installed),
                env=env,
                text=True,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                check=True,
            ).stdout
            self.assertEqual(json.loads(raw_status)["_schema"], "emotion-engine-state/v3")

    def test_installer_preserves_v2_state_and_prints_explicit_migration_flow(self):
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            skills_dir = tmp_path / "skills"
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
            env["CODEX_SKILLS_DIR"] = str(skills_dir)
            env["CODEX_EMOTION_STATE"] = str(state_file)
            env["PYTHONDONTWRITEBYTECODE"] = "1"

            installed = subprocess.run(
                ["sh", str(CODEX_SKILL / "install.sh")],
                cwd=str(CODEX_SKILL),
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

    def test_package_script_builds_self_contained_zip(self):
        output = CODEX_INTEGRATION / "emotion-engine-codex-skill.zip"
        if output.exists():
            output.unlink()

        try:
            subprocess.run(
                ["sh", str(CODEX_INTEGRATION / "package_codex_skill.sh")],
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
                    env = os.environ.copy()
                    env["CODEX_SKILLS_DIR"] = str(tmp_path / "skills")
                    env["CODEX_EMOTION_STATE"] = str(tmp_path / "state" / "emotion-state.json")
                    env["PYTHONDONTWRITEBYTECODE"] = "1"
                    unpacked = tmp_path / "unzip" / "emotion-engine-codex"

                    subprocess.run(
                        ["sh", str(unpacked / "install.sh")],
                        cwd=str(unpacked),
                        env=env,
                        text=True,
                        stdout=subprocess.PIPE,
                        stderr=subprocess.PIPE,
                        check=True,
                    )

                    installed = tmp_path / "skills" / "emotion-engine-codex"
                    raw_status = subprocess.run(
                        [str(installed / "scripts" / "codex_emotion.sh"), "status", "--raw"],
                        cwd=str(installed),
                        env=env,
                        text=True,
                        stdout=subprocess.PIPE,
                        stderr=subprocess.PIPE,
                        check=True,
                    ).stdout
                    self.assertEqual(json.loads(raw_status)["_schema"], "emotion-engine-state/v3")

            self.assertIn("emotion-engine-codex/SKILL.md", names)
            self.assertIn("emotion-engine-codex/install.sh", names)
            self.assertIn("emotion-engine-codex/scripts/codex_emotion.sh", names)
            self.assertIn("emotion-engine-codex/scripts/nora_demo.py", names)
            self.assertIn("emotion-engine-codex/scripts/emotion_engine_utils.py", names)
            self.assertIn("emotion-engine-codex/scripts/emotion_engine_mcp.py", names)
            self.assertIn("emotion-engine-codex/scripts/register_mcp_client.py", names)
            self.assertIn("emotion-engine-codex/spec/emotion-state.schema.json", names)
            self.assertIn("emotion-engine-codex/emotion-state-template.json", names)
            self.assertIn("emotion-engine-codex/LICENSE", names)
        finally:
            if output.exists():
                output.unlink()


if __name__ == "__main__":
    unittest.main()
