#!/usr/bin/env python3
"""
simulate_openclaw_session.py — Local lifecycle simulator for Emotion Engine.

Use this when OpenClaw is not installed yet. It runs the same core lifecycle:
configure -> session_start -> pre_turn_decay -> appraise -> record_turn
-> session_end -> trust update.
"""

import argparse
import json

import emotion_engine_utils as engine


DEFAULT_TURNS = [
    "谢谢你，刚才那个版本已经清楚很多了。",
    "这里我想 challenge 一下，这个设计是不是还有点空？",
    "对，我觉得这样更靠谱，我们先按 MVP 做。",
]


def choose_trust_delta(patterns):
    if not patterns.get("sufficient_data"):
        return 0.0
    if patterns.get("v_shape"):
        return 0.04
    if patterns.get("sustained_negative"):
        return -0.07
    if patterns.get("dominance_suppressed") or patterns.get("recent_boundary_events", 0) >= 2:
        return -0.04
    if patterns.get("too_smooth"):
        return 0.005
    if patterns.get("avg_pleasure_delta", 0) > 0:
        return 0.02
    return 0.0


def tone_preview(state):
    emotion = state["emotion"]
    if emotion["pleasure"] >= 0.25 and emotion["arousal"] >= 0.5:
        return "warmer, more energetic, and more proactive"
    if emotion["pleasure"] >= 0.15 and emotion["dominance"] >= 0.6:
        return "warm but clearly bounded"
    if emotion["arousal"] <= 0.25:
        return "calm, measured, and steady"
    if emotion["pleasure"] < -0.1 and emotion["dominance"] >= 0.6:
        return "guarded and firmer"
    if emotion["dominance"] < 0.4:
        return "softer and more tentative"
    return "balanced and attentive"


def print_json(label, value):
    print(f"\n## {label}")
    print(json.dumps(value, indent=2, ensure_ascii=False))


def run_simulation(args):
    if args.resume and not args.state:
        raise SystemExit("--resume requires --state")

    if args.resume:
        state = engine.load_state(args.state)
    else:
        state = engine.default_state()

    if args.style:
        state = engine.apply_configuration(state, args.style, "simulator-style")

    if args.soul_file:
        with open(args.soul_file, "r") as f:
            state = engine.apply_configuration(state, f.read(12000), "simulator-soul-file")
            state["character_profile"]["soul_file"] = args.soul_file

    turns = args.turn or DEFAULT_TURNS

    print_json("Initial Status", engine.public_status(state))

    state = engine.session_start(state)
    print_json("Session Start", {
        "emotion": state["emotion"],
        "trust": state["trust"],
        "session_count": state["session_count"],
    })

    for idx, message in enumerate(turns, 1):
        state = engine.apply_in_session_decay(state)
        appraisal = engine.appraise_message(state, message)
        suggested = appraisal["suggested"]
        state = engine.record_turn(
            state,
            suggested["P"],
            suggested["A"],
            suggested["D"],
            appraisal=appraisal["appraisal"],
            situation=f"simulated user turn: {message[:160]}",
            character_lens=state["character_profile"].get("interpretation"),
            impact=f"appraisal suggested {appraisal['actual_delta']}",
            follow_up_bias=tone_preview(state),
            salience=0.45,
        )
        print_json(f"Turn {idx}", {
            "user": message,
            "appraisal": appraisal["appraisal"],
            "actual_delta": appraisal["actual_delta"],
            "emotion": state["emotion"],
            "tone_preview": tone_preview(state),
        })

    state, patterns = engine.session_end(state)
    trust_delta = choose_trust_delta(patterns)
    if trust_delta:
        state = engine.apply_trust_delta(state, trust_delta)

    if args.state:
        engine.save_state(args.state, state)

    print_json("Session End", {
        "patterns": patterns,
        "trust_delta": trust_delta,
        "final_status": engine.public_status(state),
        "state_file": args.state,
        "saved": bool(args.state),
    })
    print_json("Recent Emotion Log", state.get("emotion_log", [])[-5:])


def main():
    parser = argparse.ArgumentParser(description="Simulate an OpenClaw Emotion Engine session locally.")
    parser.add_argument("--state", help="Optional state file to read/write. Omit for an ephemeral simulation.")
    parser.add_argument("--resume", action="store_true", help="Resume from --state instead of starting fresh.")
    parser.add_argument("--style", help="Natural-language character vibe, e.g. 温柔但不讨好.")
    parser.add_argument("--soul-file", help="Path to SOUL.md-like character description.")
    parser.add_argument("--turn", action="append", help="User turn to simulate. Can be repeated.")
    args = parser.parse_args()
    run_simulation(args)


if __name__ == "__main__":
    main()
