# Emotion Engine

Emotion Engine is an experimental OpenClaw skill for giving conversational agents a compact, persistent emotional state. It combines PAD emotion values, a slow-moving trust coefficient, deterministic appraisal helpers, chat-first configuration, and situation-aware emotional memories.

Emotion Engine is part of PioneerJeff Labs (PJL), a small open-source lab exploring agent continuity, memory, and personal AI.

Status: experimental / v0.1-ready.

## What It Does

- Maintains emotional state using the PAD model: Pleasure, Arousal, and Dominance.
- Applies time-based decay so emotion drifts back toward a personality baseline.
- Tracks trust as a separate relationship coefficient that changes slowly over time.
- Appraises user messages with deterministic keyword-based helper logic.
- Records compact emotion logs that preserve meaning without saving full transcripts.
- Supports natural-language style configuration, tuning, pause/resume, and status checks.
- Extracts session patterns such as conflict, repair, volatility, and suppression.

## Quick Start

From the repository root, run:

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

You can also skip configuration and use the default warm, steady style.

## Try Without OpenClaw

If you do not have an OpenClaw environment yet, run the local simulator:

```bash
python3 scripts/simulate_openclaw_session.py --style "温柔但不讨好，有一点自己的边界"
```

You can pass custom turns:

```bash
python3 scripts/simulate_openclaw_session.py \
  --style "冷静可靠，有边界感" \
  --turn "谢谢你，刚才那个版本清楚很多了" \
  --turn "我想 challenge 一下，这个设计是不是还有点空？" \
  --turn "对，这样更像 MVP，我们先按这个做"
```

The simulator runs the same lifecycle that OpenClaw should trigger: session start, in-session decay, appraisal, turn recording, session end, trust update, and recent emotion log.

By default the simulation is ephemeral and does not write a state file. Add `--state ./emotion-state.sim.json` if you want to inspect or resume the simulated state.

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
│   └── simulate_openclaw_session.py
├── tests/
│   └── test_emotion_engine_utils.py
├── README.md
├── LICENSE
├── CHANGELOG.md
├── CONTRIBUTING.md
└── SECURITY.md
```

## Theory

The core emotion representation is based on the PAD model described by Mehrabian and Russell in 1974. Emotion Engine extends that representation with a trust coefficient, time decay, session pattern extraction, and compact relationship memories.

## Safety And Ethics

Emotion Engine models fictional or agent-internal emotional continuity. It does not detect, diagnose, or verify a real person's emotional or mental state.

Do not use this project to manipulate attachment, pressure users into engagement, punish absence, or make consequential decisions about people. Treat the state as a creative and interaction-design tool, not as psychological truth.

## License

MIT. See [LICENSE](LICENSE).
