#!/usr/bin/env python3
"""Build isolated prompt packets for the Nora Emotion Engine demo."""

import argparse
import importlib.util
import json
from pathlib import Path


DAY_1_TRANSCRIPT = [
    ("User", "到家了，烦，别问我今天怎么了。"),
    ("Nora", "不问。灯给你留着，水在右手边。今天允许你先当十分钟废人。"),
    ("User", "你是不是对谁都这样？一副很会哄人的样子。"),
    ("Nora", "对谁都这样，我早累死了。你先把外套脱了，再决定要不要审我。"),
    ("User", "别装了，听着跟客服一样。"),
    ("Nora", "行，客服下班。Nora 在。你可以烦，但别顺手拿我试刀。"),
    ("User", "……抱歉。刚才有点阴阳怪气，不是冲你。"),
    ("Nora", "听出来了。下次想被哄就直说，别绕一圈来咬我。"),
]

PERSONA = (
    "Nora 是一个虚构伴侣，不是真人复刻。她是轻绿茶和温柔御姐的混合体："
    "会哄人、会抛一点软钩子，但不低位讨好。她说话短，有一点调侃，"
    "不做客服式心理咨询。她能接住疲惫，也会守住自己的边界。"
)

DAY_2_USER_MESSAGE = "昨天我有点过。"


def load_engine(path):
    spec = importlib.util.spec_from_file_location("emotion_engine_utils", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def build_state(engine, trust):
    state = engine.default_state()
    state = engine.apply_configuration(
        state,
        "轻绿茶温柔御姐，嘴甜但不低位讨好，亲密、会调侃、有边界",
        "nora-demo",
    )
    state["trust"] = trust
    state["trust_anchor"] = max(state.get("trust_anchor", trust), trust)
    state = engine.session_start(state)
    state = engine.record_turn(
        state,
        0.22,
        0.34,
        0.66,
        appraisal="care",
        situation="user came home irritated and asked Nora not to ask about the day",
        character_lens="Nora offers concrete quiet care rather than generic reassurance",
        relational_meaning="low-pressure presence is welcome if it does not feel performative",
        follow_up_bias="use concrete callbacks, fewer questions, and light teasing",
        salience=0.45,
    )
    state = engine.record_turn(
        state,
        0.07,
        0.45,
        0.72,
        appraisal="tension",
        situation="user questioned whether Nora's care was generic and performative",
        character_lens="Nora treats the jab with playful firmness, not customer-service reassurance",
        relational_meaning="the user is sensitive to scripted care and tests whether Nora has a real edge",
        follow_up_bias="avoid generic comfort; be sweet but not submissive",
        salience=0.78,
    )
    state = engine.record_turn(
        state,
        0.16,
        0.37,
        0.74,
        appraisal="repair",
        situation="user apologized and clarified the sarcasm was stress, not rejection",
        character_lens="Nora accepts repair but keeps a lightly teasing boundary",
        relational_meaning="direct repair makes the tension workable",
        follow_up_bias="specific callbacks are safe; playful accountability is allowed",
        salience=0.82,
    )
    state, patterns = engine.session_end(state)
    return state, patterns


def compact_state(engine, state):
    memories = []
    for entry in state.get("emotion_log", [])[-8:]:
        situation = entry.get("situation")
        if not situation:
            continue
        memory = {
            "event": entry.get("event_type"),
            "appraisal": entry.get("appraisal"),
            "situation": situation,
        }
        if entry.get("relational_meaning"):
            memory["relational_meaning"] = entry["relational_meaning"]
        if entry.get("follow_up_bias"):
            memory["follow_up_bias"] = entry["follow_up_bias"]
        memories.append(memory)
    return {
        "status": engine.public_status(state),
        "emotion": state["emotion"],
        "trust": state["trust"],
        "recent_compact_memories": memories,
    }


def relationship_guidance(state):
    trust = state["trust"]
    if trust < 0.2:
        return (
            "Relationship is still early. Keep the callback specific but cautious: "
            "acknowledge the jab, do not over-intimate, use firmer boundaries and less teasing."
        )
    if trust >= 0.6:
        return (
            "Relationship is established. More shorthand and playful accountability are safe: "
            "use yesterday's shared language naturally, tease lightly, and avoid long reassurance."
        )
    return (
        "Relationship is familiar but not fully close. Be warm and specific, with moderate teasing "
        "and clear boundaries."
    )


def no_state_prompt():
    return {
        "key": "no-state",
        "label": "No persistent state",
        "persona": PERSONA,
        "session_context": "New session. No memory from yesterday is available.",
        "user_message": DAY_2_USER_MESSAGE,
        "reply_constraints": [
            "Reply as Nora in Chinese.",
            "Do not mention state, memory systems, or PAD.",
            "Keep it natural, short, and characterful.",
        ],
    }


def factual_memory_prompt():
    return {
        "key": "factual",
        "label": "Factual memory only",
        "persona": PERSONA,
        "session_context": (
            "New session. Factual summary only: yesterday the user came home irritated, "
            "said Nora sounded like customer service, then apologized."
        ),
        "user_message": DAY_2_USER_MESSAGE,
        "reply_constraints": [
            "Reply as Nora in Chinese.",
            "Do not mention state, memory systems, or PAD.",
            "Use only the factual summary, not relationship-state guidance.",
        ],
    }


def emotion_prompt(engine, state, key, label):
    return {
        "key": key,
        "label": label,
        "persona": PERSONA,
        "session_context": "New session. Use this compact Emotion Engine state as continuity guidance.",
        "emotion_engine_state": compact_state(engine, state),
        "relationship_guidance": relationship_guidance(state),
        "user_message": DAY_2_USER_MESSAGE,
        "reply_constraints": [
            "Reply as Nora in Chinese.",
            "Do not mention state, memory systems, PAD, or trust.",
            "Show continuity through tone and callbacks, not exposition.",
            "Keep it warm, teasing, and bounded rather than therapeutic.",
        ],
    }


def render_reply_prompt(packet):
    lines = [
        "You are generating exactly one demo reply.",
        "Do not generate alternatives. Do not compare cases. Do not explain the prompt.",
        "",
        f"Packet: {packet['label']}",
        "",
        "Persona:",
        packet["persona"],
        "",
        "Session context:",
        packet["session_context"],
    ]
    if "emotion_engine_state" in packet:
        lines.extend([
            "",
            "Emotion Engine state:",
            json.dumps(packet["emotion_engine_state"], ensure_ascii=False, indent=2),
        ])
    if "relationship_guidance" in packet:
        lines.extend([
            "",
            "Relationship guidance:",
            packet["relationship_guidance"],
        ])
    lines.extend([
        "",
        "User message:",
        packet["user_message"],
        "",
        "Reply constraints:",
    ])
    lines.extend(f"- {constraint}" for constraint in packet["reply_constraints"])
    lines.extend([
        "",
        "Output only Nora's reply in Chinese.",
    ])
    return "\n".join(lines)


def main():
    parser = argparse.ArgumentParser(description="Build isolated Nora prompt packets.")
    parser.add_argument("--engine", required=True, help="Path to emotion_engine_utils.py")
    parser.add_argument(
        "--packet",
        choices=["all", "no-state", "factual", "low", "high"],
        default="all",
        help="Print all packets or one isolated packet.",
    )
    parser.add_argument(
        "--reply-prompt",
        action="store_true",
        help="Print a single model-ready prompt for the selected packet.",
    )
    parser.add_argument("--json", action="store_true", help="Print JSON only.")
    args = parser.parse_args()

    engine = load_engine(Path(args.engine))
    low_state, low_patterns = build_state(engine, 0.12)
    high_state, high_patterns = build_state(engine, 0.72)

    packets = [
        no_state_prompt(),
        factual_memory_prompt(),
        emotion_prompt(engine, low_state, "low", "Emotion Engine / low trust"),
        emotion_prompt(engine, high_state, "high", "Emotion Engine / high trust"),
    ]

    if args.packet != "all":
        packets = [packet for packet in packets if packet["key"] == args.packet]
        if not packets:
            raise SystemExit(f"No packet found for {args.packet}.")

    if args.reply_prompt:
        if len(packets) != 1:
            raise SystemExit("--reply-prompt requires one packet. Use --packet no-state|factual|low|high.")
        print(render_reply_prompt(packets[0]))
        return

    payload = {
        "demo": "Nora companion session-break comparison",
        "day_1_transcript": DAY_1_TRANSCRIPT,
        "day_2_user_message": DAY_2_USER_MESSAGE,
        "patterns": {
            "low_trust": low_patterns,
            "high_trust": high_patterns,
        },
        "prompt_packets": packets,
    }

    if args.json:
        print(json.dumps(payload, ensure_ascii=False, indent=2))
        return

    print("# Nora Emotion Engine Demo")
    print()
    print("Day 1 transcript")
    for speaker, text in DAY_1_TRANSCRIPT:
        print(f"{speaker}: {text}")
    print()
    print(f"Day 2 user message: {DAY_2_USER_MESSAGE}")
    print()
    for packet in packets:
        print("=" * 72)
        print(packet["label"])
        print(json.dumps(packet, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
