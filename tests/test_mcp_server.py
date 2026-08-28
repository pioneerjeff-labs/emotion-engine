import importlib.util
import io
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

    def write_hard_corrupt_state(self, state_file):
        state = emotion_engine_mcp.engine.default_state(
            "mcp-character",
            "mcp-relationship",
        )
        state["processed_event_ids"] = ["duplicate-event", "duplicate-event"]
        state_file.write_text(
            json.dumps(state, indent=2, sort_keys=True) + "\n",
            encoding="utf-8",
        )
        return state_file.read_bytes()

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

    def test_locked_managed_runtime_hides_state_override_and_admin_tools(self):
        listed = emotion_engine_mcp.handle_request(
            {"jsonrpc": "2.0", "id": 2, "method": "tools/list"},
            default_state_file="/tmp/owned-state.json",
            locked_state=True,
            managed_runtime=True,
        )
        tools = {tool["name"]: tool for tool in listed["result"]["tools"]}

        self.assertNotIn("emotion_engine_bind_identity", tools)
        self.assertNotIn("emotion_engine_migrate_state", tools)
        self.assertNotIn(
            "state_file",
            tools["emotion_engine_record_turn"]["inputSchema"]["properties"],
        )

    def test_locked_runtime_rejects_state_file_override(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            owned = Path(tmpdir) / "owned.json"
            foreign = Path(tmpdir) / "foreign.json"
            self.create_active_state(owned)
            self.create_active_state(foreign, session_id="foreign-session")
            before = foreign.read_bytes()

            with self.assertRaisesRegex(
                emotion_engine_mcp.JsonRpcError,
                "cannot be overridden",
            ):
                emotion_engine_mcp.handle_request(
                    {
                        "jsonrpc": "2.0",
                        "id": 3,
                        "method": "tools/call",
                        "params": {
                            "name": "emotion_engine_record_turn",
                            "arguments": {
                                "state_file": str(foreign),
                                "session_id": "foreign-session",
                                "event_id": "foreign-turn",
                                "pleasure": 0.2,
                                "arousal": 0.3,
                                "dominance": 0.5,
                                "host_approved": True,
                                "character_id": "mcp-character",
                                "relationship_id": "mcp-relationship",
                            },
                        },
                    },
                    default_state_file=str(owned),
                    locked_state=True,
                )

            self.assertEqual(foreign.read_bytes(), before)

    def test_managed_runtime_rejects_migration_apply(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            state_file = Path(tmpdir) / "legacy.json"
            legacy = emotion_engine_mcp.engine.default_state()
            legacy["_schema"] = emotion_engine_mcp.engine.LEGACY_STATE_SCHEMA
            legacy.pop("identity", None)
            state_file.write_text(json.dumps(legacy), encoding="utf-8")
            before = state_file.read_bytes()

            with self.assertRaisesRegex(
                emotion_engine_mcp.JsonRpcError,
                "owning installer transaction",
            ):
                emotion_engine_mcp.handle_request(
                    {
                        "jsonrpc": "2.0",
                        "id": 4,
                        "method": "tools/call",
                        "params": {
                            "name": "emotion_engine_migrate_state",
                            "arguments": {
                                "character_id": "mcp-character",
                                "relationship_id": "mcp-relationship",
                                "apply": True,
                            },
                        },
                    },
                    default_state_file=str(state_file),
                    locked_state=True,
                    managed_runtime=True,
                )

            self.assertEqual(state_file.read_bytes(), before)

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

    def test_tools_call_requires_id_and_object_params_without_mutating_state(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            state_file = Path(tmpdir) / "emotion-state.json"
            self.create_active_state(state_file)
            before = state_file.read_bytes()
            arguments = {
                "state_file": str(state_file),
                "session_id": "mcp-session",
                "event_id": "notification-write",
                "character_id": "mcp-character",
                "relationship_id": "mcp-relationship",
            }

            with self.assertRaisesRegex(
                emotion_engine_mcp.JsonRpcError,
                "non-null request id",
            ):
                emotion_engine_mcp.handle_request({
                    "jsonrpc": "2.0",
                    "method": "tools/call",
                    "params": {
                        "name": "emotion_engine_session_end",
                        "arguments": arguments,
                    },
                })
            self.assertEqual(state_file.read_bytes(), before)

            with self.assertRaisesRegex(
                emotion_engine_mcp.JsonRpcError,
                "params must be an object",
            ):
                emotion_engine_mcp.handle_request({
                    "jsonrpc": "2.0",
                    "id": 9,
                    "method": "tools/call",
                    "params": [],
                })

            with self.assertRaisesRegex(
                emotion_engine_mcp.JsonRpcError,
                "arguments must be an object",
            ):
                emotion_engine_mcp.handle_request({
                    "jsonrpc": "2.0",
                    "id": 10,
                    "method": "tools/call",
                    "params": {
                        "name": "emotion_engine_session_end",
                        "arguments": [],
                    },
                })
            self.assertEqual(state_file.read_bytes(), before)

    def test_stdio_rejects_array_tool_arguments_with_matching_response_id(self):
        request = {
            "jsonrpc": "2.0",
            "id": "array-arguments",
            "method": "tools/call",
            "params": {
                "name": "emotion_engine_status",
                "arguments": [],
            },
        }
        output = io.StringIO()

        emotion_engine_mcp.serve_stdio(
            input_stream=io.StringIO(json.dumps(request) + "\n"),
            output_stream=output,
        )

        response = json.loads(output.getvalue())
        self.assertEqual(response["id"], "array-arguments")
        self.assertEqual(response["error"]["code"], -32602)
        self.assertNotIn("result", response)

    def test_managed_mcp_missing_primary_fails_closed_for_reads_and_writes(self):
        calls = [
            ("emotion_engine_status", {}),
            ("emotion_engine_compact_log", {"apply": True}),
        ]
        with tempfile.TemporaryDirectory() as tmpdir:
            state_file = Path(tmpdir) / "missing.json"
            for index, (tool_name, arguments) in enumerate(calls, start=1):
                with self.subTest(tool_name=tool_name):
                    with self.assertRaises(emotion_engine_mcp.JsonRpcError) as raised:
                        emotion_engine_mcp.handle_request(
                            {
                                "jsonrpc": "2.0",
                                "id": index,
                                "method": "tools/call",
                                "params": {"name": tool_name, "arguments": arguments},
                            },
                            default_state_file=str(state_file),
                            locked_state=True,
                            managed_runtime=True,
                        )
                    self.assertEqual(raised.exception.code, -32043)
                    self.assertEqual(raised.exception.data["status"], "state_file_missing")
                    self.assertFalse(state_file.exists())
                    self.assertFalse(Path(f"{state_file}.bak").exists())

    def test_managed_mcp_writer_rejects_hard_corruption_before_mutator(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            state_file = Path(tmpdir) / "hard-corrupt.json"
            before = self.write_hard_corrupt_state(state_file)
            backup_file = Path(f"{state_file}.bak")
            backup_before = b'{"sentinel":"keep"}\n'
            backup_file.write_bytes(backup_before)
            mutator_called = False

            def mutator(state):
                nonlocal mutator_called
                mutator_called = True
                state["enabled"] = False
                return state, {"status": "mutated"}

            with self.assertRaises(emotion_engine_mcp.engine.ManagedStateError) as raised:
                emotion_engine_mcp.mutate_state_for_tool(
                    {},
                    str(state_file),
                    mutator,
                    managed_runtime=True,
                )

            self.assertEqual(raised.exception.status, "state_integrity_failed")
            self.assertFalse(mutator_called)
            self.assertEqual(state_file.read_bytes(), before)
            self.assertEqual(backup_file.read_bytes(), backup_before)

    def test_managed_mcp_writer_reports_hard_corruption_over_jsonrpc(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            state_file = Path(tmpdir) / "hard-corrupt.json"
            before = self.write_hard_corrupt_state(state_file)
            backup_file = Path(f"{state_file}.bak")
            backup_before = b'{"sentinel":"keep"}\n'
            backup_file.write_bytes(backup_before)

            with self.assertRaises(emotion_engine_mcp.JsonRpcError) as raised:
                emotion_engine_mcp.handle_request(
                    {
                        "jsonrpc": "2.0",
                        "id": 12,
                        "method": "tools/call",
                        "params": {
                            "name": "emotion_engine_session_start",
                            "arguments": {
                                "session_id": "mcp-session",
                                "event_id": "mcp-session-start",
                                "character_id": "mcp-character",
                                "relationship_id": "mcp-relationship",
                            },
                        },
                    },
                    default_state_file=str(state_file),
                    locked_state=True,
                    managed_runtime=True,
                )

            self.assertEqual(raised.exception.code, -32043)
            self.assertEqual(raised.exception.data["status"], "state_integrity_failed")
            self.assertIn(
                "duplicate_processed_event_ids",
                {item["code"] for item in raised.exception.data["hard_errors"]},
            )
            self.assertEqual(state_file.read_bytes(), before)
            self.assertEqual(backup_file.read_bytes(), backup_before)

    def test_managed_mcp_audit_reads_hard_corruption_without_mutation(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            state_file = Path(tmpdir) / "hard-corrupt.json"
            before = self.write_hard_corrupt_state(state_file)

            response = emotion_engine_mcp.handle_request(
                {
                    "jsonrpc": "2.0",
                    "id": 11,
                    "method": "tools/call",
                    "params": {
                        "name": "emotion_engine_audit_state",
                        "arguments": {},
                    },
                },
                default_state_file=str(state_file),
                locked_state=True,
                managed_runtime=True,
            )

            audit = response["result"]["structuredContent"]["audit"]
            self.assertFalse(audit["ok"])
            self.assertIn(
                "duplicate_processed_event_ids",
                {item["code"] for item in audit["hard_errors"]},
            )
            self.assertEqual(state_file.read_bytes(), before)

    def test_mcp_writer_rejects_older_v3_until_upgrade(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            state_file = Path(tmpdir) / "emotion-state.json"
            state = emotion_engine_mcp.engine.default_state(
                "mcp-character",
                "mcp-relationship",
            )
            state["capabilities"].remove("bounded_active_session/v1")
            state_file.write_text(
                json.dumps(state, indent=2, sort_keys=True) + "\n",
                encoding="utf-8",
            )
            before = state_file.read_bytes()

            with self.assertRaisesRegex(
                emotion_engine_mcp.JsonRpcError,
                "capability upgrade required",
            ):
                emotion_engine_mcp.call_tool(
                    "emotion_engine_session_start",
                    {
                        "state_file": str(state_file),
                        "session_id": "mcp-session",
                        "event_id": "mcp-session-start",
                        "character_id": "mcp-character",
                        "relationship_id": "mcp-relationship",
                    },
                )
            self.assertEqual(state_file.read_bytes(), before)


if __name__ == "__main__":
    unittest.main()
