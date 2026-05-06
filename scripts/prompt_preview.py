#!/usr/bin/env python3
"""Preview the continuity guidance an LLM integration could receive."""

import argparse
import json

import emotion_engine_utils as engine


def recent_memories(state, limit=3):
    memories = []
    for entry in state.get("emotion_log", [])[-limit:]:
        situation = entry.get("situation")
        if not situation:
            continue
        appraisal = entry.get("appraisal")
        if appraisal:
            memories.append(f"{appraisal}: {situation}")
        else:
            memories.append(situation)
    return memories


def build_guidance(state, message=None):
    state = engine.ensure_state_shape(state)
    status = engine.public_status(state)
    advisory = engine.appraise_message(state, message) if message else None
    memories = recent_memories(state)

    lines = [
        "# Emotion Engine Prompt Preview",
        "",
        "This is not an LLM response. It is continuity guidance that an LLM-powered agent could use.",
        "",
        "Current continuity state:",
        f"- Tone: {status['summary']}",
        f"- Trust tier: {status['trust_tier']}",
        f"- Style: {status['style']}",
        f"- Session count: {status['session_count']}",
    ]

    if memories:
        lines.append("- Recent compact memories:")
        lines.extend(f"  - {memory}" for memory in memories)
    else:
        lines.append("- Recent compact memories: none yet")

    if advisory:
        lines.extend([
            "",
            "Advisory appraisal:",
            f"- The deterministic helper sees this message as {advisory['appraisal']}.",
            f"- Suggested PAD shift: {advisory['actual_delta']}",
            "- Treat this as a hint, not the final judgment.",
        ])

    lines.extend([
        "",
        "LLM task:",
        "- Interpret the user message using full conversation context.",
        "- Decide the final appraisal and PAD update.",
        "- Generate a natural reply shaped by the current continuity state.",
        "- After responding, record a compact emotional memory without storing the full transcript.",
    ])

    return "\n".join(lines)


def build_json_payload(state, message=None):
    state = engine.ensure_state_shape(state)
    advisory = engine.appraise_message(state, message) if message else None
    return {
        "status": engine.public_status(state),
        "recent_memories": recent_memories(state),
        "message": message,
        "advisory_appraisal": advisory,
        "llm_responsibility": [
            "interpret context",
            "choose final appraisal",
            "choose final PAD update",
            "generate reply",
            "record compact memory",
        ],
    }


def main():
    parser = argparse.ArgumentParser(description="Preview Emotion Engine continuity guidance for an LLM.")
    parser.add_argument("--state", help="Optional state file to read. Defaults to an in-memory state.")
    parser.add_argument("--style", help="Optional style used when no state file is provided.")
    parser.add_argument("--message", help="Optional user message for advisory appraisal.")
    parser.add_argument("--json", action="store_true", help="Print machine-readable JSON.")
    args = parser.parse_args()

    if args.state:
        state = engine.load_state(args.state)
    else:
        state = engine.default_state()
        if args.style:
            state = engine.apply_configuration(state, args.style, "prompt-preview-style")

    if args.json:
        print(json.dumps(build_json_payload(state, args.message), indent=2, ensure_ascii=False))
    else:
        print(build_guidance(state, args.message))


if __name__ == "__main__":
    main()
