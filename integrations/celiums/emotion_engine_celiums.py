"""
Celiums adapter for Emotion Engine.

Bridges `emotion-engine-state/v2` (local JSON file) with Celiums' server-side
limbic state and model-scoped journal. Pure functions: no runtime dependency
on Celiums for users who don't need the bridge.

The adapter does two jobs:

1. Project an Emotion Engine state into the payloads Celiums expects
   (`limbicState` for `turn_after`, journal entries for `journal_write`).
2. Ingest Celiums' `limbicState` and journal entries back into the local
   Emotion Engine state, so the JSON file can stay authoritative for users
   who run Celiums as the persistent backend.

This is *not* a memory adapter. Long-term memory still lives in Celiums via
`remember`/`recall`. This adapter is only for the emotional-continuity layer.
"""

from __future__ import annotations

from typing import Any, Iterable, Optional


SCHEMA_VERSION = "emotion-engine-state/v2"

_TRUST_TIER_THRESHOLDS = (
    (0.75, "Established"),
    (0.5, "Trusted"),
    (0.25, "Familiar"),
    (0.0, "New"),
)


def _trust_tier(trust: float) -> str:
    for threshold, label in _TRUST_TIER_THRESHOLDS:
        if trust >= threshold:
            return label
    return "New"


def to_celiums_limbic_state(state: dict) -> dict:
    """
    Project Emotion Engine `state.emotion` into a Celiums `limbicState`
    payload (the body of POST /v1/limbic/update or the equivalent
    `turn_after` input).

    Celiums uses identical PAD field names, so the projection is straight,
    but we add `timestamp` and clamp to Celiums' [-1, 1] range explicitly
    in case the source state was edited by hand.
    """
    emotion = state.get("emotion") or {}
    return {
        "pleasure": _clamp(emotion.get("pleasure", 0.0)),
        "arousal": _clamp(emotion.get("arousal", 0.3)),
        "dominance": _clamp(emotion.get("dominance", 0.5)),
        "timestamp": state.get("last_interaction_iso"),
        "source": "emotion-engine",
        "source_schema": state.get("_schema", SCHEMA_VERSION),
    }


def to_celiums_turn_context(state: dict) -> dict:
    """
    Build the prelude block Celiums injects into its `turn_context` for
    the next interaction. Mirrors the channel structure Celiums already
    uses (`pad`, `limbic-state`, plus a trust hint).
    """
    emotion = state.get("emotion") or {}
    profile = state.get("character_profile") or {}
    trust = float(state.get("trust", 0.1))
    return {
        "pad": {
            "pleasure": _clamp(emotion.get("pleasure", 0.0)),
            "arousal": _clamp(emotion.get("arousal", 0.3)),
            "dominance": _clamp(emotion.get("dominance", 0.5)),
        },
        "limbic_style": profile.get("interpretation"),
        "character_traits": list(profile.get("traits") or []),
        "trust": {
            "value": round(trust, 4),
            "tier": _trust_tier(trust),
        },
        "session_count": int(state.get("session_count", 0)),
        "total_turns": int(state.get("total_turns", 0)),
    }


def to_celiums_journal_entries(state: dict, agent_id: str) -> list[dict]:
    """
    Convert Emotion Engine `emotion_log` entries into Celiums `journal_write`
    payloads. Each emotion-log entry becomes one journal entry tagged
    `emotion-engine` so it is filterable later.

    Celiums' `journal_write` is model-scoped (per agent_id), which matches
    the semantics of `emotion_log`: this is the agent's internal record,
    not facts about the user.
    """
    out: list[dict] = []
    for entry in state.get("emotion_log") or []:
        if not isinstance(entry, dict):
            continue
        body_lines = []
        if entry.get("situation"):
            body_lines.append(f"Situation: {entry['situation']}")
        if entry.get("appraisal"):
            body_lines.append(f"Appraisal: {entry['appraisal']}")
        if entry.get("relational_meaning"):
            body_lines.append(f"Meaning: {entry['relational_meaning']}")
        if entry.get("follow_up_bias"):
            body_lines.append(f"Follow-up bias: {entry['follow_up_bias']}")
        out.append({
            "agent_id": agent_id,
            "entry_type": "emotion",
            "content": "\n".join(body_lines),
            "importance": float(entry.get("salience", 0.5)),
            "tags": ["emotion-engine", entry.get("appraisal")] if entry.get("appraisal") else ["emotion-engine"],
            "written_at": entry.get("timestamp"),
        })
    return out


def from_celiums_limbic_state(state: dict, limbic: dict) -> dict:
    """
    Mutate-and-return: ingest a Celiums `limbicState` snapshot into the
    Emotion Engine state's `emotion` field. Preserves everything else.

    This is the path you'd use after Celiums has updated the limbic state
    server-side (e.g. via `turn_after`) and you want the local JSON file
    to stay consistent.
    """
    state.setdefault("emotion", {"pleasure": 0.0, "arousal": 0.3, "dominance": 0.5})
    for dim in ("pleasure", "arousal", "dominance"):
        if dim in limbic:
            state["emotion"][dim] = _clamp(limbic[dim])
    if limbic.get("timestamp"):
        state["last_interaction_iso"] = limbic["timestamp"]
    return state


def from_celiums_journal(
    state: dict,
    journal_entries: Iterable[dict],
    limit: Optional[int] = None,
) -> dict:
    """
    Append Celiums journal entries (filtered to entry_type=='emotion' and
    tag=='emotion-engine') into the local `emotion_log`. Respects the
    state's existing `log_limit` if `limit` is None.
    """
    log = state.setdefault("emotion_log", [])
    effective_limit = limit if limit is not None else int(state.get("log_limit", 200))
    for entry in journal_entries:
        if not _is_emotion_engine_entry(entry):
            continue
        parsed = _parse_journal_body(entry.get("content", ""))
        parsed["timestamp"] = entry.get("written_at") or entry.get("created_at")
        parsed["salience"] = float(entry.get("importance", 0.5))
        log.append(parsed)
    if effective_limit and len(log) > effective_limit:
        del log[: len(log) - effective_limit]
    return state


# ---------- helpers ----------

def _clamp(value: Any, lo: float = -1.0, hi: float = 1.0) -> float:
    try:
        v = float(value)
    except (TypeError, ValueError):
        return 0.0
    return max(lo, min(hi, v))


def _is_emotion_engine_entry(entry: dict) -> bool:
    if not isinstance(entry, dict):
        return False
    if entry.get("entry_type") != "emotion":
        return False
    tags = entry.get("tags") or []
    return "emotion-engine" in tags


_FIELD_PREFIXES = {
    "Situation:": "situation",
    "Appraisal:": "appraisal",
    "Meaning:": "relational_meaning",
    "Follow-up bias:": "follow_up_bias",
}


def _parse_journal_body(body: str) -> dict:
    parsed: dict = {}
    for line in (body or "").splitlines():
        line = line.strip()
        for prefix, field in _FIELD_PREFIXES.items():
            if line.startswith(prefix):
                parsed[field] = line[len(prefix):].strip()
                break
    return parsed
