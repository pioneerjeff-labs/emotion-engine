#!/usr/bin/env python3
"""
simulate_openclaw_session.py — Local state lifecycle checker for Emotion Engine.

Use this when OpenClaw is not installed yet. It does not call an LLM and does
not generate assistant replies. It uses the deterministic appraisal helper as
a stand-in so you can verify the state lifecycle:
configure -> session_start -> pre_turn_decay -> advisory appraisal ->
record_turn -> session_end -> trust update.
"""

import argparse
import json

import emotion_engine_utils as engine


DEFAULT_TURNS = [
    "Thanks, the last version is much clearer.",
    "I want to challenge one part of the design. Is it still a bit too abstract?",
    "Yes, this feels more like an MVP. Let's move forward with this version.",
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


def pad_line(emotion):
    return (
        f"P={emotion['pleasure']:.4f}, "
        f"A={emotion['arousal']:.4f}, "
        f"D={emotion['dominance']:.4f}"
    )


def describe_delta(delta):
    parts = []
    if delta["P"] > 0.02:
        parts.append("warmer")
    elif delta["P"] < -0.02:
        parts.append("more guarded")
    if delta["A"] > 0.02:
        parts.append("more energized")
    elif delta["A"] < -0.02:
        parts.append("calmer")
    if delta["D"] > 0.02:
        parts.append("more bounded")
    elif delta["D"] < -0.02:
        parts.append("softer")
    return ", ".join(parts) if parts else "mostly unchanged"


def format_delta(delta):
    return ", ".join(f"{key} {value:+.4f}" for key, value in delta.items())


def summarize_patterns(patterns):
    if not patterns.get("sufficient_data"):
        return f"Only {patterns.get('turn_count', 0)} turn(s), so there is not enough trajectory data yet."

    notes = [f"{patterns['turn_count']} turns analyzed"]
    if patterns.get("v_shape"):
        notes.append("conflict followed by repair")
    elif patterns.get("had_conflict"):
        notes.append("conflict detected")
    else:
        notes.append("no conflict detected")

    if patterns.get("sustained_negative"):
        notes.append("sustained negative trend")
    elif patterns.get("avg_pleasure_delta", 0) > 0:
        notes.append("slightly positive emotional trend")
    else:
        notes.append("mostly stable emotional trend")

    if patterns.get("dominance_suppressed"):
        notes.append("dominance appears suppressed")
    else:
        notes.append("boundaries remain stable")

    return "; ".join(notes) + "."


def print_human_header(state):
    status = engine.public_status(state)
    print("# Emotion Engine State Lifecycle Check")
    print()
    print("This is not an AI chat demo. No assistant reply is generated here.")
    print("The deterministic appraisal helper is used only as a stand-in for LLM judgment.")
    print("In a real integration, the LLM decides the final appraisal, PAD update, memory, and reply.")
    print()
    print(f"Configured style: {status['style']}")
    print(f"Initial status: {status['summary']} | trust tier: {status['trust_tier']}")


def print_human_turn(idx, message, appraisal, before, after, preview):
    delta = engine.emotion_delta(before, after)
    print()
    print(f"Turn {idx}")
    print(f"User input: {message}")
    print(f"Advisory helper: {appraisal['appraisal']} ({appraisal['cue']})")
    print(f"Advisory PAD shift: {format_delta(appraisal['actual_delta'])}")
    print(f"Simulated final PAD: {pad_line(after)}")
    print(f"State effect: {describe_delta(delta)}")
    print(f"Response guidance preview for the LLM: {preview}")
    print("Real integration note: an LLM should make the final contextual decision before record_turn.")


def print_human_footer(state, patterns, trust_before, trust_delta, args):
    status = engine.public_status(state)
    print()
    print("Session Summary")
    print(f"Pattern summary: {summarize_patterns(patterns)}")
    print(f"Trust update: {trust_before:.4f} -> {state['trust']:.4f} (raw delta {trust_delta})")
    print(f"Final status: {status['summary']} | {status['trust_tier']}")
    if args.state:
        print(f"Saved state file: {args.state}")
    else:
        print("State was not saved. Add --state emotion-state.sim.json to inspect or resume it.")

    print()
    print("Recent compact emotion memories")
    for entry in state.get("emotion_log", [])[-5:]:
        event = entry.get("event_type", "event")
        situation = entry.get("situation", "(no situation)")
        appraisal = entry.get("appraisal")
        if appraisal:
            print(f"- {event}: {appraisal}; {situation}")
        else:
            print(f"- {event}: {situation}")


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

    if args.json:
        print_json("Initial Status", engine.public_status(state))
    else:
        print_human_header(state)

    state = engine.session_start(state)
    if args.json:
        print_json("Session Start", {
            "emotion": state["emotion"],
            "trust": state["trust"],
            "session_count": state["session_count"],
        })

    for idx, message in enumerate(turns, 1):
        state = engine.apply_in_session_decay(state)
        appraisal = engine.appraise_message(state, message)
        suggested = appraisal["suggested"]
        before = state["emotion"].copy()
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
        if args.json:
            print_json(f"Turn {idx}", {
                "user": message,
                "advisory_appraisal": appraisal["appraisal"],
                "advisory_delta": appraisal["actual_delta"],
                "simulated_final_emotion": state["emotion"],
                "tone_preview": tone_preview(state),
                "note": "In real integration, the LLM should decide final appraisal and PAD before record_turn.",
            })
        else:
            print_human_turn(idx, message, appraisal, before, state["emotion"], tone_preview(state))

    state, patterns = engine.session_end(state)
    trust_delta = choose_trust_delta(patterns)
    trust_before = state["trust"]
    if trust_delta:
        state = engine.apply_trust_delta(state, trust_delta)

    if args.state:
        engine.save_state(args.state, state)

    if args.json:
        print_json("Session End", {
            "patterns": patterns,
            "trust_delta": trust_delta,
            "final_status": engine.public_status(state),
            "state_file": args.state,
            "saved": bool(args.state),
        })
        print_json("Recent Emotion Log", state.get("emotion_log", [])[-5:])
    else:
        print_human_footer(state, patterns, trust_before, trust_delta, args)


def main():
    parser = argparse.ArgumentParser(description="Check the Emotion Engine state lifecycle locally.")
    parser.add_argument("--state", help="Optional state file to read/write. Omit for an ephemeral simulation.")
    parser.add_argument("--resume", action="store_true", help="Resume from --state instead of starting fresh.")
    parser.add_argument("--style", help="Natural-language character vibe, e.g. 温柔但不讨好.")
    parser.add_argument("--soul-file", help="Path to SOUL.md-like character description.")
    parser.add_argument("--turn", action="append", help="User turn to simulate. Can be repeated.")
    parser.add_argument("--json", action="store_true", help="Print raw JSON debug output.")
    args = parser.parse_args()
    run_simulation(args)


if __name__ == "__main__":
    main()
