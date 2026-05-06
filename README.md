# Emotion Engine

**Emotional continuity for LLM agents.**

Most AI agents respond well in the moment, but they do not carry an emotional thread across time. They can sound warm in one turn, blank in the next, and forget what a relationship has been feeling like.

Emotion Engine gives an agent a small, inspectable inner state: mood, trust, decay, and compact emotional memories. The LLM still decides what happened and how to respond; Emotion Engine makes that judgment persistent.

Emotion Engine is part of PioneerJeff Labs (PJL), a small open-source lab exploring agent continuity, memory, and personal AI.

Status: experimental / v0.1.

[![License: MIT](https://img.shields.io/badge/license-MIT-green.svg)](LICENSE)
[![Python](https://img.shields.io/badge/python-3.9%2B-blue.svg)](https://www.python.org/)

## Why This Exists

Long-running agents need more than chat history. They need a compact way to remember the emotional shape of interaction:

- Did the user challenge the agent in a collaborative way, or in a hostile way?
- Did a conflict get repaired?
- Is trust slowly growing, or should the agent become more guarded?
- Should the next reply be warmer, calmer, firmer, or more careful?

Emotion Engine is a lightweight state layer for that kind of continuity.

## What You Can Build

- Character agents that feel emotionally consistent across sessions.
- Personal assistants with gentle, user-controlled relational memory.
- AI companions that can become warmer or more bounded without storing full transcripts.
- Game NPCs or narrative agents whose mood evolves over time.
- Research prototypes for affective computing, agent memory, and human-agent interaction.

## What It Is

Emotion Engine stores and updates:

- **PAD state**: Pleasure, Arousal, Dominance.
- **Trust**: a slow-moving relationship coefficient.
- **Personality baseline**: where the agent naturally drifts back to.
- **Emotion trajectory**: numeric state during a session.
- **Emotion log**: compact emotional memories, not full transcripts.
- **Session patterns**: conflict, repair, volatility, suppression, and trust signals.

## What It Is Not

Emotion Engine is not a chatbot. It does not generate replies by itself.

It is also not an emotion detector, mental health tool, or psychological assessment system. It models fictional or agent-internal continuity, not a real person's emotional state.

## How It Fits With An LLM

```text
User message
  -> LLM interprets context and emotional meaning
  -> Emotion Engine stores PAD / trust / compact memory
  -> LLM uses current state as response guidance
  -> Emotion Engine records what changed and why
```

The intended split:

- The **LLM** understands context, decides the final appraisal, chooses the final PAD update, writes compact emotional memory, and generates the actual reply.
- The **Python helper** stores state, clamps values, applies decay, records logs, extracts session patterns, and updates trust slowly.
- The deterministic `appraise` command is only an advisory fallback for testing or simple integrations. Treat it as a hint, not as the final emotional judgment.

In short: Python maintains continuity; the LLM makes the contextual judgment.

## Try It Without OpenClaw

You can run a local state lifecycle check without installing OpenClaw:

```bash
python3 scripts/check_state_lifecycle.py --style "温柔但不讨好，有一点自己的边界"
```

This does not call an LLM and does not generate AI replies. It checks that the state layer works: configure, session start, decay, advisory appraisal, record turn, session end, trust update, and emotion log.

Example output:

```text
# Emotion Engine State Lifecycle Check

This is not an AI chat demo. No assistant reply is generated here.
The deterministic appraisal helper is used only as a stand-in for LLM judgment.

Turn 1
User input: 谢谢你，刚才那个版本已经清楚很多了。
Advisory helper: warmth
State effect: warmer, more energized, more bounded
Response guidance preview for the LLM: warm but clearly bounded

Session Summary
Pattern summary: 3 turns analyzed; no conflict detected; slightly positive emotional trend; boundaries remain stable.
Trust update: 0.1000 -> 0.1180
```

Pass your own simulated turns:

```bash
python3 scripts/check_state_lifecycle.py \
  --style "冷静可靠，有边界感" \
  --turn "谢谢你，刚才那个版本清楚很多了" \
  --turn "我想 challenge 一下，这个设计是不是还有点空？" \
  --turn "对，这样更像 MVP，我们先按这个做"
```

Save the state if you want to inspect or resume it:

```bash
python3 scripts/check_state_lifecycle.py \
  --style "温柔但不讨好，有一点自己的边界" \
  --state emotion-state.sim.json
```

Use `--json` for raw debug output.

## OpenClaw Quick Start

From the repository root:

```bash
./setup.sh
```

The setup helper:

- copies the skill into your OpenClaw workspace
- creates `emotion-state.json` if missing
- preserves existing state if one already exists
- lets you describe the vibe in one sentence
- prints a natural-language status so you can see it is working

Example vibe:

```text
温柔但不讨好，有一点自己的边界
```

## Manual Install

```bash
mkdir -p ~/.openclaw/workspace/skills/emotion-engine/scripts
cp SKILL.md README.md emotion-state-template.json setup.sh ~/.openclaw/workspace/skills/emotion-engine/
cp scripts/*.py ~/.openclaw/workspace/skills/emotion-engine/scripts/
python3 ~/.openclaw/workspace/skills/emotion-engine/scripts/emotion_engine_utils.py init ~/.openclaw/workspace/emotion-state.json
python3 ~/.openclaw/workspace/skills/emotion-engine/scripts/emotion_engine_utils.py configure ~/.openclaw/workspace/emotion-state.json --style "冷静可靠，有边界感"
```

## Core Commands

```bash
python3 scripts/emotion_engine_utils.py init <state_file>
python3 scripts/emotion_engine_utils.py validate <state_file>
python3 scripts/emotion_engine_utils.py configure <state_file> --style <description>
python3 scripts/emotion_engine_utils.py configure <state_file> --soul-file <SOUL.md>
python3 scripts/emotion_engine_utils.py tune <state_file> <natural-language adjustment>
python3 scripts/emotion_engine_utils.py status <state_file>
python3 scripts/emotion_engine_utils.py pause <state_file>
python3 scripts/emotion_engine_utils.py resume <state_file>
python3 scripts/emotion_engine_utils.py session_start <state_file>
python3 scripts/emotion_engine_utils.py pre_turn_decay <state_file>
python3 scripts/emotion_engine_utils.py appraise <state_file> <message...>
python3 scripts/emotion_engine_utils.py record_turn <state_file> <P> <A> <D> --appraisal <label> --situation <what happened>
python3 scripts/emotion_engine_utils.py session_end <state_file>
python3 scripts/emotion_engine_utils.py update_trust <state_file> <trust_delta>
python3 scripts/emotion_engine_utils.py recent_log <state_file> 5
```

`emotion_trajectory` is numeric and session-local. `emotion_log` is long-lived and interpretive: it stores situation-aware emotional memories, not full transcripts.

`clear_log` and `reset` are available for control, but they intentionally erase local emotional history.

## Chat-First Configuration

MVP configuration is chat-first, not a separate UI. A user can say:

- "风格设成温柔但不讨好"
- "根据这个 SOUL.md 配一下"
- "更冷静一点"
- "别那么顺从"
- "暂停情绪记录"
- "恢复情绪引擎"
- "现在状态怎么样"

The skill maps those intents to `configure`, `tune`, `pause`, `resume`, or `status`.

For important events, add only the memory fields that help future behavior:

```bash
python3 scripts/emotion_engine_utils.py record_turn <state_file> <P> <A> <D> \
  --appraisal collaboration \
  --situation user challenged the design and invited a stronger revision \
  --lens calm mentor treats direct critique as useful signal \
  --meaning disagreement feels safe and productive \
  --impact pleasure rose, dominance stabilized \
  --open-loop false \
  --follow-up be more precise next turn \
  --salience 0.65
```

## Personality Presets

Edit the `personality_baseline` in your `emotion-state.json`:

| Character type | Pleasure | Arousal | Dominance |
|---|---:|---:|---:|
| Cheerful friend | 0.3 | 0.5 | 0.5 |
| Tsundere | -0.1 | 0.6 | 0.7 |
| Calm mentor | 0.2 | 0.2 | 0.6 |
| Shy introvert | 0.0 | 0.2 | 0.3 |
| Energetic companion | 0.4 | 0.7 | 0.5 |

## Project Structure

```text
emotion-engine/
├── SKILL.md
├── emotion-state-template.json
├── setup.sh
├── scripts/
│   ├── emotion_engine_utils.py
│   ├── check_state_lifecycle.py
│   └── simulate_openclaw_session.py
├── tests/
│   ├── test_emotion_engine_utils.py
│   └── test_simulate_openclaw_session.py
├── docs/
│   └── LAUNCH_KIT.md
├── README.md
├── LICENSE
├── CHANGELOG.md
├── CONTRIBUTING.md
└── SECURITY.md
```

## Roadmap

- Clearer LLM integration examples.
- Prompt-preview mode that shows the exact guidance an LLM would receive.
- Optional real chat demo using an API key or local model.
- More appraisal examples and tests.
- A portable state format for future memory migration work.

## Safety And Ethics

Emotion Engine models fictional or agent-internal emotional continuity. It does not detect, diagnose, or verify a real person's emotional or mental state.

Do not use this project to manipulate attachment, pressure users into engagement, punish absence, or make consequential decisions about people. Treat the state as a creative and interaction-design tool, not as psychological truth.

## License

MIT. See [LICENSE](LICENSE).
