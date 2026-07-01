import contextlib
import importlib.util
import io
import json
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
REGISTER_SCRIPT = ROOT / "scripts" / "register_mcp_client.py"

spec = importlib.util.spec_from_file_location("register_mcp_client", REGISTER_SCRIPT)
register_mcp_client = importlib.util.module_from_spec(spec)
spec.loader.exec_module(register_mcp_client)


class McpRegistrationTest(unittest.TestCase):
    def test_auto_profile_prefers_codex_project_state(self):
        with tempfile.TemporaryDirectory() as tmp:
            project = Path(tmp) / "project"
            sidecar = (
                project
                / ".codex"
                / "skills"
                / "emotion-engine-codex"
                / "scripts"
                / "emotion_engine_mcp.py"
            )
            sidecar.parent.mkdir(parents=True)
            sidecar.write_text("# server\n", encoding="utf-8")

            self.assertEqual(
                register_mcp_client.default_server_script(project, ROOT),
                sidecar,
            )
            self.assertEqual(
                register_mcp_client.default_state_file(project, "auto"),
                project / ".emotion-engine" / "codex-state.json",
            )

    def test_auto_profile_uses_generic_state_without_codex_marker(self):
        with tempfile.TemporaryDirectory() as tmp:
            project = Path(tmp) / "project"
            project.mkdir()

            self.assertEqual(
                register_mcp_client.default_state_file(project, "auto"),
                project / ".emotion-engine" / "emotion-state.json",
            )

    def test_client_commands_use_explicit_state(self):
        server = Path("/project/.codex/skills/emotion-engine-codex/scripts/emotion_engine_mcp.py")
        state = Path("/project/.emotion-engine/codex-state.json")

        self.assertEqual(
            register_mcp_client.codex_command("emotion-engine", "python3", server, state),
            [
                "codex",
                "mcp",
                "add",
                "emotion-engine",
                "--",
                "python3",
                "/project/.codex/skills/emotion-engine-codex/scripts/emotion_engine_mcp.py",
                "--state",
                "/project/.emotion-engine/codex-state.json",
            ],
        )
        self.assertEqual(
            register_mcp_client.claude_code_command("emotion-engine", "python3", server, state),
            [
                "claude",
                "mcp",
                "add",
                "--transport",
                "stdio",
                "emotion-engine",
                "--",
                "python3",
                "/project/.codex/skills/emotion-engine-codex/scripts/emotion_engine_mcp.py",
                "--state",
                "/project/.emotion-engine/codex-state.json",
            ],
        )

    def test_mcp_json_update_preserves_existing_servers(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / ".mcp.json"
            path.write_text(
                json.dumps({"mcpServers": {"other": {"command": "node", "args": ["server.js"]}}}),
                encoding="utf-8",
            )

            with contextlib.redirect_stdout(io.StringIO()):
                register_mcp_client.write_mcp_json(
                    path,
                    "emotion-engine",
                    "python3",
                    Path("/project/server.py"),
                    Path("/project/.emotion-engine/codex-state.json"),
                    dry_run=False,
                )

            data = json.loads(path.read_text(encoding="utf-8"))
            self.assertIn("other", data["mcpServers"])
            self.assertEqual(
                data["mcpServers"]["emotion-engine"],
                {
                    "command": "python3",
                    "args": [
                        "/project/server.py",
                        "--state",
                        "/project/.emotion-engine/codex-state.json",
                    ],
                },
            )

    def test_dry_run_does_not_create_project_files(self):
        with tempfile.TemporaryDirectory() as tmp:
            project = Path(tmp) / "project"
            project.mkdir()
            server = Path(tmp) / "emotion_engine_mcp.py"
            server.write_text("# server\n", encoding="utf-8")

            output = io.StringIO()
            with contextlib.redirect_stdout(output):
                register_mcp_client.main(
                    [
                        "mcp-json",
                        "--project-dir",
                        str(project),
                        "--server-script",
                        str(server),
                        "--state-profile",
                        "codex",
                        "--dry-run",
                    ]
                )

            self.assertIn("Would write", output.getvalue())
            self.assertFalse((project / ".mcp.json").exists())
            self.assertFalse((project / ".emotion-engine").exists())

    def test_project_dir_must_exist(self):
        with tempfile.TemporaryDirectory() as tmp:
            missing = Path(tmp) / "missing"

            with self.assertRaises(SystemExit):
                register_mcp_client.main(["mcp-json", "--project-dir", str(missing), "--dry-run"])

            self.assertFalse(missing.exists())


if __name__ == "__main__":
    unittest.main()
