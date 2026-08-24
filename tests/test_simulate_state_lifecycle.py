import importlib.util
import argparse
import io
import json
import sys
import tempfile
import unittest
from contextlib import redirect_stdout
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = ROOT / "scripts"
SCRIPT = SCRIPTS / "simulate_state_lifecycle.py"
CHECKER = SCRIPTS / "check_state_lifecycle.py"

sys.path.insert(0, str(SCRIPTS))
spec = importlib.util.spec_from_file_location("simulate_state_lifecycle", SCRIPT)
simulator = importlib.util.module_from_spec(spec)
spec.loader.exec_module(simulator)


class SimulateStateLifecycleTest(unittest.TestCase):
    def test_pattern_summary_is_human_readable(self):
        summary = simulator.summarize_patterns({
            "sufficient_data": True,
            "turn_count": 3,
            "had_conflict": False,
            "avg_pleasure_delta": 0.02,
            "sustained_negative": False,
            "dominance_suppressed": False,
        })

        self.assertIn("3 turns analyzed", summary)
        self.assertIn("no conflict detected", summary)
        self.assertIn("slightly positive emotional trend", summary)

    def test_json_delta_format(self):
        formatted = simulator.format_delta({"P": 0.1, "A": -0.02, "D": 0.0})

        self.assertEqual(formatted, "P +0.1000, A -0.0200, D +0.0000")

    def test_clearer_checker_entrypoint_exists(self):
        self.assertTrue(CHECKER.exists())

    def test_chinese_lifecycle_output_uses_chinese_labels(self):
        args = argparse.Namespace(
            state=None,
            resume=False,
            style="温柔但不讨好，有清晰边界",
            soul_file=None,
            turn=["谢谢你，刚才那个版本清楚很多了"],
            lang="zh-CN",
            json=False,
        )

        output = io.StringIO()
        with redirect_stdout(output):
            simulator.run_simulation(args)

        text = output.getvalue()
        self.assertIn("状态生命周期检查", text)
        self.assertIn("用户输入", text)
        self.assertIn("辅助评价", text)
        self.assertIn("会话总结", text)
        self.assertNotIn("User input", text)
        self.assertNotIn("Session Summary", text)

    def test_resume_opens_a_new_session_instead_of_replaying_closed_ids(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            state_file = str(Path(tmpdir) / "emotion-state.json")
            first = argparse.Namespace(
                state=state_file, resume=False, session_id=None, style=None,
                soul_file=None, turn=["Thanks for helping."], lang="en", json=False,
            )
            resumed = argparse.Namespace(
                state=state_file, resume=True, session_id=None, style=None,
                soul_file=None, turn=["Thanks for helping again."], lang="en", json=False,
            )

            with redirect_stdout(io.StringIO()):
                simulator.run_simulation(first)
                simulator.run_simulation(resumed)

            state = json.loads(Path(state_file).read_text(encoding="utf-8"))
            self.assertEqual(state["session_count"], 2)
            self.assertEqual(state["total_turns"], 2)
            self.assertEqual(len(state["session_ledger"]), 2)
            self.assertNotEqual(
                state["session_ledger"][0]["session_id"],
                state["session_ledger"][1]["session_id"],
            )


if __name__ == "__main__":
    unittest.main()
