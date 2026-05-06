import importlib.util
import sys
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = ROOT / "scripts"
SCRIPT = SCRIPTS / "prompt_preview.py"

sys.path.insert(0, str(SCRIPTS))
spec = importlib.util.spec_from_file_location("prompt_preview", SCRIPT)
prompt_preview = importlib.util.module_from_spec(spec)
spec.loader.exec_module(prompt_preview)

import emotion_engine_utils as engine


class PromptPreviewTest(unittest.TestCase):
    def test_guidance_explains_llm_task(self):
        state = engine.apply_configuration(
            engine.default_state(),
            "calm, reliable, and clearly bounded",
            "test",
        )

        guidance = prompt_preview.build_guidance(
            state,
            "Thanks, the last version is much clearer.",
        )

        self.assertIn("Current continuity state", guidance)
        self.assertIn("Advisory appraisal", guidance)
        self.assertIn("LLM task", guidance)
        self.assertIn("Treat this as a hint", guidance)

    def test_json_payload_contains_responsibilities(self):
        payload = prompt_preview.build_json_payload(
            engine.default_state(),
            "Thanks for the help.",
        )

        self.assertIn("status", payload)
        self.assertIn("advisory_appraisal", payload)
        self.assertIn("choose final PAD update", payload["llm_responsibility"])


if __name__ == "__main__":
    unittest.main()
