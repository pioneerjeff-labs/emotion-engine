import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
DEMO = ROOT / "demo"
DEMO_INDEX = DEMO / "index.html"


class DemoStaticTest(unittest.TestCase):
    def test_demo_files_exist(self):
        self.assertTrue(DEMO_INDEX.exists())
        self.assertTrue((DEMO / "README.md").exists())
        self.assertTrue((DEMO / "screenshot.png").exists())
        self.assertTrue((DEMO / "screenshot.zh-CN.png").exists())

    def test_demo_reuses_repository_assets(self):
        html = DEMO_INDEX.read_text(encoding="utf-8")

        self.assertIn("../assets/emotion-engine-mark.svg", html)
        self.assertNotIn('src="assets/emotion-engine-mark.svg"', html)
        self.assertFalse((DEMO / "assets").exists())

    def test_demo_explains_scripted_comparison(self):
        html = DEMO_INDEX.read_text(encoding="utf-8")
        readme = (ROOT / "README.md").read_text(encoding="utf-8")

        self.assertIn("Chat history remembers what happened", html)
        self.assertIn("Emotion Engine remembers how it felt", html)
        self.assertIn("Mood only is an internal ablation view, not an install option", html)
        self.assertIn("Default integrated state package", html)
        self.assertIn("anonymized and adapted traces from prior LLM interaction experiments", readme)
        self.assertIn("[Try the live demo](https://pioneerjeff-labs.github.io/emotion-engine/demo/)", readme)
        self.assertIn("https://pioneerjeff-labs.github.io/emotion-engine/demo/", readme)
        self.assertIn("the LLM decides; Emotion Engine remembers", readme)
        self.assertIn("[INSTALL_WITH_AGENT.md](INSTALL_WITH_AGENT.md)", readme)
        self.assertIn("data-prompt=\"plain\"", html)
        self.assertIn("data-prompt=\"engine\"", html)

    def test_demo_uses_character_positioning(self):
        html = DEMO_INDEX.read_text(encoding="utf-8")

        self.assertIn("Fictional character", html)
        self.assertIn("虚构角色", html)
        self.assertNotIn("Personal assistant", html)

    def test_agent_install_prompt_exists(self):
        install_doc = (ROOT / "INSTALL_WITH_AGENT.md").read_text(encoding="utf-8")

        self.assertIn("Install Emotion Engine into this project as a local state sidecar.", install_doc)
        self.assertIn("Use the minimal-agent example first.", install_doc)
        self.assertIn("Keep state in .emotion-engine/emotion-state.json.", install_doc)
        self.assertIn("Do not send state to any remote service.", install_doc)
        self.assertIn("Show me a prompt preview before changing my app code.", install_doc)


if __name__ == "__main__":
    unittest.main()
