#!/usr/bin/env python3
"""Minimal Emotion Engine agent loop.

This example does not call a real LLM. The "mock LLM decision" entries in
turns.json stand in for the host application's model call, final appraisal,
final PAD choice, assistant reply, and compact memory judgment.
"""

import argparse
import json
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
SCRIPTS = ROOT / "scripts"
if str(SCRIPTS) not in sys.path:
    sys.path.insert(0, str(SCRIPTS))

import emotion_engine_utils as engine  # noqa: E402


HERE = Path(__file__).resolve().parent
DEFAULT_TURNS = HERE / "turns.json"
DEFAULT_STATE = HERE / "out" / "emotion-state.json"
DEFAULT_STYLE = "warm, steady, practical, and clearly bounded"
INTERNAL_EVENT_TYPES = {
    "configure",
    "session_start",
    "pre_turn_decay",
    "session_end",
    "trust_settlement",
    "trust_update",
}


def load_turns(path):
    with open(path, "r", encoding="utf-8") as f:
        turns = json.load(f)
    if not isinstance(turns, list) or not turns:
        raise ValueError(f"{path} must contain a non-empty JSON list")
    return turns


def pad_line(emotion):
    return (
        f"P={emotion['pleasure']:.4f}, "
        f"A={emotion['arousal']:.4f}, "
        f"D={emotion['dominance']:.4f}"
    )


def recent_interaction_memories(state, limit=3):
    recent = []
    for entry in reversed(state.get("emotion_log", [])):
        event_type = entry.get("event_type")
        if event_type in INTERNAL_EVENT_TYPES:
            continue
        if event_type != "turn" and not entry.get("appraisal"):
            continue
        situation = entry.get("situation")
        if situation:
            recent.append(situation)
        if len(recent) == limit:
            break
    recent.reverse()
    return recent


def compact_prelude(state):
    status = engine.public_status(state)
    recent = recent_interaction_memories(state)

    lines = [
        "Continuity prelude for the next LLM call:",
        f"- Tone: {status['summary']}",
        f"- Trust tier: {status['trust_tier']}",
        f"- Style: {status['style']}",
    ]
    if recent:
        lines.append("- Recent compact memories:")
        lines.extend(f"  - {item}" for item in recent)
    else:
        lines.append("- Recent compact memories: none yet")
    return "\n".join(lines)


def print_step(title):
    print()
    print(f"== {title} ==")


def run(turns_path=DEFAULT_TURNS, state_path=DEFAULT_STATE):
    turns = load_turns(turns_path)

    print("# Minimal Emotion Engine Agent Loop")
    print("No API key is used. No real LLM is called.")
    print("The host app still owns retrieval, policy, the model call, final response, and final appraisal/PAD choice.")

    print_step("load state")
    state_exists = state_path.exists()
    state = engine.load_state(state_path)
    if state_exists:
        print(f"Loaded existing state: {state_path}")
    else:
        state = engine.apply_configuration(state, DEFAULT_STYLE, "minimal-agent")
        print(f"No state file found at {state_path}; initialized a default state.")
    print(f"Status: {engine.public_status(state)['summary']} | trust {state['trust']:.4f}")

    print_step("session_start")
    state = engine.session_start(state)
    print(f"Session count: {state['session_count']}")

    for idx, turn in enumerate(turns, 1):
        user_message = turn["user"]
        decision = turn["mock_llm_decision"]

        print_step(f"turn {idx}: pre_turn_decay")
        state = engine.apply_in_session_decay(state)
        print(f"State before prompt: {pad_line(state['emotion'])}")

        print_step("build prompt prelude")
        print(compact_prelude(state))

        print_step("advisory appraise")
        advisory = engine.appraise_message(state, user_message)
        print(f"User: {user_message}")
        print(f"Helper hint: {advisory['appraisal']} | suggested {advisory['suggested']}")
        print("Treat this as a hint. A real LLM/app can override it using full context.")

        print_step("mock LLM final decision")
        print(f"Assistant reply drafted by mock LLM: {decision['assistant_reply']}")
        print(f"Final appraisal chosen by mock LLM: {decision['final_appraisal']}")
        print(f"Final PAD chosen by mock LLM: {decision['final_pad']}")

        print_step("record_turn")
        final_pad = decision["final_pad"]
        state = engine.record_turn(
            state,
            final_pad["P"],
            final_pad["A"],
            final_pad["D"],
            appraisal=decision["final_appraisal"],
            situation=decision["situation"],
            relational_meaning=decision["relational_meaning"],
            impact=decision["impact"],
            follow_up_bias=decision["follow_up_bias"],
            salience=decision["salience"],
            character_lens=state["character_profile"].get("interpretation"),
        )
        print(f"Recorded turn {len(state['emotion_trajectory'])}; state is now {pad_line(state['emotion'])}")

    print_step("settle_trust")
    trust_before = state["trust"]
    state, settlement = engine.settle_trust(state)
    print(f"Settlement: {settlement['status']} | raw delta {settlement['raw_delta']:+.4f}")
    print(f"Reason: {settlement.get('reason', settlement['status'])}")
    print(f"Trust: {trust_before:.4f} -> {state['trust']:.4f}")

    print_step("save final state")
    state_path.parent.mkdir(parents=True, exist_ok=True)
    engine.save_state(state_path, state)
    print(f"Wrote final state to {state_path}")

    print()
    print("Recent compact emotion memories:")
    recent = recent_interaction_memories(state, limit=4)
    if recent:
        for situation in recent:
            print(f"- {situation}")
    else:
        print("- none yet")


def main():
    parser = argparse.ArgumentParser(description="Run a minimal Emotion Engine agent-loop example.")
    parser.add_argument("--turns", type=Path, default=DEFAULT_TURNS, help="Turns JSON file to replay.")
    parser.add_argument("--state", type=Path, default=DEFAULT_STATE, help="Output state path.")
    args = parser.parse_args()
    run(args.turns, args.state)


if __name__ == "__main__":
    main()
