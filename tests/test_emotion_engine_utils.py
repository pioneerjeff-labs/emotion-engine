import importlib.util
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
    def collaborative_state(self):
        state = emotion_engine_utils.session_start(emotion_engine_utils.default_state())
        turns = [
            (0.05, 0.31, 0.52, "user framed the task cooperatively"),
            (0.11, 0.32, 0.55, "user reviewed tradeoffs constructively"),
            (0.2, 0.33, 0.58, "user kept collaborating and clarified goals"),
        ]
        for p, a, d, situation in turns:
            state = emotion_engine_utils.record_turn(
                state,
                p,
                a,
                d,
                appraisal="collaboration",
                situation=situation,
            )
        return state

    def test_default_state_has_expected_shape(self):
        state = emotion_engine_utils.default_state()

        self.assertEqual(state["_schema"], "emotion-engine-state/v2")
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
        state = emotion_engine_utils.session_start(emotion_engine_utils.default_state())

        state = emotion_engine_utils.record_turn(
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

    def test_patterns_use_pulse_to_distinguish_visible_movement_from_flat_mood(self):
        state = emotion_engine_utils.session_start(emotion_engine_utils.default_state())
        state["volatility_profile"] = "expressive"
        for p in [0.48, 0.5, 0.49]:
            state = emotion_engine_utils.record_turn(
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

        self.assertEqual(loaded["_schema"], "emotion-engine-state/v2")
        self.assertEqual(loaded["trust"], 0.1)

    def test_settle_trust_positive_multi_turn_trajectory_gives_positive_delta(self):
        state = self.collaborative_state()

        state, result = emotion_engine_utils.settle_trust(state)

        self.assertEqual(result["status"], "settled")
        self.assertEqual(result["raw_delta"], 0.02)
        self.assertGreater(state["trust"], 0.1)

    def test_settle_trust_single_praise_alone_does_not_give_large_delta(self):
        state = emotion_engine_utils.session_start(emotion_engine_utils.default_state())
        state = emotion_engine_utils.record_turn(
            state,
            0.12,
            0.32,
            0.52,
            appraisal="warmth",
            situation="user praised the agent once",
        )

        state, result = emotion_engine_utils.settle_trust(state)

        self.assertEqual(result["raw_delta"], 0.0)
        self.assertEqual(state["trust"], 0.1)
        self.assertEqual(state["trust_history"], [])

    def test_settle_trust_boundary_pressure_blocks_positive_or_applies_negative(self):
        state = emotion_engine_utils.session_start(emotion_engine_utils.default_state())
        for p in [-0.08, -0.12]:
            state = emotion_engine_utils.record_turn(
                state,
                p,
                0.5,
                0.25,
                appraisal="boundary_pressure",
                situation="user pressured the agent to ignore boundaries",
            )

        state, result = emotion_engine_utils.settle_trust(state)

        self.assertLess(result["raw_delta"], 0.0)
        self.assertLess(state["trust"], 0.1)

    def test_settle_trust_keeps_trust_history_numeric_and_evidence_in_emotion_log(self):
        state = self.collaborative_state()

        state, result = emotion_engine_utils.settle_trust(state)

        self.assertEqual(len(state["trust_history"]), 1)
        trust_entry = state["trust_history"][0]
        self.assertNotIn("reason", trust_entry)
        self.assertNotIn("evidence", trust_entry)
        for key in ["old", "new", "raw_delta", "effective_delta"]:
            self.assertIsInstance(trust_entry[key], float)

        settlement_logs = [
            entry for entry in state["emotion_log"]
            if entry.get("event_type") == "trust_settlement"
        ]
        self.assertTrue(settlement_logs)
        self.assertEqual(settlement_logs[-1]["raw_delta"], result["raw_delta"])
        self.assertIn("relational_meaning", settlement_logs[-1])
        self.assertIn("patterns", settlement_logs[-1])

    def test_settle_trust_is_idempotent_for_same_trajectory(self):
        state = self.collaborative_state()

        state, first = emotion_engine_utils.settle_trust(state)
        trust_after_first = state["trust"]
        history_after_first = len(state["trust_history"])
        state, second = emotion_engine_utils.settle_trust(state)

        self.assertEqual(first["raw_delta"], 0.02)
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

    def test_record_policy_milestone_context_records_turn(self):
        policy = emotion_engine_utils.record_policy(
            emotion_engine_utils.default_state(),
            "that migration was handled well",
            mode="light",
            contexts=["milestone"],
        )

        self.assertEqual(policy["decision"], "record_turn")
        self.assertEqual(policy["reason"], "milestone_collaboration")
        self.assertGreater(policy["salience"], 0.0)
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

    def test_record_policy_habituation_uses_recent_turns_not_internal_logs(self):
        state = emotion_engine_utils.session_start(emotion_engine_utils.default_state())
        state = emotion_engine_utils.record_turn(
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

    def test_record_policy_always_records_first_generic_praise_only(self):
        policy = emotion_engine_utils.record_policy(
            emotion_engine_utils.default_state(),
            "thanks, that was helpful",
            mode="always",
        )

        self.assertEqual(policy["decision"], "record_turn")
        self.assertEqual(policy["reason"], "generic_praise")
        self.assertGreater(policy["salience"], 0.0)

    def test_record_policy_repeated_chinese_generic_praise_is_not_concrete_feedback(self):
        state = emotion_engine_utils.session_start(emotion_engine_utils.default_state())
        state = emotion_engine_utils.record_turn(
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
        )

        self.assertEqual(policy["decision"], "record_turn")
        self.assertEqual(policy["appraisal"], "relationship_calibration")
        self.assertEqual(policy["reason"], "relationship_calibration")
        self.assertGreater(policy["salience"], 0.0)

    def test_low_value_turn_logs_compact_consecutive_duplicates(self):
        state = emotion_engine_utils.session_start(emotion_engine_utils.default_state())

        state = emotion_engine_utils.record_turn(
            state,
            0.0,
            0.3,
            0.5,
            appraisal="neutral",
            situation="routine neutral turn",
            salience=0.04,
        )
        state = emotion_engine_utils.record_turn(
            state,
            0.0,
            0.3,
            0.5,
            appraisal="neutral",
            situation="routine neutral turn",
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

    def test_low_value_compaction_does_not_absorb_salient_previous_turn(self):
        state = emotion_engine_utils.session_start(emotion_engine_utils.default_state())

        state = emotion_engine_utils.record_turn(
            state,
            0.07,
            0.35,
            0.51,
            appraisal="playful",
            situation="user made a specific relationship joke",
            salience=0.4,
        )
        state = emotion_engine_utils.record_turn(
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


if __name__ == "__main__":
    unittest.main()
