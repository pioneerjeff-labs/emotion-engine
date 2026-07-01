import importlib.util
import json
import os
import sys
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = ROOT / "scripts"
MCP_SERVER = SCRIPTS / "emotion_engine_mcp.py"

sys.path.insert(0, str(SCRIPTS))

spec = importlib.util.spec_from_file_location("emotion_engine_mcp", MCP_SERVER)
emotion_engine_mcp = importlib.util.module_from_spec(spec)
spec.loader.exec_module(emotion_engine_mcp)


def _restore_env(name, value):
    if value is None:
        os.environ.pop(name, None)
    else:
        os.environ[name] = value


class EmotionEngineMcpTest(unittest.TestCase):
    def test_initialize_and_tool_list(self):
        initialized = emotion_engine_mcp.handle_request({"jsonrpc": "2.0", "id": 1, "method": "initialize"})

        self.assertEqual(initialized["result"]["serverInfo"]["name"], "emotion-engine")
        self.assertEqual(initialized["result"]["serverInfo"]["version"], "0.2.2")
        self.assertIn("tools", initialized["result"]["capabilities"])

        listed = emotion_engine_mcp.handle_request({"jsonrpc": "2.0", "id": 2, "method": "tools/list"})
        tool_names = {tool["name"] for tool in listed["result"]["tools"]}

        self.assertIn("emotion_engine_status", tool_names)
        self.assertIn("emotion_engine_record_policy", tool_names)
        self.assertIn("emotion_engine_record_turn", tool_names)
        self.assertIn("emotion_engine_settle_trust", tool_names)
        self.assertNotIn("emotion_engine_doctor", tool_names)
        self.assertNotIn("emotion_engine_repair", tool_names)

    def test_record_policy_is_side_effect_free(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            state_file = Path(tmpdir) / "emotion-state.json"
            response = emotion_engine_mcp.handle_request(
                {
                    "jsonrpc": "2.0",
                    "id": 1,
                    "method": "tools/call",
                    "params": {
                        "name": "emotion_engine_record_policy",
                        "arguments": {
                            "state_file": str(state_file),
                            "message": "that migration was handled well",
                            "mode": "light",
                            "contexts": ["milestone"],
                        },
                    },
                }
            )

            content = response["result"]["structuredContent"]
            self.assertEqual(content["policy"]["decision"], "record_turn")
            self.assertEqual(content["policy"]["reason"], "milestone_collaboration")
            self.assertFalse(state_file.exists())

    def test_state_resolution_matches_codex_wrapper(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            env_state = root / "env" / "codex-state.json"
            project = root / "project"
            (project / ".codex").mkdir(parents=True)
            old_cwd = Path.cwd()
            old_codex_state = os.environ.get("CODEX_EMOTION_STATE")
            old_engine_state = os.environ.get("EMOTION_ENGINE_STATE")
            old_project_dir = os.environ.get("EMOTION_ENGINE_PROJECT_DIR")
            try:
                os.environ["CODEX_EMOTION_STATE"] = str(env_state)
                os.environ["EMOTION_ENGINE_STATE"] = str(root / "engine-state.json")
                self.assertEqual(
                    os.path.realpath(emotion_engine_mcp.resolve_state_file()),
                    os.path.realpath(env_state),
                )

                os.environ.pop("CODEX_EMOTION_STATE", None)
                os.environ.pop("EMOTION_ENGINE_STATE", None)
                os.environ["EMOTION_ENGINE_PROJECT_DIR"] = str(project)
                self.assertEqual(
                    os.path.realpath(emotion_engine_mcp.resolve_state_file()),
                    os.path.realpath(project / ".emotion-engine" / "codex-state.json"),
                )

                os.environ.pop("EMOTION_ENGINE_PROJECT_DIR", None)
                os.chdir(project)
                self.assertEqual(
                    os.path.realpath(emotion_engine_mcp.resolve_state_file()),
                    os.path.realpath(project / ".emotion-engine" / "codex-state.json"),
                )
            finally:
                os.chdir(old_cwd)
                _restore_env("CODEX_EMOTION_STATE", old_codex_state)
                _restore_env("EMOTION_ENGINE_STATE", old_engine_state)
                _restore_env("EMOTION_ENGINE_PROJECT_DIR", old_project_dir)

    def test_record_turn_persists_with_existing_state_helpers(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            state_file = Path(tmpdir) / "emotion-state.json"
            response = emotion_engine_mcp.handle_request(
                {
                    "jsonrpc": "2.0",
                    "id": 1,
                    "method": "tools/call",
                    "params": {
                        "name": "emotion_engine_record_turn",
                        "arguments": {
                            "state_file": str(state_file),
                            "pleasure": 0.12,
                            "arousal": 0.34,
                            "dominance": 0.56,
                            "appraisal": "collaboration",
                            "situation": "user asked for a careful MCP boundary",
                            "salience": 0.4,
                        },
                    },
                }
            )

            content = response["result"]["structuredContent"]
            self.assertEqual(content["turn"], 1)
            self.assertEqual(content["emotion"]["pleasure"], 0.12)
            self.assertTrue(state_file.exists())

            saved = json.loads(state_file.read_text(encoding="utf-8"))
            self.assertEqual(saved["_schema"], "emotion-engine-state/v2")
            self.assertEqual(saved["total_turns"], 1)
            self.assertEqual(saved["emotion_log"][-1]["appraisal"], "collaboration")

    def test_summary_returns_prompt_safe_guidance(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            state_file = Path(tmpdir) / "emotion-state.json"
            emotion_engine_mcp.call_tool(
                "emotion_engine_record_turn",
                {
                    "state_file": str(state_file),
                    "pleasure": 0.1,
                    "arousal": 0.3,
                    "dominance": 0.55,
                    "appraisal": "collaboration",
                    "situation": "user clarified MCP belongs to runtime only",
                },
            )

            summary = emotion_engine_mcp.call_tool("emotion_engine_summary", {"state_file": str(state_file)})["summary"]

            self.assertIn("tone", summary)
            self.assertIn("reply_rules", summary)
            self.assertEqual(summary["recent_memories"][-1]["appraisal"], "collaboration")
            self.assertNotIn("emotion", summary)
            self.assertNotIn("trust", summary)


if __name__ == "__main__":
    unittest.main()
