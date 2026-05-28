"""Tests for the Celiums adapter."""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from integrations.celiums.emotion_engine_celiums import (  # noqa: E402
    from_celiums_journal,
    from_celiums_limbic_state,
    to_celiums_journal_entries,
    to_celiums_limbic_state,
    to_celiums_turn_context,
)


def _sample_state() -> dict:
    return {
        "_schema": "emotion-engine-state/v2",
        "emotion": {"pleasure": 0.4, "arousal": 0.5, "dominance": 0.6},
        "personality_baseline": {"pleasure": 0.0, "arousal": 0.3, "dominance": 0.5},
        "character_profile": {
            "description": "warm, steady, clearly bounded",
            "interpretation": "mildly warm; calm; strongly bounded",
            "traits": ["warm", "steady", "bounded"],
        },
        "trust": 0.62,
        "trust_anchor": 0.5,
        "session_count": 4,
        "total_turns": 27,
        "last_interaction_iso": "2026-05-28T14:00:00Z",
        "emotion_log": [
            {
                "situation": "user challenged the design constructively",
                "appraisal": "collaboration",
                "relational_meaning": "disagreement felt safe",
                "follow_up_bias": "be precise and bounded",
                "salience": 0.7,
                "timestamp": "2026-05-28T14:00:00Z",
            }
        ],
        "log_limit": 200,
    }


def test_to_celiums_limbic_state_preserves_pad_and_adds_source() -> None:
    payload = to_celiums_limbic_state(_sample_state())
    assert payload["pleasure"] == 0.4
    assert payload["arousal"] == 0.5
    assert payload["dominance"] == 0.6
    assert payload["timestamp"] == "2026-05-28T14:00:00Z"
    assert payload["source"] == "emotion-engine"
    assert payload["source_schema"] == "emotion-engine-state/v2"


def test_to_celiums_limbic_state_clamps_out_of_range() -> None:
    payload = to_celiums_limbic_state({"emotion": {"pleasure": 2.0, "arousal": -3.0, "dominance": "bad"}})
    assert payload["pleasure"] == 1.0
    assert payload["arousal"] == -1.0
    assert payload["dominance"] == 0.0


def test_to_celiums_turn_context_includes_trust_tier_and_traits() -> None:
    block = to_celiums_turn_context(_sample_state())
    assert block["pad"] == {"pleasure": 0.4, "arousal": 0.5, "dominance": 0.6}
    assert block["limbic_style"] == "mildly warm; calm; strongly bounded"
    assert block["character_traits"] == ["warm", "steady", "bounded"]
    assert block["trust"]["value"] == 0.62
    assert block["trust"]["tier"] == "Trusted"
    assert block["session_count"] == 4
    assert block["total_turns"] == 27


def test_trust_tier_thresholds() -> None:
    assert to_celiums_turn_context({"trust": 0.0})["trust"]["tier"] == "New"
    assert to_celiums_turn_context({"trust": 0.3})["trust"]["tier"] == "Familiar"
    assert to_celiums_turn_context({"trust": 0.55})["trust"]["tier"] == "Trusted"
    assert to_celiums_turn_context({"trust": 0.9})["trust"]["tier"] == "Established"


def test_to_celiums_journal_entries_tags_and_shape() -> None:
    entries = to_celiums_journal_entries(_sample_state(), agent_id="agent-x")
    assert len(entries) == 1
    e = entries[0]
    assert e["agent_id"] == "agent-x"
    assert e["entry_type"] == "emotion"
    assert "emotion-engine" in e["tags"]
    assert "collaboration" in e["tags"]
    assert "Situation: user challenged the design constructively" in e["content"]
    assert "Appraisal: collaboration" in e["content"]
    assert "Meaning: disagreement felt safe" in e["content"]
    assert "Follow-up bias: be precise and bounded" in e["content"]
    assert e["importance"] == 0.7
    assert e["written_at"] == "2026-05-28T14:00:00Z"


def test_from_celiums_limbic_state_updates_emotion() -> None:
    state = {"emotion": {"pleasure": 0.0, "arousal": 0.0, "dominance": 0.0}}
    out = from_celiums_limbic_state(state, {
        "pleasure": 0.2,
        "arousal": 0.4,
        "dominance": -0.1,
        "timestamp": "2026-05-28T15:00:00Z",
    })
    assert out["emotion"] == {"pleasure": 0.2, "arousal": 0.4, "dominance": -0.1}
    assert out["last_interaction_iso"] == "2026-05-28T15:00:00Z"


def test_from_celiums_journal_appends_filtered_entries() -> None:
    state = {"emotion_log": [], "log_limit": 200}
    journal_entries = [
        {
            "entry_type": "emotion",
            "tags": ["emotion-engine", "collaboration"],
            "content": "Situation: user asked a question\nAppraisal: neutral\nMeaning: fine\nFollow-up bias: stay calm",
            "importance": 0.4,
            "written_at": "2026-05-28T16:00:00Z",
        },
        {
            "entry_type": "lesson",  # not emotion → ignored
            "tags": ["emotion-engine"],
            "content": "Situation: foo",
            "importance": 0.9,
        },
        {
            "entry_type": "emotion",
            "tags": ["other"],  # missing emotion-engine tag → ignored
            "content": "Situation: bar",
        },
    ]
    out = from_celiums_journal(state, journal_entries)
    assert len(out["emotion_log"]) == 1
    entry = out["emotion_log"][0]
    assert entry["situation"] == "user asked a question"
    assert entry["appraisal"] == "neutral"
    assert entry["relational_meaning"] == "fine"
    assert entry["follow_up_bias"] == "stay calm"
    assert entry["salience"] == 0.4
    assert entry["timestamp"] == "2026-05-28T16:00:00Z"


def test_from_celiums_journal_respects_log_limit() -> None:
    state = {"emotion_log": [{"situation": f"old{i}"} for i in range(195)], "log_limit": 200}
    new_entries = [
        {
            "entry_type": "emotion",
            "tags": ["emotion-engine"],
            "content": f"Situation: new{i}",
        }
        for i in range(10)
    ]
    out = from_celiums_journal(state, new_entries)
    assert len(out["emotion_log"]) == 200  # trimmed to limit
    assert out["emotion_log"][-1]["situation"] == "new9"


def test_roundtrip_preserves_pad_values() -> None:
    state = _sample_state()
    payload = to_celiums_limbic_state(state)
    out = from_celiums_limbic_state({"emotion": {}}, payload)
    assert out["emotion"] == state["emotion"]
