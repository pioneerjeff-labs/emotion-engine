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

DEFAULT_TURNS_ZH = [
    "谢谢你，刚才那个版本清楚很多了。",
    "我想认真挑战一下这个设计，它是不是还是有点抽象？",
    "对，这样更像最小可行版本，我们先按这个方向推进。",
]

ZH_APPRAISAL = {
    "warmth": "温暖或感谢",
    "repair": "修复或道歉",
    "collaboration": "协作",
    "vulnerability": "脆弱或求助",
    "boundary_pressure": "边界压力",
    "hostility": "敌意",
    "neutral": "中性",
}

ZH_APPRAISAL_CUE = {
    "warmth": "表达温暖或感谢",
    "repair": "修复尝试或道歉",
    "collaboration": "协作型请求",
    "vulnerability": "用户脆弱或求助",
    "boundary_pressure": "对自主性或边界施压",
    "hostility": "敌意或轻蔑",
    "neutral": "中性或情绪信号不明确",
}

ZH_TRUST_TIER = {
    "New": "新关系",
    "Acquaintance": "初步熟悉",
    "Familiar": "熟悉",
    "Close": "亲近",
    "Intimate": "高度亲密",
}

ZH_JSON_LABELS = {
    "Initial Status": "初始状态",
    "Session Start": "会话开始",
    "Session End": "会话结束",
    "Recent Emotion Log": "最近情绪日志",
}

ZH_EVENT_LABELS = {
    "configure": "配置",
    "pre_turn_decay": "轮次前衰减",
    "turn": "轮次记录",
    "session_end": "会话结束",
    "trust_update": "信任更新",
}

ZH_SITUATIONS = {
    "character style configured": "已配置角色风格",
    "session patterns extracted for trust evaluation": "已提取会话模式，用于评估信任变化",
    "relationship trust recalibrated from session evidence": "已根据会话证据重新校准信任",
}


def is_zh(lang):
    return lang == "zh-CN"


def default_turns(lang):
    return DEFAULT_TURNS_ZH if is_zh(lang) else DEFAULT_TURNS


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


def tone_preview(state, lang="en"):
    emotion = state["emotion"]
    if emotion["pleasure"] >= 0.25 and emotion["arousal"] >= 0.5:
        if is_zh(lang):
            return "更温暖、更有活力，也更主动"
        return "warmer, more energetic, and more proactive"
    if emotion["pleasure"] >= 0.15 and emotion["dominance"] >= 0.6:
        if is_zh(lang):
            return "温暖但边界清晰"
        return "warm but clearly bounded"
    if emotion["arousal"] <= 0.25:
        if is_zh(lang):
            return "冷静、克制、稳定"
        return "calm, measured, and steady"
    if emotion["pleasure"] < -0.1 and emotion["dominance"] >= 0.6:
        if is_zh(lang):
            return "更谨慎，也更坚定"
        return "guarded and firmer"
    if emotion["dominance"] < 0.4:
        if is_zh(lang):
            return "更柔和，也更试探"
        return "softer and more tentative"
    if is_zh(lang):
        return "均衡而专注"
    return "balanced and attentive"


def print_json(label, value, lang="en"):
    display_label = label
    if is_zh(lang):
        if label.startswith("Turn "):
            display_label = "轮次 " + label.removeprefix("Turn ")
        else:
            display_label = ZH_JSON_LABELS.get(label, label)
    print(f"\n## {display_label}")
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


def describe_delta_zh(delta):
    parts = []
    if delta["P"] > 0.02:
        parts.append("更温暖")
    elif delta["P"] < -0.02:
        parts.append("更谨慎")
    if delta["A"] > 0.02:
        parts.append("更有能量")
    elif delta["A"] < -0.02:
        parts.append("更冷静")
    if delta["D"] > 0.02:
        parts.append("边界更清晰")
    elif delta["D"] < -0.02:
        parts.append("更柔和")
    return "、".join(parts) if parts else "基本不变"


def format_delta(delta):
    return ", ".join(f"{key} {value:+.4f}" for key, value in delta.items())


def zh_tone_summary(state):
    emotion = state["emotion"]
    tone = []
    if emotion["pleasure"] >= 0.25:
        tone.append("温暖")
    elif emotion["pleasure"] <= -0.2:
        tone.append("谨慎")
    else:
        tone.append("平稳")

    if emotion["arousal"] >= 0.6:
        tone.append("活跃")
    elif emotion["arousal"] <= 0.25:
        tone.append("冷静")
    else:
        tone.append("稳定")

    if emotion["dominance"] >= 0.65:
        tone.append("有边界")
    elif emotion["dominance"] <= 0.35:
        tone.append("柔和")
    else:
        tone.append("均衡")

    return "、".join(tone)


def trust_label(tier, lang):
    if is_zh(lang):
        return ZH_TRUST_TIER.get(tier, tier)
    return tier


def appraisal_label(appraisal, lang):
    if is_zh(lang):
        return ZH_APPRAISAL.get(appraisal, appraisal)
    return appraisal


def appraisal_cue_label(appraisal, cue, lang):
    if is_zh(lang):
        return ZH_APPRAISAL_CUE.get(appraisal, cue)
    return cue


def summarize_patterns(patterns, lang="en"):
    if is_zh(lang):
        if not patterns.get("sufficient_data"):
            return f"只有 {patterns.get('turn_count', 0)} 个轮次，暂时还没有足够的轨迹数据。"

        notes = [f"已分析 {patterns['turn_count']} 个轮次"]
        if patterns.get("v_shape"):
            notes.append("出现冲突后的修复")
        elif patterns.get("had_conflict"):
            notes.append("检测到冲突")
        else:
            notes.append("未检测到冲突")

        if patterns.get("sustained_negative"):
            notes.append("存在持续负向趋势")
        elif patterns.get("avg_pleasure_delta", 0) > 0:
            notes.append("情绪趋势略微正向")
        else:
            notes.append("情绪趋势基本稳定")

        if patterns.get("dominance_suppressed"):
            notes.append("边界感可能被压低")
        else:
            notes.append("边界保持稳定")

        return "；".join(notes) + "。"

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


def print_human_header(state, lang="en"):
    status = engine.public_status(state)
    if is_zh(lang):
        profile = state.get("character_profile", {})
        print("# Emotion Engine 状态生命周期检查")
        print()
        print("这不是 AI 聊天演示。这里不会生成助手回复。")
        print("规则化辅助评价只用作大模型判断的占位提示。")
        print("真实集成中，大模型负责最终评价、PAD 更新、记忆取舍和回复生成。")
        print()
        print(f"配置风格：{profile.get('description', status['style'])}")
        print(f"初始状态：{zh_tone_summary(state)} | 信任阶段：{trust_label(status['trust_tier'], lang)}")
        return

    print("# Emotion Engine State Lifecycle Check")
    print()
    print("This is not an AI chat demo. No assistant reply is generated here.")
    print("The deterministic appraisal helper is used only as a stand-in for LLM judgment.")
    print("In a real integration, the LLM decides the final appraisal, PAD update, memory, and reply.")
    print()
    print(f"Configured style: {status['style']}")
    print(f"Initial status: {status['summary']} | trust tier: {status['trust_tier']}")


def print_human_turn(idx, message, appraisal, before, after, preview, lang="en"):
    delta = engine.emotion_delta(before, after)
    if is_zh(lang):
        label = appraisal_label(appraisal["appraisal"], lang)
        cue = appraisal_cue_label(appraisal["appraisal"], appraisal["cue"], lang)
        print()
        print(f"轮次 {idx}")
        print(f"用户输入：{message}")
        print(f"辅助评价：{label}（{cue}）")
        print(f"建议 PAD 变化：{format_delta(appraisal['actual_delta'])}")
        print(f"模拟后的最终 PAD：{pad_line(after)}")
        print(f"状态影响：{describe_delta_zh(delta)}")
        print(f"给大模型的回复提示预览：{preview}")
        print("真实集成说明：大模型应在 record_turn 之前，根据完整上下文决定最终评价和 PAD 更新。")
        return

    print()
    print(f"Turn {idx}")
    print(f"User input: {message}")
    print(f"Advisory helper: {appraisal['appraisal']} ({appraisal['cue']})")
    print(f"Advisory PAD shift: {format_delta(appraisal['actual_delta'])}")
    print(f"Simulated final PAD: {pad_line(after)}")
    print(f"State effect: {describe_delta(delta)}")
    print(f"Response guidance preview for the LLM: {preview}")
    print("Real integration note: an LLM should make the final contextual decision before record_turn.")


def log_situation(message, lang):
    if is_zh(lang):
        return f"模拟用户输入：{message[:160]}"
    return f"simulated user turn: {message[:160]}"


def log_impact(appraisal, lang):
    if is_zh(lang):
        return f"辅助评价建议 {appraisal['actual_delta']}"
    return f"appraisal suggested {appraisal['actual_delta']}"


def integration_note(lang):
    if is_zh(lang):
        return "真实集成中，大模型应在 record_turn 之前决定最终评价和 PAD 更新。"
    return "In real integration, the LLM should decide final appraisal and PAD before record_turn."


def compact_situation_label(situation, lang):
    if not is_zh(lang):
        return situation
    if situation.startswith("simulated user turn: "):
        return "模拟用户输入：" + situation.removeprefix("simulated user turn: ")
    return ZH_SITUATIONS.get(situation, situation)


def print_compact_memory(entry, lang):
    event = entry.get("event_type", "event")
    situation = entry.get("situation", "(no situation)")
    appraisal = entry.get("appraisal")

    if is_zh(lang):
        event = ZH_EVENT_LABELS.get(event, event)
        situation = compact_situation_label(situation, lang)
        if appraisal:
            print(f"- {event}：{appraisal_label(appraisal, lang)}；{situation}")
        else:
            print(f"- {event}：{situation}")
        return

    if appraisal:
        print(f"- {event}: {appraisal}; {situation}")
    else:
        print(f"- {event}: {situation}")


def print_human_footer(state, patterns, trust_before, trust_delta, args):
    status = engine.public_status(state)
    lang = args.lang
    if is_zh(lang):
        print()
        print("会话总结")
        print(f"模式总结：{summarize_patterns(patterns, lang)}")
        print(f"信任更新：{trust_before:.4f} -> {state['trust']:.4f}（原始变化 {trust_delta}）")
        print(f"最终状态：{zh_tone_summary(state)} | {trust_label(status['trust_tier'], lang)}")
        if args.state:
            print(f"已保存状态文件：{args.state}")
        else:
            print("状态未保存。加入 --state emotion-state.sim.json 后可以检查或继续使用。")

        print()
        print("最近紧凑情绪记忆")
        for entry in state.get("emotion_log", [])[-5:]:
            print_compact_memory(entry, lang)
        return

    print()
    print("Session Summary")
    print(f"Pattern summary: {summarize_patterns(patterns, lang)}")
    print(f"Trust update: {trust_before:.4f} -> {state['trust']:.4f} (raw delta {trust_delta})")
    print(f"Final status: {status['summary']} | {status['trust_tier']}")
    if args.state:
        print(f"Saved state file: {args.state}")
    else:
        print("State was not saved. Add --state emotion-state.sim.json to inspect or resume it.")

    print()
    print("Recent compact emotion memories")
    for entry in state.get("emotion_log", [])[-5:]:
        print_compact_memory(entry, lang)


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

    turns = args.turn or default_turns(args.lang)

    if args.json:
        print_json("Initial Status", engine.public_status(state), args.lang)
    else:
        print_human_header(state, args.lang)

    state = engine.session_start(state)
    if args.json:
        print_json("Session Start", {
            "emotion": state["emotion"],
            "trust": state["trust"],
            "session_count": state["session_count"],
        }, args.lang)

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
            situation=log_situation(message, args.lang),
            character_lens=state["character_profile"].get("interpretation"),
            impact=log_impact(appraisal, args.lang),
            follow_up_bias=tone_preview(state, args.lang),
            salience=0.45,
        )
        if args.json:
            print_json(f"Turn {idx}", {
                "user": message,
                "advisory_appraisal": appraisal["appraisal"],
                "advisory_delta": appraisal["actual_delta"],
                "simulated_final_emotion": state["emotion"],
                "tone_preview": tone_preview(state, args.lang),
                "note": integration_note(args.lang),
            }, args.lang)
        else:
            print_human_turn(
                idx,
                message,
                appraisal,
                before,
                state["emotion"],
                tone_preview(state, args.lang),
                args.lang,
            )

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
        }, args.lang)
        print_json("Recent Emotion Log", state.get("emotion_log", [])[-5:], args.lang)
    else:
        print_human_footer(state, patterns, trust_before, trust_delta, args)


def main():
    parser = argparse.ArgumentParser(description="Check the Emotion Engine state lifecycle locally.")
    parser.add_argument("--state", help="Optional state file to read/write. Omit for an ephemeral simulation.")
    parser.add_argument("--resume", action="store_true", help="Resume from --state instead of starting fresh.")
    parser.add_argument("--style", help="Natural-language character vibe, e.g. warm but clearly bounded.")
    parser.add_argument("--soul-file", help="Path to SOUL.md-like character description.")
    parser.add_argument("--turn", action="append", help="User turn to simulate. Can be repeated.")
    parser.add_argument("--lang", default="en", choices=["en", "zh-CN"], help="Output language.")
    parser.add_argument("--json", action="store_true", help="Print raw JSON debug output.")
    args = parser.parse_args()
    run_simulation(args)


if __name__ == "__main__":
    main()
