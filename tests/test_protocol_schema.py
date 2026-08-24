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
        self.assertEqual(self.schema["properties"]["_schema"]["const"], "emotion-engine-state/v3")
        self.assertEqual(self.template["_schema"], "emotion-engine-state/v3")
        self.assertIn("affective_pulse", self.template)
        self.assertIn("volatility_profile", self.template)
        self.assertEqual(self.template["identity"]["status"], "unbound")
        self.assertIn("state_identity/v1", self.template["capabilities"])

        for field in self.schema["required"]:
            self.assertIn(field, self.template)

    def test_schema_documents_affective_pulse_as_optional_extension(self):
        self.assertIn("affective_pulse", self.schema["properties"])
        self.assertIn("volatility_profile", self.schema["properties"])
        self.assertNotIn("affective_pulse", self.schema["required"])
        self.assertNotIn("volatility_profile", self.schema["required"])
        self.assertIn("affectivePulse", self.schema["$defs"])
        self.assertEqual(
            self.schema["$defs"]["emotionTrajectoryEntry"]["properties"]["pulse"]["$ref"],
            "#/$defs/affectivePulse",
        )
        self.assertEqual(
            self.schema["$defs"]["compactSnapshot"]["properties"]["affective_pulse"]["$ref"],
            "#/$defs/affectivePulse",
        )
        pulse_properties = self.schema["$defs"]["affectivePulse"]["properties"]
        self.assertEqual(pulse_properties["A"]["minimum"], -1.0)
        self.assertEqual(pulse_properties["D"]["minimum"], -1.0)

    def test_schema_exposes_adapter_envelopes(self):
        defs = self.schema["$defs"]

        self.assertIn("adapterEvent", defs)
        self.assertIn("adapterOutput", defs)
        self.assertEqual(
            defs["adapterEvent"]["properties"]["_schema"]["const"],
            "emotion-engine-adapter-event/v2",
        )
        self.assertEqual(
            defs["adapterOutput"]["properties"]["_schema"]["const"],
            "emotion-engine-adapter-output/v2",
        )
        self.assertIn(
            "turn",
            defs["adapterEvent"]["properties"]["event_type"]["enum"],
        )
        for field in ["event_id", "session_id", "character_id", "relationship_id"]:
            self.assertIn(field, defs["adapterEvent"]["required"])
        self.assertEqual(
            defs["adapterOutput"]["properties"]["state_schema"]["const"],
            "emotion-engine-state/v3",
        )
        self.assertIn("oneOf", defs["adapterEvent"]["properties"]["limbicState"])
        self.assertIn("oneOf", defs["adapterEvent"]["properties"]["limbic_state"])

    def test_emotion_log_snapshots_use_compact_pad(self):
        properties = self.schema["$defs"]["emotionLogEntry"]["properties"]

        self.assertEqual(properties["before"]["$ref"], "#/$defs/compactPadState")
        self.assertEqual(properties["after"]["$ref"], "#/$defs/compactPadState")
        self.assertEqual(properties["delta"]["$ref"], "#/$defs/compactPadDelta")
        self.assertEqual(self.schema["$defs"]["compactPadDelta"]["properties"]["A"]["minimum"], -1.0)
        self.assertEqual(self.schema["$defs"]["compactPadDelta"]["properties"]["D"]["minimum"], -1.0)
        self.assertIn("source_refs", properties)

    def test_schema_exposes_identity_session_and_evidence_ledgers(self):
        for field in [
            "identity", "capabilities", "session", "session_ledger",
            "processed_event_ids", "idempotency_retention", "trust_evidence", "trust_settlements",
        ]:
            self.assertIn(field, self.schema["required"])
        self.assertTrue(self.schema["properties"]["processed_event_ids"]["uniqueItems"])
        self.assertEqual(
            self.template["idempotency_retention"]["scope"], "retained_window"
        )
        self.assertIn("event_id", self.schema["$defs"]["trustSettlement"]["properties"])
        self.assertIn(
            "settlement_event_id",
            self.schema["$defs"]["sessionLedgerEntry"]["properties"],
        )
        self.assertIn("bounded_idempotency/v1", self.template["capabilities"])
        self.assertEqual(
            self.schema["$defs"]["trustEvidenceInput"]["properties"]["eligible"]["const"],
            True,
        )

    def test_trust_history_stays_numeric_ledger(self):
        trust_history = self.schema["$defs"]["trustHistoryEntry"]
        properties = trust_history["properties"]

        self.assertEqual(
            self.schema["properties"]["trust_history"]["description"],
            "Numeric ledger of applied trust changes. Automatic settlements reference authoritative trust_evidence ids.",
        )
        self.assertIn("agent-to-user", self.schema["properties"]["trust"]["description"])
        self.assertFalse(trust_history["additionalProperties"])
        for semantic_field in ["reason", "source_refs", "confidence"]:
            self.assertNotIn(semantic_field, trust_history["required"])
            self.assertNotIn(semantic_field, properties)
        self.assertIn("evidence_ids", properties)

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
        self.assertIn("emotion-engine-adapter-event/v2", protocol)
        self.assertIn("emotion-engine-adapter-output/v2", protocol)

    def test_github_tap_schema_matches_root_schema(self):
        self.assertEqual(
            json.loads(GITHUB_TAP_SCHEMA.read_text()),
            self.schema,
        )


if __name__ == "__main__":
    unittest.main()
