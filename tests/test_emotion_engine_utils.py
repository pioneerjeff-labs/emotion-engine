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


if __name__ == "__main__":
    unittest.main()
