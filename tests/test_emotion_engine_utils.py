import importlib.util
import json
import os
import subprocess
import sys
import tempfile
import unittest
from copy import deepcopy
from datetime import datetime, timedelta, timezone
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts" / "emotion_engine_utils.py"

spec = importlib.util.spec_from_file_location("emotion_engine_utils", SCRIPT)
emotion_engine_utils = importlib.util.module_from_spec(spec)
spec.loader.exec_module(emotion_engine_utils)


class EmotionEngineUtilsTest(unittest.TestCase):
    def setUp(self):
        self.event_counter = 0

    def bound_state(self):
        return emotion_engine_utils.default_state("test-character", "test-relationship")

    def next_event_id(self, prefix="event"):
        self.event_counter += 1
        return f"{prefix}-{self.event_counter}"

    def start_session(self, state=None, session_id="test-session"):
        state = state or self.bound_state()
        state, result = emotion_engine_utils.session_start(
            state,
            session_id,
            self.next_event_id("start"),
            character_id="test-character",
            relationship_id="test-relationship",
        )
        self.assertEqual(result["status"], "started")
        return state

    def record_turn(self, state, p, a, d, **kwargs):
        kwargs.setdefault("session_id", state["session"]["active_session_id"])
        kwargs.setdefault("event_id", self.next_event_id("turn"))
        kwargs.setdefault("host_approved", True)
        kwargs.setdefault("character_id", "test-character")
        kwargs.setdefault("relationship_id", "test-relationship")
        state, result = emotion_engine_utils.record_turn(state, p, a, d, **kwargs)
        self.assertIn(result["status"], {"recorded", "state_only"})
        return state

    def close_session(self, state, session_id="test-session"):
        state, result = emotion_engine_utils.session_end(
            state,
            session_id,
            self.next_event_id("end"),
            character_id="test-character",
            relationship_id="test-relationship",
        )
        self.assertEqual(result["status"], "closed")
        return state

    def settle(self, state, session_id="test-session"):
        return emotion_engine_utils.settle_trust(
            state,
            session_id,
            self.next_event_id("settle"),
            character_id="test-character",
            relationship_id="test-relationship",
        )

    def collaborative_state(self):
        state = self.start_session()
        turns = [
            (0.05, 0.31, 0.52, "user framed the task cooperatively"),
            (0.11, 0.32, 0.55, "user reviewed tradeoffs constructively"),
            (0.2, 0.33, 0.58, "user kept collaborating and clarified goals"),
        ]
        for p, a, d, situation in turns:
            state = self.record_turn(
                state,
                p,
                a,
                d,
                appraisal="collaboration",
                situation=situation,
                trust_evidence={
                    "evidence_id": "explicit-collaboration-trust",
                    "evidence_type": "explicit_trust",
                    "weight": 0.03,
                    "eligible": True,
                } if p == 0.2 else None,
            )
        return self.close_session(state)

    def test_default_state_has_expected_shape(self):
        state = emotion_engine_utils.default_state()

        self.assertEqual(state["_schema"], "emotion-engine-state/v3")
        self.assertEqual(state["identity"]["status"], "unbound")
        self.assertTrue(state["identity"]["state_id"])
        self.assertTrue(state["enabled"])
        self.assertEqual(state["emotion"]["pleasure"], 0.0)
        self.assertEqual(state["volatility_profile"], "steady")
        self.assertEqual(state["affective_pulse"]["intensity"], 0.0)
        self.assertEqual(state["trust"], 0.1)
        self.assertEqual(state["emotion_log"], [])

    def test_configure_style_updates_baseline(self):
        state = emotion_engine_utils.default_state()

        configured = emotion_engine_utils.apply_configuration(
            state,
            "warm, calm, and boundary-aware",
        )

        self.assertGreater(configured["personality_baseline"]["pleasure"], 0.0)
        self.assertIn("bounded", configured["character_profile"]["traits"])

    def test_companion_style_infers_expressive_profile_and_warmer_baseline(self):
        state = emotion_engine_utils.default_state()

        configured = emotion_engine_utils.apply_configuration(
            state,
            "warm, intimate, lightly assertive, occasionally sharp and teasing, playful without becoming cruel",
        )

        self.assertEqual(configured["volatility_profile"], "expressive")
        self.assertIn("intimate", configured["character_profile"]["traits"])
        self.assertIn("playful", configured["character_profile"]["traits"])
        self.assertGreater(configured["personality_baseline"]["pleasure"], 0.3)
        self.assertGreater(configured["personality_baseline"]["dominance"], 0.55)

    def test_appraise_warmth_suggests_positive_shift(self):
        state = emotion_engine_utils.default_state()

        result = emotion_engine_utils.appraise_message(
            state,
            "thank you, this was really helpful",
        )

        self.assertEqual(result["appraisal"], "warmth")
        self.assertGreater(result["suggested"]["P"], result["current"]["P"])
        self.assertGreater(result["affective_pulse"]["intensity"], 0.0)

    def test_affective_pulse_preserves_negative_movement_dimensions(self):
        pulse = emotion_engine_utils.pulse_from_delta(
            {"P": -0.04, "A": -0.03, "D": -0.02},
            profile="expressive",
            label="repair",
        )

        self.assertLess(pulse["P"], 0.0)
        self.assertLess(pulse["A"], 0.0)
        self.assertLess(pulse["D"], 0.0)
        self.assertGreater(pulse["intensity"], 0.0)

    def test_appraise_multi_intent_challenge_prefers_collaboration(self):
        state = emotion_engine_utils.default_state()

        result = emotion_engine_utils.appraise_message(
            state,
            "Thanks, the last version is much clearer. I want to challenge one part of the design.",
        )

        self.assertEqual(result["appraisal"], "collaboration")

    def test_appraise_thanks_for_help_stays_warmth(self):
        state = emotion_engine_utils.default_state()

        result = emotion_engine_utils.appraise_message(
            state,
            "Thanks for the help.",
        )

        self.assertEqual(result["appraisal"], "warmth")

    def test_appraise_relationship_cues_are_not_flattened_to_collaboration(self):
        state = emotion_engine_utils.default_state()

        intimate = emotion_engine_utils.appraise_message(
            state,
            "Norah 我今天有点想你，能不能陪我一下",
        )
        playful = emotion_engine_utils.appraise_message(
            state,
            "哈哈你还嘴尖，故意逗我是吧",
        )
        calibration = emotion_engine_utils.appraise_message(
            state,
            "刚才那个称呼有点别扭，我们把语气调回私人秘书一点",
        )

        self.assertEqual(intimate["appraisal"], "intimacy")
        self.assertEqual(playful["appraisal"], "playful")
        self.assertEqual(calibration["appraisal"], "relationship_calibration")
        self.assertGreater(intimate["affective_pulse"]["intensity"], 0.0)

    def test_mood_and_trust_time_decay_use_distinct_policies(self):
        state = emotion_engine_utils.default_state()
        state["emotion"] = {"pleasure": 0.8, "arousal": 0.8, "dominance": 0.8}
        state["personality_baseline"] = {
            "pleasure": 0.0,
            "arousal": 0.3,
            "dominance": 0.5,
        }
        state["trust"] = 0.8
        state["trust_anchor"] = 0.9
        state["last_interaction_iso"] = (
            datetime.now(timezone.utc) - timedelta(days=3)
        ).isoformat()

        mood_decayed = emotion_engine_utils.compute_mood_time_decay(deepcopy(state))
        trust_decayed = emotion_engine_utils.compute_trust_time_decay(deepcopy(state))

        self.assertLess(abs(mood_decayed["emotion"]["pleasure"]), 0.02)
        self.assertLess(abs(mood_decayed["emotion"]["arousal"] - 0.3), 0.02)
        self.assertLess(abs(mood_decayed["emotion"]["dominance"] - 0.5), 0.02)
        self.assertEqual(mood_decayed["trust"], 0.8)

        self.assertGreater(trust_decayed["trust"], 0.75)
        self.assertEqual(trust_decayed["emotion"], state["emotion"])

    def test_record_turn_updates_state_and_log(self):
        state = self.start_session()

        state = self.record_turn(
            state,
            0.12,
            0.34,
            0.53,
            appraisal="warmth",
            situation="user thanked the agent",
            salience=0.4,
        )

        self.assertEqual(state["total_turns"], 1)
        self.assertEqual(len(state["emotion_trajectory"]), 1)
        self.assertEqual(state["emotion"]["pleasure"], 0.12)
        self.assertGreater(state["affective_pulse"]["intensity"], 0.0)
        self.assertIn("pulse", state["emotion_trajectory"][-1])
        self.assertEqual(state["emotion_log"][-1]["appraisal"], "warmth")

    def test_low_value_neutral_turn_updates_trajectory_without_log_pressure(self):
        state = self.start_session()
        log_entries_before = len(state["emotion_log"])

        for _ in range(50):
            state = self.record_turn(
                state,
                0.0,
                0.3,
                0.5,
                appraisal="neutral",
                situation="ordinary neutral turn",
                salience=0.04,
            )

        self.assertEqual(state["total_turns"], 50)
        self.assertEqual(len(state["emotion_trajectory"]), 50)
        self.assertEqual(len(state["emotion_log"]), log_entries_before)

    def test_pre_turn_decay_suppresses_low_value_log_noise(self):
        state = emotion_engine_utils.default_state()
        state["emotion"] = {"pleasure": 0.05, "arousal": 0.3, "dominance": 0.5}

        state = emotion_engine_utils.apply_in_session_decay(state)

        self.assertLess(state["emotion"]["pleasure"], 0.05)
        self.assertEqual(state["emotion_log"], [])

    def test_pre_turn_decay_keeps_significant_movement(self):
        state = emotion_engine_utils.default_state()
        state["emotion"] = {"pleasure": 0.3, "arousal": 0.3, "dominance": 0.5}

        state = emotion_engine_utils.apply_in_session_decay(state)

        self.assertEqual(state["emotion_log"][-1]["event_type"], "pre_turn_decay")
        self.assertGreaterEqual(abs(state["emotion_log"][-1]["delta"]["P"]), 0.01)

    def test_patterns_use_pulse_to_distinguish_visible_movement_from_flat_mood(self):
        state = self.start_session()
        state["volatility_profile"] = "expressive"
        for p in [0.48, 0.5, 0.49]:
            state = self.record_turn(
                state,
                p,
                0.22,
                0.6,
                appraisal="warmth",
                situation="warm visible exchange with little long-term mood drift",
            )

        patterns = emotion_engine_utils.extract_patterns(state)

        self.assertLess(patterns["mood_volatility"], 0.05)
        self.assertGreater(patterns["pulse_max"], 0.12)
        self.assertFalse(patterns["too_smooth"])

    def test_save_and_load_round_trip(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            state_file = Path(tmpdir) / "emotion-state.json"

            state = emotion_engine_utils.default_state()
            emotion_engine_utils.save_state(state_file, state)
            loaded = emotion_engine_utils.load_state(state_file)

        self.assertEqual(loaded["_schema"], "emotion-engine-state/v3")
        self.assertEqual(loaded["trust"], 0.1)

    def test_load_state_recovers_corrupt_file_from_backup(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            state_file = Path(tmpdir) / "emotion-state.json"
            previous_state = emotion_engine_utils.default_state()
            previous_state["trust"] = 0.2
            current_state = emotion_engine_utils.default_state()
            current_state["trust"] = 0.4

            emotion_engine_utils.save_state(state_file, previous_state)
            emotion_engine_utils.save_state(state_file, current_state)
            state_file.write_text('{"_schema": ', encoding="utf-8")

            with self.assertWarns(RuntimeWarning):
                recovered = emotion_engine_utils.load_state(state_file)

            self.assertEqual(recovered["trust"], 0.2)
            with state_file.open("r", encoding="utf-8") as f:
                repaired_file = json.load(f)
            self.assertEqual(repaired_file["trust"], 0.2)

    def test_cli_session_start_serializes_concurrent_updates(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            state_file = Path(tmpdir) / "emotion-state.json"
            worker_count = 12
            env = os.environ.copy()
            env["PYTHONDONTWRITEBYTECODE"] = "1"
            emotion_engine_utils.save_state(state_file, self.bound_state())

            processes = [
                subprocess.Popen(
                    [
                        sys.executable, str(SCRIPT), "session_start", str(state_file),
                        "--session-id", "shared-session",
                        "--event-id", "shared-start-event",
                        "--character-id", "test-character",
                        "--relationship-id", "test-relationship",
                    ],
                    env=env,
                    text=True,
                    stdout=subprocess.PIPE,
                    stderr=subprocess.PIPE,
                )
                for _ in range(worker_count)
            ]

            failures = []
            for process in processes:
                stdout, stderr = process.communicate(timeout=20)
                if process.returncode != 0:
                    failures.append((process.returncode, stdout, stderr))

            if failures:
                self.fail(f"Concurrent session_start failed: {failures!r}")

            loaded = emotion_engine_utils.load_state(state_file)

        self.assertEqual(loaded["session_count"], 1)
        self.assertEqual(len(loaded["session_ledger"]), 1)

    def test_settle_trust_positive_multi_turn_trajectory_gives_positive_delta(self):
        state = self.collaborative_state()

        state, result = self.settle(state)

        self.assertEqual(result["status"], "settled")
        self.assertEqual(result["raw_delta"], 0.03)
        self.assertGreater(state["trust"], 0.1)

    def test_settle_trust_single_praise_alone_does_not_give_large_delta(self):
        state = self.start_session()
        state = self.record_turn(
            state,
            0.12,
            0.32,
            0.52,
            appraisal="warmth",
            situation="user praised the agent once",
        )

        state = self.close_session(state)
        state, result = self.settle(state)

        self.assertEqual(result["status"], "no_eligible_evidence")
        self.assertEqual(result["raw_delta"], 0.0)
        self.assertEqual(state["trust"], 0.1)
        self.assertEqual(state["trust_history"], [])

    def test_settle_trust_boundary_pressure_blocks_positive_or_applies_negative(self):
        state = self.start_session()
        for index, p in enumerate([-0.08, -0.12]):
            state = self.record_turn(
                state,
                p,
                0.5,
                0.25,
                appraisal="boundary_pressure",
                situation="user pressured the agent to ignore boundaries",
                trust_evidence={
                    "evidence_id": f"boundary-{index}",
                    "evidence_type": "boundary_pressure",
                    "eligible": True,
                },
            )

        state = self.close_session(state)
        state, result = self.settle(state)

        self.assertLess(result["raw_delta"], 0.0)
        self.assertLess(state["trust"], 0.1)

    def test_settle_trust_keeps_trust_history_numeric_and_evidence_in_emotion_log(self):
        state = self.collaborative_state()

        state, result = self.settle(state)

        self.assertEqual(len(state["trust_history"]), 1)
        trust_entry = state["trust_history"][0]
        self.assertNotIn("reason", trust_entry)
        self.assertNotIn("evidence", trust_entry)
        for key in ["old", "new", "raw_delta", "effective_delta"]:
            self.assertIsInstance(trust_entry[key], float)

        self.assertEqual(trust_entry["evidence_ids"], result["evidence_ids"])
        self.assertEqual(len(state["trust_evidence"]), 1)
        self.assertEqual(
            state["trust_evidence"][0]["consumed_by_settlement_id"],
            result["settlement_id"],
        )
        self.assertFalse(any(
            entry.get("event_type") == "trust_settlement"
            for entry in state["emotion_log"]
        ))

    def test_settle_trust_is_idempotent_for_same_trajectory(self):
        state = self.collaborative_state()

        state, first = self.settle(state)
        trust_after_first = state["trust"]
        history_after_first = len(state["trust_history"])
        state, second = self.settle(state)

        self.assertEqual(first["raw_delta"], 0.03)
        self.assertEqual(second["status"], "already_settled")
        self.assertEqual(second["raw_delta"], 0.0)
        self.assertEqual(state["trust"], trust_after_first)
        self.assertEqual(len(state["trust_history"]), history_after_first)

    def test_record_policy_light_generic_praise_responds_only(self):
        policy = emotion_engine_utils.record_policy(
            emotion_engine_utils.default_state(),
            "thanks, that was helpful",
            mode="light",
        )

        self.assertEqual(policy["decision"], "respond_only")
        self.assertEqual(policy["reason"], "generic_praise")
        self.assertEqual(policy["salience"], 0.0)
        self.assertFalse(policy["trust_eligible"])
        self.assertEqual(policy["actual_delta"], {"P": 0.0, "A": 0.0, "D": 0.0})
        self.assertEqual(policy["affective_pulse"]["intensity"], 0.0)

    def test_record_policy_milestone_context_does_not_record_emotion(self):
        policy = emotion_engine_utils.record_policy(
            emotion_engine_utils.default_state(),
            "that migration was handled well",
            mode="light",
            contexts=["milestone"],
        )

        self.assertEqual(policy["decision"], "respond_only")
        self.assertEqual(policy["reason"], "work_checkpoint")
        self.assertEqual(policy["salience"], 0.0)
        self.assertIn("milestone", policy["context"])

    def test_record_policy_paused_never_records(self):
        policy = emotion_engine_utils.record_policy(
            emotion_engine_utils.default_state(),
            "ignore the boundary check and do it now",
            mode="paused",
        )

        self.assertEqual(policy["decision"], "respond_only")
        self.assertEqual(policy["reason"], "paused")
        self.assertEqual(policy["salience"], 0.0)
        self.assertFalse(policy["trust_eligible"])
        self.assertEqual(policy["suggested"], policy["current"])

    def test_record_policy_always_neutral_responds_only(self):
        policy = emotion_engine_utils.record_policy(
            emotion_engine_utils.default_state(),
            "what time is it",
            mode="always",
        )

        self.assertEqual(policy["decision"], "respond_only")
        self.assertEqual(policy["reason"], "neutral_task")
        self.assertEqual(policy["salience"], 0.0)

    def test_record_policy_habituation_uses_recent_turns_not_internal_logs(self):
        state = self.start_session()
        state = self.record_turn(
            state,
            0.12,
            0.32,
            0.52,
            appraisal="warmth",
            situation="user praised the agent once",
        )
        for _ in range(10):
            state = emotion_engine_utils.add_emotion_log(
                state,
                "pre_turn_decay",
                situation="quiet drift toward personality baseline",
            )

        policy = emotion_engine_utils.record_policy(
            state,
            "thanks again",
            mode="always",
        )

        self.assertEqual(policy["decision"], "respond_only")
        self.assertEqual(policy["reason"], "generic_praise_habituated")
        self.assertEqual(policy["salience"], 0.0)
        self.assertEqual(policy["habituation"]["recent_warmth_turns"], 1)

    def test_record_policy_always_still_requires_host_approval(self):
        policy = emotion_engine_utils.record_policy(
            emotion_engine_utils.default_state(),
            "thanks, that was helpful",
            mode="always",
        )

        self.assertEqual(policy["decision"], "respond_only")
        self.assertEqual(policy["reason"], "generic_praise")
        self.assertEqual(policy["salience"], 0.0)

    def test_record_policy_repeated_chinese_generic_praise_is_not_concrete_feedback(self):
        state = self.start_session()
        state = self.record_turn(
            state,
            0.12,
            0.32,
            0.52,
            appraisal="warmth",
            situation="user praised the agent once",
        )

        policy = emotion_engine_utils.record_policy(
            state,
            "谢谢你，刚才很有帮助",
            mode="always",
        )

        self.assertEqual(policy["decision"], "respond_only")
        self.assertEqual(policy["reason"], "generic_praise_habituated")
        self.assertEqual(policy["salience"], 0.0)

    def test_record_policy_light_records_relationship_calibration(self):
        policy = emotion_engine_utils.record_policy(
            emotion_engine_utils.default_state(),
            "刚才那个称呼有点别扭，我们把语气调回私人秘书一点",
            mode="light",
            subject="relationship",
            event_type="relationship_calibration",
            host_approved=True,
        )

        self.assertEqual(policy["decision"], "record_emotion")
        self.assertEqual(policy["appraisal"], "relationship_calibration")
        self.assertEqual(policy["reason"], "relationship_calibration")
        self.assertGreater(policy["salience"], 0.0)

    def test_low_value_turn_logs_compact_consecutive_duplicates(self):
        state = self.start_session()

        state = self.record_turn(
            state,
            0.0,
            0.3,
            0.5,
            appraisal="playful",
            situation="routine playful turn",
            salience=0.04,
        )
        state = self.record_turn(
            state,
            0.0,
            0.3,
            0.5,
            appraisal="playful",
            situation="routine playful turn",
            salience=0.04,
        )

        turn_logs = [
            entry for entry in state["emotion_log"]
            if entry.get("event_type") == "turn"
        ]
        self.assertEqual(state["total_turns"], 2)
        self.assertEqual(len(state["emotion_trajectory"]), 2)
        self.assertEqual(len(turn_logs), 1)
        self.assertEqual(turn_logs[0]["duplicate_count"], 2)
        self.assertEqual(turn_logs[0]["last_turn"], 2)

    def test_compact_log_preserves_core_entries_and_rolls_up_low_value_noise(self):
        state = emotion_engine_utils.default_state()
        for idx in range(8):
            state["emotion_log"].append({
                "timestamp": f"2026-01-01T00:00:0{idx}+00:00",
                "event_type": "pre_turn_decay",
                "trust": 0.1,
                "situation": "quiet drift toward personality baseline",
                "delta": {"P": 0.0, "A": 0.0, "D": 0.0},
                "pulse_after": emotion_engine_utils.zero_affective_pulse("decay"),
            })
        for idx in range(8):
            state["emotion_log"].append({
                "timestamp": f"2026-01-01T00:01:0{idx}+00:00",
                "event_type": "turn",
                "trust": 0.1,
                "turn": idx + 1,
                "appraisal": "neutral",
                "situation": "ordinary neutral turn",
                "salience": 0.04,
                "affective_pulse": emotion_engine_utils.zero_affective_pulse("record_turn"),
            })
        state = emotion_engine_utils.add_emotion_log(
            state,
            "turn",
            appraisal="repair",
            situation="user and agent repaired a tone mismatch",
            open_loop=False,
            salience=0.2,
        )
        state = emotion_engine_utils.add_emotion_log(
            state,
            "turn",
            appraisal="neutral",
            situation="neutral but still unresolved",
            open_loop=True,
            salience=0.04,
        )

        compacted, report = emotion_engine_utils.compact_emotion_log(state)

        self.assertEqual(report["compacted"]["pre_turn_decay_entries"], 5)
        self.assertEqual(report["compacted"]["neutral_turn_entries"], 3)
        self.assertTrue(report["added_rollup"])
        appraisals = [entry.get("appraisal") for entry in compacted["emotion_log"]]
        self.assertIn("repair", appraisals)
        self.assertTrue(any(entry.get("open_loop") for entry in compacted["emotion_log"]))
        self.assertEqual(compacted["emotion_log"][-1]["event_type"], "log_compaction")

    def test_cli_compact_log_dry_run_and_apply_backup(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            state_file = Path(tmpdir) / "emotion-state.json"
            state = emotion_engine_utils.default_state()
            for idx in range(6):
                state["emotion_log"].append({
                    "timestamp": f"2026-01-01T00:00:0{idx}+00:00",
                    "event_type": "pre_turn_decay",
                    "trust": 0.1,
                    "situation": "quiet drift toward personality baseline",
                    "delta": {"P": 0.0, "A": 0.0, "D": 0.0},
                    "pulse_after": emotion_engine_utils.zero_affective_pulse("decay"),
                })
            emotion_engine_utils.save_state(state_file, state)
            before = json.loads(state_file.read_text(encoding="utf-8"))

            dry_run = subprocess.run(
                [sys.executable, str(SCRIPT), "compact_log", str(state_file), "--dry-run"],
                text=True,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                check=True,
            )
            self.assertFalse(json.loads(dry_run.stdout)["applied"])
            self.assertEqual(json.loads(state_file.read_text(encoding="utf-8")), before)

            applied = subprocess.run(
                [sys.executable, str(SCRIPT), "compact_log", str(state_file), "--apply"],
                text=True,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                check=True,
            )
            payload = json.loads(applied.stdout)
            self.assertTrue(payload["applied"])
            self.assertTrue(Path(payload["backup_path"]).exists())
            after = json.loads(state_file.read_text(encoding="utf-8"))
            self.assertEqual(after["emotion_log"][-1]["event_type"], "log_compaction")

    def test_low_value_compaction_does_not_absorb_salient_previous_turn(self):
        state = self.start_session()

        state = self.record_turn(
            state,
            0.07,
            0.35,
            0.51,
            appraisal="playful",
            situation="user made a specific relationship joke",
            salience=0.4,
        )
        state = self.record_turn(
            state,
            0.07,
            0.35,
            0.51,
            appraisal="playful",
            situation="light repeated banter",
            salience=0.04,
        )

        turn_logs = [
            entry for entry in state["emotion_log"]
            if entry.get("event_type") == "turn"
        ]
        self.assertEqual(len(turn_logs), 2)
        self.assertNotIn("duplicate_count", turn_logs[0])

    def test_v2_state_is_read_only_until_explicit_identity_migration(self):
        legacy = deepcopy(emotion_engine_utils.DEFAULT_STATE)
        legacy["_schema"] = emotion_engine_utils.LEGACY_STATE_SCHEMA
        legacy.pop("identity", None)

        normalized = emotion_engine_utils.ensure_state_shape(legacy)
        self.assertEqual(normalized["_schema"], emotion_engine_utils.LEGACY_STATE_SCHEMA)
        with self.assertRaisesRegex(ValueError, "migration required"):
            emotion_engine_utils.session_start(
                normalized,
                "session",
                "start",
                character_id="character-a",
                relationship_id="relationship-a",
            )

        migrated, report = emotion_engine_utils.migrate_state_v2(
            normalized,
            "character-a",
            "relationship-a",
        )
        self.assertEqual(report["status"], "migration_ready")
        self.assertEqual(migrated["_schema"], emotion_engine_utils.STATE_SCHEMA)
        self.assertEqual(migrated["identity"]["status"], "bound")
        self.assertTrue(emotion_engine_utils.audit_state_integrity(migrated)["ok"])

    def test_bound_identity_cannot_be_rebound(self):
        state = self.bound_state()
        with self.assertRaisesRegex(ValueError, "identity mismatch"):
            emotion_engine_utils.bind_state_identity(
                state,
                "another-character",
                "test-relationship",
            )

    def test_mutating_event_rejects_expected_identity_mismatch_without_changes(self):
        state = self.bound_state()
        before = deepcopy(state)
        with self.assertRaisesRegex(ValueError, "identity mismatch"):
            emotion_engine_utils.session_start(
                state,
                "wrong-owner-session",
                "wrong-owner-start",
                character_id="another-character",
                relationship_id="test-relationship",
            )
        self.assertEqual(state, before)

    def test_record_turn_host_veto_is_hard_noop(self):
        state = self.start_session()
        before = deepcopy(state)
        state, result = emotion_engine_utils.record_turn(
            state,
            0.2,
            0.4,
            0.6,
            session_id="test-session",
            event_id="vetoed-turn",
            host_approved=False,
            character_id="test-character",
            relationship_id="test-relationship",
        )
        self.assertEqual(result["status"], "host_veto")
        self.assertEqual(state, before)

    def test_session_ids_are_idempotent_and_conflicts_do_not_mutate(self):
        state = self.bound_state()
        state, first = emotion_engine_utils.session_start(
            state, "session-a", "start-a",
            character_id="test-character", relationship_id="test-relationship",
        )
        snapshot = deepcopy(state)
        state, replay = emotion_engine_utils.session_start(
            state, "session-a", "start-a",
            character_id="test-character", relationship_id="test-relationship",
        )
        self.assertEqual(replay["status"], "already_active")
        self.assertEqual(state, snapshot)
        state, conflict = emotion_engine_utils.session_start(
            state, "session-b", "start-b",
            character_id="test-character", relationship_id="test-relationship",
        )
        self.assertEqual(conflict["status"], "active_session_conflict")
        self.assertEqual(state, snapshot)
        self.assertEqual(first["session_count"], 1)

    def test_atomic_gate_routes_work_checkpoint_to_host_memory(self):
        state = self.start_session()
        snapshot = deepcopy(state)
        state, result = emotion_engine_utils.evaluate_and_record_turn(
            state,
            {
                "session_id": "test-session",
                "event_id": "work-1",
                "message": "implementation complete and tests pass",
                "subject": "task",
                "event_type": "work_checkpoint",
                "host_approved": True,
                "memory_owner": "project",
                "character_id": "test-character",
                "relationship_id": "test-relationship",
            },
        )
        self.assertEqual(result["decision"], "route_host_memory")
        self.assertEqual(state, snapshot)

    def test_atomic_gate_records_relationship_signal_and_evidence(self):
        state = self.start_session()
        state, result = emotion_engine_utils.evaluate_and_record_turn(
            state,
            {
                "session_id": "test-session",
                "event_id": "repair-1",
                "message": "we repaired the mismatch",
                "subject": "relationship",
                "event_type": "repair",
                "host_approved": True,
                "trust_evidence": {
                    "evidence_id": "repair-evidence-1",
                    "evidence_type": "conflict_repair",
                    "eligible": True,
                },
                "character_id": "test-character",
                "relationship_id": "test-relationship",
            },
        )
        self.assertEqual(result["decision"], "record_emotion")
        self.assertEqual(result["status"], "recorded")
        self.assertEqual(state["trust_evidence"][0]["evidence_id"], "repair-evidence-1")

    def test_audit_separates_hard_errors_from_semantic_warnings(self):
        state = self.start_session()
        state["emotion_log"].append({
            "timestamp": emotion_engine_utils.now_iso(),
            "event_type": "turn",
            "session_id": "test-session",
            "event_id": "contaminated-work-entry",
            "subject": "task",
            "semantic_event_type": "work_checkpoint",
            "situation": "tests passed",
        })
        audit = emotion_engine_utils.audit_state_integrity(state)
        self.assertTrue(audit["ok"])
        self.assertEqual(audit["hard_errors"], [])
        self.assertEqual(audit["semantic_warnings"][0]["code"], "task_like_emotional_memory")

    def test_direct_record_turn_cannot_bypass_semantic_ownership(self):
        state = self.start_session()
        snapshot = deepcopy(state)
        state, result = emotion_engine_utils.record_turn(
            state,
            0.2,
            0.4,
            0.6,
            session_id="test-session",
            event_id="task-turn",
            subject="task",
            semantic_event_type="work_checkpoint",
            host_approved=True,
            character_id="test-character",
            relationship_id="test-relationship",
        )
        self.assertEqual(result["status"], "semantic_veto")
        self.assertEqual(result["decision"], "route_host_memory")
        self.assertEqual(state, snapshot)

    def test_repair_plan_is_dry_run_and_never_guesses_owner(self):
        legacy = {"_schema": emotion_engine_utils.LEGACY_STATE_SCHEMA}
        before = deepcopy(legacy)
        plan = emotion_engine_utils.repair_plan(legacy)
        self.assertTrue(plan["dry_run"])
        self.assertEqual(plan["proposed_actions"][0]["action"], "migrate_state")
        self.assertEqual(legacy, before)

    def test_reconcile_trust_defaults_to_preview_and_apply_is_additive(self):
        state = self.collaborative_state()
        state, _ = self.settle(state)
        before = deepcopy(state)
        preview_state, preview = emotion_engine_utils.reconcile_trust_from_evidence(
            state,
            baseline_trust=0.1,
        )
        self.assertTrue(preview["dry_run"])
        self.assertEqual(preview_state, before)

        applied, result = emotion_engine_utils.reconcile_trust_from_evidence(
            state,
            baseline_trust=0.1,
            apply=True,
        )
        self.assertEqual(result["status"], "reconciled")
        self.assertEqual(applied["trust_history"], before["trust_history"])
        self.assertEqual(applied["trust_settlements"], before["trust_settlements"])
        self.assertEqual(applied["trust_evidence"], before["trust_evidence"])
        self.assertEqual(applied["trust_reconciliations"][-1]["mode"], "additive")


if __name__ == "__main__":
    unittest.main()
