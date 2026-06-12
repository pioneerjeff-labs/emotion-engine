import importlib.util
import tempfile
import unittest
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

    def test_appraise_warmth_suggests_positive_shift(self):
        state = emotion_engine_utils.default_state()

        result = emotion_engine_utils.appraise_message(
            state,
            "thank you, this was really helpful",
        )

        self.assertEqual(result["appraisal"], "warmth")
        self.assertGreater(result["suggested"]["P"], result["current"]["P"])

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
        self.assertEqual(state["emotion_log"][-1]["appraisal"], "warmth")

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


if __name__ == "__main__":
    unittest.main()
