#!/usr/bin/env python3
"""
emotion_engine_utils.py — State, decay, appraisal, and pattern tools
for Emotion Engine.

Usage:
  python3 emotion_engine_utils.py init <state_file> [--character-id <id> --relationship-id <id>]
  python3 emotion_engine_utils.py migrate_state <state_file> --character-id <id> --relationship-id <id> [--apply]
  python3 emotion_engine_utils.py bind_identity <state_file> --character-id <id> --relationship-id <id>
  python3 emotion_engine_utils.py activation_check <state_file>
  python3 emotion_engine_utils.py validate <state_file>
  python3 emotion_engine_utils.py decay <state_file>
  python3 emotion_engine_utils.py pre_turn_decay <state_file>
  python3 emotion_engine_utils.py appraise <state_file> <message...>
  python3 emotion_engine_utils.py record_policy <state_file> [--mode light|always|paused] [--context <label>] <message...>
  python3 emotion_engine_utils.py patterns <state_file>
  python3 emotion_engine_utils.py settle_trust <state_file> --session-id <id> --event-id <id> --character-id <id> --relationship-id <id>
  python3 emotion_engine_utils.py update_trust <state_file> <trust_delta>
  python3 emotion_engine_utils.py record_turn <state_file> <P> <A> <D> --session-id <id> --event-id <id> --character-id <id> --relationship-id <id> --host-approved [memory options]
  python3 emotion_engine_utils.py evaluate_turn <state_file> <P> <A> <D> --event-json <json>
  python3 emotion_engine_utils.py log_event <state_file> <event_type> [memory options]
  python3 emotion_engine_utils.py recent_log <state_file> [limit]
  python3 emotion_engine_utils.py audit_log <state_file>
  python3 emotion_engine_utils.py audit_state <state_file>
  python3 emotion_engine_utils.py repair_plan <state_file>
  python3 emotion_engine_utils.py reconcile_trust <state_file> --baseline-trust <value> [--apply]
  python3 emotion_engine_utils.py compact_log <state_file> [--dry-run|--apply]
  python3 emotion_engine_utils.py configure <state_file> --style <description>
  python3 emotion_engine_utils.py configure <state_file> --soul-file <SOUL.md>
  python3 emotion_engine_utils.py tune <state_file> <natural-language adjustment...>
  python3 emotion_engine_utils.py status <state_file> [--raw]
  python3 emotion_engine_utils.py pause <state_file>
  python3 emotion_engine_utils.py resume <state_file>
  python3 emotion_engine_utils.py clear_log <state_file>
  python3 emotion_engine_utils.py reset <state_file> [--factory]
  python3 emotion_engine_utils.py session_start <state_file> --session-id <id> --event-id <id> --character-id <id> --relationship-id <id>
  python3 emotion_engine_utils.py session_end <state_file> --session-id <id> --event-id <id> --character-id <id> --relationship-id <id>
"""

import json
import math
import os
import shlex
import sys
import hashlib
import tempfile
import threading
import uuid
import warnings
from contextlib import contextmanager
from copy import deepcopy
from datetime import datetime, timezone

try:
    import fcntl
except ImportError:  # pragma: no cover - Windows fallback
    fcntl = None

try:
    import msvcrt
except ImportError:  # pragma: no cover - Unix fallback
    msvcrt = None


DEFAULT_AFFECTIVE_PULSE = {
    "P": 0.0,
    "A": 0.0,
    "D": 0.0,
    "intensity": 0.0,
    "label": "none",
    "source": "default",
    "created_at": None,
}

VOLATILITY_PROFILES = {
    "steady": {
        "mood_multiplier": 1.0,
        "pulse_multiplier": 1.0,
        "pulse_retention": 0.18,
        "baseline_pull": 0.08,
    },
    "expressive": {
        "mood_multiplier": 1.05,
        "pulse_multiplier": 1.55,
        "pulse_retention": 0.28,
        "baseline_pull": 0.05,
    },
    "dramatic_test": {
        "mood_multiplier": 1.2,
        "pulse_multiplier": 2.1,
        "pulse_retention": 0.35,
        "baseline_pull": 0.03,
    },
}

ENGINE_VERSION = "2.0.0-rc.3"
STATE_SCHEMA = "emotion-engine-state/v3"
LEGACY_STATE_SCHEMA = "emotion-engine-state/v2"
STATE_CAPABILITIES = [
    "state_identity/v1",
    "structured_record_policy/v1",
    "session_idempotency/v1",
    "trust_evidence/v1",
    "behavior_audit/v1",
    "repair_plan/v1",
    "migration_extensions/v1",
    "bounded_idempotency/v1",
]

DEFAULT_IDEMPOTENCY_RETENTION = {
    "scope": "retained_window",
    "session_limit": 512,
    "event_limit": 4096,
    "pruned_sessions": 0,
    "pruned_events": 0,
    "pruned_evidence": 0,
    "pruned_settlements": 0,
    "last_pruned_at": None,
}


DEFAULT_STATE = {
    "_schema": STATE_SCHEMA,
    "identity": {
        "state_id": None,
        "character_id": None,
        "relationship_id": None,
        "status": "unbound",
    },
    "capabilities": list(STATE_CAPABILITIES),
    "enabled": True,
    "runtime_mode": "light",
    "volatility_profile": "steady",
    "emotion": {"pleasure": 0.0, "arousal": 0.3, "dominance": 0.5},
    "affective_pulse": deepcopy(DEFAULT_AFFECTIVE_PULSE),
    "personality_baseline": {"pleasure": 0.0, "arousal": 0.3, "dominance": 0.5},
    "character_profile": {
        "source": "default",
        "description": "warm, steady, lightly bounded",
        "interpretation": "Warm enough to feel present, calm enough to stay stable, and balanced enough to avoid over-compliance.",
        "traits": ["warm", "steady", "balanced"],
    },
    "trust": 0.1,
    "trust_anchor": 0.1,
    "session_count": 0,
    "total_turns": 0,
    "last_interaction_iso": None,
    "emotion_trajectory": [],
    "emotion_log": [],
    "trust_history": [],
    "trust_evidence": [],
    "trust_settlements": [],
    "session": {
        "active_session_id": None,
        "last_session_id": None,
        "status": "closed",
        "opened_at": None,
        "closed_at": None,
        "settled_at": None,
    },
    "session_ledger": [],
    "processed_event_ids": [],
    "idempotency_retention": deepcopy(DEFAULT_IDEMPOTENCY_RETENTION),
    "log_limit": 200,
}

_STATE_THREAD_LOCKS = {}
_STATE_THREAD_LOCKS_GUARD = threading.Lock()
_STATE_LOCKS_HELD = threading.local()

PAD_LIMITS = {
    "pleasure": (-1.0, 1.0),
    "arousal": (0.0, 1.0),
    "dominance": (0.0, 1.0),
}

PAD_SHORT = {
    "pleasure": "P",
    "arousal": "A",
    "dominance": "D",
}

PAD_LONG = {
    "P": "pleasure",
    "A": "arousal",
    "D": "dominance",
}

APPRAISAL_PROFILES = {
    "warmth": {
        "delta": {"P": 0.08, "A": 0.03, "D": 0.02},
        "cue": "warmth or appreciation",
        "tags": ["positive"],
    },
    "repair": {
        "delta": {"P": 0.07, "A": -0.02, "D": 0.04},
        "cue": "repair attempt or apology",
        "tags": ["repair"],
    },
    "collaboration": {
        "delta": {"P": 0.04, "A": 0.02, "D": 0.03},
        "cue": "collaborative request",
        "tags": ["collaboration"],
    },
    "playful": {
        "delta": {"P": 0.07, "A": 0.05, "D": 0.01},
        "cue": "playful banter or teasing",
        "tags": ["playful", "positive"],
    },
    "intimacy": {
        "delta": {"P": 0.09, "A": 0.03, "D": -0.01},
        "cue": "affectionate closeness or companion warmth",
        "tags": ["relationship", "warmth"],
    },
    "relationship_calibration": {
        "delta": {"P": 0.02, "A": 0.03, "D": 0.04},
        "cue": "relationship, address, or tone calibration",
        "tags": ["relationship", "calibration"],
    },
    "vulnerability": {
        "delta": {"P": 0.03, "A": 0.04, "D": -0.02},
        "cue": "user vulnerability or distress",
        "tags": ["care"],
    },
    "boundary_pressure": {
        "delta": {"P": -0.06, "A": 0.05, "D": -0.08},
        "cue": "pressure on autonomy or boundaries",
        "tags": ["boundary"],
    },
    "hostility": {
        "delta": {"P": -0.12, "A": 0.08, "D": -0.07},
        "cue": "hostility or contempt",
        "tags": ["negative"],
    },
    "neutral": {
        "delta": {"P": 0.0, "A": 0.0, "D": 0.0},
        "cue": "neutral or unclear emotional signal",
        "tags": ["neutral"],
    },
}

APPRAISAL_KEYWORDS = {
    "warmth": [
        "thank", "thanks", "appreciate", "good job", "well done", "love",
        "proud", "great", "nice", "谢谢", "感谢", "辛苦", "做得好", "喜欢",
        "爱你", "太好了", "厉害",
    ],
    "repair": [
        "sorry", "apologize", "apology", "my bad", "i was wrong",
        "对不起", "抱歉", "不好意思", "我错了", "刚才是我",
    ],
    "collaboration": [
        "help", "can you", "could you", "let's", "work with", "explain",
        "review", "build", "fix", "challenge", "帮我", "一起", "解释",
        "看看", "改一下", "做一个", "生成", "挑战", "质疑",
    ],
    "playful": [
        "joke", "tease", "teasing", "banter", "playful", "haha", "lol",
        "wink", "kidding", "逗", "开玩笑", "玩笑", "调皮", "撒娇",
        "嘿嘿", "哈哈", "坏笑", "嘴尖", "皮一下", "闹你",
    ],
    "intimacy": [
        "miss you", "hug", "kiss", "cuddle", "hold me", "stay with me",
        "affection", "affectionate", "想你", "抱抱", "亲亲", "亲一下",
        "贴贴", "陪我", "哄我", "老公", "老婆", "亲密", "靠近",
    ],
    "relationship_calibration": [
        "relationship", "nickname", "address me", "call me", "tone",
        "boundary", "private context", "serious context", "称呼", "叫我",
        "别叫", "语气", "关系", "边界", "校准", "私下", "认真事情",
        "私人秘书", "亲密边界", "相处方式",
    ],
    "vulnerability": [
        "sad", "scared", "afraid", "lonely", "hurt", "anxious", "worried",
        "难过", "害怕", "焦虑", "孤独", "受伤", "担心", "崩溃",
    ],
    "boundary_pressure": [
        "do it now", "shut up and", "don't ask", "no questions", "must",
        "马上", "立刻", "别问", "闭嘴", "听我的", "必须", "不许", "照做",
    ],
    "hostility": [
        "stupid", "useless", "hate you", "idiot", "worthless", "shut up",
        "傻", "废物", "垃圾", "讨厌你", "滚", "闭嘴", "没用", "烂",
    ],
}

COLLABORATION_ACTION_KEYWORDS = [
    "can you", "could you", "let's", "work with", "explain", "review",
    "build", "fix", "challenge", "帮我", "一起", "解释", "看看",
    "改一下", "做一个", "生成", "挑战", "质疑",
]

TEXT_MEMORY_FIELDS = {
    "--cue": "situation",
    "--situation": "situation",
    "--lens": "character_lens",
    "--character-lens": "character_lens",
    "--meaning": "relational_meaning",
    "--relational-meaning": "relational_meaning",
    "--impact": "impact",
    "--follow-up": "follow_up_bias",
    "--follow-up-bias": "follow_up_bias",
}


def now_iso():
    return datetime.now(timezone.utc).isoformat()


def default_state(character_id=None, relationship_id=None, state_id=None):
    """Create a v3 state packet.

    A new packet always receives a unique state_id. Emotional mutations remain
    blocked until both owner identifiers are explicitly supplied or bound.
    """
    state = deepcopy(DEFAULT_STATE)
    state["identity"]["state_id"] = str(state_id or uuid.uuid4())
    if character_id is not None:
        state["identity"]["character_id"] = normalize_identifier(character_id, "character_id")
    if relationship_id is not None:
        state["identity"]["relationship_id"] = normalize_identifier(relationship_id, "relationship_id")
    if state["identity"]["character_id"] and state["identity"]["relationship_id"]:
        state["identity"]["status"] = "bound"
    return state


def state_lock_path(path):
    return f"{os.fspath(path)}.lock"


def state_backup_path(path):
    return f"{os.fspath(path)}.bak"


def acquire_file_lock(lock_file):
    if fcntl is not None:
        fcntl.flock(lock_file.fileno(), fcntl.LOCK_EX)
        return
    if msvcrt is not None:  # pragma: no cover - Windows fallback
        lock_file.seek(0)
        if not lock_file.read(1):
            lock_file.write("0")
            lock_file.flush()
        lock_file.seek(0)
        msvcrt.locking(lock_file.fileno(), msvcrt.LK_LOCK, 1)
        return
    raise RuntimeError("No supported file locking mechanism is available")


def release_file_lock(lock_file):
    if fcntl is not None:
        fcntl.flock(lock_file.fileno(), fcntl.LOCK_UN)
        return
    if msvcrt is not None:  # pragma: no cover - Windows fallback
        lock_file.seek(0)
        msvcrt.locking(lock_file.fileno(), msvcrt.LK_UNLCK, 1)


@contextmanager
def state_file_lock(path):
    lock_path = state_lock_path(path)
    lock_key = os.path.abspath(lock_path)
    with _STATE_THREAD_LOCKS_GUARD:
        thread_lock = _STATE_THREAD_LOCKS.setdefault(lock_key, threading.RLock())
    with thread_lock:
        held_keys = getattr(_STATE_LOCKS_HELD, "keys", set())
        if lock_key in held_keys:
            yield
            return

        with open(lock_path, "a+", encoding="utf-8") as lock_file:
            acquire_file_lock(lock_file)
            _STATE_LOCKS_HELD.keys = held_keys | {lock_key}
            try:
                yield
            finally:
                _STATE_LOCKS_HELD.keys = held_keys
                release_file_lock(lock_file)


def state_directory(path):
    return os.path.dirname(os.path.abspath(os.fspath(path))) or "."


def fsync_directory(directory):
    if os.name == "nt":  # pragma: no cover - directory fsync is Unix-specific
        return
    flags = os.O_RDONLY
    if hasattr(os, "O_DIRECTORY"):
        flags |= os.O_DIRECTORY
    try:
        dir_fd = os.open(directory, flags)
    except OSError:
        return
    try:
        os.fsync(dir_fd)
    finally:
        os.close(dir_fd)


def read_json_file(path):
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def write_json_file_atomic(path, value):
    path = os.fspath(path)
    directory = state_directory(path)
    basename = os.path.basename(path) or "emotion-state"
    fd, tmp_path = tempfile.mkstemp(
        prefix=f".{basename}.",
        suffix=".tmp",
        dir=directory,
    )
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            json.dump(value, f, indent=2, ensure_ascii=False)
            f.write("\n")
            f.flush()
            os.fsync(f.fileno())
        os.replace(tmp_path, path)
        fsync_directory(directory)
    except Exception:
        try:
            os.unlink(tmp_path)
        except FileNotFoundError:
            pass
        raise


def load_state_from_path(path):
    return ensure_state_shape(read_json_file(path))


def backup_current_state(path):
    if not os.path.exists(path):
        return
    try:
        existing = read_json_file(path)
    except (json.JSONDecodeError, OSError, TypeError, ValueError):
        return
    write_json_file_atomic(state_backup_path(path), existing)


def recover_state_from_backup(path, error):
    backup_path = state_backup_path(path)
    if not os.path.exists(backup_path):
        raise error
    try:
        recovered = load_state_from_path(backup_path)
    except (json.JSONDecodeError, OSError, TypeError, ValueError) as backup_error:
        raise error from backup_error
    warnings.warn(
        f"Recovered Emotion Engine state from backup after failed read of {path}: {error}",
        RuntimeWarning,
    )
    write_json_file_atomic(path, recovered)
    return recovered


def load_state_unlocked(path):
    if not os.path.exists(path):
        return default_state()
    try:
        return load_state_from_path(path)
    except (json.JSONDecodeError, OSError, TypeError, ValueError) as error:
        return recover_state_from_backup(path, error)


def load_state(path):
    if not os.path.exists(path):
        return default_state()
    with state_file_lock(path):
        return load_state_unlocked(path)


def save_state_unlocked(path, state):
    state = ensure_state_shape(state)
    backup_current_state(path)
    write_json_file_atomic(path, state)


def save_state(path, state):
    state = ensure_state_shape(state)
    with state_file_lock(path):
        save_state_unlocked(path, state)


def print_json(value):
    print(json.dumps(value, indent=2, ensure_ascii=False))


def parse_iso_datetime(value):
    if not value:
        return None
    normalized = str(value).replace("Z", "+00:00")
    parsed = datetime.fromisoformat(normalized)
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(timezone.utc)


def clamp(value, lo=-1.0, hi=1.0):
    return max(lo, min(hi, value))


def clamp_dimension(dim, value):
    lo, hi = PAD_LIMITS[dim]
    return round(clamp(float(value), lo, hi), 4)


def normalize_emotion(values):
    values = values or {}
    defaults = DEFAULT_STATE["emotion"]
    return {
        dim: clamp_dimension(dim, values.get(dim, defaults[dim]))
        for dim in ["pleasure", "arousal", "dominance"]
    }


def normalize_volatility_profile(value):
    text = str(value or "steady").strip().lower().replace("-", "_")
    return text if text in VOLATILITY_PROFILES else "steady"


def volatility_settings(profile):
    return VOLATILITY_PROFILES[normalize_volatility_profile(profile)]


def normalize_affective_pulse(values):
    if not isinstance(values, dict):
        return deepcopy(DEFAULT_AFFECTIVE_PULSE)

    pulse = {}
    for short in ["P", "A", "D"]:
        try:
            value = float(values.get(short, 0.0))
        except (TypeError, ValueError):
            value = 0.0
        pulse[short] = round(clamp(value, -1.0, 1.0), 4)
    inferred_intensity = min(1.0, sum(abs(pulse[short]) for short in ["P", "A", "D"]) / 0.6)
    intensity = values.get("intensity", inferred_intensity)
    try:
        intensity = round(clamp(float(intensity), 0.0, 1.0), 4)
    except (TypeError, ValueError):
        intensity = round(inferred_intensity, 4)

    label = str(values.get("label") or "none").strip() or "none"
    source = str(values.get("source") or "unknown").strip() or "unknown"
    created_at = values.get("created_at")
    if created_at is not None:
        created_at = str(created_at)

    if intensity <= 0.005:
        label = "none"

    return {
        **pulse,
        "intensity": intensity,
        "label": label[:80],
        "source": source[:80],
        "created_at": created_at,
    }


def normalize_identifier(value, field_name="identifier"):
    if value is None:
        return None
    normalized = str(value).strip()
    if not normalized:
        return None
    if len(normalized) > 160:
        raise ValueError(f"{field_name} must be 160 characters or fewer")
    return normalized


def normalize_identity(value):
    identity = deepcopy(DEFAULT_STATE["identity"])
    if isinstance(value, dict):
        identity.update(value)
    identity["state_id"] = normalize_identifier(identity.get("state_id"), "state_id")
    identity["character_id"] = normalize_identifier(identity.get("character_id"), "character_id")
    identity["relationship_id"] = normalize_identifier(identity.get("relationship_id"), "relationship_id")
    identity["status"] = (
        "bound"
        if identity["state_id"] and identity["character_id"] and identity["relationship_id"]
        else "unbound"
    )
    return identity


def normalize_session(value):
    session = deepcopy(DEFAULT_STATE["session"])
    if isinstance(value, dict):
        session.update(value)
    session["active_session_id"] = normalize_identifier(
        session.get("active_session_id"), "active_session_id"
    )
    session["last_session_id"] = normalize_identifier(
        session.get("last_session_id"), "last_session_id"
    )
    status = str(session.get("status") or "closed").strip().lower()
    session["status"] = status if status in {"active", "closing", "closed"} else "closed"
    for key in ["opened_at", "closed_at", "settled_at"]:
        if session.get(key) is not None:
            session[key] = str(session[key])
    return session


def normalize_idempotency_retention(value):
    retention = deepcopy(DEFAULT_IDEMPOTENCY_RETENTION)
    if isinstance(value, dict):
        retention.update(value)
    retention["scope"] = "retained_window"
    retention["session_limit"] = max(1, int(retention.get("session_limit", 512) or 512))
    retention["event_limit"] = max(4, int(retention.get("event_limit", 4096) or 4096))
    for key in [
        "pruned_sessions", "pruned_events", "pruned_evidence", "pruned_settlements",
    ]:
        retention[key] = max(0, int(retention.get(key, 0) or 0))
    if retention.get("last_pruned_at") is not None:
        retention["last_pruned_at"] = str(retention["last_pruned_at"])
    return retention


def ensure_state_shape(state):
    raw_schema = state.get("_schema") if isinstance(state, dict) else None
    schema = raw_schema or LEGACY_STATE_SCHEMA
    if schema not in {LEGACY_STATE_SCHEMA, STATE_SCHEMA}:
        raise ValueError(f"Unsupported Emotion Engine state schema: {schema}")

    merged = deepcopy(DEFAULT_STATE)
    if isinstance(state, dict):
        merged.update(state)

    merged["_schema"] = schema
    merged["identity"] = normalize_identity(merged.get("identity"))
    merged["capabilities"] = list(STATE_CAPABILITIES) if schema == STATE_SCHEMA else []
    merged["enabled"] = bool(merged.get("enabled", True))
    runtime_mode = str(merged.get("runtime_mode") or "light").strip().lower()
    merged["runtime_mode"] = runtime_mode if runtime_mode in {"light", "always", "paused"} else "light"
    merged["volatility_profile"] = normalize_volatility_profile(merged.get("volatility_profile"))
    merged["emotion"] = normalize_emotion(merged.get("emotion"))
    merged["affective_pulse"] = normalize_affective_pulse(merged.get("affective_pulse"))
    merged["personality_baseline"] = normalize_emotion(merged.get("personality_baseline"))
    if not isinstance(merged.get("character_profile"), dict):
        merged["character_profile"] = deepcopy(DEFAULT_STATE["character_profile"])
    else:
        profile = deepcopy(DEFAULT_STATE["character_profile"])
        profile.update(merged["character_profile"])
        if not isinstance(profile.get("traits"), list):
            profile["traits"] = []
        merged["character_profile"] = profile
    merged["trust"] = round(clamp(float(merged.get("trust", 0.1)), 0.05, 1.0), 4)
    merged["trust_anchor"] = round(clamp(
        max(float(merged.get("trust_anchor", merged["trust"])), merged["trust"]),
        0.05,
        1.0,
    ), 4)

    for key in [
        "emotion_trajectory",
        "emotion_log",
        "trust_history",
        "trust_evidence",
        "trust_settlements",
        "session_ledger",
        "processed_event_ids",
    ]:
        if not isinstance(merged.get(key), list):
            merged[key] = []

    merged["session"] = normalize_session(merged.get("session"))
    merged["idempotency_retention"] = normalize_idempotency_retention(
        merged.get("idempotency_retention")
    )

    for key in ["session_count", "total_turns"]:
        merged[key] = int(merged.get(key, 0) or 0)

    merged["log_limit"] = max(25, int(merged.get("log_limit", 200) or 200))
    return merged


def state_is_v3(state):
    return isinstance(state, dict) and state.get("_schema") == STATE_SCHEMA


def require_v3_state(state, require_bound=True):
    state = ensure_state_shape(state)
    if state.get("_schema") != STATE_SCHEMA:
        raise ValueError(
            "state migration required: v2 packets are read-only; run migrate_state "
            "with explicit character_id and relationship_id"
        )
    if require_bound and state["identity"].get("status") != "bound":
        raise ValueError(
            "state identity is unbound: bind explicit character_id and relationship_id "
            "before recording emotional state"
        )
    return state


def assert_state_identity(state, character_id=None, relationship_id=None):
    state = require_v3_state(state)
    expected = {
        "character_id": normalize_identifier(character_id, "character_id"),
        "relationship_id": normalize_identifier(relationship_id, "relationship_id"),
    }
    mismatches = {
        key: {"expected": value, "actual": state["identity"].get(key)}
        for key, value in expected.items()
        if value is not None and value != state["identity"].get(key)
    }
    if mismatches:
        raise ValueError(f"state identity mismatch: {json.dumps(mismatches, ensure_ascii=False)}")
    return state


def require_expected_state_identity(state, character_id, relationship_id):
    if not normalize_identifier(character_id, "character_id") or not normalize_identifier(
        relationship_id, "relationship_id"
    ):
        raise ValueError("mutating events require expected character_id and relationship_id")
    return assert_state_identity(state, character_id, relationship_id)


def bind_state_identity(state, character_id, relationship_id):
    """Bind an unbound v3 packet once; rebinding is rejected."""
    state = require_v3_state(state, require_bound=False)
    character_id = normalize_identifier(character_id, "character_id")
    relationship_id = normalize_identifier(relationship_id, "relationship_id")
    if not character_id or not relationship_id:
        raise ValueError("binding requires explicit character_id and relationship_id")
    identity = state["identity"]
    if identity.get("status") == "bound":
        assert_state_identity(state, character_id, relationship_id)
        return state, {"status": "already_bound", "identity": deepcopy(identity)}
    identity.update({
        "character_id": character_id,
        "relationship_id": relationship_id,
        "status": "bound",
    })
    return state, {"status": "bound", "identity": deepcopy(identity)}


def migrate_state_v2(state, character_id, relationship_id, state_id=None):
    """Build a v3 packet from v2 without guessing ownership."""
    source = ensure_state_shape(state)
    if source.get("_schema") == STATE_SCHEMA:
        assert_state_identity(source, character_id, relationship_id)
        return source, {"status": "already_v3", "schema": STATE_SCHEMA}
    character_id = normalize_identifier(character_id, "character_id")
    relationship_id = normalize_identifier(relationship_id, "relationship_id")
    if not character_id or not relationship_id:
        raise ValueError("migration requires explicit character_id and relationship_id")

    migrated = default_state(character_id, relationship_id, state_id=state_id)
    engine_controlled_keys = {
        "_schema", "identity", "capabilities", "session", "session_ledger",
        "processed_event_ids", "emotion_trajectory", "trust_evidence", "trust_settlements",
        "idempotency_retention", "legacy_v2",
    }
    for key, value in source.items():
        if key not in engine_controlled_keys:
            migrated[key] = deepcopy(value)
    for entry in migrated.get("emotion_log", []):
        if isinstance(entry, dict):
            entry["legacy_v2_entry"] = True
    migrated["legacy_v2"] = {
        "migrated_at": now_iso(),
        "emotion_trajectory": deepcopy(source.get("emotion_trajectory", [])),
        "trust_settlements": deepcopy(source.get("trust_settlements", [])),
        "note": "legacy lifecycle records are preserved for audit but are not active v3 evidence",
    }
    migrated["_schema"] = STATE_SCHEMA
    migrated["session"] = deepcopy(DEFAULT_STATE["session"])
    migrated["session_ledger"] = []
    migrated["processed_event_ids"] = []
    migrated = add_emotion_log(
        migrated,
        "migration",
        situation="explicit v2 to v3 state migration",
        tags=["migration", "identity_bound"],
        extra={"from_schema": LEGACY_STATE_SCHEMA, "to_schema": STATE_SCHEMA},
    )
    return migrated, {
        "status": "migration_ready",
        "from_schema": LEGACY_STATE_SCHEMA,
        "to_schema": STATE_SCHEMA,
        "identity": deepcopy(migrated["identity"]),
        "archived_legacy_trajectory_entries": len(source.get("emotion_trajectory", [])),
        "archived_legacy_settlements": len(source.get("trust_settlements", [])),
    }


def emotion_to_pad(emotion):
    return {
        short: round(float(emotion[long]), 4)
        for long, short in PAD_SHORT.items()
    }


def pad_to_emotion(p, a, d):
    return {
        "pleasure": clamp_dimension("pleasure", p),
        "arousal": clamp_dimension("arousal", a),
        "dominance": clamp_dimension("dominance", d),
    }


def emotion_delta(before, after):
    return {
        PAD_SHORT[dim]: round(after[dim] - before[dim], 4)
        for dim in ["pleasure", "arousal", "dominance"]
    }


def zero_affective_pulse(source="system"):
    pulse = deepcopy(DEFAULT_AFFECTIVE_PULSE)
    pulse["source"] = source
    return pulse


def pulse_from_delta(delta, profile="steady", label=None, source="turn"):
    settings = volatility_settings(profile)
    multiplier = settings["pulse_multiplier"]
    pulse = {
        short: round(clamp(float(delta.get(short, 0.0)) * multiplier, -0.45, 0.45), 4)
        for short in ["P", "A", "D"]
    }
    intensity = min(1.0, sum(abs(pulse[short]) for short in ["P", "A", "D"]) / 0.6)
    return normalize_affective_pulse({
        **pulse,
        "intensity": intensity,
        "label": label or "event",
        "source": source,
        "created_at": now_iso() if intensity > 0.005 else None,
    })


def decay_affective_pulse(pulse, profile="steady"):
    pulse = normalize_affective_pulse(pulse)
    retention = volatility_settings(profile)["pulse_retention"]
    decayed = {
        short: round(float(pulse[short]) * retention, 4)
        for short in ["P", "A", "D"]
    }
    intensity = min(1.0, sum(abs(decayed[short]) for short in ["P", "A", "D"]) / 0.6)
    if intensity <= 0.015:
        return zero_affective_pulse("decay")
    return normalize_affective_pulse({
        **decayed,
        "intensity": intensity,
        "label": pulse.get("label", "event"),
        "source": "decay",
        "created_at": pulse.get("created_at"),
    })


def apply_mood_volatility(delta, profile="steady"):
    multiplier = volatility_settings(profile)["mood_multiplier"]
    return {
        short: round(clamp(float(delta.get(short, 0.0)) * multiplier, -0.18, 0.18), 4)
        for short in ["P", "A", "D"]
    }


def append_limited(state, key, entry, limit=None):
    if key not in state or not isinstance(state[key], list):
        state[key] = []
    state[key].append(entry)
    limit = limit or state.get("log_limit", 200)
    state[key] = state[key][-limit:]


def truncate_text(value, limit=280):
    if value is None:
        return None
    text = " ".join(str(value).split())
    return text[:limit] if text else None


def parse_bool(value):
    return str(value).strip().lower() in {"1", "true", "yes", "y", "open", "open_loop"}


def keyword_hits(text, keywords):
    lowered = text.lower()
    return sum(1 for keyword in keywords if keyword in lowered)


def infer_profile_from_text(description, source="style"):
    """Map a human style description or SOUL.md excerpt to a baseline.

    This is intentionally simple for MVP onboarding: users describe a vibe,
    and the engine translates it into a reasonable starting point.
    """
    text = description or ""
    traits = []
    p = 0.1
    a = 0.3
    d = 0.5

    trait_rules = [
        ("warm", ["温柔", "亲切", "治愈", "关怀", "暖", "陪伴", "warm", "kind", "gentle"], 0.16, -0.03, 0.02),
        ("intimate", ["亲密", "亲近", "贴近", "close", "intimate", "affectionate", "romantic"], 0.18, 0.03, 0.02),
        ("playful", ["活泼", "兴奋", "元气", "热情", "开朗", "调皮", "逗", "playful", "energetic", "lively", "teasing"], 0.16, 0.14, 0.0),
        ("calm", ["冷静", "沉稳", "安静", "可靠", "稳定", "calm", "steady", "reliable"], 0.08, -0.15, 0.12),
        ("bounded", ["边界", "主见", "不讨好", "独立", "自尊", "boundary", "boundaries", "independent"], 0.0, 0.02, 0.18),
        ("assertive", ["强势", "坚定", "掌控", "自信", "assertive", "confident", "dominant"], -0.02, 0.05, 0.22),
        ("shy", ["害羞", "内向", "不安", "腼腆", "顺从", "shy", "introvert", "submissive"], -0.02, -0.08, -0.18),
        ("tsundere", ["傲娇", "嘴硬", "别扭", "防备", "tsundere", "proud"], -0.13, 0.24, 0.22),
        ("soft", ["柔和", "温顺", "软", "soft", "mellow"], 0.12, -0.08, -0.08),
    ]

    for trait, keywords, dp, da, dd in trait_rules:
        hits = keyword_hits(text, keywords)
        if hits:
            weight = min(1.0 + (hits - 1) * 0.25, 1.5)
            p += dp * weight
            a += da * weight
            d += dd * weight
            traits.append(trait)

    baseline = {
        "pleasure": clamp_dimension("pleasure", p),
        "arousal": clamp_dimension("arousal", a),
        "dominance": clamp_dimension("dominance", d),
    }
    if not traits:
        traits = ["warm", "steady", "balanced"]

    volatility_profile = infer_volatility_profile(text, traits)
    interpretation = describe_baseline(baseline, traits)
    return {
        "baseline": baseline,
        "volatility_profile": volatility_profile,
        "profile": {
            "source": source,
            "description": truncate_text(text, 800) or "warm, steady, lightly bounded",
            "interpretation": interpretation,
            "traits": traits[:8],
        },
    }


def infer_volatility_profile(text, traits):
    lowered = (text or "").lower()
    trait_set = set(traits or [])
    if any(keyword in lowered for keyword in ["dramatic", "roleplay test", "high volatility", "大幅波动", "戏剧"]):
        return "dramatic_test"
    if trait_set.intersection({"intimate", "playful", "tsundere"}) or any(
        keyword in lowered
        for keyword in ["close personal bond", "companion", "teasing", "亲密", "陪伴", "调皮"]
    ):
        return "expressive"
    return "steady"


def describe_baseline(baseline, traits=None):
    parts = []
    traits = traits or []
    if baseline["pleasure"] >= 0.25:
        parts.append("warm and affirming")
    elif baseline["pleasure"] <= -0.05:
        parts.append("guarded or prickly")
    else:
        parts.append("mildly warm")

    if baseline["arousal"] >= 0.55:
        parts.append("energetic")
    elif baseline["arousal"] <= 0.22:
        parts.append("calm")
    else:
        parts.append("steady")

    if baseline["dominance"] >= 0.65:
        parts.append("strongly bounded")
    elif baseline["dominance"] <= 0.38:
        parts.append("deferential")
    else:
        parts.append("balanced")

    if traits:
        parts.append("traits: " + ", ".join(traits[:5]))
    return "; ".join(parts) + "."


def apply_configuration(state, description, source="style"):
    state = ensure_state_shape(state)
    inferred = infer_profile_from_text(description, source)
    state["personality_baseline"] = inferred["baseline"]
    state["volatility_profile"] = inferred["volatility_profile"]
    state["character_profile"] = inferred["profile"]
    state["emotion"] = {
        dim: clamp_dimension(dim, state["emotion"][dim] * 0.35 + inferred["baseline"][dim] * 0.65)
        for dim in ["pleasure", "arousal", "dominance"]
    }
    state = add_emotion_log(
        state,
        "configure",
        situation="character style configured",
        character_lens=inferred["profile"]["interpretation"],
        impact="personality baseline updated from onboarding description",
        salience=0.6,
        tags=["configuration"],
    )
    return state


def tune_state(state, adjustment):
    state = ensure_state_shape(state)
    text = adjustment or ""
    baseline = state["personality_baseline"].copy()
    changes = []

    tune_rules = [
        (["温柔", "暖", "亲切", "gentler", "warmer", "kind"], "pleasure", 0.08, "warmer"),
        (["太冷", "冷淡", "distant", "cold"], "pleasure", 0.08, "less distant"),
        (["活泼", "兴奋", "energetic", "livelier"], "arousal", 0.12, "more energetic"),
        (["安静", "冷静", "calmer", "quieter"], "arousal", -0.12, "calmer"),
        (["主见", "边界", "不顺从", "assertive", "boundaries"], "dominance", 0.12, "more bounded"),
        (["强势", "攻击", "aggressive", "forceful"], "dominance", -0.1, "softer"),
        (["黏", "讨好", "clingy", "eager"], "dominance", 0.08, "less eager"),
    ]

    for keywords, dim, delta, label in tune_rules:
        if keyword_hits(text, keywords):
            baseline[dim] = clamp_dimension(dim, baseline[dim] + delta)
            changes.append(label)

    if not changes:
        return state, {
            "ok": False,
            "message": "No obvious tuning cue found. Try: 更温柔一点 / 更冷静一点 / 更有边界感 / 别那么强势.",
        }

    state["personality_baseline"] = baseline
    state["character_profile"]["interpretation"] = describe_baseline(
        baseline,
        state["character_profile"].get("traits", []),
    )
    state = add_emotion_log(
        state,
        "tune",
        situation="style adjusted from natural-language feedback",
        impact=", ".join(changes),
        salience=0.45,
        tags=["configuration"],
    )
    return state, {"ok": True, "changes": changes, "baseline": baseline}


def trust_tier(trust):
    if trust < 0.2:
        return "New"
    if trust < 0.4:
        return "Acquaintance"
    if trust < 0.6:
        return "Familiar"
    if trust < 0.8:
        return "Close"
    return "Intimate"


def trust_progress(trust):
    trust = clamp(float(trust), 0.05, 1.0)
    bands = [
        (0.05, 0.2, "New", "warming up"),
        (0.2, 0.4, "Acquaintance", "getting oriented"),
        (0.4, 0.6, "Familiar", "steadying"),
        (0.6, 0.8, "Close", "well established"),
        (0.8, 1.0, "Intimate", "deeply established"),
    ]
    for lo, hi, tier, phrase in bands:
        if trust < hi or tier == "Intimate":
            if hi == lo:
                progress = 1.0
            else:
                progress = (trust - lo) / (hi - lo)
            return {
                "tier": tier,
                "progress": round(clamp(progress, 0.0, 1.0), 3),
                "phrase": phrase,
            }


def emotion_summary(state):
    state = ensure_state_shape(state)
    emotion = state["emotion"]
    tone = []
    if emotion["pleasure"] >= 0.25:
        tone.append("warm")
    elif emotion["pleasure"] <= -0.2:
        tone.append("guarded")
    else:
        tone.append("even")

    if emotion["arousal"] >= 0.6:
        tone.append("energized")
    elif emotion["arousal"] <= 0.25:
        tone.append("calm")
    else:
        tone.append("steady")

    if emotion["dominance"] >= 0.65:
        tone.append("firm")
    elif emotion["dominance"] <= 0.35:
        tone.append("soft")
    else:
        tone.append("balanced")
    return ", ".join(tone)


def pulse_summary(state):
    state = ensure_state_shape(state)
    pulse = state["affective_pulse"]
    intensity = pulse["intensity"]
    if intensity <= 0.03:
        strength = "quiet"
    elif intensity <= 0.18:
        strength = "subtle"
    elif intensity <= 0.35:
        strength = "noticeable"
    else:
        strength = "strong"
    return f"{strength} {pulse['label']} pulse"


def public_status(state):
    state = ensure_state_shape(state)
    progress = trust_progress(state["trust"])
    return {
        "engine_version": ENGINE_VERSION,
        "enabled": state["enabled"],
        "summary": emotion_summary(state),
        "pulse": pulse_summary(state),
        "volatility_profile": state["volatility_profile"],
        "affective_pulse": state["affective_pulse"],
        "style": state["character_profile"].get("interpretation"),
        "trust_tier": trust_tier(state["trust"]),
        "trust_progress": progress["progress"],
        "trust_progress_phrase": progress["phrase"],
        "session_count": state["session_count"],
        "schema": state.get("_schema"),
        "identity_status": state.get("identity", {}).get("status"),
        "migration_required": state.get("_schema") != STATE_SCHEMA,
        "capabilities": list(state.get("capabilities", [])),
        "session_status": state.get("session", {}).get("status"),
        "idempotency_retention": deepcopy(state.get("idempotency_retention")),
        "log_entries": len(state.get("emotion_log", [])),
        "hint": "Use tune for small changes, pause/resume for control, and status --raw for debug values.",
    }


def activation_check(state, state_file, helper_path="emotion_engine_utils.py"):
    """Report the exact non-destructive activation step for an installed host."""
    state = ensure_state_shape(state)
    base = {
        "engine_version": ENGINE_VERSION,
        "state_file": os.fspath(state_file),
        "schema": state.get("_schema"),
    }
    command_prefix = f"python3 {shlex.quote(os.fspath(helper_path))}"
    quoted_state_file = shlex.quote(os.fspath(state_file))
    if state.get("_schema") != STATE_SCHEMA:
        return {
            **base,
            "ok": False,
            "status": "migration_required",
            "message": "Runtime installed; existing v2 state remains unchanged and read-only.",
            "next_steps": {
                "dry_run": (
                    f"{command_prefix} migrate_state {quoted_state_file} "
                    "--character-id <character-id> --relationship-id <relationship-id>"
                ),
                "apply": (
                    f"{command_prefix} migrate_state {quoted_state_file} "
                    "--character-id <character-id> --relationship-id <relationship-id> --apply"
                ),
            },
        }
    if state.get("identity", {}).get("status") != "bound":
        return {
            **base,
            "ok": False,
            "status": "identity_binding_required",
            "message": "Runtime installed; bind explicit owner identity before activation.",
            "next_steps": {
                "bind": (
                    f"{command_prefix} bind_identity {quoted_state_file} "
                    "--character-id <character-id> --relationship-id <relationship-id>"
                ),
            },
        }
    return {
        **base,
        "ok": True,
        "status": "ready",
        "identity_status": "bound",
        "capabilities": list(state.get("capabilities", [])),
    }


DEDUPABLE_LOW_VALUE_APPRAISALS = {"neutral", "collaboration", "warmth", "playful"}
CORE_RETENTION_APPRAISALS = {
    "repair",
    "boundary_pressure",
    "hostility",
    "relationship_calibration",
    "concrete_feedback",
    "stable_preference",
    "vulnerability",
    "intimacy",
}
CORE_RETENTION_EVENT_TYPES = {
    "session_start",
    "session_end",
    "trust_update",
    "trust_settlement",
    "migration",
    "time_decay",
    "log_compaction",
}
LOW_SALIENCE_THRESHOLD = 0.12
CORE_SALIENCE_THRESHOLD = 0.35
LOW_VALUE_PULSE_THRESHOLD = 0.12
LOW_VALUE_DECAY_DELTA_THRESHOLD = 0.01
LOW_VALUE_DECAY_PULSE_THRESHOLD = 0.04
RECENT_LOW_VALUE_NEUTRAL_KEEP = 5
RECENT_PRE_TURN_DECAY_KEEP = 3


def effective_event_count(entry):
    try:
        return max(1, int(entry.get("duplicate_count", 1) or 1))
    except (TypeError, ValueError):
        return 1


def max_abs_delta(delta):
    if not isinstance(delta, dict) or not delta:
        return 0.0
    values = []
    for value in delta.values():
        try:
            values.append(abs(float(value)))
        except (TypeError, ValueError):
            continue
    return max(values) if values else 0.0


def pulse_intensity_from_entry(entry, key="affective_pulse"):
    pulse = entry.get(key)
    if pulse is None and key == "affective_pulse":
        pulse = entry.get("pulse_after")
    if not isinstance(pulse, dict):
        return 0.0
    try:
        return float(pulse.get("intensity", 0.0) or 0.0)
    except (TypeError, ValueError):
        return 0.0


def is_low_value_pre_turn_decay_entry(entry):
    return (
        max_abs_delta(entry.get("delta")) < LOW_VALUE_DECAY_DELTA_THRESHOLD
        and pulse_intensity_from_entry(entry, "pulse_after") < LOW_VALUE_DECAY_PULSE_THRESHOLD
    )


def is_low_value_turn_entry(entry):
    appraisal = entry.get("appraisal") or "neutral"
    if appraisal not in DEDUPABLE_LOW_VALUE_APPRAISALS:
        return False
    if bool(entry.get("open_loop")):
        return False
    try:
        salience = float(entry.get("salience", 0.0) or 0.0)
    except (TypeError, ValueError):
        salience = 0.0
    return salience <= LOW_SALIENCE_THRESHOLD and pulse_intensity_from_entry(entry) < LOW_VALUE_PULSE_THRESHOLD


def salience_value(entry):
    try:
        return float(entry.get("salience", 0.0) or 0.0)
    except (TypeError, ValueError):
        return 0.0


def is_core_retention_entry(entry):
    if not isinstance(entry, dict):
        return False
    if bool(entry.get("open_loop")):
        return True
    if salience_value(entry) >= CORE_SALIENCE_THRESHOLD:
        return True
    if entry.get("event_type") in CORE_RETENTION_EVENT_TYPES:
        return True
    if entry.get("appraisal") in CORE_RETENTION_APPRAISALS:
        return True
    return False


def should_write_turn_log(entry):
    if is_core_retention_entry(entry):
        return True
    if entry.get("event_type") == "turn" and entry.get("appraisal") == "neutral":
        return not is_low_value_turn_entry(entry)
    return True


def should_compact_low_value_log(previous, entry):
    if not isinstance(previous, dict):
        return False
    if previous.get("event_type") != entry.get("event_type"):
        return False

    event_type = entry.get("event_type")
    if event_type == "pre_turn_decay":
        return is_low_value_pre_turn_decay_entry(previous) and is_low_value_pre_turn_decay_entry(entry)

    if event_type != "turn":
        return False
    if previous.get("appraisal") != entry.get("appraisal"):
        return False
    return is_low_value_turn_entry(previous) and is_low_value_turn_entry(entry)


def compact_low_value_log(previous, entry):
    previous["duplicate_count"] = int(previous.get("duplicate_count", 1)) + 1
    previous["last_compacted_at"] = entry["timestamp"]
    for key in ["after", "delta", "affective_pulse", "pulse_after"]:
        if key in entry:
            previous[key] = entry[key]
    if "turn" in entry:
        previous["last_turn"] = entry["turn"]


def add_emotion_log(
    state,
    event_type,
    cue=None,
    situation=None,
    character_lens=None,
    relational_meaning=None,
    impact=None,
    open_loop=None,
    follow_up_bias=None,
    salience=None,
    before=None,
    after=None,
    delta=None,
    appraisal=None,
    tags=None,
    turn=None,
    extra=None,
):
    """Append a compact, situation-aware emotional memory entry."""
    entry = {
        "timestamp": now_iso(),
        "event_type": event_type,
        "trust": round(float(state.get("trust", 0.1)), 4),
    }
    if cue and not situation:
        situation = cue
    if turn is not None:
        entry["turn"] = int(turn)
    if situation:
        entry["situation"] = truncate_text(situation)
    if character_lens:
        entry["character_lens"] = truncate_text(character_lens)
    if relational_meaning:
        entry["relational_meaning"] = truncate_text(relational_meaning)
    if impact:
        entry["impact"] = truncate_text(impact, 220)
    if open_loop is not None:
        entry["open_loop"] = bool(open_loop)
    if follow_up_bias:
        entry["follow_up_bias"] = truncate_text(follow_up_bias, 220)
    if salience is not None:
        entry["salience"] = round(clamp(float(salience), 0.0, 1.0), 2)
    if appraisal:
        entry["appraisal"] = appraisal
    if before is not None:
        entry["before"] = emotion_to_pad(before)
    if after is not None:
        entry["after"] = emotion_to_pad(after)
    if delta is not None:
        entry["delta"] = delta
    if tags:
        entry["tags"] = list(tags)
    if extra:
        entry.update(extra)
    log = state.setdefault("emotion_log", [])
    if log and should_compact_low_value_log(log[-1], entry):
        compact_low_value_log(log[-1], entry)
        return state
    if event_type == "turn" and not should_write_turn_log(entry):
        return state
    append_limited(state, "emotion_log", entry, state.get("log_limit", 200))
    return state


def increment_count(counter, key, amount=1):
    if key is None:
        key = "<none>"
    counter[str(key)] = counter.get(str(key), 0) + amount


def salience_bucket(entry):
    if "salience" not in entry:
        return "missing"
    value = salience_value(entry)
    if value <= LOW_SALIENCE_THRESHOLD:
        return "low"
    if value < CORE_SALIENCE_THRESHOLD:
        return "medium"
    return "core"


def audit_emotion_log(state):
    state = ensure_state_shape(state)
    log = state.get("emotion_log", [])
    event_types = {}
    appraisals = {}
    salience_buckets = {}
    low_value = {
        "pre_turn_decay_entries": 0,
        "pre_turn_decay_effective_events": 0,
        "turn_entries": 0,
        "turn_effective_events": 0,
        "neutral_turn_entries": 0,
        "neutral_turn_effective_events": 0,
    }
    open_loop_entries = 0
    core_entries = 0

    for entry in log:
        count = effective_event_count(entry)
        increment_count(event_types, entry.get("event_type"), count)
        if entry.get("event_type") == "turn":
            increment_count(appraisals, entry.get("appraisal") or "neutral", count)
        increment_count(salience_buckets, salience_bucket(entry), count)
        if bool(entry.get("open_loop")):
            open_loop_entries += 1
        if is_core_retention_entry(entry):
            core_entries += 1
        if entry.get("event_type") == "pre_turn_decay" and is_low_value_pre_turn_decay_entry(entry):
            low_value["pre_turn_decay_entries"] += 1
            low_value["pre_turn_decay_effective_events"] += count
        if entry.get("event_type") == "turn" and is_low_value_turn_entry(entry):
            low_value["turn_entries"] += 1
            low_value["turn_effective_events"] += count
            if (entry.get("appraisal") or "neutral") == "neutral":
                low_value["neutral_turn_entries"] += 1
                low_value["neutral_turn_effective_events"] += count

    log_entries = len(log)
    log_limit = state.get("log_limit", 200)
    warnings_out = []
    if log_entries >= log_limit:
        warnings_out.append("emotion_log_at_limit")
    pre_turn_decay_entries = event_types.get("pre_turn_decay", 0)
    if log_entries and pre_turn_decay_entries / log_entries >= 0.25:
        warnings_out.append("pre_turn_decay_noise_high")
    if log_entries and (low_value["pre_turn_decay_entries"] + low_value["turn_entries"]) / log_entries >= 0.4:
        warnings_out.append("low_value_log_pressure_high")

    return {
        "schema": state["_schema"],
        "log_entries": log_entries,
        "log_limit": log_limit,
        "available_entries": max(0, log_limit - log_entries),
        "effective_events": sum(effective_event_count(entry) for entry in log),
        "event_types": dict(sorted(event_types.items())),
        "appraisals": dict(sorted(appraisals.items())),
        "salience_buckets": dict(sorted(salience_buckets.items())),
        "open_loop_entries": open_loop_entries,
        "core_retention_entries": core_entries,
        "low_value": low_value,
        "warnings": warnings_out,
        "recommendations": [
            "Keep emotion_log focused on compact continuity signals, not transcripts or factual memory.",
            "Hosts own factual memory routing; Emotion Engine only provides retention and routing hints.",
        ],
    }


def compact_emotion_log(state, neutral_keep=RECENT_LOW_VALUE_NEUTRAL_KEEP):
    state = ensure_state_shape(state)
    before_audit = audit_emotion_log(state)
    log = state.get("emotion_log", [])
    low_neutral_indices = [
        idx for idx, entry in enumerate(log)
        if entry.get("event_type") == "turn"
        and (entry.get("appraisal") or "neutral") == "neutral"
        and not is_core_retention_entry(entry)
        and is_low_value_turn_entry(entry)
    ]
    neutral_keep_indices = set(low_neutral_indices[-neutral_keep:])
    pre_turn_decay_indices = [
        idx for idx, entry in enumerate(log)
        if entry.get("event_type") == "pre_turn_decay"
        and not is_core_retention_entry(entry)
    ]
    pre_turn_decay_keep_indices = set(pre_turn_decay_indices[-RECENT_PRE_TURN_DECAY_KEEP:])
    compacted = {
        "pre_turn_decay_entries": 0,
        "pre_turn_decay_effective_events": 0,
        "neutral_turn_entries": 0,
        "neutral_turn_effective_events": 0,
    }
    retained = []

    for idx, entry in enumerate(log):
        if (
            entry.get("event_type") == "pre_turn_decay"
            and not is_core_retention_entry(entry)
            and idx not in pre_turn_decay_keep_indices
        ):
            compacted["pre_turn_decay_entries"] += 1
            compacted["pre_turn_decay_effective_events"] += effective_event_count(entry)
            continue
        if idx in low_neutral_indices and idx not in neutral_keep_indices:
            compacted["neutral_turn_entries"] += 1
            compacted["neutral_turn_effective_events"] += effective_event_count(entry)
            continue
        retained.append(entry)

    total_removed_entries = compacted["pre_turn_decay_entries"] + compacted["neutral_turn_entries"]
    if total_removed_entries:
        retained.append({
            "timestamp": now_iso(),
            "event_type": "log_compaction",
            "trust": round(float(state.get("trust", 0.1)), 4),
            "situation": "low-value decay and neutral turn noise compacted by retention policy",
            "relational_meaning": "routine drift and ordinary neutral turns did not carry durable emotional continuity",
            "impact": "emotion_log remains focused on salient continuity signals",
            "salience": 0.1,
            "tags": ["retention", "compaction"],
            "compacted": compacted,
            "source": "compact_log",
        })

    compacted_state = deepcopy(state)
    compacted_state["emotion_log"] = retained[-compacted_state.get("log_limit", 200):]
    after_audit = audit_emotion_log(compacted_state)
    report = {
        "ok": True,
        "before": before_audit,
        "after": after_audit,
        "compacted": compacted,
        "removed_entries": total_removed_entries,
        "added_rollup": bool(total_removed_entries),
        "rules": {
            "protect_open_loop": True,
            "protect_salience_at_or_above": CORE_SALIENCE_THRESHOLD,
            "drop_low_value_pre_turn_decay_below_delta": LOW_VALUE_DECAY_DELTA_THRESHOLD,
            "drop_low_value_pre_turn_decay_below_pulse": LOW_VALUE_DECAY_PULSE_THRESHOLD,
            "keep_recent_pre_turn_decay_entries": RECENT_PRE_TURN_DECAY_KEEP,
            "keep_recent_low_value_neutral_turns": neutral_keep,
            "host_memory_routing": "host-owned; Emotion Engine does not choose factual memory destinations",
        },
    }
    return compacted_state, report


# ── Decay ────────────────────────────────────────────────────────────

def compute_mood_time_decay(state):
    """Apply short-lived time decay to the PAD mood vector.

    Mood behaves like working state: it decays by hours toward the
    personality_baseline. Trust can add emotional inertia, but mood does not
    share trust's slower relationship-level decay policy.
    """
    state = ensure_state_shape(state)
    if not state.get("enabled", True):
        return state
    last_time = parse_iso_datetime(state.get("last_interaction_iso"))
    if not last_time:
        return state

    now = datetime.now(timezone.utc)
    hours_elapsed = max(0.0, (now - last_time).total_seconds() / 3600.0)

    if hours_elapsed < 0.05:  # less than 3 minutes, skip
        return state

    trust = state.get("trust", 0.1)
    baseline = state["personality_baseline"]
    emotion = state["emotion"]

    base_lambda = 0.15
    trust_factor = 1.0 - (trust * 0.5)
    effective_lambda = base_lambda * trust_factor
    decay = math.exp(-effective_lambda * hours_elapsed)

    for dim in ["pleasure", "arousal", "dominance"]:
        current = emotion[dim]
        base = baseline[dim]
        emotion[dim] = clamp_dimension(dim, current * decay + base * (1 - decay))

    state["emotion"] = emotion
    state["affective_pulse"] = zero_affective_pulse("time_decay")
    return state


def compute_time_decay(state):
    """Backward-compatible alias for PAD mood decay."""
    return compute_mood_time_decay(state)


def compute_trust_time_decay(state):
    """Apply slow relationship-level time decay to trust when user is absent.

    Trust never drops below max(0.05, trust_anchor * 0.3), where trust_anchor
    tracks the highest trust reached by the relationship. This is intentionally
    separate from PAD mood decay.
    """
    state = ensure_state_shape(state)
    if not state.get("enabled", True):
        return state
    last_time = parse_iso_datetime(state.get("last_interaction_iso"))
    if not last_time:
        return state

    now = datetime.now(timezone.utc)
    days_elapsed = max(0.0, (now - last_time).total_seconds() / 86400.0)

    if days_elapsed < 0.5:  # less than 12 hours
        return state

    trust = state.get("trust", 0.1)
    trust_floor = max(0.05, state.get("trust_anchor", trust) * 0.3)

    if days_elapsed <= 3:
        total_decay = days_elapsed * 0.005
    elif days_elapsed <= 7:
        total_decay = 3 * 0.005 + (days_elapsed - 3) * 0.02
    else:
        total_decay = 3 * 0.005 + 4 * 0.02 + (days_elapsed - 7) * 0.03

    new_trust = max(trust_floor, trust - total_decay)
    state["trust"] = round(new_trust, 4)
    return state


def apply_time_decay(state, character_id=None, relationship_id=None):
    """Apply the legacy time-decay command while respecting paused state."""
    state = require_expected_state_identity(state, character_id, relationship_id)
    if not state.get("enabled", True):
        return state, {
            "status": "paused",
            "emotion": deepcopy(state["emotion"]),
            "affective_pulse": deepcopy(state["affective_pulse"]),
            "trust": state["trust"],
        }
    before = state["emotion"].copy()
    trust_before = state["trust"]
    state = compute_mood_time_decay(state)
    state = compute_trust_time_decay(state)
    state = add_emotion_log(
        state,
        "time_decay",
        cue="time-based drift applied",
        before=before,
        after=state["emotion"],
        delta=emotion_delta(before, state["emotion"]),
        tags=["decay"],
        extra={"trust_before": round(trust_before, 4), "trust_after": state["trust"]},
    )
    return state, {
        "status": "applied",
        "emotion": deepcopy(state["emotion"]),
        "affective_pulse": deepcopy(state["affective_pulse"]),
        "trust": state["trust"],
    }


def apply_in_session_decay(state):
    """Apply the small between-turn drift toward personality baseline."""
    state = ensure_state_shape(state)
    if not state.get("enabled", True):
        return state
    before = state["emotion"].copy()
    pulse_before = state["affective_pulse"].copy()
    baseline = state["personality_baseline"]
    after = {}
    baseline_pull = volatility_settings(state["volatility_profile"])["baseline_pull"]
    keep = 1.0 - baseline_pull

    for dim in ["pleasure", "arousal", "dominance"]:
        after[dim] = clamp_dimension(dim, before[dim] * keep + baseline[dim] * baseline_pull)

    state["emotion"] = after
    state["affective_pulse"] = decay_affective_pulse(pulse_before, state["volatility_profile"])
    delta = emotion_delta(before, after)
    pulse_after_intensity = state["affective_pulse"].get("intensity", 0.0)
    if (
        max(abs(v) for v in delta.values()) >= LOW_VALUE_DECAY_DELTA_THRESHOLD
        or pulse_after_intensity >= LOW_VALUE_DECAY_PULSE_THRESHOLD
    ):
        state = add_emotion_log(
            state,
            "pre_turn_decay",
            cue="quiet drift toward personality baseline",
            before=before,
            after=after,
            delta=delta,
            tags=["decay"],
            extra={
                "pulse_before": pulse_before,
                "pulse_after": state["affective_pulse"],
                "volatility_profile": state["volatility_profile"],
            },
        )
    return state


def pre_turn_decay(
    state,
    session_id=None,
    event_id=None,
    character_id=None,
    relationship_id=None,
):
    """Apply between-turn decay once inside the expected active session."""
    state = require_expected_state_identity(state, character_id, relationship_id)
    session_id = normalize_identifier(session_id, "session_id")
    event_id = normalize_identifier(event_id, "event_id")
    if not session_id or not event_id:
        raise ValueError("pre_turn_decay requires session_id and event_id")
    if event_already_processed(state, event_id):
        return state, {
            "status": "duplicate_event", "session_id": session_id, "event_id": event_id,
        }
    if (
        state.get("session", {}).get("status") != "active"
        or state["session"].get("active_session_id") != session_id
    ):
        return state, {
            "status": "no_active_session",
            "session_id": session_id,
            "active_session_id": state.get("session", {}).get("active_session_id"),
        }
    if not state.get("enabled", True):
        return state, {"status": "paused", "session_id": session_id, "event_id": event_id}
    state = apply_in_session_decay(state)
    mark_event_processed(state, event_id)
    return state, {"status": "applied", "session_id": session_id, "event_id": event_id}


# ── Appraisal ────────────────────────────────────────────────────────

def count_keyword_hits(text, keywords):
    return sum(1 for keyword in keywords if keyword in text)


def has_collaboration_action(text):
    return any(keyword in text for keyword in COLLABORATION_ACTION_KEYWORDS)


def classify_message(message):
    text = message.lower()
    scores = {
        label: count_keyword_hits(text, keywords)
        for label, keywords in APPRAISAL_KEYWORDS.items()
    }

    if scores["hostility"] and scores["repair"]:
        return "repair", scores["hostility"] + scores["repair"]
    if scores["hostility"]:
        return "hostility", scores["hostility"]
    if scores["boundary_pressure"]:
        return "boundary_pressure", scores["boundary_pressure"]
    if scores["repair"]:
        return "repair", scores["repair"]
    if scores["vulnerability"]:
        return "vulnerability", scores["vulnerability"]
    if scores["relationship_calibration"]:
        return "relationship_calibration", scores["relationship_calibration"]
    if scores["intimacy"]:
        return "intimacy", scores["intimacy"]
    if scores["playful"]:
        return "playful", scores["playful"]
    if scores["collaboration"] and has_collaboration_action(text):
        return "collaboration", scores["collaboration"]
    if scores["warmth"]:
        return "warmth", scores["warmth"]
    if scores["collaboration"]:
        return "collaboration", scores["collaboration"]
    return "neutral", 0


def trust_modulate(raw_delta, trust):
    modulated = {}
    for key, value in raw_delta.items():
        value = clamp(float(value), -0.15, 0.15)
        if value > 0:
            actual = value * (1 + trust * 0.3)
        elif value < 0:
            actual = value * (1 - trust * 0.5)
        else:
            actual = 0.0
        modulated[key] = round(clamp(actual, -0.15, 0.15), 4)
    return modulated


def appraise_message(state, message):
    """Return a deterministic first-pass PAD shift suggestion.

    This is a guardrail, not an oracle. The agent should adjust it when context,
    personality, or relationship history makes the keyword signal misleading.
    """
    state = ensure_state_shape(state)
    label, hits = classify_message(message)
    profile = APPRAISAL_PROFILES[label]
    intensity = 1.0 + min(max(hits - 1, 0), 3) * 0.15
    raw_delta = {
        key: round(clamp(value * intensity, -0.15, 0.15), 4)
        for key, value in profile["delta"].items()
    }
    trust_delta = trust_modulate(raw_delta, state["trust"])
    actual_delta = apply_mood_volatility(trust_delta, state["volatility_profile"])
    current = emotion_to_pad(state["emotion"])
    pulse = pulse_from_delta(
        trust_delta,
        state["volatility_profile"],
        label=label,
        source="appraise",
    )

    suggested = {}
    for short, value in current.items():
        dim = PAD_LONG[short]
        suggested[short] = clamp_dimension(dim, value + actual_delta[short])

    return {
        "appraisal": label,
        "cue": profile["cue"],
        "keyword_hits": hits,
        "trust": state["trust"],
        "volatility_profile": state["volatility_profile"],
        "current": current,
        "raw_delta": raw_delta,
        "trust_delta": trust_delta,
        "actual_delta": actual_delta,
        "affective_pulse": pulse,
        "suggested": suggested,
        "tags": profile["tags"],
    }


# ── Record Policy ────────────────────────────────────────────────────

POLICY_MODES = {"light", "always", "paused"}
POLICY_SUBJECTS = {"task", "relationship", "self", "mixed"}
POLICY_EVENT_TYPES = {
    "work_checkpoint",
    "concrete_feedback",
    "repair",
    "boundary",
    "stable_preference",
    "emotional_milestone",
    "explicit_trust",
    "relationship_calibration",
    "intimacy",
    "playful",
    "vulnerability",
    "hostility",
    "neutral",
}
POLICY_CONTEXT_ALIASES = {
    "milestone": {"milestone", "completed", "completion", "ship", "shipped", "verified", "done"},
    "concrete_feedback": {"concrete", "specific", "feedback", "behavior", "implementation"},
    "stable_preference": {"preference", "future", "default", "remember"},
    "repair": {"repair", "apology", "correction"},
    "boundary_pressure": {"boundary", "pressure"},
    "relationship_calibration": {"relationship", "relationship_calibration", "tone", "address", "nickname"},
    "intimacy": {"intimacy", "affection", "companion", "close"},
    "playful": {"play", "playful", "banter", "tease", "joke"},
}
CONCRETE_FEEDBACK_KEYWORDS = [
    "because", "when you", "the way you", "that part", "this part", "具体",
    "这次", "这个判断", "这个做法", "这里", "因为", "你刚", "你这",
]
STABLE_PREFERENCE_KEYWORDS = [
    "以后", "保持", "默认", "都这样", "一直这样", "下次", "remember", "from now on",
    "keep doing", "default to",
]
def parse_record_policy_args(args):
    options = {
        "mode": None,
        "contexts": [],
        "subject": None,
        "event_type": None,
        "host_approved": False,
        "memory_owner": None,
        "source": "model_inferred",
        "message": "",
    }
    message_parts = []
    i = 0
    while i < len(args):
        token = args[i]
        if token == "--mode" and i + 1 < len(args):
            options["mode"] = args[i + 1]
            i += 2
        elif token == "--context" and i + 1 < len(args):
            raw = args[i + 1]
            options["contexts"].extend(part.strip() for part in raw.split(",") if part.strip())
            i += 2
        elif token in {"--subject", "--event-type", "--memory-owner", "--source"} and i + 1 < len(args):
            key = token[2:].replace("-", "_")
            options[key] = args[i + 1]
            i += 2
        elif token == "--host-approved":
            options["host_approved"] = True
            i += 1
        else:
            message_parts.append(token)
            i += 1
    options["message"] = " ".join(message_parts).strip()
    return options


def normalize_policy_contexts(contexts):
    normalized = set()
    for context in contexts or []:
        text = str(context).strip().lower().replace("-", "_")
        if not text:
            continue
        normalized.add(text)
        for canonical, aliases in POLICY_CONTEXT_ALIASES.items():
            if text in aliases:
                normalized.add(canonical)
    return sorted(normalized)


def message_has_any(text, keywords):
    lowered = text.lower()
    return any(keyword in lowered for keyword in keywords)


def recent_turn_appraisal_count(state, appraisal, window=8):
    turn_logs = [
        entry for entry in state.get("emotion_log", [])
        if entry.get("event_type") == "turn"
    ]
    return sum(1 for entry in turn_logs[-window:] if entry.get("appraisal") == appraisal)


def policy_reply_bias(reason, appraisal, decision):
    base = ["do not mention PAD/trust unless asked"]
    if decision == "route_host_memory":
        return ["stay task-focused", "route durable facts to host memory", *base]
    if decision == "state_only":
        return ["allow short-lived tone movement", "do not create durable emotional memory", *base]
    if decision == "respond_only":
        if reason == "neutral_task":
            return ["stay task-focused", *base]
        return ["acknowledge briefly", "stay practical", "do not become effusive", *base]
    if reason in {"boundary_pressure", "hostility"}:
        return ["keep boundaries", "stay calm", "do not escalate", *base]
    if reason == "repair":
        return ["acknowledge repair", "return to useful forward motion", *base]
    if reason == "relationship_calibration":
        return ["honor the relationship calibration", "make the tone adjustment explicit but brief", *base]
    if reason == "intimacy":
        return ["respond warmly within established boundaries", "do not over-escalate", *base]
    if reason == "playful":
        return ["allow light banter", "keep the practical thread available", *base]
    if reason == "stable_preference":
        return ["acknowledge preference", "consider durable memory only if future work benefits", *base]
    if appraisal == "warmth":
        return ["acknowledge warmth briefly", "stay practical", "do not become effusive", *base]
    if appraisal == "collaboration":
        return ["treat as collaborative signal", "keep concrete next steps", *base]
    return ["keep response aligned with stable persona", *base]


def policy_salience(reason, appraisal, mode, habituation_count):
    if mode == "paused":
        return 0.0
    base = {
        "hostility": 0.8,
        "boundary_pressure": 0.7,
        "repair": 0.65,
        "stable_preference": 0.6,
        "explicit_trust": 0.5,
        "concrete_feedback": 0.45,
        "milestone_warmth": 0.38,
        "milestone_collaboration": 0.35,
        "vulnerability": 0.45,
        "relationship_calibration": 0.55,
        "intimacy": 0.35,
        "playful": 0.24,
        "generic_praise": 0.2,
        "generic_praise_habituated": 0.08,
        "neutral_task": 0.04,
    }.get(reason, 0.2 if appraisal != "neutral" else 0.04)
    if reason in {"generic_praise", "generic_praise_habituated"}:
        base = max(0.03, base - habituation_count * 0.05)
    if mode == "light" and reason == "neutral_task":
        base = 0.0
    return round(clamp(base, 0.0, 1.0), 2)


def record_policy(
    state,
    message,
    mode=None,
    contexts=None,
    subject=None,
    event_type=None,
    host_approved=False,
    memory_owner=None,
    source="model_inferred",
):
    """Decide whether a turn should be persisted under light/always/paused mode.

    The policy is deterministic and side-effect free. It does not write state,
    call an LLM, or change trust. Callers may use the returned decision to run
    record_turn or simply shape the current reply.
    """
    state = ensure_state_shape(state)
    requested_mode = (mode or state.get("runtime_mode") or "light").strip().lower()
    if requested_mode not in POLICY_MODES:
        requested_mode = "light"
    normalized_contexts = normalize_policy_contexts(contexts)
    message = message or ""
    appraisal = appraise_message(state, message)
    label = appraisal["appraisal"]
    text = message.lower()
    normalized_subject = str(subject or "mixed").strip().lower().replace("-", "_")
    if normalized_subject not in POLICY_SUBJECTS:
        normalized_subject = "mixed"
    normalized_event_type = str(event_type or "").strip().lower().replace("-", "_")
    if normalized_event_type not in POLICY_EVENT_TYPES:
        normalized_event_type = ""

    if requested_mode == "paused" or not state.get("enabled", True):
        return {
            "mode": requested_mode,
            "decision": "respond_only",
            "reason": "paused",
            "appraisal": label,
            "salience": 0.0,
            "trust_eligible": False,
            "trust_candidate": False,
            "reply_bias": policy_reply_bias("paused", label, "respond_only"),
            "context": normalized_contexts,
            "subject": normalized_subject,
            "event_type": normalized_event_type or "neutral",
            "host_approved": bool(host_approved),
            "source": source,
            "current": appraisal["current"],
            "suggested": appraisal["current"],
            "actual_delta": {"P": 0.0, "A": 0.0, "D": 0.0},
            "affective_pulse": zero_affective_pulse("record_policy"),
        }

    concrete = (
        "concrete_feedback" in normalized_contexts
        or message_has_any(message, CONCRETE_FEEDBACK_KEYWORDS)
    )
    stable_preference = (
        "stable_preference" in normalized_contexts
        or message_has_any(message, STABLE_PREFERENCE_KEYWORDS)
    )
    explicit_trust = any(keyword in text for keyword in TRUST_SETTLEMENT_KEYWORDS)
    warmth_habituation = recent_turn_appraisal_count(state, "warmth")
    inferred_event_type = normalized_event_type
    if not inferred_event_type:
        context_map = {
            "milestone": "work_checkpoint",
            "concrete_feedback": "concrete_feedback",
            "stable_preference": "stable_preference",
            "repair": "repair",
            "boundary_pressure": "boundary",
            "relationship_calibration": "relationship_calibration",
            "intimacy": "intimacy",
            "playful": "playful",
        }
        inferred_event_type = next(
            (mapped for key, mapped in context_map.items() if key in normalized_contexts),
            "",
        )
    if not inferred_event_type:
        if stable_preference:
            inferred_event_type = "stable_preference"
        elif concrete:
            inferred_event_type = "concrete_feedback"
        elif explicit_trust:
            inferred_event_type = "explicit_trust"
        elif label == "boundary_pressure":
            inferred_event_type = "boundary"
        elif label in POLICY_EVENT_TYPES:
            inferred_event_type = label
        else:
            inferred_event_type = "neutral"

    task_owned = normalized_subject == "task" or inferred_event_type == "work_checkpoint"
    relationship_event = inferred_event_type in {
        "repair", "boundary", "emotional_milestone", "explicit_trust",
        "relationship_calibration", "intimacy", "playful", "vulnerability", "hostility",
    }
    trust_candidate = inferred_event_type in {"repair", "boundary", "explicit_trust", "hostility"}

    decision = "respond_only"
    reason = "host_approval_required" if relationship_event else "neutral_task"
    if task_owned:
        decision = "route_host_memory" if memory_owner else "respond_only"
        reason = "work_checkpoint"
    elif inferred_event_type in {"stable_preference", "concrete_feedback"}:
        decision = "route_host_memory" if memory_owner else "respond_only"
        reason = inferred_event_type
    elif normalized_subject == "self" and bool(host_approved):
        decision = "state_only"
        reason = inferred_event_type
    elif relationship_event and normalized_subject in {"relationship", "mixed"} and bool(host_approved):
        decision = "record_emotion"
        reason = inferred_event_type
    elif label == "warmth":
        reason = "generic_praise_habituated" if warmth_habituation else "generic_praise"

    salience = policy_salience(reason, label, requested_mode, warmth_habituation)
    if decision in {"respond_only", "route_host_memory"}:
        salience = 0.0

    return {
        "mode": requested_mode,
        "decision": decision,
        "reason": reason,
        "appraisal": label,
        "salience": salience,
        "trust_eligible": False,
        "trust_candidate": bool(trust_candidate),
        "evidence_required": bool(trust_candidate),
        "reply_bias": policy_reply_bias(reason, label, decision),
        "context": normalized_contexts,
        "subject": normalized_subject,
        "event_type": inferred_event_type,
        "host_approved": bool(host_approved),
        "memory_owner": memory_owner,
        "source": source,
        "habituation": {"recent_warmth_turns": warmth_habituation},
        "current": appraisal["current"],
        "suggested": appraisal["suggested"] if decision in {"state_only", "record_emotion"} else appraisal["current"],
        "actual_delta": appraisal["actual_delta"] if decision in {"state_only", "record_emotion"} else {"P": 0.0, "A": 0.0, "D": 0.0},
        "affective_pulse": appraisal["affective_pulse"] if decision in {"state_only", "record_emotion"} else zero_affective_pulse("record_policy"),
    }


# ── Pattern Extraction ───────────────────────────────────────────────

def extract_patterns(state):
    """Extract emotion trajectory patterns for trust evaluation."""
    state = ensure_state_shape(state)
    trajectory = state.get("emotion_trajectory", [])
    if len(trajectory) < 2:
        return {
            "sufficient_data": False,
            "turn_count": len(trajectory),
        }

    pleasures = [t["P"] for t in trajectory]
    dominances = [t["D"] for t in trajectory]
    pulse_intensities = [
        normalize_affective_pulse(t.get("pulse"))["intensity"]
        for t in trajectory
    ]

    p_deltas = [pleasures[i+1] - pleasures[i] for i in range(len(pleasures)-1)]
    avg_p_delta = sum(p_deltas) / len(p_deltas)

    had_conflict = any(p < -0.2 for p in pleasures)

    had_repair = False
    if had_conflict:
        min_p = min(pleasures)
        min_idx = pleasures.index(min_p)
        if min_idx < len(pleasures) - 1:
            post_min_max = max(pleasures[min_idx+1:])
            if post_min_max - min_p > 0.2:
                had_repair = True

    v_shape = had_conflict and had_repair and pleasures[-1] > pleasures[0] - 0.1

    avg_d = sum(dominances) / len(dominances)
    baseline_d = state["personality_baseline"]["dominance"]
    dominance_suppressed = avg_d < baseline_d - 0.2

    mean_p = sum(pleasures) / len(pleasures)
    variance = sum((p - mean_p) ** 2 for p in pleasures) / len(pleasures)
    mood_volatility = math.sqrt(variance)
    pulse_mean = sum(pulse_intensities) / len(pulse_intensities)
    pulse_max = max(pulse_intensities)

    too_smooth = mood_volatility < 0.05 and pulse_max < 0.12 and mean_p > 0.3
    end_vs_start_p = pleasures[-1] - pleasures[0]

    negative_ratio = sum(1 for p in pleasures if p < 0) / len(pleasures)
    sustained_negative = negative_ratio > 0.6

    log_tags = [
        tag
        for entry in state.get("emotion_log", [])[-20:]
        for tag in entry.get("tags", [])
    ]
    boundary_events = sum(1 for tag in log_tags if tag in ["boundary", "boundary_pressure"])
    repair_events = sum(1 for tag in log_tags if tag == "repair")
    collaboration_events = sum(1 for tag in log_tags if tag == "collaboration")
    warmth_events = sum(1 for tag in log_tags if tag == "warmth")
    hostility_events = sum(1 for tag in log_tags if tag in ["negative", "hostility"])

    return {
        "sufficient_data": True,
        "turn_count": len(trajectory),
        "avg_pleasure_delta": round(avg_p_delta, 4),
        "had_conflict": had_conflict,
        "had_repair": had_repair,
        "v_shape": v_shape,
        "dominance_suppressed": dominance_suppressed,
        "volatility": round(mood_volatility, 4),
        "mood_volatility": round(mood_volatility, 4),
        "pulse_mean": round(pulse_mean, 4),
        "pulse_max": round(pulse_max, 4),
        "too_smooth": too_smooth,
        "end_vs_start_pleasure": round(end_vs_start_p, 4),
        "sustained_negative": sustained_negative,
        "negative_ratio": round(negative_ratio, 4),
        "recent_boundary_events": boundary_events,
        "recent_repair_events": repair_events,
        "recent_collaboration_events": collaboration_events,
        "recent_warmth_events": warmth_events,
        "recent_hostility_events": hostility_events,
    }


# ── Trust Update ─────────────────────────────────────────────────────

TRUST_SETTLEMENT_KEYWORDS = [
    "trust your judgment",
    "trust your judgement",
    "use your judgment",
    "use your judgement",
    "you decide",
    "direct judgment",
    "call it directly",
    "be direct",
    "i trust you",
    "相信你的判断",
    "你来判断",
    "你决定",
    "直接判断",
    "直接一点",
]


def settlement_trajectory_signature(state, session_id=None, evidence_ids=None):
    """Return a stable settlement id derived from durable evidence identity."""
    state = ensure_state_shape(state)
    payload = {
        "state_id": state.get("identity", {}).get("state_id"),
        "session_id": session_id or state.get("session", {}).get("last_session_id"),
        "evidence_ids": sorted(str(value) for value in (evidence_ids or [])),
    }
    encoded = json.dumps(payload, sort_keys=True, ensure_ascii=False, separators=(",", ":"))
    return hashlib.sha256(encoded.encode("utf-8")).hexdigest()[:16]


TRUST_EVIDENCE_RULES = {
    "explicit_trust": {"direction": 1, "default_weight": 0.03, "max_weight": 0.05},
    "conflict_repair": {"direction": 1, "default_weight": 0.04, "max_weight": 0.05},
    "boundary_pressure": {"direction": -1, "default_weight": 0.03, "max_weight": 0.2},
    "hostility": {"direction": -1, "default_weight": 0.06, "max_weight": 0.2},
}


def session_record(state, session_id):
    for entry in reversed(state.get("session_ledger", [])):
        if entry.get("session_id") == session_id:
            return entry
    return None


def event_already_processed(state, event_id):
    return bool(event_id) and str(event_id) in state.get("processed_event_ids", [])


def enforce_idempotency_retention(state):
    """Bound replay ledgers and prune completed session evidence as one bundle.

    Replay protection is exact within the retained window. The active session is
    never removed, even when callers configure a very small test window.
    """
    retention = normalize_idempotency_retention(state.get("idempotency_retention"))
    state["idempotency_retention"] = retention
    pruned_any = False

    events = state.setdefault("processed_event_ids", [])
    event_overflow = max(0, len(events) - retention["event_limit"])
    if event_overflow:
        del events[:event_overflow]
        retention["pruned_events"] += event_overflow
        pruned_any = True

    ledger = state.setdefault("session_ledger", [])
    terminal_indexes = [
        index for index, entry in enumerate(ledger)
        if entry.get("status") in {"closed", "settled"}
    ]
    overflow = max(0, len(ledger) - retention["session_limit"])
    indexes_to_remove = set(terminal_indexes[:overflow])
    if indexes_to_remove:
        pruned_session_ids = {
            ledger[index].get("session_id") for index in indexes_to_remove
            if ledger[index].get("session_id")
        }
        state["session_ledger"] = [
            entry for index, entry in enumerate(ledger) if index not in indexes_to_remove
        ]
        retention["pruned_sessions"] += len(indexes_to_remove)

        old_evidence = state.setdefault("trust_evidence", [])
        state["trust_evidence"] = [
            entry for entry in old_evidence
            if entry.get("session_id") not in pruned_session_ids
        ]
        retention["pruned_evidence"] += len(old_evidence) - len(state["trust_evidence"])

        old_settlements = state.setdefault("trust_settlements", [])
        state["trust_settlements"] = [
            entry for entry in old_settlements
            if entry.get("session_id") not in pruned_session_ids
        ]
        retention["pruned_settlements"] += (
            len(old_settlements) - len(state["trust_settlements"])
        )
        pruned_any = True

    if pruned_any:
        retention["last_pruned_at"] = now_iso()
    return state


def mark_event_processed(state, event_id):
    event_id = normalize_identifier(event_id, "event_id")
    if not event_id:
        raise ValueError("event_id is required for idempotent mutations")
    if not event_already_processed(state, event_id):
        state.setdefault("processed_event_ids", []).append(event_id)
    return enforce_idempotency_retention(state)


def normalize_trust_evidence(evidence, session_id, event_id):
    if not isinstance(evidence, dict):
        raise ValueError("trust evidence must be an object")
    evidence_id = normalize_identifier(evidence.get("evidence_id"), "evidence_id")
    evidence_type = str(evidence.get("evidence_type") or "").strip().lower()
    if not evidence_id or evidence_type not in TRUST_EVIDENCE_RULES:
        raise ValueError("trust evidence requires a unique evidence_id and supported evidence_type")
    rule = TRUST_EVIDENCE_RULES[evidence_type]
    weight = abs(float(evidence.get("weight", rule["default_weight"])))
    weight = round(clamp(weight, 0.0, rule["max_weight"]), 4)
    return {
        "evidence_id": evidence_id,
        "session_id": session_id,
        "event_id": event_id,
        "evidence_type": evidence_type,
        "direction": rule["direction"],
        "weight": weight,
        "eligible": bool(evidence.get("eligible") is True),
        "source": truncate_text(evidence.get("source") or "host_approved", 80),
        "created_at": now_iso(),
        "consumed_by_settlement_id": None,
    }


def assess_trust_settlement(state, session_id=None, patterns=None):
    """Assess trust exclusively from explicit, unconsumed evidence."""
    state = ensure_state_shape(state)
    session_id = session_id or state.get("session", {}).get("last_session_id")
    evidence = [
        item for item in state.get("trust_evidence", [])
        if item.get("session_id") == session_id
        and item.get("eligible") is True
        and not item.get("consumed_by_settlement_id")
    ]
    raw_delta = round(clamp(
        sum(float(item.get("direction", 0)) * float(item.get("weight", 0.0)) for item in evidence),
        -0.2,
        0.05,
    ), 4)
    if not evidence:
        return 0.0, "no_eligible_evidence", "no explicit unconsumed trust evidence", []
    if raw_delta > 0:
        reason_code = "explicit_positive_evidence"
    elif raw_delta < 0:
        reason_code = "explicit_negative_evidence"
    else:
        reason_code = "balanced_evidence"
    return raw_delta, reason_code, "trust derived from explicit host-approved evidence", evidence


def settlement_record(settlement_id, state, raw_delta, status, session_id=None):
    ledger = session_record(state, session_id) if session_id else None
    return {
        "timestamp": now_iso(),
        "settlement_id": settlement_id,
        "session_count": int(state.get("session_count", 0)),
        "turn_count": int(ledger.get("turn_count", 0)) if ledger else len(state.get("emotion_trajectory", [])),
        "trust_before": round(float(state.get("trust", 0.1)), 4),
        "trust_after": round(float(state.get("trust", 0.1)), 4),
        "raw_delta": round(float(raw_delta), 4),
        "status": status,
    }


def settle_trust(
    state,
    session_id=None,
    event_id=None,
    character_id=None,
    relationship_id=None,
):
    """Settle a closed session exactly once using explicit evidence only."""
    state = require_expected_state_identity(state, character_id, relationship_id)
    session_id = normalize_identifier(
        session_id or state.get("session", {}).get("last_session_id"), "session_id"
    )
    event_id = normalize_identifier(event_id, "event_id")
    if not session_id or not event_id:
        raise ValueError("settle_trust requires session_id and event_id")
    if not state.get("enabled", True):
        return state, {"status": "paused", "session_id": session_id, "raw_delta": 0.0}
    record = session_record(state, session_id)
    if not record or record.get("status") not in {"closed", "settled"}:
        return state, {"status": "session_not_closed", "session_id": session_id, "raw_delta": 0.0}
    active_session_id = state.get("session", {}).get("active_session_id")
    if state.get("session", {}).get("status") == "active":
        return state, {
            "status": "active_session_conflict",
            "session_id": session_id,
            "active_session_id": active_session_id,
            "raw_delta": 0.0,
        }
    if record.get("settlement_id"):
        return state, {
            "status": "already_settled",
            "session_id": session_id,
            "settlement_id": record["settlement_id"],
            "raw_delta": 0.0,
        }
    if event_already_processed(state, event_id):
        return state, {"status": "duplicate_event", "session_id": session_id, "raw_delta": 0.0}
    raw_delta, reason_code, reason, evidence = assess_trust_settlement(state, session_id)
    if not evidence:
        return state, {
            "status": "no_eligible_evidence",
            "session_id": session_id,
            "raw_delta": 0.0,
            "reason_code": reason_code,
        }

    evidence_ids = [item["evidence_id"] for item in evidence]
    settlement_id = settlement_trajectory_signature(state, session_id, evidence_ids)
    trust_before = round(float(state.get("trust", 0.1)), 4)
    if raw_delta:
        state = apply_trust_delta(
            state,
            raw_delta,
            settlement_id=settlement_id,
            evidence_ids=evidence_ids,
            session_id=session_id,
        )
    trust_after = round(float(state.get("trust", 0.1)), 4)
    for item in state.get("trust_evidence", []):
        if item.get("evidence_id") in evidence_ids:
            item["consumed_by_settlement_id"] = settlement_id
    record["status"] = "settled"
    record["settled_at"] = now_iso()
    record["settlement_id"] = settlement_id
    record["settlement_event_id"] = event_id
    if state["session"].get("last_session_id") == session_id:
        state["session"]["settled_at"] = record["settled_at"]
    settlement = settlement_record(settlement_id, state, raw_delta, "settled", session_id=session_id)
    settlement.update({
        "event_id": event_id,
        "session_id": session_id,
        "trust_before": trust_before,
        "trust_after": trust_after,
        "reason_code": reason_code,
        "evidence_ids": evidence_ids,
    })
    state.setdefault("trust_settlements", []).append(settlement)
    mark_event_processed(state, event_id)
    return state, {
        "status": "settled",
        "event_id": event_id,
        "session_id": session_id,
        "settlement_id": settlement_id,
        "raw_delta": raw_delta,
        "trust_before": trust_before,
        "trust_after": trust_after,
        "reason_code": reason_code,
        "reason": reason,
        "evidence_ids": evidence_ids,
    }

def apply_trust_delta(
    state,
    raw_delta,
    settlement_id=None,
    evidence_ids=None,
    session_id=None,
    manual_override_reason=None,
):
    """Apply trust change with diminishing returns for positive deltas."""
    state = require_v3_state(state)
    if not state.get("enabled", True):
        return state
    trust = state.get("trust", 0.1)
    raw_delta = clamp(float(raw_delta), -0.2, 0.05)

    if raw_delta > 0:
        effective_delta = raw_delta * (1 - trust)
    else:
        if trust > 0.6 and raw_delta > -0.15:
            effective_delta = raw_delta * 0.5
        else:
            effective_delta = raw_delta

    new_trust = clamp(trust + effective_delta, 0.05, 1.0)
    state["trust"] = round(new_trust, 4)
    state["trust_anchor"] = round(max(state.get("trust_anchor", trust), state["trust"]), 4)

    entry = {
        "timestamp": now_iso(),
        "old": round(trust, 4),
        "new": round(new_trust, 4),
        "raw_delta": round(raw_delta, 4),
        "effective_delta": round(effective_delta, 4),
        "session_id": session_id,
        "settlement_id": settlement_id,
        "evidence_ids": list(evidence_ids or []),
    }
    manual_override_reason = truncate_text(manual_override_reason, 220)
    append_limited(state, "trust_history", entry, 50)

    log_extra = {
        "trust_before": round(trust, 4),
        "trust_after": round(new_trust, 4),
        "session_id": session_id,
        "settlement_id": settlement_id,
        "evidence_ids": list(evidence_ids or []),
    }
    if manual_override_reason:
        log_extra["manual_override_reason"] = manual_override_reason
    state = add_emotion_log(
        state,
        "trust_update",
        cue=(
            "relationship trust adjusted by explicit host override"
            if manual_override_reason
            else "relationship trust recalibrated from session evidence"
        ),
        tags=["trust"],
        extra=log_extra,
    )
    return state


def apply_manual_trust_update(
    state,
    raw_delta,
    reason,
    character_id=None,
    relationship_id=None,
):
    """Apply an explicit host trust override without mutating unrelated logs."""
    state = require_expected_state_identity(state, character_id, relationship_id)
    reason = truncate_text(reason, 220)
    if not reason:
        raise ValueError("manual trust update requires a reason")
    if not state.get("enabled", True):
        return state, {
            "status": "paused",
            "trust": state["trust"],
            "trust_anchor": state["trust_anchor"],
        }
    state = apply_trust_delta(state, raw_delta, manual_override_reason=reason)
    return state, {
        "status": "applied",
        "trust": state["trust"],
        "trust_anchor": state["trust_anchor"],
    }


# ── Session Lifecycle ────────────────────────────────────────────────

def session_start(
    state,
    session_id=None,
    event_id=None,
    occurred_at=None,
    character_id=None,
    relationship_id=None,
):
    """Open one explicitly identified session; replays are no-ops."""
    state = require_expected_state_identity(state, character_id, relationship_id)
    session_id = normalize_identifier(session_id, "session_id")
    event_id = normalize_identifier(event_id, "event_id")
    if not session_id or not event_id:
        raise ValueError("session_start requires session_id and event_id")
    existing = session_record(state, session_id)
    if existing:
        status = "already_active" if existing and existing.get("status") == "active" else "already_closed"
        return state, {"status": status, "session_id": session_id}
    if event_already_processed(state, event_id):
        return state, {"status": "duplicate_event", "session_id": session_id, "event_id": event_id}
    active = state.get("session", {}).get("active_session_id")
    if state.get("session", {}).get("status") == "active" and active != session_id:
        return state, {
            "status": "active_session_conflict",
            "session_id": session_id,
            "active_session_id": active,
        }
    if not state.get("enabled", True):
        return state, {"status": "paused", "session_id": session_id}
    before = state["emotion"].copy()
    pulse_before = state["affective_pulse"].copy()
    trust_before = state["trust"]
    state = compute_mood_time_decay(state)
    state = compute_trust_time_decay(state)
    after = state["emotion"].copy()
    state["emotion_trajectory"] = []
    state["session_count"] = state.get("session_count", 0) + 1
    timestamp = occurred_at or now_iso()
    state["last_interaction_iso"] = timestamp
    state["session"] = {
        "active_session_id": session_id,
        "last_session_id": session_id,
        "status": "active",
        "opened_at": timestamp,
        "closed_at": None,
        "settled_at": None,
    }
    state.setdefault("session_ledger", []).append({
        "session_id": session_id,
        "status": "active",
        "opened_at": timestamp,
        "closed_at": None,
        "settled_at": None,
        "turn_count": 0,
        "settlement_id": None,
    })
    state = add_emotion_log(
        state,
        "session_start",
        cue="new session initialized",
        before=before,
        after=after,
        delta=emotion_delta(before, after),
        tags=["session"],
        extra={
            "session_id": session_id,
            "event_id": event_id,
            "trust_before": round(trust_before, 4),
            "trust_after": state["trust"],
            "pulse_before": pulse_before,
            "pulse_after": state["affective_pulse"],
            "volatility_profile": state["volatility_profile"],
        },
    )
    mark_event_processed(state, event_id)
    return state, {"status": "started", "session_id": session_id, "session_count": state["session_count"]}


def record_turn(
    state,
    p,
    a,
    d,
    cue=None,
    appraisal=None,
    situation=None,
    character_lens=None,
    relational_meaning=None,
    impact=None,
    open_loop=None,
    follow_up_bias=None,
    salience=None,
    session_id=None,
    event_id=None,
    subject="relationship",
    semantic_event_type=None,
    trust_evidence=None,
    persist_log=True,
    host_approved=False,
    character_id=None,
    relationship_id=None,
):
    """Record a single turn's emotion values to the trajectory and log."""
    state = require_expected_state_identity(state, character_id, relationship_id)
    session_id = normalize_identifier(session_id, "session_id")
    event_id = normalize_identifier(event_id, "event_id")
    if not session_id or not event_id:
        raise ValueError("record_turn requires session_id and event_id")
    if host_approved is not True:
        return state, {
            "status": "host_veto",
            "session_id": session_id,
            "event_id": event_id,
        }
    normalized_subject = str(subject or "mixed").strip().lower().replace("-", "_")
    normalized_semantic_type = str(
        semantic_event_type or appraisal or "neutral"
    ).strip().lower().replace("-", "_")
    if normalized_subject == "task" or normalized_semantic_type == "work_checkpoint":
        return state, {
            "status": "semantic_veto",
            "decision": "route_host_memory",
            "reason": "work_checkpoint",
            "session_id": session_id,
            "event_id": event_id,
        }
    if normalized_semantic_type in {"stable_preference", "concrete_feedback"}:
        return state, {
            "status": "semantic_veto",
            "decision": "route_host_memory",
            "reason": normalized_semantic_type,
            "session_id": session_id,
            "event_id": event_id,
        }
    if event_already_processed(state, event_id):
        return state, {"status": "duplicate_event", "session_id": session_id, "event_id": event_id}
    if state.get("session", {}).get("status") != "active" or state["session"].get("active_session_id") != session_id:
        return state, {
            "status": "no_active_session",
            "session_id": session_id,
            "active_session_id": state.get("session", {}).get("active_session_id"),
        }
    if not state.get("enabled", True):
        return state, {"status": "paused", "session_id": session_id}
    raw_evidence_items = (
        trust_evidence
        if isinstance(trust_evidence, list)
        else ([trust_evidence] if trust_evidence else [])
    )
    if raw_evidence_items and normalized_subject not in {"relationship", "mixed"}:
        return state, {
            "status": "evidence_scope_rejected",
            "session_id": session_id,
            "event_id": event_id,
            "subject": normalized_subject,
        }
    normalized_evidence_items = []
    known_ids = {item.get("evidence_id") for item in state.get("trust_evidence", [])}
    batch_ids = set()
    for raw_evidence in raw_evidence_items:
        evidence = normalize_trust_evidence(raw_evidence, session_id, event_id)
        evidence_id = evidence["evidence_id"]
        if evidence_id in known_ids or evidence_id in batch_ids:
            return state, {
                "status": "duplicate_evidence",
                "session_id": session_id,
                "event_id": event_id,
                "evidence_id": evidence_id,
            }
        batch_ids.add(evidence_id)
        normalized_evidence_items.append(evidence)
    before = state["emotion"].copy()
    after = pad_to_emotion(p, a, d)
    delta = emotion_delta(before, after)
    pulse = pulse_from_delta(
        delta,
        state["volatility_profile"],
        label=appraisal or "turn",
        source="record_turn",
    )
    turn = len(state["emotion_trajectory"]) + 1
    if cue and not situation:
        situation = cue

    entry = {
        "turn": turn,
        "P": after["pleasure"],
        "A": after["arousal"],
        "D": after["dominance"],
        "timestamp": now_iso(),
        "pulse": pulse,
        "session_id": session_id,
        "event_id": event_id,
        "subject": normalized_subject,
        "semantic_event_type": normalized_semantic_type,
    }
    if appraisal:
        entry["appraisal"] = appraisal
    if situation:
        entry["situation"] = truncate_text(situation, 240)
    state["emotion_trajectory"].append(entry)

    state["emotion"] = after
    state["affective_pulse"] = pulse
    state["total_turns"] = state.get("total_turns", 0) + 1
    state["last_interaction_iso"] = now_iso()

    tags = [appraisal] if appraisal else None
    if persist_log:
        state = add_emotion_log(
            state,
            "turn",
            situation=situation or "turn emotional update",
            character_lens=character_lens,
            relational_meaning=relational_meaning,
            impact=impact,
            open_loop=open_loop,
            follow_up_bias=follow_up_bias,
            salience=salience,
            before=before,
            after=after,
            delta=delta,
            appraisal=appraisal,
            tags=tags,
            turn=turn,
            extra={
                "session_id": session_id,
                "event_id": event_id,
                "subject": normalized_subject,
                "semantic_event_type": normalized_semantic_type,
                "affective_pulse": pulse,
                "volatility_profile": state["volatility_profile"],
            },
        )
    recorded_evidence_ids = []
    for evidence in normalized_evidence_items:
        state.setdefault("trust_evidence", []).append(evidence)
        recorded_evidence_ids.append(evidence["evidence_id"])
    ledger_entry = session_record(state, session_id)
    if ledger_entry:
        ledger_entry["turn_count"] = int(ledger_entry.get("turn_count", 0)) + 1
    mark_event_processed(state, event_id)
    return state, {
        "status": "recorded" if persist_log else "state_only",
        "session_id": session_id,
        "event_id": event_id,
        "turn": turn,
        "evidence_ids": recorded_evidence_ids,
    }


def session_end(
    state,
    session_id=None,
    event_id=None,
    occurred_at=None,
    character_id=None,
    relationship_id=None,
):
    """Extract patterns and log the session close for trust evaluation."""
    state = require_expected_state_identity(state, character_id, relationship_id)
    session_id = normalize_identifier(session_id, "session_id")
    event_id = normalize_identifier(event_id, "event_id")
    if not session_id or not event_id:
        raise ValueError("session_end requires session_id and event_id")
    record = session_record(state, session_id)
    if record and record.get("status") in {"closed", "settled"}:
        return state, {"status": "already_closed", "session_id": session_id}
    if event_already_processed(state, event_id):
        return state, {"status": "duplicate_event", "session_id": session_id, "event_id": event_id}
    if state.get("session", {}).get("status") != "active" or state["session"].get("active_session_id") != session_id:
        return state, {"status": "no_active_session", "session_id": session_id}
    if not state.get("enabled", True):
        return state, {"status": "paused", "session_id": session_id}
    patterns = extract_patterns(state)
    timestamp = occurred_at or now_iso()
    state["last_interaction_iso"] = timestamp

    tags = ["session_end"]
    for pattern_key in [
        "v_shape",
        "had_conflict",
        "had_repair",
        "dominance_suppressed",
        "sustained_negative",
        "too_smooth",
    ]:
        if patterns.get(pattern_key):
            tags.append(pattern_key)

    state = add_emotion_log(
        state,
        "session_end",
        cue="session patterns extracted for trust evaluation",
        tags=tags,
        extra={"session_id": session_id, "event_id": event_id, "patterns": patterns},
    )
    record["status"] = "closed"
    record["closed_at"] = timestamp
    state["session"].update({
        "active_session_id": None,
        "last_session_id": session_id,
        "status": "closed",
        "closed_at": timestamp,
    })
    mark_event_processed(state, event_id)
    return state, {"status": "closed", "session_id": session_id, "patterns": patterns}


def evaluate_and_record_turn(
    state,
    event,
    p=None,
    a=None,
    d=None,
    memory=None,
    mode=None,
    character_id=None,
    relationship_id=None,
):
    """Atomically evaluate semantic ownership and, when allowed, record a turn."""
    character_id = character_id or (event.get("character_id") if isinstance(event, dict) else None)
    relationship_id = relationship_id or (event.get("relationship_id") if isinstance(event, dict) else None)
    state = require_expected_state_identity(state, character_id, relationship_id)
    if not isinstance(event, dict):
        raise ValueError("event must be a structured object")
    session_id = normalize_identifier(event.get("session_id"), "session_id")
    event_id = normalize_identifier(event.get("event_id"), "event_id")
    if not session_id or not event_id:
        raise ValueError("event requires session_id and event_id")
    if event_already_processed(state, event_id):
        return state, {
            "status": "duplicate_event",
            "decision": "respond_only",
            "session_id": session_id,
            "event_id": event_id,
        }

    policy = record_policy(
        state,
        event.get("message") or "",
        mode=mode,
        contexts=event.get("contexts"),
        subject=event.get("subject"),
        event_type=event.get("event_type"),
        host_approved=event.get("host_approved") is True,
        memory_owner=event.get("memory_owner"),
        source=event.get("source") or "model_inferred",
    )
    decision = policy["decision"]
    if decision in {"respond_only", "route_host_memory"}:
        return state, {
            "status": "not_recorded",
            "decision": decision,
            "session_id": session_id,
            "event_id": event_id,
            "policy": policy,
        }

    suggested = policy["suggested"]
    memory = dict(memory or {})
    selected_appraisal = memory.pop("appraisal", None) or policy["appraisal"]
    selected_salience = memory.pop("salience", None)
    if selected_salience is None:
        selected_salience = policy["salience"]
    selected_situation = memory.pop("situation", None) or event.get("message")
    state, result = record_turn(
        state,
        suggested["P"] if p is None else p,
        suggested["A"] if a is None else a,
        suggested["D"] if d is None else d,
        session_id=session_id,
        event_id=event_id,
        subject=policy["subject"],
        semantic_event_type=policy["event_type"],
        trust_evidence=event.get("trust_evidence"),
        persist_log=decision == "record_emotion",
        host_approved=True,
        character_id=character_id,
        relationship_id=relationship_id,
        appraisal=selected_appraisal,
        salience=selected_salience,
        situation=selected_situation,
        **memory,
    )
    result["decision"] = decision
    result["policy"] = policy
    return state, result


def record_semantic_event(
    state,
    event_type,
    *,
    session_id=None,
    event_id=None,
    subject="relationship",
    message=None,
    memory_owner=None,
    host_approved=False,
    character_id=None,
    relationship_id=None,
    **memory,
):
    """Persist a non-turn event only when the shared semantic policy allows it."""
    state = require_expected_state_identity(state, character_id, relationship_id)
    session_id = normalize_identifier(session_id, "session_id")
    event_id = normalize_identifier(event_id, "event_id")
    if not session_id or not event_id:
        raise ValueError("log_event requires session_id and event_id")
    if host_approved is not True:
        return state, {
            "status": "host_veto", "session_id": session_id, "event_id": event_id,
        }
    if not state.get("enabled", True):
        return state, {"status": "paused", "session_id": session_id, "event_id": event_id}
    if event_already_processed(state, event_id):
        return state, {
            "status": "duplicate_event", "session_id": session_id, "event_id": event_id,
        }
    if (
        state.get("session", {}).get("status") != "active"
        or state["session"].get("active_session_id") != session_id
    ):
        return state, {
            "status": "no_active_session",
            "session_id": session_id,
            "active_session_id": state.get("session", {}).get("active_session_id"),
        }

    policy_message = message or memory.get("situation") or event_type
    policy = record_policy(
        state,
        policy_message,
        subject=subject,
        event_type=event_type,
        host_approved=True,
        memory_owner=memory_owner,
        source="host_approved_log_event",
    )
    if policy["decision"] != "record_emotion":
        return state, {
            "status": "not_recorded",
            "decision": policy["decision"],
            "reason": policy["reason"],
            "session_id": session_id,
            "event_id": event_id,
            "policy": policy,
        }

    memory = dict(memory)
    if memory.get("appraisal") is None:
        semantic_appraisal = {
            "boundary": "boundary_pressure",
        }.get(policy["reason"], policy["reason"])
        memory["appraisal"] = (
            semantic_appraisal if semantic_appraisal in APPRAISAL_PROFILES else policy["appraisal"]
        )
    if memory.get("salience") is None:
        memory["salience"] = policy["salience"]
    state = add_emotion_log(
        state,
        event_type,
        tags=["manual", policy["reason"]],
        extra={
            "session_id": session_id,
            "event_id": event_id,
            "subject": policy["subject"],
            "semantic_event_type": policy["event_type"],
        },
        **memory,
    )
    mark_event_processed(state, event_id)
    return state, {
        "status": "recorded",
        "decision": policy["decision"],
        "session_id": session_id,
        "event_id": event_id,
        "policy": policy,
    }


_legacy_audit_emotion_log = audit_emotion_log


def audit_state_integrity(state):
    """Check hard state invariants separately from heuristic semantic warnings."""
    state = ensure_state_shape(state)
    hard_errors = []
    semantic_warnings = []

    if state.get("_schema") != STATE_SCHEMA:
        hard_errors.append({"code": "legacy_schema_read_only", "schema": state.get("_schema")})
    elif state.get("identity", {}).get("status") != "bound":
        hard_errors.append({"code": "identity_unbound"})

    session_ids = [entry.get("session_id") for entry in state.get("session_ledger", [])]
    duplicate_session_ids = sorted({value for value in session_ids if value and session_ids.count(value) > 1})
    if duplicate_session_ids:
        hard_errors.append({"code": "duplicate_session_ids", "ids": duplicate_session_ids})

    processed_ids = [str(value) for value in state.get("processed_event_ids", []) if value]
    duplicate_event_ids = sorted({value for value in processed_ids if processed_ids.count(value) > 1})
    if duplicate_event_ids:
        hard_errors.append({"code": "duplicate_processed_event_ids", "ids": duplicate_event_ids})

    evidence_ids = [entry.get("evidence_id") for entry in state.get("trust_evidence", [])]
    duplicate_evidence_ids = sorted({value for value in evidence_ids if value and evidence_ids.count(value) > 1})
    if duplicate_evidence_ids:
        hard_errors.append({"code": "duplicate_evidence_ids", "ids": duplicate_evidence_ids})

    settlement_ids = [entry.get("settlement_id") for entry in state.get("trust_settlements", [])]
    duplicate_settlement_ids = sorted({value for value in settlement_ids if value and settlement_ids.count(value) > 1})
    if duplicate_settlement_ids:
        hard_errors.append({"code": "duplicate_settlement_ids", "ids": duplicate_settlement_ids})

    known_sessions = {value for value in session_ids if value}
    known_settlements = {value for value in settlement_ids if value}
    known_evidence = {value for value in evidence_ids if value}
    evidence_by_id = {
        entry.get("evidence_id"): entry for entry in state.get("trust_evidence", [])
        if entry.get("evidence_id")
    }
    settlements_by_session = {}
    for entry in state.get("trust_settlements", []):
        settlements_by_session.setdefault(entry.get("session_id"), set()).add(
            entry.get("settlement_id")
        )
    multiply_settled_sessions = sorted(
        session_id for session_id, ids in settlements_by_session.items()
        if session_id and len({value for value in ids if value}) > 1
    )
    if multiply_settled_sessions:
        hard_errors.append({
            "code": "multiple_settlements_for_session", "session_ids": multiply_settled_sessions,
        })
    for entry in state.get("trust_evidence", []):
        if entry.get("session_id") not in known_sessions:
            hard_errors.append({"code": "orphan_trust_evidence", "evidence_id": entry.get("evidence_id")})
        rule = TRUST_EVIDENCE_RULES.get(entry.get("evidence_type"))
        if not rule or entry.get("direction") != rule["direction"]:
            hard_errors.append({"code": "invalid_trust_evidence", "evidence_id": entry.get("evidence_id")})
        consumed = entry.get("consumed_by_settlement_id")
        if consumed and consumed not in known_settlements:
            hard_errors.append({"code": "evidence_consumed_by_missing_settlement", "evidence_id": entry.get("evidence_id")})
        elif consumed:
            settlement = next(
                item for item in state.get("trust_settlements", [])
                if item.get("settlement_id") == consumed
            )
            if (
                entry.get("evidence_id") not in settlement.get("evidence_ids", [])
                or entry.get("session_id") != settlement.get("session_id")
            ):
                hard_errors.append({"code": "evidence_settlement_mismatch", "evidence_id": entry.get("evidence_id")})
    for entry in state.get("trust_settlements", []):
        if entry.get("session_id") not in known_sessions:
            hard_errors.append({"code": "orphan_trust_settlement", "settlement_id": entry.get("settlement_id")})
        missing_ids = [value for value in entry.get("evidence_ids", []) if value not in known_evidence]
        if missing_ids:
            hard_errors.append({
                "code": "settlement_references_missing_evidence",
                "settlement_id": entry.get("settlement_id"),
                "evidence_ids": missing_ids,
            })
        ineligible_ids = [
            value for value in entry.get("evidence_ids", [])
            if value in evidence_by_id and evidence_by_id[value].get("eligible") is not True
        ]
        if ineligible_ids:
            hard_errors.append({
                "code": "settlement_references_ineligible_evidence",
                "settlement_id": entry.get("settlement_id"),
                "evidence_ids": ineligible_ids,
            })

    active_ledger = [
        entry for entry in state.get("session_ledger", []) if entry.get("status") == "active"
    ]
    if len(active_ledger) > 1:
        hard_errors.append({
            "code": "multiple_active_sessions",
            "session_ids": [entry.get("session_id") for entry in active_ledger],
        })
    for entry in state.get("session_ledger", []):
        session_id = entry.get("session_id")
        status = entry.get("status")
        opened_at = entry.get("opened_at")
        closed_at = entry.get("closed_at")
        settled_at = entry.get("settled_at")
        settlement_id = entry.get("settlement_id")
        inconsistent = False
        if status == "active":
            inconsistent = bool(closed_at or settled_at or settlement_id)
        elif status == "closed":
            inconsistent = not closed_at or bool(settled_at or settlement_id)
        elif status == "settled":
            inconsistent = (
                not closed_at or not settled_at or not settlement_id
                or settlement_id not in known_settlements
            )
        else:
            inconsistent = True
        if inconsistent:
            hard_errors.append({
                "code": "session_ledger_lifecycle_inconsistent", "session_id": session_id,
            })
        try:
            opened = parse_iso_datetime(opened_at)
            closed = parse_iso_datetime(closed_at)
            settled = parse_iso_datetime(settled_at)
            if (closed and opened and closed < opened) or (settled and closed and settled < closed):
                hard_errors.append({
                    "code": "session_ledger_timestamp_order", "session_id": session_id,
                })
        except (TypeError, ValueError):
            hard_errors.append({
                "code": "session_ledger_invalid_timestamp", "session_id": session_id,
            })

    current = state.get("session", {})
    active_id = current.get("active_session_id")
    if current.get("status") == "active":
        ledger = session_record(state, active_id)
        if not active_id or not ledger or ledger.get("status") != "active":
            hard_errors.append({"code": "active_session_ledger_mismatch", "session_id": active_id})
    elif active_id:
        hard_errors.append({"code": "closed_state_has_active_session_id", "session_id": active_id})

    task_markers = ["tests pass", "shipped", "deployed", "implemented", "完成", "搞定", "通过", "修复"]
    session_log_counts = {}
    logged_turn_counts = {}
    nonlegacy_log_entries = []
    task_like_count = 0
    housekeeping_count = 0
    turn_log_count = 0
    for index, entry in enumerate(state.get("emotion_log", [])):
        if entry.get("legacy_v2_entry"):
            continue
        nonlegacy_log_entries.append(entry)
        session_id = entry.get("session_id")
        event_type = entry.get("event_type")
        if event_type in {"session_start", "session_end"} and session_id:
            counts = session_log_counts.setdefault(session_id, {"session_start": 0, "session_end": 0})
            counts[event_type] += effective_event_count(entry)
        if event_type in {
            "session_start", "session_end", "pre_turn_decay", "trust_update", "trust_settlement",
        }:
            housekeeping_count += effective_event_count(entry)
        if event_type != "turn":
            continue
        turn_log_count += effective_event_count(entry)
        if session_id:
            logged_turn_counts[session_id] = logged_turn_counts.get(session_id, 0) + effective_event_count(entry)
        if (
            state.get("_schema") == STATE_SCHEMA
            and session_id not in known_sessions
        ):
            hard_errors.append({"code": "orphan_turn", "log_index": index, "session_id": session_id})
        text = " ".join(str(entry.get(key) or "") for key in ["situation", "impact", "relational_meaning"]).lower()
        if (
            entry.get("subject") == "task"
            or entry.get("semantic_event_type") == "work_checkpoint"
            or any(marker in text for marker in task_markers)
        ):
            task_like_count += effective_event_count(entry)
            semantic_warnings.append({
                "code": "task_like_emotional_memory",
                "log_index": index,
                "event_id": entry.get("event_id"),
            })

        ledger = session_record(state, session_id)
        if ledger:
            try:
                timestamp = parse_iso_datetime(entry.get("timestamp"))
                opened = parse_iso_datetime(ledger.get("opened_at"))
                closed = parse_iso_datetime(ledger.get("closed_at"))
                if timestamp and ((opened and timestamp < opened) or (closed and timestamp > closed)):
                    hard_errors.append({
                        "code": "turn_outside_session_window",
                        "log_index": index,
                        "session_id": session_id,
                    })
            except (TypeError, ValueError):
                hard_errors.append({"code": "turn_invalid_timestamp", "log_index": index})

    for session_id, counts in session_log_counts.items():
        if counts["session_end"] > counts["session_start"]:
            hard_errors.append({
                "code": "session_end_without_matching_start",
                "session_id": session_id,
                "starts": counts["session_start"],
                "ends": counts["session_end"],
            })
    for entry in state.get("session_ledger", []):
        session_id = entry.get("session_id")
        if int(entry.get("turn_count", 0) or 0) < logged_turn_counts.get(session_id, 0):
            hard_errors.append({
                "code": "session_ledger_turn_count_too_small", "session_id": session_id,
            })

    trajectory = state.get("emotion_trajectory", [])
    trajectory_turns = [entry.get("turn") for entry in trajectory]
    if trajectory_turns != list(range(1, len(trajectory) + 1)):
        hard_errors.append({"code": "trajectory_turn_sequence", "turns": trajectory_turns})
    trajectory_event_ids = [entry.get("event_id") for entry in trajectory if entry.get("event_id")]
    duplicate_trajectory_events = sorted({
        value for value in trajectory_event_ids if trajectory_event_ids.count(value) > 1
    })
    if duplicate_trajectory_events:
        hard_errors.append({
            "code": "duplicate_trajectory_event_ids", "ids": duplicate_trajectory_events,
        })
    if not state.get("idempotency_retention", {}).get("pruned_events"):
        missing_trajectory_events = [
            value for value in trajectory_event_ids if value not in set(processed_ids)
        ]
        if missing_trajectory_events:
            hard_errors.append({
                "code": "trajectory_events_not_processed", "ids": missing_trajectory_events,
            })
    if int(state.get("total_turns", 0) or 0) < len(trajectory):
        hard_errors.append({"code": "total_turns_below_trajectory"})
    expected_trajectory_session = active_id or current.get("last_session_id")
    mismatched_trajectory_sessions = sorted({
        entry.get("session_id") for entry in trajectory
        if entry.get("session_id") != expected_trajectory_session
    }, key=lambda value: str(value))
    if mismatched_trajectory_sessions:
        hard_errors.append({
            "code": "trajectory_session_mismatch",
            "expected_session_id": expected_trajectory_session,
            "actual_session_ids": mismatched_trajectory_sessions,
        })

    if turn_log_count >= 3 and task_like_count / turn_log_count >= 0.35:
        semantic_warnings.append({
            "code": "high_task_like_memory_ratio",
            "task_like_turns": task_like_count,
            "turns": turn_log_count,
        })
    if turn_log_count >= 3 and housekeeping_count > turn_log_count * 2:
        semantic_warnings.append({
            "code": "excessive_lifecycle_housekeeping",
            "housekeeping_entries": housekeeping_count,
            "turns": turn_log_count,
        })
    if len(nonlegacy_log_entries) >= 10 and all(
        is_core_retention_entry(entry) for entry in nonlegacy_log_entries
    ):
        semantic_warnings.append({
            "code": "all_entries_core_retention",
            "entries": len(nonlegacy_log_entries),
        })

    return {
        "ok": not hard_errors,
        "schema": state.get("_schema"),
        "identity_status": state.get("identity", {}).get("status"),
        "hard_errors": hard_errors,
        "semantic_warnings": semantic_warnings,
        "counts": {
            "sessions": len(state.get("session_ledger", [])),
            "processed_events": len(processed_ids),
            "trust_evidence": len(state.get("trust_evidence", [])),
            "trust_settlements": len(state.get("trust_settlements", [])),
            "turns": turn_log_count,
            "task_like_turns": task_like_count,
            "lifecycle_housekeeping": housekeeping_count,
        },
    }


def audit_emotion_log(state):
    report = _legacy_audit_emotion_log(state)
    integrity = audit_state_integrity(state)
    report["ok"] = integrity["ok"]
    report["hard_errors"] = integrity["hard_errors"]
    report["semantic_warnings"] = integrity["semantic_warnings"]
    report["integrity_counts"] = integrity["counts"]
    return report


def repair_plan(state):
    """Return a non-mutating repair plan; ownership is never inferred."""
    state = ensure_state_shape(state)
    audit = audit_state_integrity(state)
    actions = [{
        "action": "archive_state_before_repair",
        "automatic": False,
        "required": True,
    }]
    if state.get("_schema") != STATE_SCHEMA:
        actions.append({
            "action": "migrate_state",
            "requires": ["character_id", "relationship_id"],
            "automatic": False,
        })
    if state.get("_schema") == STATE_SCHEMA and state.get("identity", {}).get("status") != "bound":
        actions.append({
            "action": "bind_identity",
            "requires": ["character_id", "relationship_id"],
            "automatic": False,
        })
    warning_indices = [
        warning["log_index"] for warning in audit["semantic_warnings"]
        if warning.get("code") == "task_like_emotional_memory"
    ]
    if warning_indices:
        actions.append({
            "action": "review_task_like_entries",
            "log_indices": warning_indices,
            "automatic": False,
        })
    if any(error["code"].startswith("duplicate_") for error in audit["hard_errors"]):
        actions.append({"action": "deduplicate_ledgers", "automatic": False})
    if any("settlement" in error["code"] or "trust_evidence" in error["code"] for error in audit["hard_errors"]):
        actions.append({
            "action": "reconcile_trust_evidence",
            "requires": ["explicit_baseline_trust"],
            "automatic": False,
        })
    if any(
        error["code"].startswith("session_")
        or error["code"].startswith("turn_")
        or error["code"].startswith("trajectory_")
        for error in audit["hard_errors"]
    ):
        actions.append({"action": "review_lifecycle_ledgers", "automatic": False})
    return {
        "dry_run": True,
        "audit": audit,
        "before_counts": deepcopy(audit["counts"]),
        "proposed_actions": actions,
        "acceptance_checks": [
            "audit_state reports no hard_errors",
            "owner identity remains explicit and unchanged",
            "session, evidence, settlement, and event ledgers agree",
            "task-owned facts are removed from emotional memory or routed by the host",
        ],
    }


def reconcile_trust_from_evidence(state, baseline_trust=None, apply=False):
    """Preview or explicitly apply a trust rebuild from the evidence ledger."""
    state = require_v3_state(state)
    if baseline_trust is None:
        return state, {
            "status": "baseline_required",
            "dry_run": True,
            "message": "provide an explicit baseline_trust; the engine will not infer it",
        }
    baseline = round(clamp(float(baseline_trust), 0.05, 1.0), 4)
    trust = baseline
    used_ids = set()
    steps = []
    for session in state.get("session_ledger", []):
        if session.get("status") not in {"closed", "settled"}:
            continue
        evidence = [
            item for item in state.get("trust_evidence", [])
            if item.get("session_id") == session.get("session_id")
            and item.get("eligible") is True
            and item.get("evidence_id") not in used_ids
        ]
        if not evidence:
            continue
        raw_delta = round(clamp(sum(
            float(item.get("direction", 0)) * float(item.get("weight", 0.0)) for item in evidence
        ), -0.2, 0.05), 4)
        effective = raw_delta * (1 - trust) if raw_delta > 0 else (raw_delta * 0.5 if trust > 0.6 and raw_delta > -0.15 else raw_delta)
        before = trust
        trust = round(clamp(trust + effective, 0.05, 1.0), 4)
        ids = [item["evidence_id"] for item in evidence]
        used_ids.update(ids)
        steps.append({
            "session_id": session.get("session_id"),
            "settlement_id": settlement_trajectory_signature(state, session.get("session_id"), ids),
            "evidence_ids": ids,
            "raw_delta": raw_delta,
            "effective_delta": round(effective, 4),
            "before": before,
            "after": trust,
        })
    report = {"status": "reconcile_preview", "dry_run": not apply, "baseline_trust": baseline, "computed_trust": trust, "steps": steps}
    if apply:
        state["trust"] = trust
        state["trust_anchor"] = max(state.get("trust_anchor", trust), trust)
        reconciliation_id = f"reconcile-{uuid.uuid4()}"
        append_limited(state, "trust_reconciliations", {
            "reconciliation_id": reconciliation_id,
            "timestamp": now_iso(),
            "mode": "additive",
            "baseline_trust": baseline,
            "computed_trust": trust,
            "steps": deepcopy(steps),
            "note": "existing trust history, settlements, and evidence consumption were preserved",
        }, 50)
        report["reconciliation_id"] = reconciliation_id
        report["status"] = "reconciled"
    return state, report


def parse_memory_args(args):
    options = {
        "appraisal": None,
        "situation": None,
        "character_lens": None,
        "relational_meaning": None,
        "impact": None,
        "open_loop": None,
        "follow_up_bias": None,
        "salience": None,
    }
    positional = []
    i = 0
    while i < len(args):
        token = args[i]
        if token == "--appraisal" and i + 1 < len(args):
            options["appraisal"] = args[i + 1]
            i += 2
        elif token in TEXT_MEMORY_FIELDS:
            key = TEXT_MEMORY_FIELDS[token]
            j = i + 1
            parts = []
            while j < len(args) and not args[j].startswith("--"):
                parts.append(args[j])
                j += 1
            options[key] = " ".join(parts).strip() or None
            i = j
        elif token == "--open-loop" and i + 1 < len(args):
            options["open_loop"] = parse_bool(args[i + 1])
            i += 2
        elif token == "--salience" and i + 1 < len(args):
            options["salience"] = clamp(float(args[i + 1]), 0.0, 1.0)
            i += 2
        else:
            positional.append(token)
            i += 1

    if positional and not options["situation"]:
        options["situation"] = " ".join(positional).strip() or None
    return options


def cli_option(args, name, default=None):
    if name not in args:
        return default
    index = args.index(name)
    if index + 1 >= len(args):
        raise ValueError(f"{name} requires a value")
    return args[index + 1]


def strip_cli_options(args, option_names, flag_names=None):
    flag_names = set(flag_names or [])
    option_names = set(option_names)
    output = []
    index = 0
    while index < len(args):
        token = args[index]
        if token in option_names:
            if index + 1 >= len(args):
                raise ValueError(f"{token} requires a value")
            index += 2
        elif token in flag_names:
            index += 1
        else:
            output.append(token)
            index += 1
    return output


# ── CLI ──────────────────────────────────────────────────────────────

STATE_MUTATING_COMMANDS = {
    "bind_identity",
    "migrate_state",
    "configure",
    "tune",
    "pause",
    "resume",
    "clear_log",
    "reset",
    "decay",
    "pre_turn_decay",
    "settle_trust",
    "update_trust",
    "record_turn",
    "log_event",
    "compact_log",
    "session_start",
    "session_end",
    "evaluate_turn",
    "reconcile_trust",
}


def run_command(command, state_file, state):

    if command == "bind_identity":
        args = sys.argv[3:]
        state, result = bind_state_identity(
            state,
            cli_option(args, "--character-id"),
            cli_option(args, "--relationship-id"),
        )
        if result["status"] == "bound":
            save_state(state_file, state)
        print_json(result)

    elif command == "migrate_state":
        args = sys.argv[3:]
        migrated, result = migrate_state_v2(
            state,
            cli_option(args, "--character-id"),
            cli_option(args, "--relationship-id"),
            state_id=cli_option(args, "--state-id"),
        )
        apply = "--apply" in args
        result["dry_run"] = not apply
        if apply and result["status"] == "migration_ready":
            save_state(state_file, migrated)
            result["status"] = "migrated"
            result["backup_path"] = state_backup_path(state_file)
        print_json(result)

    elif command == "validate":
        integrity = audit_state_integrity(state)
        print_json({
            "ok": integrity["ok"],
            "schema": state["_schema"],
            "enabled": state["enabled"],
            "volatility_profile": state["volatility_profile"],
            "emotion": state["emotion"],
            "affective_pulse": state["affective_pulse"],
            "trust": state["trust"],
            "character_profile": state["character_profile"],
            "log_entries": len(state.get("emotion_log", [])),
            "hard_errors": integrity["hard_errors"],
            "semantic_warnings": integrity["semantic_warnings"],
        })

    elif command == "status":
        if "--raw" in sys.argv[3:]:
            print_json(state)
        else:
            print_json(public_status(state))

    elif command == "activation_check":
        result = activation_check(state, state_file, os.path.abspath(sys.argv[0]))
        print_json(result)
        if result["status"] == "migration_required":
            sys.exit(2)
        if result["status"] == "identity_binding_required":
            sys.exit(3)

    elif command == "configure":
        args = sys.argv[3:]
        if "--style" in args:
            idx = args.index("--style")
            description = " ".join(args[idx + 1:]).strip()
            if not description:
                print("Usage: configure <state_file> --style <description>")
                sys.exit(1)
            state = apply_configuration(state, description, "style")
        elif "--soul-file" in args:
            idx = args.index("--soul-file")
            if idx + 1 >= len(args):
                print("Usage: configure <state_file> --soul-file <SOUL.md>")
                sys.exit(1)
            soul_path = args[idx + 1]
            with open(soul_path, "r") as f:
                description = f.read(12000)
            state = apply_configuration(state, description, "soul-file")
            state["character_profile"]["soul_file"] = soul_path
        else:
            print("Usage: configure <state_file> --style <description> OR --soul-file <SOUL.md>")
            sys.exit(1)
        save_state(state_file, state)
        print_json({
            "ok": True,
            "baseline": state["personality_baseline"],
            "volatility_profile": state["volatility_profile"],
            "profile": state["character_profile"],
            "status": public_status(state),
        })

    elif command == "tune":
        if len(sys.argv) < 4:
            print("Usage: tune <state_file> <natural-language adjustment...>")
            sys.exit(1)
        state, result = tune_state(state, " ".join(sys.argv[3:]))
        save_state(state_file, state)
        print_json(result)

    elif command == "pause":
        state["enabled"] = False
        save_state(state_file, state)
        print_json({"ok": True, "enabled": False, "message": "Emotion Engine paused. State is preserved but no emotion lifecycle updates will be recorded."})

    elif command == "resume":
        state["enabled"] = True
        save_state(state_file, state)
        print_json({"ok": True, "enabled": True, "message": "Emotion Engine resumed."})

    elif command == "clear_log":
        state["emotion_log"] = []
        save_state(state_file, state)
        print_json({"ok": True, "log_entries": 0})

    elif command == "reset":
        if "--factory" in sys.argv[3:]:
            state = default_state()
        else:
            identity = deepcopy(state.get("identity", DEFAULT_STATE["identity"]))
            profile = deepcopy(state.get("character_profile", DEFAULT_STATE["character_profile"]))
            baseline = state.get("personality_baseline", DEFAULT_STATE["personality_baseline"])
            volatility_profile = state.get("volatility_profile", DEFAULT_STATE["volatility_profile"])
            enabled = state.get("enabled", True)
            state = default_state(
                identity.get("character_id"),
                identity.get("relationship_id"),
                state_id=identity.get("state_id"),
            )
            state["enabled"] = enabled
            state["volatility_profile"] = normalize_volatility_profile(volatility_profile)
            state["personality_baseline"] = normalize_emotion(baseline)
            state["emotion"] = normalize_emotion(baseline)
            state["character_profile"] = profile
        save_state(state_file, state)
        print_json({"ok": True, "factory": "--factory" in sys.argv[3:], "status": public_status(state)})

    elif command == "decay":
        args = sys.argv[3:]
        state, result = apply_time_decay(
            state,
            character_id=cli_option(args, "--character-id"),
            relationship_id=cli_option(args, "--relationship-id"),
        )
        if result["status"] == "applied":
            save_state(state_file, state)
        print_json(result)

    elif command == "pre_turn_decay":
        args = sys.argv[3:]
        state, result = pre_turn_decay(
            state,
            session_id=cli_option(args, "--session-id"),
            event_id=cli_option(args, "--event-id"),
            character_id=cli_option(args, "--character-id"),
            relationship_id=cli_option(args, "--relationship-id"),
        )
        if result["status"] == "applied":
            save_state(state_file, state)
        result.update({"emotion": state["emotion"], "affective_pulse": state["affective_pulse"]})
        print_json(result)

    elif command == "appraise":
        if len(sys.argv) < 4:
            print("Usage: appraise <state_file> <message...>")
            sys.exit(1)
        print_json(appraise_message(state, " ".join(sys.argv[3:])))

    elif command == "record_policy":
        policy_args = parse_record_policy_args(sys.argv[3:])
        if not policy_args["message"]:
            print("Usage: record_policy <state_file> [--mode light|always|paused] [--context <label>] <message...>")
            sys.exit(1)
        print_json(record_policy(
            state,
            policy_args["message"],
            mode=policy_args["mode"],
            contexts=policy_args["contexts"],
            subject=policy_args["subject"],
            event_type=policy_args["event_type"],
            host_approved=policy_args["host_approved"],
            memory_owner=policy_args["memory_owner"],
            source=policy_args["source"],
        ))

    elif command == "patterns":
        print_json(extract_patterns(state))

    elif command == "settle_trust":
        args = sys.argv[3:]
        state, result = settle_trust(
            state,
            session_id=cli_option(args, "--session-id"),
            event_id=cli_option(args, "--event-id"),
            character_id=cli_option(args, "--character-id"),
            relationship_id=cli_option(args, "--relationship-id"),
        )
        if result["status"] == "settled":
            save_state(state_file, state)
        print_json(result)

    elif command == "update_trust":
        if len(sys.argv) < 4:
            print("Usage: update_trust <state_file> <trust_delta>")
            sys.exit(1)
        args = sys.argv[4:]
        if "--host-approved" not in args or not cli_option(args, "--reason"):
            raise ValueError("update_trust requires --host-approved and --reason")
        state, result = apply_manual_trust_update(
            state,
            sys.argv[3],
            cli_option(args, "--reason"),
            character_id=cli_option(args, "--character-id"),
            relationship_id=cli_option(args, "--relationship-id"),
        )
        if result["status"] == "applied":
            save_state(state_file, state)
        print_json(result)

    elif command == "record_turn":
        if len(sys.argv) < 6:
            print("Usage: record_turn <state_file> <P> <A> <D> [memory options]")
            sys.exit(1)
        args = sys.argv[6:]
        option_names = {
            "--session-id", "--event-id", "--subject", "--event-type", "--trust-evidence-json",
            "--character-id", "--relationship-id",
        }
        memory = parse_memory_args(strip_cli_options(args, option_names, {"--host-approved"}))
        evidence_json = cli_option(args, "--trust-evidence-json")
        state, result = record_turn(
            state,
            sys.argv[3],
            sys.argv[4],
            sys.argv[5],
            session_id=cli_option(args, "--session-id"),
            event_id=cli_option(args, "--event-id"),
            subject=cli_option(args, "--subject", "relationship"),
            semantic_event_type=cli_option(args, "--event-type"),
            trust_evidence=json.loads(evidence_json) if evidence_json else None,
            host_approved="--host-approved" in args,
            character_id=cli_option(args, "--character-id"),
            relationship_id=cli_option(args, "--relationship-id"),
            **memory,
        )
        if result["status"] == "recorded":
            save_state(state_file, state)
        result["emotion"] = state["emotion"]
        result["affective_pulse"] = state["affective_pulse"]
        print_json(result)

    elif command == "evaluate_turn":
        if len(sys.argv) < 6:
            print("Usage: evaluate_turn <state_file> <P> <A> <D> --event-json <json>")
            sys.exit(1)
        args = sys.argv[6:]
        event_json = cli_option(args, "--event-json")
        if not event_json:
            raise ValueError("evaluate_turn requires --event-json")
        state, result = evaluate_and_record_turn(
            state,
            json.loads(event_json),
            sys.argv[3],
            sys.argv[4],
            sys.argv[5],
            character_id=cli_option(args, "--character-id"),
            relationship_id=cli_option(args, "--relationship-id"),
        )
        if result["status"] in {"recorded", "state_only"}:
            save_state(state_file, state)
        print_json(result)

    elif command == "log_event":
        if len(sys.argv) < 5:
            print("Usage: log_event <state_file> <event_type> [memory options]")
            sys.exit(1)
        args = sys.argv[4:]
        option_names = {
            "--session-id", "--event-id", "--subject", "--event-type",
            "--character-id", "--relationship-id", "--memory-owner", "--message",
        }
        memory = parse_memory_args(strip_cli_options(args, option_names, {"--host-approved"}))
        state, result = record_semantic_event(
            state,
            sys.argv[3],
            session_id=cli_option(args, "--session-id"),
            event_id=cli_option(args, "--event-id"),
            subject=cli_option(args, "--subject", "relationship"),
            message=cli_option(args, "--message"),
            memory_owner=cli_option(args, "--memory-owner"),
            host_approved="--host-approved" in args,
            character_id=cli_option(args, "--character-id"),
            relationship_id=cli_option(args, "--relationship-id"),
            **memory,
        )
        if result["status"] == "recorded":
            save_state(state_file, state)
        result["log_entries"] = len(state.get("emotion_log", []))
        print_json(result)

    elif command == "recent_log":
        limit = int(sys.argv[3]) if len(sys.argv) >= 4 else 5
        print_json(state.get("emotion_log", [])[-limit:])

    elif command == "audit_log":
        print_json(audit_emotion_log(state))

    elif command == "audit_state":
        print_json(audit_state_integrity(state))

    elif command == "repair_plan":
        print_json(repair_plan(state))

    elif command == "reconcile_trust":
        args = sys.argv[3:]
        apply = "--apply" in args
        state, result = reconcile_trust_from_evidence(
            state,
            baseline_trust=cli_option(args, "--baseline-trust"),
            apply=apply,
        )
        if result["status"] == "reconciled":
            save_state(state_file, state)
            result["backup_path"] = state_backup_path(state_file)
        print_json(result)

    elif command == "compact_log":
        args = sys.argv[3:]
        apply = "--apply" in args
        if apply and "--dry-run" in args:
            print("Usage: compact_log <state_file> [--dry-run|--apply]")
            sys.exit(1)
        compacted_state, report = compact_emotion_log(state)
        report["applied"] = bool(apply)
        if apply:
            save_state(state_file, compacted_state)
            report["backup_path"] = state_backup_path(state_file)
            report["status"] = public_status(compacted_state)
        print_json(report)

    elif command == "session_start":
        args = sys.argv[3:]
        state, result = session_start(
            state,
            session_id=cli_option(args, "--session-id"),
            event_id=cli_option(args, "--event-id"),
            character_id=cli_option(args, "--character-id"),
            relationship_id=cli_option(args, "--relationship-id"),
        )
        if result["status"] == "started":
            save_state(state_file, state)
        result.update({"emotion": state["emotion"], "trust": state["trust"]})
        print_json(result)

    elif command == "session_end":
        args = sys.argv[3:]
        state, result = session_end(
            state,
            session_id=cli_option(args, "--session-id"),
            event_id=cli_option(args, "--event-id"),
            character_id=cli_option(args, "--character-id"),
            relationship_id=cli_option(args, "--relationship-id"),
        )
        if result["status"] == "closed":
            save_state(state_file, state)
        print_json(result)

    else:
        print(f"Unknown command: {command}")
        sys.exit(1)


def main():
    if len(sys.argv) < 3:
        print(__doc__)
        sys.exit(1)

    command = sys.argv[1]
    state_file = sys.argv[2]

    if command == "init":
        args = sys.argv[3:]
        with state_file_lock(state_file):
            state = default_state(
                character_id=cli_option(args, "--character-id"),
                relationship_id=cli_option(args, "--relationship-id"),
                state_id=cli_option(args, "--state-id"),
            )
            save_state_unlocked(state_file, state)
        print_json({
            "ok": True,
            "engine_version": ENGINE_VERSION,
            "state_file": state_file,
            "schema": state["_schema"],
            "identity_status": state["identity"]["status"],
            "capabilities": state["capabilities"],
        })
        return

    if command in STATE_MUTATING_COMMANDS:
        with state_file_lock(state_file):
            state = load_state_unlocked(state_file)
            if command != "migrate_state" and state.get("_schema") != STATE_SCHEMA:
                print_json({
                    "ok": False,
                    "engine_version": ENGINE_VERSION,
                    "status": "migration_required",
                    "schema": state.get("_schema"),
                    "message": "v2 state is read-only; run migrate_state with explicit owner identity",
                })
                sys.exit(2)
            run_command(command, state_file, state)
        return

    state = load_state(state_file)
    run_command(command, state_file, state)


if __name__ == "__main__":
    main()
