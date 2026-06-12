import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
EXAMPLE = ROOT / "examples" / "minimal-agent"
SCRIPT = EXAMPLE / "run_demo.py"
README = EXAMPLE / "README.md"
TURNS = EXAMPLE / "turns.json"


class MinimalAgentExampleTest(unittest.TestCase):
    def test_files_exist(self):
        self.assertTrue(SCRIPT.exists())
        self.assertTrue(README.exists())
        self.assertTrue(TURNS.exists())

    def test_turns_include_collaboration_and_boundary_pressure(self):
        turns = json.loads(TURNS.read_text(encoding="utf-8"))
        appraisals = {
            turn["mock_llm_decision"]["final_appraisal"]
            for turn in turns
        }

        self.assertIn("collaboration", appraisals)
        self.assertIn("boundary_pressure", appraisals)

    def test_demo_runs_and_writes_valid_state(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            state_file = Path(tmpdir) / "emotion-state.json"
            result = subprocess.run(
                [
                    sys.executable,
                    str(SCRIPT),
                    "--state",
                    str(state_file),
                ],
                cwd=ROOT,
                text=True,
                capture_output=True,
                check=True,
            )

            output = result.stdout
            self.assertIn("Minimal Emotion Engine Agent Loop", output)
            self.assertIn("build prompt prelude", output)
            self.assertIn("mock LLM final decision", output)
            self.assertIn("record_turn", output)
            self.assertIn("settle_trust", output)
            self.assertNotIn("character style configured", output)
            self.assertNotIn("new session initialized", output)
            self.assertNotIn("quiet drift toward personality baseline", output)
            self.assertIn("- Recent compact memories: none yet", output)

            state = json.loads(state_file.read_text(encoding="utf-8"))
            self.assertEqual(state["_schema"], "emotion-engine-state/v2")
            self.assertEqual(state["total_turns"], 2)
            self.assertGreaterEqual(len(state["emotion_log"]), 2)
            self.assertEqual(state["emotion_trajectory"][-1]["appraisal"], "boundary_pressure")

    def test_readme_command_and_root_links_are_valid(self):
        example_readme = README.read_text(encoding="utf-8")
        root_readme = (ROOT / "README.md").read_text(encoding="utf-8")
        zh_readme = (ROOT / "README.zh-CN.md").read_text(encoding="utf-8")

        self.assertIn("python3 examples/minimal-agent/run_demo.py", example_readme)
        self.assertIn("[examples/minimal-agent](examples/minimal-agent)", root_readme)
        self.assertIn("[examples/minimal-agent](examples/minimal-agent)", zh_readme)
        self.assertTrue((ROOT / "examples" / "minimal-agent" / "run_demo.py").exists())


if __name__ == "__main__":
    unittest.main()
