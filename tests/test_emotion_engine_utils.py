import importlib.util
import json
import os
import subprocess
import sys
import tempfile
import threading
import time
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
        self.assertEqual(
            emotion_engine_utils.public_status(state)["engine_version"], "2.0.0-rc.4"
        )

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

    def test_guarded_pre_turn_decay_is_idempotent_and_paused_is_noop(self):
        state = self.start_session()
        state["emotion"] = {"pleasure": 0.4, "arousal": 0.5, "dominance": 0.7}
        state, applied = emotion_engine_utils.pre_turn_decay(
            state, "test-session", "decay-once",
            character_id="test-character", relationship_id="test-relationship",
        )
        self.assertEqual(applied["status"], "applied")
        snapshot = deepcopy(state)
        state, duplicate = emotion_engine_utils.pre_turn_decay(
            state, "test-session", "decay-once",
            character_id="test-character", relationship_id="test-relationship",
        )
        self.assertEqual(duplicate["status"], "duplicate_event")
        self.assertEqual(state, snapshot)

        state["enabled"] = False
        paused_snapshot = deepcopy(state)
        state, paused = emotion_engine_utils.pre_turn_decay(
            state, "test-session", "decay-paused",
            character_id="test-character", relationship_id="test-relationship",
        )
        self.assertEqual(paused["status"], "paused")
        self.assertEqual(state, paused_snapshot)

    def test_paused_legacy_decay_and_manual_trust_update_are_exact_noops(self):
        state = self.bound_state()
        state["enabled"] = False
        snapshot = deepcopy(state)

        state, decay = emotion_engine_utils.apply_time_decay(
            state,
            character_id="test-character",
            relationship_id="test-relationship",
        )
        self.assertEqual(decay["status"], "paused")
        self.assertEqual(state, snapshot)

        state, trust_update = emotion_engine_utils.apply_manual_trust_update(
            state,
            0.02,
            "explicit host relationship judgment",
            character_id="test-character",
            relationship_id="test-relationship",
        )
        self.assertEqual(trust_update["status"], "paused")
        self.assertEqual(state, snapshot)

    def test_pause_and_resume_keep_runtime_mode_in_sync(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            state_file = Path(tmpdir) / "state.json"
            state = self.bound_state()
            state["runtime_mode"] = "always"
            emotion_engine_utils.save_state(state_file, state)

            paused = subprocess.run(
                [sys.executable, str(SCRIPT), "pause", str(state_file)],
                check=True,
                capture_output=True,
                text=True,
            )
            self.assertEqual(json.loads(paused.stdout)["runtime_mode"], "paused")
            paused_state = emotion_engine_utils.load_state(state_file)
            self.assertFalse(paused_state["enabled"])
            self.assertEqual(paused_state["runtime_mode"], "paused")

            resumed = subprocess.run(
                [
                    sys.executable,
                    str(SCRIPT),
                    "resume",
                    str(state_file),
                    "--mode",
                    "light",
                ],
                check=True,
                capture_output=True,
                text=True,
            )
            self.assertEqual(json.loads(resumed.stdout)["runtime_mode"], "light")
            resumed_state = emotion_engine_utils.load_state(state_file)
            self.assertTrue(resumed_state["enabled"])
            self.assertEqual(resumed_state["runtime_mode"], "light")
            self.assertNotIn("runtime_mode_before_pause", resumed_state)

    def test_manual_trust_update_writes_its_own_reason_without_touching_previous_log(self):
        state = self.bound_state()
        state = emotion_engine_utils.add_emotion_log(
            state,
            "turn",
            situation="previous unrelated event",
            appraisal="repair",
        )
        previous_log = deepcopy(state["emotion_log"])

        state, result = emotion_engine_utils.apply_manual_trust_update(
            state,
            0.02,
            "explicit host relationship judgment",
            character_id="test-character",
            relationship_id="test-relationship",
        )

        self.assertEqual(result["status"], "applied")
        self.assertEqual(state["emotion_log"][:-1], previous_log)
        self.assertEqual(state["emotion_log"][-1]["event_type"], "trust_update")
        self.assertEqual(
            state["emotion_log"][-1]["manual_override_reason"],
            "explicit host relationship judgment",
        )

    def test_paused_decay_and_update_trust_cli_leave_state_file_byte_identical(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            state_file = Path(tmpdir) / "emotion-state.json"
            state = self.bound_state()
            state["enabled"] = False
            emotion_engine_utils.save_state(state_file, state)
            before = state_file.read_bytes()
            identity_args = [
                "--character-id", "test-character",
                "--relationship-id", "test-relationship",
            ]

            decay = subprocess.run(
                [sys.executable, str(SCRIPT), "decay", str(state_file), *identity_args],
                text=True,
                capture_output=True,
                check=True,
            )
            self.assertEqual(json.loads(decay.stdout)["status"], "paused")
            self.assertEqual(state_file.read_bytes(), before)

            trust_update = subprocess.run(
                [
                    sys.executable,
                    str(SCRIPT),
                    "update_trust",
                    str(state_file),
                    "0.02",
                    "--host-approved",
                    "--reason",
                    "explicit host relationship judgment",
                    *identity_args,
                ],
                text=True,
                capture_output=True,
                check=True,
            )
            self.assertEqual(json.loads(trust_update.stdout)["status"], "paused")
            self.assertEqual(state_file.read_bytes(), before)

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

    def test_state_file_lock_serializes_threads_in_same_process(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            state_file = Path(tmpdir) / "emotion-state.json"
            emotion_engine_utils.save_state(state_file, self.bound_state())
            outer_acquired = threading.Event()
            inner_started = threading.Event()
            inner_acquired = threading.Event()

            def update_outer():
                with emotion_engine_utils.state_file_lock(state_file):
                    state = emotion_engine_utils.load_state_unlocked(state_file)
                    outer_acquired.set()
                    inner_started.wait(timeout=2)
                    time.sleep(0.1)
                    state["session_count"] += 1
                    emotion_engine_utils.save_state_unlocked(state_file, state)

            def update_inner():
                outer_acquired.wait(timeout=2)
                inner_started.set()
                with emotion_engine_utils.state_file_lock(state_file):
                    inner_acquired.set()
                    state = emotion_engine_utils.load_state_unlocked(state_file)
                    state["session_count"] += 1
                    emotion_engine_utils.save_state_unlocked(state_file, state)

            outer = threading.Thread(target=update_outer)
            inner = threading.Thread(target=update_inner)
            outer.start()
            inner.start()
            inner_started.wait(timeout=2)
            self.assertFalse(inner_acquired.wait(timeout=0.05))
            outer.join(timeout=3)
            inner.join(timeout=3)

            self.assertFalse(outer.is_alive())
            self.assertFalse(inner.is_alive())
            self.assertEqual(emotion_engine_utils.load_state(state_file)["session_count"], 2)

    def test_settle_trust_positive_multi_turn_trajectory_gives_positive_delta(self):
        state = self.collaborative_state()

        state, result = self.settle(state)

        self.assertEqual(result["status"], "settled")
        self.assertEqual(result["raw_delta"], 0.03)
        self.assertGreater(state["trust"], 0.1)

    def test_settle_trust_requires_event_id_and_records_successful_event(self):
        state = self.collaborative_state()
        snapshot = deepcopy(state)

        with self.assertRaisesRegex(ValueError, "session_id and event_id"):
            emotion_engine_utils.settle_trust(
                state,
                "test-session",
                character_id="test-character",
                relationship_id="test-relationship",
            )
        self.assertEqual(state, snapshot)

        state, result = emotion_engine_utils.settle_trust(
            state,
            "test-session",
            "settlement-audit-event",
            character_id="test-character",
            relationship_id="test-relationship",
        )
        self.assertEqual(result["status"], "settled")
        self.assertIn("settlement-audit-event", state["processed_event_ids"])
        self.assertEqual(result["event_id"], "settlement-audit-event")
        self.assertEqual(
            state["trust_settlements"][-1]["event_id"], "settlement-audit-event"
        )
        self.assertEqual(
            state["session_ledger"][-1]["settlement_event_id"],
            "settlement-audit-event",
        )

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

    def test_v2_migration_preserves_boundary_and_host_extension_fields(self):
        legacy = deepcopy(emotion_engine_utils.DEFAULT_STATE)
        legacy["_schema"] = emotion_engine_utils.LEGACY_STATE_SCHEMA
        legacy.pop("identity", None)
        legacy["boundary_state"] = {"pressure_count": 2, "last_boundary": "keep scope"}
        legacy["host_extension"] = {"nested": [1, {"preserve": True}]}

        migrated, _ = emotion_engine_utils.migrate_state_v2(
            legacy, "character-a", "relationship-a"
        )

        self.assertEqual(migrated["boundary_state"], legacy["boundary_state"])
        self.assertEqual(migrated["host_extension"], legacy["host_extension"])

    def test_v3_upgrade_adds_capability_bounds_active_session_and_preserves_extensions(self):
        state = self.start_session()
        state["capabilities"].remove("bounded_active_session/v1")
        state.pop("active_session_retention")
        state["host_extension"] = {"nested": [1, {"preserve": True}]}
        state["emotion_trajectory"] = [
            {"P": ((index % 7) - 3) / 10, "D": 0.5}
            for index in range(600)
        ]

        upgraded, report = emotion_engine_utils.upgrade_state_v3(state)

        self.assertEqual(report["status"], "upgrade_ready")
        self.assertEqual(report["missing_capabilities"], ["bounded_active_session/v1"])
        self.assertIn("active_session_retention", report["initialized_fields"])
        self.assertEqual(report["trajectory_entries_summarized"], 88)
        self.assertEqual(upgraded["host_extension"], state["host_extension"])
        self.assertIn("bounded_active_session/v1", upgraded["capabilities"])
        self.assertEqual(len(upgraded["emotion_trajectory"]), 512)
        self.assertEqual(
            upgraded["active_session_retention"]["trajectory_summary"]["count"],
            88,
        )

    def test_cli_upgrade_state_dry_run_and_apply_backup(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            state_file = Path(tmpdir) / "emotion-state.json"
            state = self.start_session()
            state["capabilities"].remove("bounded_active_session/v1")
            state.pop("active_session_retention")
            state["host_extension"] = {"preserve": True}
            state_file.write_text(json.dumps(state), encoding="utf-8")
            before = state_file.read_bytes()

            dry_run = subprocess.run(
                [sys.executable, str(SCRIPT), "upgrade_state", str(state_file)],
                text=True,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                check=True,
            )
            self.assertTrue(json.loads(dry_run.stdout)["dry_run"])
            self.assertEqual(state_file.read_bytes(), before)

            applied = subprocess.run(
                [
                    sys.executable,
                    str(SCRIPT),
                    "upgrade_state",
                    str(state_file),
                    "--apply",
                ],
                text=True,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                check=True,
            )
            report = json.loads(applied.stdout)
            self.assertEqual(report["status"], "upgraded")
            self.assertFalse(report["dry_run"])
            self.assertTrue(Path(report["backup_path"]).exists())
            upgraded = json.loads(state_file.read_text(encoding="utf-8"))
            backup = json.loads(Path(report["backup_path"]).read_text(encoding="utf-8"))
            self.assertIn("bounded_active_session/v1", upgraded["capabilities"])
            self.assertEqual(upgraded["host_extension"], state["host_extension"])
            self.assertNotIn("bounded_active_session/v1", backup["capabilities"])

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

    def test_log_event_uses_semantic_gate_for_task_checkpoint(self):
        state = self.start_session()
        snapshot = deepcopy(state)

        state, result = emotion_engine_utils.record_semantic_event(
            state,
            "work_checkpoint",
            session_id="test-session",
            event_id="task-log-1",
            subject="task",
            message="implementation complete and tests pass",
            memory_owner="project",
            host_approved=True,
            character_id="test-character",
            relationship_id="test-relationship",
            situation="tests passed",
        )

        self.assertEqual(result["status"], "not_recorded")
        self.assertEqual(result["decision"], "route_host_memory")
        self.assertEqual(state, snapshot)

    def test_log_event_is_exact_noop_while_paused(self):
        state = self.start_session()
        state["enabled"] = False
        snapshot = deepcopy(state)

        state, result = emotion_engine_utils.record_semantic_event(
            state,
            "repair",
            session_id="test-session",
            event_id="paused-log-1",
            subject="relationship",
            message="we repaired the mismatch",
            host_approved=True,
            character_id="test-character",
            relationship_id="test-relationship",
        )

        self.assertEqual(result["status"], "paused")
        self.assertEqual(state, snapshot)

    def test_log_event_records_host_approved_relationship_event(self):
        state = self.start_session()
        state, result = emotion_engine_utils.record_semantic_event(
            state,
            "repair",
            session_id="test-session",
            event_id="repair-log-1",
            subject="relationship",
            message="we repaired the mismatch",
            host_approved=True,
            character_id="test-character",
            relationship_id="test-relationship",
            situation="the mismatch was repaired",
        )

        self.assertEqual(result["status"], "recorded")
        self.assertEqual(state["emotion_log"][-1]["appraisal"], "repair")
        self.assertIn("repair-log-1", state["processed_event_ids"])

    def test_cli_log_event_veto_and_pause_leave_state_file_byte_identical(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            state_file = Path(tmpdir) / "emotion-state.json"
            state = self.start_session()
            emotion_engine_utils.save_state(state_file, state)
            before_task = state_file.read_bytes()
            task = subprocess.run(
                [
                    sys.executable, str(SCRIPT), "log_event", str(state_file), "work_checkpoint",
                    "--session-id", "test-session", "--event-id", "cli-task-log",
                    "--subject", "task", "--memory-owner", "project",
                    "--message", "implementation complete and tests pass",
                    "--host-approved", "--character-id", "test-character",
                    "--relationship-id", "test-relationship",
                ],
                text=True, capture_output=True, check=True,
            )
            self.assertEqual(json.loads(task.stdout)["status"], "not_recorded")
            self.assertEqual(state_file.read_bytes(), before_task)

            state["enabled"] = False
            emotion_engine_utils.save_state(state_file, state)
            before_paused = state_file.read_bytes()
            paused = subprocess.run(
                [
                    sys.executable, str(SCRIPT), "log_event", str(state_file), "repair",
                    "--session-id", "test-session", "--event-id", "cli-paused-log",
                    "--message", "we repaired the mismatch", "--host-approved",
                    "--character-id", "test-character", "--relationship-id", "test-relationship",
                ],
                text=True, capture_output=True, check=True,
            )
            self.assertEqual(json.loads(paused.stdout)["status"], "paused")
            self.assertEqual(state_file.read_bytes(), before_paused)

    def test_idempotency_retention_bounds_ledgers_and_prunes_session_bundle(self):
        state = self.bound_state()
        state["idempotency_retention"]["session_limit"] = 3
        state["idempotency_retention"]["event_limit"] = 8

        for index in range(6):
            session_id = f"session-{index}"
            state, started = emotion_engine_utils.session_start(
                state, session_id, f"start-{index}",
                character_id="test-character", relationship_id="test-relationship",
            )
            self.assertEqual(started["status"], "started")
            state, recorded = emotion_engine_utils.record_turn(
                state, 0.1, 0.3, 0.5,
                session_id=session_id,
                event_id=f"turn-{index}",
                host_approved=True,
                character_id="test-character",
                relationship_id="test-relationship",
                appraisal="repair",
                semantic_event_type="repair",
                trust_evidence={
                    "evidence_id": f"evidence-{index}",
                    "evidence_type": "conflict_repair",
                    "eligible": True,
                },
            )
            self.assertEqual(recorded["status"], "recorded")
            state, closed = emotion_engine_utils.session_end(
                state, session_id, f"end-{index}",
                character_id="test-character", relationship_id="test-relationship",
            )
            self.assertEqual(closed["status"], "closed")
            state, settled = emotion_engine_utils.settle_trust(
                state, session_id, f"settle-{index}",
                character_id="test-character", relationship_id="test-relationship",
            )
            self.assertEqual(settled["status"], "settled")

        retained_sessions = {entry["session_id"] for entry in state["session_ledger"]}
        self.assertEqual(len(state["session_ledger"]), 3)
        self.assertLessEqual(len(state["processed_event_ids"]), 8)
        self.assertEqual(retained_sessions, {"session-3", "session-4", "session-5"})
        self.assertTrue(all(
            entry["session_id"] in retained_sessions for entry in state["trust_evidence"]
        ))
        self.assertTrue(all(
            entry["session_id"] in retained_sessions for entry in state["trust_settlements"]
        ))
        self.assertEqual(state["idempotency_retention"]["pruned_sessions"], 3)
        self.assertGreater(state["idempotency_retention"]["pruned_events"], 0)

    def test_active_session_retention_bounds_detail_without_changing_patterns_or_trust(self):
        bounded = self.start_session()
        control = deepcopy(bounded)
        bounded["active_session_retention"]["trajectory_limit"] = 16
        bounded["active_session_retention"]["evidence_limit"] = 8
        control["active_session_retention"]["trajectory_limit"] = 512
        control["active_session_retention"]["evidence_limit"] = 256

        for index in range(80):
            pleasure = -0.5 if index == 5 else (0.45 if index == 65 else ((index % 7) - 3) / 10)
            evidence_type = "explicit_trust" if index % 2 == 0 else "hostility"
            arguments = {
                "session_id": "test-session",
                "event_id": f"long-turn-{index}",
                "host_approved": True,
                "persist_log": False,
                "character_id": "test-character",
                "relationship_id": "test-relationship",
                "semantic_event_type": "relationship_calibration",
                "trust_evidence": {
                    "evidence_id": f"long-evidence-{index}",
                    "evidence_type": evidence_type,
                    "weight": 0.03,
                    "eligible": True,
                },
            }
            bounded, bounded_result = emotion_engine_utils.record_turn(
                bounded, pleasure, 0.4, 0.5, **arguments
            )
            control, control_result = emotion_engine_utils.record_turn(
                control, pleasure, 0.4, 0.5, **arguments
            )
            self.assertEqual(bounded_result["status"], "state_only")
            self.assertEqual(control_result["status"], "state_only")

        retention = bounded["active_session_retention"]
        self.assertEqual(len(bounded["emotion_trajectory"]), 16)
        self.assertEqual(len(bounded["trust_evidence"]), 8)
        self.assertEqual(retention["trajectory_summary"]["count"], 64)
        self.assertEqual(retention["evidence_summaries"][0]["count"], 72)
        self.assertEqual(
            emotion_engine_utils.extract_patterns(bounded),
            emotion_engine_utils.extract_patterns(control),
        )

        bounded, bounded_closed = emotion_engine_utils.session_end(
            bounded,
            "test-session",
            "long-end",
            character_id="test-character",
            relationship_id="test-relationship",
        )
        control, control_closed = emotion_engine_utils.session_end(
            control,
            "test-session",
            "long-end",
            character_id="test-character",
            relationship_id="test-relationship",
        )
        self.assertEqual(bounded_closed["patterns"], control_closed["patterns"])
        bounded, bounded_settled = emotion_engine_utils.settle_trust(
            bounded,
            "test-session",
            "long-settle",
            character_id="test-character",
            relationship_id="test-relationship",
        )
        control, control_settled = emotion_engine_utils.settle_trust(
            control,
            "test-session",
            "long-settle",
            character_id="test-character",
            relationship_id="test-relationship",
        )
        self.assertEqual(bounded_settled["raw_delta"], control_settled["raw_delta"])
        self.assertEqual(bounded["trust"], control["trust"])
        self.assertTrue(
            bounded["active_session_retention"]["evidence_summaries"][0][
                "consumed_by_settlement_id"
            ]
        )
        audit = emotion_engine_utils.audit_state_integrity(bounded)
        self.assertTrue(audit["ok"], audit)
        self.assertEqual(audit["counts"]["summarized_trajectory"], 64)
        self.assertEqual(audit["counts"]["summarized_trust_evidence"], 72)

    def test_activation_check_reports_migration_binding_and_ready_states(self):
        legacy = deepcopy(emotion_engine_utils.DEFAULT_STATE)
        legacy["_schema"] = emotion_engine_utils.LEGACY_STATE_SCHEMA
        legacy.pop("identity", None)
        migration = emotion_engine_utils.activation_check(legacy, "/tmp/state.json")
        binding = emotion_engine_utils.activation_check(
            emotion_engine_utils.default_state(), "/tmp/state.json"
        )
        ready = emotion_engine_utils.activation_check(self.bound_state(), "/tmp/state.json")

        self.assertEqual(migration["status"], "migration_required")
        self.assertIn("--apply", migration["next_steps"]["apply"])
        self.assertEqual(binding["status"], "identity_binding_required")
        self.assertEqual(ready["status"], "ready")
        self.assertEqual(ready["engine_version"], "2.0.0-rc.4")

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
        state["session_ledger"][0]["turn_count"] = 1
        audit = emotion_engine_utils.audit_state_integrity(state)
        self.assertTrue(audit["ok"])
        self.assertEqual(audit["hard_errors"], [])
        self.assertEqual(audit["semantic_warnings"][0]["code"], "task_like_emotional_memory")

    def test_audit_detects_lifecycle_trajectory_and_settlement_corruption(self):
        state = self.collaborative_state()
        state, settled = self.settle(state)
        self.assertEqual(settled["status"], "settled")
        duplicate_settlement = deepcopy(state["trust_settlements"][0])
        duplicate_settlement["settlement_id"] = "another-settlement"
        state["trust_settlements"].append(duplicate_settlement)
        state["trust_evidence"][0]["eligible"] = False
        state["session_ledger"][0]["turn_count"] = 0
        state["emotion_trajectory"][0]["turn"] = 7
        state["emotion_trajectory"][0]["session_id"] = "wrong-session"

        audit = emotion_engine_utils.audit_state_integrity(state)
        codes = {error["code"] for error in audit["hard_errors"]}

        self.assertFalse(audit["ok"])
        self.assertIn("multiple_settlements_for_session", codes)
        self.assertIn("settlement_references_ineligible_evidence", codes)
        self.assertIn("session_ledger_turn_count_too_small", codes)
        self.assertIn("trajectory_turn_sequence", codes)
        self.assertIn("trajectory_session_mismatch", codes)

    def test_audit_reports_aggregate_task_memory_contamination(self):
        state = self.start_session()
        for index in range(3):
            state["emotion_log"].append({
                "timestamp": emotion_engine_utils.now_iso(),
                "event_type": "turn",
                "session_id": "test-session",
                "event_id": f"task-{index}",
                "subject": "task",
                "semantic_event_type": "work_checkpoint",
                "situation": "tests passed",
            })
        state["session_ledger"][0]["turn_count"] = 3

        audit = emotion_engine_utils.audit_state_integrity(state)
        warning_codes = {warning["code"] for warning in audit["semantic_warnings"]}

        self.assertTrue(audit["ok"])
        self.assertIn("high_task_like_memory_ratio", warning_codes)
        self.assertEqual(audit["counts"]["task_like_turns"], 3)

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
        self.assertEqual(plan["proposed_actions"][0]["action"], "archive_state_before_repair")
        self.assertEqual(plan["proposed_actions"][1]["action"], "migrate_state")
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
