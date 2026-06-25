#!/usr/bin/env python3
"""Preview the continuity guidance an LLM integration could receive."""

import argparse
import json

import emotion_engine_utils as engine


ZH_APPRAISAL = {
    "warmth": "温暖或感谢",
    "repair": "修复或道歉",
    "collaboration": "协作",
    "vulnerability": "脆弱或求助",
    "boundary_pressure": "边界压力",
    "hostility": "敌意",
    "neutral": "中性",
}

ZH_TRUST_TIER = {
    "New": "新关系",
    "Acquaintance": "初步熟悉",
    "Familiar": "熟悉",
    "Close": "亲近",
    "Intimate": "高度亲密",
}


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


def translate_memory_zh(memory):
    translations = {
        "character style configured": "已配置角色风格",
        "session patterns extracted for trust evaluation": "已提取会话模式，用于评估信任变化",
        "relationship trust recalibrated from session evidence": "已根据会话证据重新校准信任",
    }
    return translations.get(memory, memory)


def zh_tone_summary(state):
    emotion = state["emotion"]
    if emotion["pleasure"] >= 0.25:
        pleasure = "温暖"
    elif emotion["pleasure"] <= -0.2:
        pleasure = "防备"
    else:
        pleasure = "平稳"

    if emotion["arousal"] >= 0.6:
        arousal = "活跃"
    elif emotion["arousal"] <= 0.25:
        arousal = "冷静"
    else:
        arousal = "稳定"

    if emotion["dominance"] >= 0.65:
        dominance = "有边界"
    elif emotion["dominance"] <= 0.35:
        dominance = "柔和"
    else:
        dominance = "均衡"

    return f"{pleasure}、{arousal}、{dominance}"


def zh_pulse_summary(state):
    pulse = state.get("affective_pulse", {})
    intensity = pulse.get("intensity", 0.0)
    label = pulse.get("label", "none")
    if intensity <= 0.03:
        strength = "安静"
    elif intensity <= 0.18:
        strength = "轻微"
    elif intensity <= 0.35:
        strength = "明显"
    else:
        strength = "强烈"
    return f"{strength}的{label}短期波动"


def build_guidance(state, message=None, lang="en"):
    state = engine.ensure_state_shape(state)
    status = engine.public_status(state)
    advisory = engine.appraise_message(state, message) if message else None
    memories = recent_memories(state)

    if lang == "zh-CN":
        lines = [
            "# Emotion Engine 提示预览",
            "",
            "这不是大模型回复，而是给大模型智能体使用的连续性上下文。",
            "",
            "当前连续性状态：",
            f"- 语气倾向：{zh_tone_summary(state)}",
            f"- 短期情绪波动：{zh_pulse_summary(state)}",
            f"- 波动档位：{state.get('volatility_profile', 'steady')}",
            f"- 信任阶段：{ZH_TRUST_TIER.get(status['trust_tier'], status['trust_tier'])}",
            f"- 风格描述：{state.get('character_profile', {}).get('description', status['style'])}",
            f"- 会话次数：{status['session_count']}",
        ]

        if memories:
            lines.append("- 最近紧凑记忆：")
            lines.extend(f"  - {translate_memory_zh(memory)}" for memory in memories)
        else:
            lines.append("- 最近紧凑记忆：暂无")

        if advisory:
            label = ZH_APPRAISAL.get(advisory["appraisal"], advisory["appraisal"])
            lines.extend([
                "",
                "辅助评价：",
                f"- 规则工具暂时把这句话看作：{label}。",
                f"- 建议 PAD 变化：{advisory['actual_delta']}",
                f"- 建议短期 pulse：{advisory['affective_pulse']}",
                "- 这只是提示，不是最终判断。",
            ])

        lines.extend([
            "",
            "大模型任务：",
            "- 结合完整上下文理解用户消息。",
            "- 决定最终评价和 PAD 更新。",
            "- 生成受当前连续性状态影响的自然回复。",
            "- 回复后记录一条紧凑情绪记忆，不保存完整对话原文。",
        ])

        return "\n".join(lines)

    lines = [
        "# Emotion Engine Prompt Preview",
        "",
        "This is not an LLM response. It is continuity guidance that an LLM-powered agent could use.",
        "",
        "Current continuity state:",
        f"- Tone: {status['summary']}",
        f"- Affective pulse: {status['pulse']}",
        f"- Volatility profile: {status['volatility_profile']}",
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
            f"- Suggested affective pulse: {advisory['affective_pulse']}",
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


def build_json_payload(state, message=None, lang="en"):
    state = engine.ensure_state_shape(state)
    advisory = engine.appraise_message(state, message) if message else None
    return {
        "status": engine.public_status(state),
        "language": lang,
        "recent_memories": recent_memories(state),
        "message": message,
        "advisory_appraisal": advisory,
        "affective_pulse": state["affective_pulse"],
        "volatility_profile": state["volatility_profile"],
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
    parser.add_argument("--lang", default="en", choices=["en", "zh-CN"], help="Output language.")
    parser.add_argument("--json", action="store_true", help="Print machine-readable JSON.")
    args = parser.parse_args()

    if args.state:
        state = engine.load_state(args.state)
    else:
        state = engine.default_state()
        if args.style:
            state = engine.apply_configuration(state, args.style, "prompt-preview-style")

    if args.json:
        print(json.dumps(build_json_payload(state, args.message, args.lang), indent=2, ensure_ascii=False))
    else:
        print(build_guidance(state, args.message, args.lang))


if __name__ == "__main__":
    main()
