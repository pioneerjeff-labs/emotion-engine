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
  python3 emotion_engine_utils.py record_policy <state_file> [--mode light|always|paused] [--context <label>] <message...>
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

DEFAULT_STATE = {
    "_schema": "emotion-engine-state/v2",
    "enabled": True,
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


def ensure_state_shape(state):
    merged = default_state()
    if isinstance(state, dict):
        merged.update(state)

    merged["_schema"] = "emotion-engine-state/v2"
    merged["enabled"] = bool(merged.get("enabled", True))
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
        "log_entries": len(state.get("emotion_log", [])),
        "hint": "Use tune for small changes, pause/resume for control, and status --raw for debug values.",
    }


DEDUPABLE_LOW_VALUE_APPRAISALS = {"neutral", "collaboration", "warmth", "playful"}


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
        max_abs_delta(entry.get("delta")) < 0.01
        and pulse_intensity_from_entry(entry, "pulse_after") < 0.04
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
    return salience <= 0.12 and pulse_intensity_from_entry(entry) < 0.12


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
    append_limited(state, "emotion_log", entry, state.get("log_limit", 200))
    return state


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
    pulse_changed = pulse_before != state["affective_pulse"]
    if max(abs(v) for v in delta.values()) >= 0.005 or pulse_changed:
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
MILESTONE_KEYWORDS = [
    "done", "shipped", "verified", "passed", "complete", "完成", "搞定", "通过", "验证", "落地",
]


def parse_record_policy_args(args):
    options = {"mode": None, "contexts": [], "message": ""}
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


def record_policy(state, message, mode=None, contexts=None):
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

    if requested_mode == "paused" or not state.get("enabled", True):
        return {
            "mode": requested_mode,
            "decision": "respond_only",
            "reason": "paused",
            "appraisal": label,
            "salience": 0.0,
            "trust_eligible": False,
            "reply_bias": policy_reply_bias("paused", label, "respond_only"),
            "context": normalized_contexts,
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
    milestone = (
        "milestone" in normalized_contexts
        or message_has_any(message, MILESTONE_KEYWORDS)
    )
    explicit_trust = any(keyword in text for keyword in TRUST_SETTLEMENT_KEYWORDS)
    warmth_habituation = recent_turn_appraisal_count(state, "warmth")
    relationship_context = any(
        context in normalized_contexts
        for context in {"relationship_calibration", "intimacy", "playful"}
    )

    decision = "respond_only"
    reason = "neutral_task"
    trust_eligible = False

    if label in {"hostility", "boundary_pressure", "repair", "vulnerability"}:
        decision = "record_turn"
        reason = label
        trust_eligible = label in {"hostility", "boundary_pressure", "repair"}
    elif label in {"relationship_calibration", "intimacy", "playful"} or relationship_context:
        decision = "record_turn"
        reason = label if label in {"relationship_calibration", "intimacy", "playful"} else "relationship_calibration"
        trust_eligible = False
    elif stable_preference:
        decision = "record_turn"
        reason = "stable_preference"
        trust_eligible = False
    elif explicit_trust:
        decision = "record_turn"
        reason = "explicit_trust"
        trust_eligible = True
    elif milestone and label == "warmth":
        decision = "record_turn"
        reason = "milestone_warmth"
        trust_eligible = False
    elif concrete:
        decision = "record_turn"
        reason = "concrete_feedback"
        trust_eligible = False
    elif milestone and label in {"collaboration", "neutral"}:
        decision = "record_turn"
        reason = "milestone_collaboration"
        trust_eligible = False
    elif label == "warmth":
        if requested_mode == "always" and not warmth_habituation:
            decision = "record_turn"
            reason = "generic_praise"
        else:
            decision = "respond_only"
            reason = "generic_praise_habituated" if warmth_habituation else "generic_praise"
    elif requested_mode == "always" and label != "neutral":
        decision = "record_turn"
        reason = label
        trust_eligible = label in {"collaboration", "repair", "boundary_pressure", "hostility"}
    elif requested_mode == "always":
        decision = "record_turn"
        reason = "neutral_task"

    salience = policy_salience(reason, label, requested_mode, warmth_habituation)
    if decision == "respond_only":
        salience = 0.0

    return {
        "mode": requested_mode,
        "decision": decision,
        "reason": reason,
        "appraisal": label,
        "salience": salience,
        "trust_eligible": bool(trust_eligible),
        "reply_bias": policy_reply_bias(reason, label, decision),
        "context": normalized_contexts,
        "habituation": {"recent_warmth_turns": warmth_habituation},
        "current": appraisal["current"],
        "suggested": appraisal["suggested"] if decision == "record_turn" else appraisal["current"],
        "actual_delta": appraisal["actual_delta"] if decision == "record_turn" else {"P": 0.0, "A": 0.0, "D": 0.0},
        "affective_pulse": appraisal["affective_pulse"] if decision == "record_turn" else zero_affective_pulse("record_policy"),
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
    pulse_before = state["affective_pulse"].copy()
    trust_before = state["trust"]
    state = compute_mood_time_decay(state)
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
        extra={
            "trust_before": round(trust_before, 4),
            "trust_after": state["trust"],
            "pulse_before": pulse_before,
            "pulse_after": state["affective_pulse"],
            "volatility_profile": state["volatility_profile"],
        },
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
            "affective_pulse": pulse,
            "volatility_profile": state["volatility_profile"],
        },
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
            "volatility_profile": state["volatility_profile"],
            "emotion": state["emotion"],
            "affective_pulse": state["affective_pulse"],
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
            profile = deepcopy(state.get("character_profile", DEFAULT_STATE["character_profile"]))
            baseline = state.get("personality_baseline", DEFAULT_STATE["personality_baseline"])
            volatility_profile = state.get("volatility_profile", DEFAULT_STATE["volatility_profile"])
            enabled = state.get("enabled", True)
            state = default_state()
            state["enabled"] = enabled
            state["volatility_profile"] = normalize_volatility_profile(volatility_profile)
            state["personality_baseline"] = normalize_emotion(baseline)
            state["emotion"] = normalize_emotion(baseline)
            state["character_profile"] = profile
        save_state(state_file, state)
        print_json({"ok": True, "factory": "--factory" in sys.argv[3:], "status": public_status(state)})

    elif command == "decay":
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
        save_state(state_file, state)
        print_json({"emotion": state["emotion"], "affective_pulse": state["affective_pulse"], "trust": state["trust"]})

    elif command == "pre_turn_decay":
        state = apply_in_session_decay(state)
        save_state(state_file, state)
        print_json({"emotion": state["emotion"], "affective_pulse": state["affective_pulse"]})

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
        ))

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
        print_json({
            "emotion": state["emotion"],
            "affective_pulse": state["affective_pulse"],
            "turn": len(state["emotion_trajectory"]),
        })

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
            "affective_pulse": state["affective_pulse"],
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
