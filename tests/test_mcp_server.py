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
    def create_active_state(self, state_file, session_id="mcp-session"):
        emotion_engine_mcp.engine.save_state(
            state_file,
            emotion_engine_mcp.engine.default_state("mcp-character", "mcp-relationship"),
        )
        emotion_engine_mcp.call_tool(
            "emotion_engine_session_start",
            {
                "state_file": str(state_file),
                "session_id": session_id,
                "event_id": f"{session_id}-start",
                "character_id": "mcp-character",
                "relationship_id": "mcp-relationship",
            },
        )

    def test_initialize_and_tool_list(self):
        initialized = emotion_engine_mcp.handle_request({"jsonrpc": "2.0", "id": 1, "method": "initialize"})

        self.assertEqual(initialized["result"]["serverInfo"]["name"], "emotion-engine")
        self.assertEqual(initialized["result"]["serverInfo"]["version"], "2.0.0-rc.4")
        self.assertIn("tools", initialized["result"]["capabilities"])

        listed = emotion_engine_mcp.handle_request({"jsonrpc": "2.0", "id": 2, "method": "tools/list"})
        tool_names = {tool["name"] for tool in listed["result"]["tools"]}

        self.assertIn("emotion_engine_status", tool_names)
        self.assertIn("emotion_engine_record_policy", tool_names)
        self.assertIn("emotion_engine_record_turn", tool_names)
        self.assertIn("emotion_engine_settle_trust", tool_names)
        self.assertIn("emotion_engine_audit_log", tool_names)
        self.assertIn("emotion_engine_compact_log", tool_names)
        self.assertIn("emotion_engine_capabilities", tool_names)
        self.assertIn("emotion_engine_evaluate_and_record_turn", tool_names)
        self.assertIn("emotion_engine_repair_plan", tool_names)
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
            self.assertEqual(content["policy"]["decision"], "respond_only")
            self.assertEqual(content["policy"]["reason"], "work_checkpoint")
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
            self.create_active_state(state_file)
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
                            "session_id": "mcp-session",
                            "event_id": "mcp-turn-1",
                            "host_approved": True,
                            "character_id": "mcp-character",
                            "relationship_id": "mcp-relationship",
                        },
                    },
                }
            )

            content = response["result"]["structuredContent"]
            self.assertEqual(content["turn"], 1)
            self.assertEqual(content["emotion"]["pleasure"], 0.12)
            self.assertTrue(state_file.exists())

            saved = json.loads(state_file.read_text(encoding="utf-8"))
            self.assertEqual(saved["_schema"], "emotion-engine-state/v3")
            self.assertEqual(saved["total_turns"], 1)
            self.assertEqual(saved["emotion_log"][-1]["appraisal"], "collaboration")

    def test_summary_returns_prompt_safe_guidance(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            state_file = Path(tmpdir) / "emotion-state.json"
            self.create_active_state(state_file)
            emotion_engine_mcp.call_tool(
                "emotion_engine_record_turn",
                {
                    "state_file": str(state_file),
                    "pleasure": 0.1,
                    "arousal": 0.3,
                    "dominance": 0.55,
                    "appraisal": "collaboration",
                    "situation": "user clarified MCP belongs to runtime only",
                    "session_id": "mcp-session",
                    "event_id": "mcp-turn-1",
                    "host_approved": True,
                    "character_id": "mcp-character",
                    "relationship_id": "mcp-relationship",
                },
            )

            summary = emotion_engine_mcp.call_tool("emotion_engine_summary", {"state_file": str(state_file)})["summary"]

            self.assertIn("tone", summary)
            self.assertIn("reply_rules", summary)
            self.assertEqual(summary["recent_memories"][-1]["appraisal"], "collaboration")
            self.assertNotIn("emotion", summary)
            self.assertNotIn("trust", summary)

    def test_audit_and_compact_log_tools(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            state_file = Path(tmpdir) / "emotion-state.json"
            self.create_active_state(state_file)
            for index in range(3):
                emotion_engine_mcp.call_tool(
                    "emotion_engine_pre_turn_decay",
                    {
                        "state_file": str(state_file),
                        "session_id": "mcp-session",
                        "event_id": f"decay-{index}",
                        "character_id": "mcp-character",
                        "relationship_id": "mcp-relationship",
                    },
                )
            emotion_engine_mcp.call_tool(
                "emotion_engine_record_turn",
                {
                    "state_file": str(state_file),
                    "pleasure": 0.0,
                    "arousal": 0.3,
                    "dominance": 0.5,
                    "appraisal": "neutral",
                    "situation": "ordinary neutral turn",
                    "salience": 0.04,
                    "session_id": "mcp-session",
                    "event_id": "mcp-turn-1",
                    "host_approved": True,
                    "character_id": "mcp-character",
                    "relationship_id": "mcp-relationship",
                },
            )

            audit = emotion_engine_mcp.call_tool("emotion_engine_audit_log", {"state_file": str(state_file)})["audit"]
            self.assertIn("log_entries", audit)
            before = json.loads(state_file.read_text(encoding="utf-8"))

            dry_run = emotion_engine_mcp.call_tool("emotion_engine_compact_log", {"state_file": str(state_file)})
            self.assertFalse(dry_run["report"]["applied"])
            self.assertEqual(json.loads(state_file.read_text(encoding="utf-8")), before)

            applied = emotion_engine_mcp.call_tool(
                "emotion_engine_compact_log",
                {"state_file": str(state_file), "apply": True},
            )
            self.assertTrue(applied["report"]["applied"])
            self.assertTrue(state_file.exists())

    def test_migration_defaults_to_dry_run_and_requires_explicit_apply(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            state_file = Path(tmpdir) / "legacy.json"
            legacy = emotion_engine_mcp.engine.default_state()
            legacy["_schema"] = emotion_engine_mcp.engine.LEGACY_STATE_SCHEMA
            legacy.pop("identity", None)
            legacy["boundary_state"] = {"last_boundary": "keep scope"}
            legacy["host_extension"] = {"preserve": [1, 2, 3]}
            state_file.write_text(json.dumps(legacy), encoding="utf-8")
            before = state_file.read_text(encoding="utf-8")

            preview = emotion_engine_mcp.call_tool(
                "emotion_engine_migrate_state",
                {
                    "state_file": str(state_file),
                    "character_id": "mcp-character",
                    "relationship_id": "mcp-relationship",
                },
            )
            self.assertTrue(preview["dry_run"])
            self.assertEqual(state_file.read_text(encoding="utf-8"), before)

            applied = emotion_engine_mcp.call_tool(
                "emotion_engine_migrate_state",
                {
                    "state_file": str(state_file),
                    "character_id": "mcp-character",
                    "relationship_id": "mcp-relationship",
                    "apply": True,
                },
            )
            self.assertEqual(applied["status"], "migrated")
            migrated = json.loads(state_file.read_text())
            self.assertEqual(migrated["_schema"], "emotion-engine-state/v3")
            self.assertEqual(migrated["boundary_state"], legacy["boundary_state"])
            self.assertEqual(migrated["host_extension"], legacy["host_extension"])
            backup = json.loads(Path(f"{state_file}.bak").read_text())
            self.assertEqual(backup["_schema"], "emotion-engine-state/v2")
            self.assertNotIn("identity", backup)

    def test_atomic_tool_routes_task_checkpoint_without_state_write(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            state_file = Path(tmpdir) / "emotion-state.json"
            self.create_active_state(state_file)
            before = state_file.read_text(encoding="utf-8")
            result = emotion_engine_mcp.call_tool(
                "emotion_engine_evaluate_and_record_turn",
                {
                    "state_file": str(state_file),
                    "event": {
                        "session_id": "mcp-session",
                        "event_id": "task-1",
                        "message": "all tests passed",
                        "subject": "task",
                        "event_type": "work_checkpoint",
                        "host_approved": True,
                        "memory_owner": "project",
                    },
                    "character_id": "mcp-character",
                    "relationship_id": "mcp-relationship",
                },
            )
            self.assertEqual(result["decision"], "route_host_memory")
            self.assertEqual(state_file.read_text(encoding="utf-8"), before)


if __name__ == "__main__":
    unittest.main()
