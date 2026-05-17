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

        self.assertIn("Chat history remembers what happened", html)
        self.assertIn("Emotion Engine remembers how it felt", html)
        self.assertIn("anonymized and adapted traces from prior LLM interaction experiments", (ROOT / "README.md").read_text(encoding="utf-8"))
        self.assertIn("[Try the live demo](https://pioneerjeff-labs.github.io/emotion-engine/demo/)", (ROOT / "README.md").read_text(encoding="utf-8"))
        self.assertIn("https://pioneerjeff-labs.github.io/emotion-engine/demo/", (ROOT / "README.md").read_text(encoding="utf-8"))
        self.assertIn("the LLM decides; Emotion Engine remembers", (ROOT / "README.md").read_text(encoding="utf-8"))
        self.assertIn("data-prompt=\"plain\"", html)
        self.assertIn("data-prompt=\"engine\"", html)

    def test_demo_uses_character_positioning(self):
        html = DEMO_INDEX.read_text(encoding="utf-8")

        self.assertIn("Fictional character", html)
        self.assertIn("虚构角色", html)
        self.assertNotIn("Personal assistant", html)


if __name__ == "__main__":
    unittest.main()
