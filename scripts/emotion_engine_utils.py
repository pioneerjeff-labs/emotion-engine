#!/usr/bin/env python3
"""
emotion_engine_utils.py — State, decay, appraisal, and pattern tools
for Emotion Engine.

Usage:
  python3 emotion_engine_utils.py init <state_file>
  python3 emotion_engine_utils.py validate <state_file>
  python3 emotion_engine_utils.py decay <state_file>
  python3 emotion_engine_utils.py pre_turn_decay <state_file>
  python3 emotion_engine_utils.py appraise <state_file> <message...>
  python3 emotion_engine_utils.py patterns <state_file>
  python3 emotion_engine_utils.py settle_trust <state_file>
  python3 emotion_engine_utils.py update_trust <state_file> <trust_delta>
  python3 emotion_engine_utils.py record_turn <state_file> <P> <A> <D> [memory options]
  python3 emotion_engine_utils.py log_event <state_file> <event_type> [memory options]
  python3 emotion_engine_utils.py recent_log <state_file> [limit]
  python3 emotion_engine_utils.py configure <state_file> --style <description>
  python3 emotion_engine_utils.py configure <state_file> --soul-file <SOUL.md>
  python3 emotion_engine_utils.py tune <state_file> <natural-language adjustment...>
  python3 emotion_engine_utils.py status <state_file> [--raw]
  python3 emotion_engine_utils.py pause <state_file>
  python3 emotion_engine_utils.py resume <state_file>
  python3 emotion_engine_utils.py clear_log <state_file>
  python3 emotion_engine_utils.py reset <state_file> [--factory]
  python3 emotion_engine_utils.py session_start <state_file>
  python3 emotion_engine_utils.py session_end <state_file>
"""

import json
import math
import os
import sys
import hashlib
from copy import deepcopy
from datetime import datetime, timezone


DEFAULT_STATE = {
    "_schema": "emotion-engine-state/v2",
    "enabled": True,
    "emotion": {"pleasure": 0.0, "arousal": 0.3, "dominance": 0.5},
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
    "trust_settlements": [],
    "log_limit": 200,
}

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


def default_state():
    return deepcopy(DEFAULT_STATE)


def load_state(path):
    if not os.path.exists(path):
        return default_state()
    with open(path, "r") as f:
        return ensure_state_shape(json.load(f))


def save_state(path, state):
    state = ensure_state_shape(state)
    with open(path, "w") as f:
        json.dump(state, f, indent=2, ensure_ascii=False)
        f.write("\n")


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


def ensure_state_shape(state):
    merged = default_state()
    if isinstance(state, dict):
        merged.update(state)

    merged["_schema"] = "emotion-engine-state/v2"
    merged["enabled"] = bool(merged.get("enabled", True))
    merged["emotion"] = normalize_emotion(merged.get("emotion"))
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

    for key in ["emotion_trajectory", "emotion_log", "trust_history", "trust_settlements"]:
        if not isinstance(merged.get(key), list):
            merged[key] = []

    for key in ["session_count", "total_turns"]:
        merged[key] = int(merged.get(key, 0) or 0)

    merged["log_limit"] = max(25, int(merged.get("log_limit", 200) or 200))
    return merged


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
        ("playful", ["活泼", "兴奋", "元气", "热情", "开朗", "playful", "energetic", "lively"], 0.16, 0.26, 0.0),
        ("calm", ["冷静", "沉稳", "安静", "可靠", "稳定", "calm", "steady", "reliable"], 0.08, -0.15, 0.12),
        ("bounded", ["边界", "主见", "不讨好", "独立", "自尊", "boundary", "boundaries", "independent"], 0.0, 0.02, 0.18),
        ("assertive", ["强势", "坚定", "掌控", "自信", "assertive", "confident", "dominant"], -0.02, 0.08, 0.22),
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

    interpretation = describe_baseline(baseline, traits)
    return {
        "baseline": baseline,
        "profile": {
            "source": source,
            "description": truncate_text(text, 800) or "warm, steady, lightly bounded",
            "interpretation": interpretation,
            "traits": traits[:8],
        },
    }


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


def public_status(state):
    state = ensure_state_shape(state)
    progress = trust_progress(state["trust"])
    return {
        "enabled": state["enabled"],
        "summary": emotion_summary(state),
        "style": state["character_profile"].get("interpretation"),
        "trust_tier": trust_tier(state["trust"]),
        "trust_progress": progress["progress"],
        "trust_progress_phrase": progress["phrase"],
        "session_count": state["session_count"],
        "log_entries": len(state.get("emotion_log", [])),
        "hint": "Use tune for small changes, pause/resume for control, and status --raw for debug values.",
    }


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
    append_limited(state, "emotion_log", entry, state.get("log_limit", 200))
    return state


# ── Decay ────────────────────────────────────────────────────────────

def compute_time_decay(state):
    """Apply time-based decay to PAD emotion vector.

    Decay pulls emotions toward personality_baseline. Trust slows the decay
    rate, so higher trust makes emotions linger longer between sessions.
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
    return state


def compute_trust_time_decay(state):
    """Apply time-based decay to trust when user is absent.

    Trust never drops below max(0.05, trust_anchor * 0.3), where trust_anchor
    tracks the highest trust reached by the relationship.
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


def apply_in_session_decay(state):
    """Apply the small between-turn drift toward personality baseline."""
    state = ensure_state_shape(state)
    if not state.get("enabled", True):
        return state
    before = state["emotion"].copy()
    baseline = state["personality_baseline"]
    after = {}

    for dim in ["pleasure", "arousal", "dominance"]:
        after[dim] = clamp_dimension(dim, before[dim] * 0.92 + baseline[dim] * 0.08)

    state["emotion"] = after
    delta = emotion_delta(before, after)
    if max(abs(v) for v in delta.values()) >= 0.005:
        state = add_emotion_log(
            state,
            "pre_turn_decay",
            cue="quiet drift toward personality baseline",
            before=before,
            after=after,
            delta=delta,
            tags=["decay"],
        )
    return state


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
    actual_delta = trust_modulate(raw_delta, state["trust"])
    current = emotion_to_pad(state["emotion"])

    suggested = {}
    for short, value in current.items():
        dim = PAD_LONG[short]
        suggested[short] = clamp_dimension(dim, value + actual_delta[short])

    return {
        "appraisal": label,
        "cue": profile["cue"],
        "keyword_hits": hits,
        "trust": state["trust"],
        "current": current,
        "raw_delta": raw_delta,
        "actual_delta": actual_delta,
        "suggested": suggested,
        "tags": profile["tags"],
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
    volatility = math.sqrt(variance)

    too_smooth = volatility < 0.05 and mean_p > 0.3
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
        "volatility": round(volatility, 4),
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

TRUST_SETTLEMENT_TEXT_FIELDS = [
    "situation",
    "character_lens",
    "relational_meaning",
    "impact",
    "follow_up_bias",
]

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


def current_session_turn_logs(state):
    trajectory_turns = {
        int(entry.get("turn"))
        for entry in state.get("emotion_trajectory", [])
        if entry.get("turn") is not None
    }
    if not trajectory_turns:
        return []
    turn_logs = []
    for entry in state.get("emotion_log", [])[-50:]:
        if entry.get("event_type") == "turn" and entry.get("turn") in trajectory_turns:
            turn_logs.append(entry)
    return turn_logs


def settlement_trajectory_signature(state):
    state = ensure_state_shape(state)
    trajectory = state.get("emotion_trajectory", [])
    payload = {
        "session_count": state.get("session_count", 0),
        "trajectory": [
            {
                "turn": entry.get("turn"),
                "P": entry.get("P"),
                "A": entry.get("A"),
                "D": entry.get("D"),
                "timestamp": entry.get("timestamp"),
                "appraisal": entry.get("appraisal"),
            }
            for entry in trajectory
        ],
    }
    encoded = json.dumps(payload, sort_keys=True, ensure_ascii=False, separators=(",", ":"))
    return hashlib.sha256(encoded.encode("utf-8")).hexdigest()[:16]


def settlement_already_applied(state, settlement_id):
    for entry in state.get("trust_settlements", []):
        if entry.get("settlement_id") == settlement_id:
            return True
    return any(
        entry.get("event_type") == "trust_settlement"
        and entry.get("settlement_id") == settlement_id
        for entry in state.get("emotion_log", [])[-50:]
    )


def turn_log_text(turn_logs):
    parts = []
    for entry in turn_logs:
        for field in TRUST_SETTLEMENT_TEXT_FIELDS:
            if entry.get(field):
                parts.append(str(entry[field]).lower())
    return " ".join(parts)


def assess_trust_settlement(state, patterns=None):
    state = ensure_state_shape(state)
    patterns = patterns or extract_patterns(state)
    turn_logs = current_session_turn_logs(state)
    appraisals = [
        entry.get("appraisal")
        for entry in turn_logs
        if entry.get("appraisal")
    ]
    tags = [
        tag
        for entry in turn_logs
        for tag in entry.get("tags", [])
    ]
    text = turn_log_text(turn_logs)

    turn_count = int(patterns.get("turn_count", len(state.get("emotion_trajectory", []))) or 0)
    collaboration_count = tags.count("collaboration") + appraisals.count("collaboration")
    warmth_count = tags.count("warmth") + appraisals.count("warmth")
    repair_count = tags.count("repair") + appraisals.count("repair")
    boundary_count = tags.count("boundary") + appraisals.count("boundary_pressure")
    hostility_count = tags.count("negative") + appraisals.count("hostility")
    explicit_trust = any(keyword in text for keyword in TRUST_SETTLEMENT_KEYWORDS)

    if not patterns.get("sufficient_data") or turn_count < 2:
        return 0.0, "insufficient_data", "insufficient turn-level evidence for trust settlement"

    if hostility_count and not repair_count:
        return -0.06, "unrepaired_hostility", "recent hostility was not repaired"

    if boundary_count >= 2:
        return -0.04, "repeated_boundary_pressure", "repeated boundary pressure blocks positive trust gain"

    if patterns.get("dominance_suppressed") and boundary_count:
        return -0.03, "boundary_pressure_with_suppression", "boundary pressure coincided with suppressed dominance"

    if patterns.get("sustained_negative") and not patterns.get("had_repair"):
        return -0.05, "sustained_negative_unrepaired", "session stayed negative without repair"

    if boundary_count:
        return -0.02, "boundary_pressure_blocks_gain", "boundary pressure blocks positive trust gain"

    if patterns.get("v_shape") and patterns.get("had_repair"):
        return 0.05, "conflict_repair", "genuine conflict repair improved the session trajectory"

    if patterns.get("had_conflict") and patterns.get("had_repair"):
        return 0.04, "conflict_repair", "conflict was followed by meaningful repair"

    if collaboration_count >= 2 and explicit_trust:
        if patterns.get("end_vs_start_pleasure", 0.0) > 0.05:
            return 0.04, "collaboration_with_direct_trust", "multiple cooperative turns included explicit trust in direct judgment"
        return 0.03, "collaboration_with_direct_trust", "multiple cooperative turns included explicit trust in direct judgment"

    if (
        collaboration_count >= 2
        and turn_count >= 3
        and patterns.get("avg_pleasure_delta", 0.0) > 0
        and patterns.get("end_vs_start_pleasure", 0.0) > 0
    ):
        return 0.02, "sustained_collaboration", "sustained collaborative interaction showed a positive pleasure trend"

    if warmth_count and collaboration_count == 0:
        return 0.0, "praise_only", "single warmth or praise is not enough for trust growth"

    return 0.0, "no_clear_trust_signal", "no clear session-level trust signal"


def settlement_record(settlement_id, state, raw_delta, status):
    return {
        "timestamp": now_iso(),
        "settlement_id": settlement_id,
        "session_count": int(state.get("session_count", 0)),
        "turn_count": len(state.get("emotion_trajectory", [])),
        "trust_before": round(float(state.get("trust", 0.1)), 4),
        "trust_after": round(float(state.get("trust", 0.1)), 4),
        "raw_delta": round(float(raw_delta), 4),
        "status": status,
    }


def has_current_session_end_log(state, patterns):
    return any(
        entry.get("event_type") == "session_end"
        and entry.get("patterns") == patterns
        for entry in state.get("emotion_log", [])[-10:]
    )


def settle_trust(state):
    """Conservatively settle session trust once for the current trajectory."""
    state = ensure_state_shape(state)
    settlement_id = settlement_trajectory_signature(state)
    patterns = extract_patterns(state)

    if not state.get("enabled", True):
        return state, {
            "status": "paused",
            "settlement_id": settlement_id,
            "raw_delta": 0.0,
            "patterns": patterns,
        }

    if settlement_already_applied(state, settlement_id):
        return state, {
            "status": "already_settled",
            "settlement_id": settlement_id,
            "raw_delta": 0.0,
            "patterns": patterns,
        }

    if not has_current_session_end_log(state, patterns):
        state, patterns = session_end(state)
    raw_delta, reason_code, reason = assess_trust_settlement(state, patterns)
    raw_delta = round(clamp(raw_delta, -0.2, 0.05), 4)
    trust_before = round(float(state.get("trust", 0.1)), 4)

    if raw_delta != 0.0:
        state = apply_trust_delta(state, raw_delta)

    trust_after = round(float(state.get("trust", 0.1)), 4)
    state = add_emotion_log(
        state,
        "trust_settlement",
        situation="host-side trust settlement completed",
        relational_meaning=reason,
        impact=f"raw trust delta {raw_delta:+.4f}",
        tags=["trust", "trust_settlement", reason_code],
        extra={
            "settlement_id": settlement_id,
            "reason_code": reason_code,
            "raw_delta": raw_delta,
            "trust_before": trust_before,
            "trust_after": trust_after,
            "patterns": patterns,
        },
    )

    record = settlement_record(settlement_id, state, raw_delta, "settled")
    record["trust_before"] = trust_before
    record["trust_after"] = trust_after
    append_limited(state, "trust_settlements", record, 50)

    return state, {
        "status": "settled",
        "settlement_id": settlement_id,
        "raw_delta": raw_delta,
        "trust_before": trust_before,
        "trust_after": trust_after,
        "reason_code": reason_code,
        "reason": reason,
        "patterns": patterns,
    }

def apply_trust_delta(state, raw_delta):
    """Apply trust change with diminishing returns for positive deltas."""
    state = ensure_state_shape(state)
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
    }
    append_limited(state, "trust_history", entry, 50)

    state = add_emotion_log(
        state,
        "trust_update",
        cue="relationship trust recalibrated from session evidence",
        tags=["trust"],
        extra={"trust_before": round(trust, 4), "trust_after": round(new_trust, 4)},
    )
    return state


# ── Session Lifecycle ────────────────────────────────────────────────

def session_start(state):
    """Apply decay, clear trajectory, bump count, and log the session start."""
    state = ensure_state_shape(state)
    if not state.get("enabled", True):
        return state
    before = state["emotion"].copy()
    trust_before = state["trust"]
    state = compute_time_decay(state)
    state = compute_trust_time_decay(state)
    after = state["emotion"].copy()
    state["emotion_trajectory"] = []
    state["session_count"] = state.get("session_count", 0) + 1
    state["last_interaction_iso"] = now_iso()
    state = add_emotion_log(
        state,
        "session_start",
        cue="new session initialized",
        before=before,
        after=after,
        delta=emotion_delta(before, after),
        tags=["session"],
        extra={"trust_before": round(trust_before, 4), "trust_after": state["trust"]},
    )
    return state


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
):
    """Record a single turn's emotion values to the trajectory and log."""
    state = ensure_state_shape(state)
    if not state.get("enabled", True):
        return state
    before = state["emotion"].copy()
    after = pad_to_emotion(p, a, d)
    turn = len(state["emotion_trajectory"]) + 1
    if cue and not situation:
        situation = cue

    entry = {
        "turn": turn,
        "P": after["pleasure"],
        "A": after["arousal"],
        "D": after["dominance"],
        "timestamp": now_iso(),
    }
    if appraisal:
        entry["appraisal"] = appraisal
    if situation:
        entry["situation"] = truncate_text(situation, 240)
    state["emotion_trajectory"].append(entry)

    state["emotion"] = after
    state["total_turns"] = state.get("total_turns", 0) + 1
    state["last_interaction_iso"] = now_iso()

    tags = [appraisal] if appraisal else None
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
        delta=emotion_delta(before, after),
        appraisal=appraisal,
        tags=tags,
        turn=turn,
    )
    return state


def session_end(state):
    """Extract patterns and log the session close for trust evaluation."""
    state = ensure_state_shape(state)
    if not state.get("enabled", True):
        return state, {"paused": True, "sufficient_data": False, "turn_count": len(state.get("emotion_trajectory", []))}
    patterns = extract_patterns(state)
    state["last_interaction_iso"] = now_iso()

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
        extra={"patterns": patterns},
    )
    return state, patterns


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


# ── CLI ──────────────────────────────────────────────────────────────

def main():
    if len(sys.argv) < 3:
        print(__doc__)
        sys.exit(1)

    command = sys.argv[1]
    state_file = sys.argv[2]

    if command == "init":
        state = default_state()
        save_state(state_file, state)
        print_json({"ok": True, "state_file": state_file, "schema": state["_schema"]})
        return

    state = load_state(state_file)

    if command == "validate":
        save_state(state_file, state)
        print_json({
            "ok": True,
            "schema": state["_schema"],
            "enabled": state["enabled"],
            "emotion": state["emotion"],
            "trust": state["trust"],
            "character_profile": state["character_profile"],
            "log_entries": len(state.get("emotion_log", [])),
        })

    elif command == "status":
        if "--raw" in sys.argv[3:]:
            print_json(state)
        else:
            print_json(public_status(state))

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
            profile = deepcopy(state.get("character_profile", DEFAULT_STATE["character_profile"]))
            baseline = state.get("personality_baseline", DEFAULT_STATE["personality_baseline"])
            enabled = state.get("enabled", True)
            state = default_state()
            state["enabled"] = enabled
            state["personality_baseline"] = normalize_emotion(baseline)
            state["emotion"] = normalize_emotion(baseline)
            state["character_profile"] = profile
        save_state(state_file, state)
        print_json({"ok": True, "factory": "--factory" in sys.argv[3:], "status": public_status(state)})

    elif command == "decay":
        before = state["emotion"].copy()
        trust_before = state["trust"]
        state = compute_time_decay(state)
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
        save_state(state_file, state)
        print_json({"emotion": state["emotion"], "trust": state["trust"]})

    elif command == "pre_turn_decay":
        state = apply_in_session_decay(state)
        save_state(state_file, state)
        print_json({"emotion": state["emotion"]})

    elif command == "appraise":
        if len(sys.argv) < 4:
            print("Usage: appraise <state_file> <message...>")
            sys.exit(1)
        print_json(appraise_message(state, " ".join(sys.argv[3:])))

    elif command == "patterns":
        print_json(extract_patterns(state))

    elif command == "settle_trust":
        state, result = settle_trust(state)
        save_state(state_file, state)
        print_json(result)

    elif command == "update_trust":
        if len(sys.argv) < 4:
            print("Usage: update_trust <state_file> <trust_delta>")
            sys.exit(1)
        state = apply_trust_delta(state, sys.argv[3])
        save_state(state_file, state)
        print_json({"trust": state["trust"], "trust_anchor": state["trust_anchor"]})

    elif command == "record_turn":
        if len(sys.argv) < 6:
            print("Usage: record_turn <state_file> <P> <A> <D> [memory options]")
            sys.exit(1)
        memory = parse_memory_args(sys.argv[6:])
        state = record_turn(state, sys.argv[3], sys.argv[4], sys.argv[5], **memory)
        save_state(state_file, state)
        print_json({"emotion": state["emotion"], "turn": len(state["emotion_trajectory"])})

    elif command == "log_event":
        if len(sys.argv) < 5:
            print("Usage: log_event <state_file> <event_type> [memory options]")
            sys.exit(1)
        memory = parse_memory_args(sys.argv[4:])
        state = add_emotion_log(
            state,
            sys.argv[3],
            tags=["manual"],
            **memory,
        )
        save_state(state_file, state)
        print_json({"ok": True, "log_entries": len(state.get("emotion_log", []))})

    elif command == "recent_log":
        limit = int(sys.argv[3]) if len(sys.argv) >= 4 else 5
        print_json(state.get("emotion_log", [])[-limit:])

    elif command == "session_start":
        state = session_start(state)
        save_state(state_file, state)
        print_json({
            "emotion": state["emotion"],
            "trust": state["trust"],
            "session_count": state["session_count"],
        })

    elif command == "session_end":
        state, patterns = session_end(state)
        save_state(state_file, state)
        print_json(patterns)

    else:
        print(f"Unknown command: {command}")
        sys.exit(1)


if __name__ == "__main__":
    main()
