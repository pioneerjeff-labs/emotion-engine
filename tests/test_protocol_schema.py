import json
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SCHEMA = ROOT / "spec" / "emotion-state.schema.json"
TEMPLATE = ROOT / "emotion-state-template.json"
PROTOCOL = ROOT / "docs" / "PROTOCOL.md"
GITHUB_TAP_SCHEMA = ROOT / "skills" / "emotion-engine" / "spec" / "emotion-state.schema.json"


class ProtocolSchemaTest(unittest.TestCase):
    def setUp(self):
        self.schema = json.loads(SCHEMA.read_text())
        self.template = json.loads(TEMPLATE.read_text())

    def test_template_matches_required_state_contract(self):
        self.assertEqual(self.schema["$schema"], "https://json-schema.org/draft/2020-12/schema")
        self.assertEqual(self.schema["properties"]["_schema"]["const"], "emotion-engine-state/v2")
        self.assertEqual(self.template["_schema"], "emotion-engine-state/v2")

        for field in self.schema["required"]:
            self.assertIn(field, self.template)

    def test_schema_exposes_adapter_envelopes(self):
        defs = self.schema["$defs"]

        self.assertIn("adapterEvent", defs)
        self.assertIn("adapterOutput", defs)
        self.assertEqual(
            defs["adapterEvent"]["properties"]["_schema"]["const"],
            "emotion-engine-adapter-event/v1",
        )
        self.assertEqual(
            defs["adapterOutput"]["properties"]["_schema"]["const"],
            "emotion-engine-adapter-output/v1",
        )
        self.assertIn(
            "turn_after",
            defs["adapterEvent"]["properties"]["event_type"]["enum"],
        )
        self.assertIn("oneOf", defs["adapterEvent"]["properties"]["limbicState"])
        self.assertIn("oneOf", defs["adapterEvent"]["properties"]["limbic_state"])

    def test_emotion_log_snapshots_use_compact_pad(self):
        properties = self.schema["$defs"]["emotionLogEntry"]["properties"]

        self.assertEqual(properties["before"]["$ref"], "#/$defs/compactPadState")
        self.assertEqual(properties["after"]["$ref"], "#/$defs/compactPadState")
        self.assertEqual(properties["delta"]["$ref"], "#/$defs/compactPadState")
        self.assertIn("source_refs", properties)

    def test_trust_history_stays_numeric_ledger(self):
        trust_history = self.schema["$defs"]["trustHistoryEntry"]
        properties = trust_history["properties"]

        self.assertEqual(
            self.schema["properties"]["trust_history"]["description"],
            "Numeric ledger of applied trust changes. Semantic reasons and provenance belong in emotion_log, not trust_history.",
        )
        self.assertIn("agent-to-user", self.schema["properties"]["trust"]["description"])
        self.assertFalse(trust_history["additionalProperties"])
        for semantic_field in ["reason", "source_refs", "confidence"]:
            self.assertNotIn(semantic_field, trust_history["required"])
            self.assertNotIn(semantic_field, properties)

    def test_boundary_state_is_optional_extension(self):
        boundary = self.schema["properties"]["boundary_state"]
        statuses = self.schema["$defs"]["boundaryState"]["properties"]["status"]["enum"]

        self.assertIn({"type": "null"}, boundary["oneOf"])
        self.assertIn("watch", statuses)
        self.assertIn("repairing", statuses)

    def test_protocol_documents_celiums_boundary(self):
        protocol = PROTOCOL.read_text()

        self.assertIn("Celiums Memory Adapter Boundary", protocol)
        self.assertIn("limbicState", protocol)
        self.assertIn("emotion-engine-adapter-event/v1", protocol)
        self.assertIn("emotion-engine-adapter-output/v1", protocol)

    def test_github_tap_schema_matches_root_schema(self):
        self.assertEqual(
            json.loads(GITHUB_TAP_SCHEMA.read_text()),
            self.schema,
        )


if __name__ == "__main__":
    unittest.main()
