<p align="center">
  <img src="assets/emotion-engine-logo.svg" alt="Emotion Engine" width="540">
</p>

# Emotion Engine

**Emotional continuity for LLM agents.**

[English](README.md) | [Chinese](README.zh-CN.md)

[![License: MIT](https://img.shields.io/badge/license-MIT-green.svg)](LICENSE)
[![Python](https://img.shields.io/badge/python-3.9%2B-blue.svg)](https://www.python.org/)

Most AI agents can respond well in the moment, but they do not carry an emotional thread across time. They may sound warm in one turn, blank in the next, and forget whether the last interaction felt collaborative, tense, repaired, or unresolved.

Emotion Engine gives an LLM-powered agent a small, inspectable continuity layer: mood, agent-to-user trust, decay, boundary signals, and compact emotional memories. The LLM still decides what happened and how to respond. Emotion Engine makes that judgment persistent.

Memory systems remember facts and events. Emotion Engine remembers a small, inspectable continuity signal for how the interaction has been going.

It is not a memory stack. It is a portable emotional-continuity state layer that can sit beside memory retrieval, character systems, or agent runtimes.

Emotion Engine is part of PioneerJeff Labs, an open-source lab building reusable infrastructure layers for creative AI applications.

Status: experimental. Current release: [v0.2.1 - Persistence hardening and agent install guide](https://github.com/pioneerjeff-labs/emotion-engine/releases/tag/v0.2.1).

## Start Here

| Goal | Start with |
|---|---|
| See the idea in 30 seconds | [Live web demo](https://pioneerjeff-labs.github.io/emotion-engine/demo/) |
| Inspect the state packet | [Hugging Face state playground](https://huggingface.co/spaces/pioneerjeff/emotion-engine-state-playground) |
| Wire the smallest agent loop | `python3 examples/minimal-agent/run_demo.py` |
| Ask a coding agent to install it | [INSTALL_WITH_AGENT.md](INSTALL_WITH_AGENT.md) |
| Connect a local MCP-capable agent | [docs/MCP.md](docs/MCP.md) |
| Integrate with an OpenAI/API host | [docs/OPENAI_GPT.md](docs/OPENAI_GPT.md) |
| Implement an adapter | [docs/PROTOCOL.md](docs/PROTOCOL.md) |

The demo and minimal-agent paths do not require an API key or a live LLM call.

## The Problem

Long-running agents need more than chat history.

Chat history stores what happened. Emotion Engine stores how the interaction has been feeling.

Without a continuity layer, an agent often treats every session as emotionally fresh. With Emotion Engine, an agent can carry forward lightweight signals such as:

- the last session was collaborative
- agent-to-user trust has grown slightly, but the relationship is still early
- a challenge felt productive rather than hostile
- the next response should be warm, steady, and clearly bounded

## What You Can Build

- Character agents that feel emotionally consistent across sessions.
- Personal assistants with gentle, user-controlled relational memory.
- AI companions that can become warmer or more bounded without storing full transcripts.
- Game NPCs or narrative agents whose mood evolves over time.
- Research prototypes for affective computing, agent memory, and human-agent interaction.

## How It Works

```text
User message
  -> LLM interprets the context
  -> LLM decides the final emotional meaning and response
  -> Emotion Engine stores PAD state, trust, and compact memory
  -> Future prompts receive continuity guidance
```

The split is intentional:

- The **LLM** makes the contextual judgment and generates the reply.
- The **Python helper** persists state, applies decay, records logs, extracts session patterns, and updates trust slowly.
- The deterministic `appraise` helper is only a fallback or debugging aid. It is not the source of truth in a real integration.

In short: **the LLM decides; Emotion Engine remembers.**

## Web Demo

The best first look is the side-by-side web demo in [demo](demo). It compares a baseline assistant with one using an Emotion Engine state packet, so the difference is visible as a conversation unfolds. The demo also includes a small v0.2 compare block showing `Mood only` as an internal ablation against the default integrated `mood + affective_pulse` state package.

<p align="center">
  <img src="demo/screenshot.png" alt="Emotion Engine web demo showing baseline memory beside Emotion Engine state" width="900">
</p>

The demo is based on anonymized and adapted traces from prior LLM interaction experiments, not a purely fabricated benchmark. It is still curated for explanation: the browser does not call an LLM, does not generate live replies, and does not infer a real user's emotional state.

Live demo: [Try the live demo](https://pioneerjeff-labs.github.io/emotion-engine/demo/)

Hugging Face Space: [Try the state playground](https://huggingface.co/spaces/pioneerjeff/emotion-engine-state-playground) to inspect the prompt prelude and `emotion-engine-state/v2` packet directly.

Open it directly:

```text
demo/index.html
```

Or serve the repository locally:

```bash
python3 -m http.server 4173 --bind 127.0.0.1
```

Then visit:

```text
http://127.0.0.1:4173/demo/
```

## 5-Minute Minimal Agent

If you want the smallest concrete loop before choosing a platform package, run:

```bash
python3 examples/minimal-agent/run_demo.py
```

The example loads state, builds a prompt prelude, lets a mock LLM choose the final appraisal/PAD values, records the turn, settles trust, and saves the final state. It does not call an LLM or require an API key. Repeat runs reuse generated state; pass `--state <path>` for a clean run.

## Local State Checks

The Python scripts are not the main product demo. They are developer-facing checks for the core state layer: useful for validating lifecycle behavior, debugging integrations, and proving the shared engine still works under OpenClaw, Claude Skill, Hermes Agent, or another host.

Run a lifecycle check without installing any agent runtime:

```bash
python3 scripts/check_state_lifecycle.py --style "warm but not over-compliant, with clear boundaries"
```

This does not call an LLM and does not generate assistant replies. It checks that the state layer works: configure, session start, decay, advisory appraisal, record turn, session end, trust settlement, and emotion log.

To see the kind of guidance an LLM integration would receive:

```bash
python3 scripts/prompt_preview.py \
  --style "calm, reliable, and clearly bounded" \
  --message "Thanks, the last version is much clearer. I want to challenge one part of the design."
```

Example guidance:

```text
Current continuity state:
- Tone: warm, steady, firm
- Trust tier: New
- Style: mildly warm; calm; strongly bounded

Advisory appraisal:
- The helper sees this message as collaboration.

LLM task:
- Interpret the message using full context.
- Decide the final appraisal and PAD update.
- Generate a natural reply shaped by the current state.
- Record a compact emotional memory after the turn.
```

## Which Package Should I Use?

| Need | Use |
|---|---|
| Scripted web demo for product explanation | [demo](demo) |
| Hosted state playground for inspecting prompt prelude and state packets | [Hugging Face Space](https://huggingface.co/spaces/pioneerjeff/emotion-engine-state-playground) |
| 5-minute reference loop for wiring Emotion Engine into an agent | [examples/minimal-agent](examples/minimal-agent) |
| Coding-agent assisted local install | [INSTALL_WITH_AGENT.md](INSTALL_WITH_AGENT.md) |
| Local stdio MCP server for runtime/protocol tools | [docs/MCP.md](docs/MCP.md) |
| Core state engine checks and local tooling | [scripts](scripts) |
| OpenClaw skill | [integrations/openclaw](integrations/openclaw) |
| Claude Skill / Claude Code package | [integrations/claude-skill](integrations/claude-skill) |
| Hermes Agent skill package | [integrations/hermes](integrations/hermes) |
| Codex skill package | [integrations/codex](integrations/codex) |
| OpenAI GPT / API host-side integration guide | [docs/OPENAI_GPT.md](docs/OPENAI_GPT.md) |

The repository root is the Emotion Engine project. Platform-specific packages live under `integrations/`.
The first-party starter integrations are OpenClaw, Claude Skill, Hermes Agent, and Codex. Codex ships as a user-installed skill package. GPT/API usage is documented as a host-side integration pattern because the host application owns persistence and model calls.

For Codex or Agent Harness project targets, register MCP clients with an explicit `--state .emotion-engine/codex-state.json`; see [docs/MCP.md](docs/MCP.md).

For the smallest concrete loop before choosing a platform package, see [examples/minimal-agent](examples/minimal-agent).

## Protocol And Adapter Boundary

The stable state contract lives in [Emotion Engine State Protocol](docs/PROTOCOL.md), with a machine-readable schema at [spec/emotion-state.schema.json](spec/emotion-state.schema.json).

For memory systems such as Celiums Memory, Emotion Engine should be used as a thin adapter target: map host PAD / `limbicState` into `state.emotion`, map compact journal or `turn_after` events into `emotion_log`, then return a compact snapshot or prompt prelude for the host to store or inject.

Emotion Engine does not replace a memory stack, retrieval, ethics/policy, turn context, or clinical emotion inference. Host systems keep ownership of grounded memory and safety decisions.

## When To Use It

Use Emotion Engine when an agent needs compact continuity signals that are easy to inspect, tune, and inject into a prompt prelude.

Good fits:

- A character, companion, or NPC should carry emotional inertia across sessions.
- A personal assistant should remember whether the last interaction felt collaborative, tense, repaired, or unresolved.
- A memory system is already present, but relationship state should stay small and debuggable.
- A prototype needs stateful behavior without running a full retrieval stack.

## When Not To Use It

Do not use Emotion Engine as a substitute for full experiential memory. If your agent should derive emotion entirely from retrieved lived context, use a memory system first.

Poor fits:

- The agent needs factual recall, graph memory, semantic search, or audit-grade history.
- Emotional meaning must remain grounded in complete event context rather than a compact state snapshot.
- The system cannot accept numeric or summarized relationship-state signals.
- The use case involves mental-health assessment, emotion detection for real people, or consequential decisions.

## Integrations

### OpenClaw

The OpenClaw-compatible package lives in [integrations/openclaw](integrations/openclaw).

For local OpenClaw installation:

```bash
cd integrations/openclaw/emotion-engine
./install.sh
```

The installer:

- copies the skill into your OpenClaw workspace
- creates `emotion-state.json` if missing
- preserves existing state if one already exists
- lets you describe the agent's style in one sentence
- prints a natural-language status so you can see it is working

Example style:

```text
warm but not over-compliant, with clear boundaries
```

To build an OpenClaw upload zip:

```bash
cd integrations/openclaw
./package_openclaw_skill.sh
```

This creates `emotion-engine-openclaw-skill.zip`.

### Claude Skill

The Claude-compatible package lives in [integrations/claude-skill](integrations/claude-skill).

For Claude Code:

```bash
cd integrations/claude-skill/emotion-engine
./install.sh
```

To build a Claude Skills upload zip:

```bash
cd integrations/claude-skill
./package_claude_skill.sh
```

This creates `emotion-engine-claude-skill.zip`. The zip is a generated release artifact, so it is not committed to the repository.

### Hermes Agent

The Hermes-compatible package lives in [integrations/hermes](integrations/hermes).

Install from Skills Hub / skills.sh:

```bash
hermes skills install skills-sh/pioneerjeff-labs/emotion-engine/skills/emotion-engine
```

Or install directly from GitHub:

```bash
hermes skills install pioneerjeff-labs/emotion-engine/skills/emotion-engine
```

For local Hermes installation:

```bash
cd integrations/hermes/emotion-engine
./install.sh
```

To build a Hermes skill zip:

```bash
cd integrations/hermes
./package_hermes_skill.sh
```

This creates `emotion-engine-hermes-skill.zip`. The zip is a generated release artifact, so it is not committed to the repository.

### Codex

The Codex-compatible package lives in [integrations/codex](integrations/codex).

For local Codex installation:

```bash
cd integrations/codex/emotion-engine-codex
sh install.sh
```

The installer creates a user-level Codex skill, not a bundled/system skill. It copies the skill into `CODEX_SKILLS_DIR` if set; otherwise it prefers an existing `~/.codex/skills` directory and falls back to:

```text
~/.agents/skills/emotion-engine-codex
```

Personal state defaults to the matching local home: `~/.codex/emotion-engine/emotion-state.json` when `~/.codex` is active, or `~/.agents/emotion-engine/emotion-state.json` for the `~/.agents` fallback.

To build a Codex skill zip:

```bash
cd integrations/codex
./package_codex_skill.sh
```

This creates `emotion-engine-codex-skill.zip`. The zip is a generated release artifact, so it is not committed to the repository.

### OpenAI GPT / API

For GPT/API integrations, keep Emotion Engine state in your host application and inject compact continuity guidance into the model prompt. This is not the Codex skill package; it is a pattern for applications that call OpenAI models. See [OpenAI GPT / API Integration](docs/OPENAI_GPT.md).

## Core Concepts

Emotion Engine stores and updates:

- **PAD mood state**: Pleasure, Arousal, Dominance; a slow mood layer that drifts back toward baseline.
- **Affective pulse**: short-lived visible per-turn movement, integrated with mood in the default state package.
- **Volatility profile**: internal or advanced movement envelope for different agent types.
- **Trust**: a slow-moving agent-to-user relationship coefficient with its own decay policy. It is not the user's trust in the agent.
- **Personality baseline**: where the agent naturally drifts back to.
- **Emotion trajectory**: numeric state during a session.
- **Emotion log**: compact emotional memories, not full transcripts.
- **Trust history**: numeric ledger for trust changes; reasons belong in `emotion_log`.
- **Session patterns**: conflict, repair, volatility, suppression, and trust signals.

Read more in [Concepts](docs/CONCEPTS.md).

## Integration

The typical integration loop is:

1. Load the current state.
2. Apply session or turn decay.
3. Let the LLM interpret the user message and choose the final emotional update.
4. Record the turn with compact memory.
5. Use the updated state as guidance for future replies.
6. At session end, settle agent-to-user trust from session evidence.

See [Integration Guide](docs/INTEGRATION.md) for the full sequence.

## CLI

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
python3 scripts/emotion_engine_utils.py settle_trust <state_file>
python3 scripts/emotion_engine_utils.py session_end <state_file>
python3 scripts/emotion_engine_utils.py update_trust <state_file> <trust_delta>
python3 scripts/emotion_engine_utils.py recent_log <state_file> 5
```

## What It Is Not

Emotion Engine is not a chatbot and does not generate replies by itself.

It is also not an emotion detector, mental health tool, or psychological assessment system. It models fictional or agent-internal continuity, not a real person's emotional state.

## Brand Assets

Starter logo assets live in [assets](assets). Brand guidance lives in [Brand Notes](docs/BRAND.md).

## Project Structure

```text
emotion-engine/
├── INSTALL_WITH_AGENT.md
├── emotion-state-template.json
├── spec/
│   └── emotion-state.schema.json
├── scripts/
│   ├── emotion_engine_utils.py
│   ├── check_state_lifecycle.py
│   ├── prompt_preview.py
│   └── simulate_state_lifecycle.py
├── integrations/
│   ├── openclaw/
│   ├── claude-skill/
│   ├── hermes/
│   └── codex/
├── tests/
├── docs/
├── demo/
├── assets/
├── README.md
├── README.zh-CN.md
├── LICENSE
├── CHANGELOG.md
├── CONTRIBUTING.md
└── SECURITY.md
```

## Roadmap

- Clearer LLM integration examples.
- Optional real chat demo using an API key or local model.
- More appraisal examples and tests.
- Portable state format for future memory migration work.
- Better examples for character agents, personal assistants, and game NPCs.

## Safety And Ethics

Emotion Engine models fictional or agent-internal emotional continuity. It does not detect, diagnose, or verify a real person's emotional or mental state.

Do not use this project to manipulate attachment, pressure users into engagement, punish absence, or make consequential decisions about people. Treat the state as a creative and interaction-design tool, not as psychological truth.

## License

MIT. See [LICENSE](LICENSE).
