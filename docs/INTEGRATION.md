# Integration Guide

This guide describes how to use Emotion Engine as a state layer in an LLM-powered agent.

The stable state and adapter contract live in [Emotion Engine State Protocol](PROTOCOL.md). Use [spec/emotion-state.schema.json](../spec/emotion-state.schema.json) when an integration needs a machine-readable contract for state packets, adapter events, or adapter outputs.

Ready-to-adapt starter integrations:

- OpenClaw: [integrations/openclaw](../integrations/openclaw)
- Claude Skill: [integrations/claude-skill](../integrations/claude-skill)
- Hermes Agent: [integrations/hermes](../integrations/hermes)
- Codex: [integrations/codex](../integrations/codex)
- OpenAI GPT / API host-side guide: [docs/OPENAI_GPT.md](OPENAI_GPT.md)

## Minimal Loop

```text
1. Load state
2. Apply session or turn decay
3. Ask the LLM to interpret the user message
4. Ask the LLM to choose final appraisal and PAD values
5. Record the turn
6. Generate or refine the assistant response using current state
7. At session end, extract patterns and update agent-to-user trust
```

## Adapter Boundary

Use an adapter when Emotion Engine sits beside a host memory or agent runtime. The adapter should stay thin:

- map host PAD / emotion state into Emotion Engine PAD
- map final turn or journal events into compact `emotion_log` entries
- return a compact snapshot or prompt prelude for the host to store or inject
- keep factual memory, retrieval, policy, and user-facing decisions in the host runtime
- map only agent-to-user trust unless a host system explicitly owns another trust model

Do not use Emotion Engine as a replacement memory stack, retrieval layer, safety policy, or clinical emotion inference system.

## Start A Session

```bash
python3 scripts/emotion_engine_utils.py session_start emotion-state.json
```

This applies time-based decay, updates session counters, and clears the current trajectory.

## Before Each User Message

Apply in-session drift:

```bash
python3 scripts/emotion_engine_utils.py pre_turn_decay emotion-state.json
```

Optionally get an advisory appraisal:

```bash
python3 scripts/emotion_engine_utils.py appraise emotion-state.json "Thanks, this is much clearer."
```

Treat this as a hint. The LLM should still decide the final appraisal and PAD update using full context.

## Prompt Guidance

Use `prompt_preview.py` to see the kind of continuity guidance you can provide to an LLM:

```bash
python3 scripts/prompt_preview.py \
  --state emotion-state.json \
  --message "I want to challenge one part of the design."
```

In a real agent, you can convert the same fields into a system or developer message:

```text
Current continuity state:
- Tone: warm, steady, firm
- Trust tier: New
- Recent memories: ...

LLM task:
- Interpret the user message in context.
- Decide the final appraisal and PAD update.
- Generate a natural reply shaped by the current state.
- Record a compact emotional memory after the turn.
```

## Record A Turn

After the LLM chooses the final PAD values:

```bash
python3 scripts/emotion_engine_utils.py record_turn emotion-state.json 0.18 0.32 0.61 \
  --appraisal collaboration \
  --situation user challenged the design in a constructive way \
  --meaning disagreement feels safe and productive \
  --follow-up be precise, warm, and clearly bounded \
  --salience 0.65
```

## End A Session

```bash
python3 scripts/emotion_engine_utils.py session_end emotion-state.json
```

Then choose an agent-to-user trust delta using both:

- extracted trajectory patterns
- the LLM's interpretation of the session

Apply the final trust update:

```bash
python3 scripts/emotion_engine_utils.py update_trust emotion-state.json 0.02
```

`update_trust` writes the numeric effect to `trust_history`. Keep the reason for the change in `emotion_log`: the preceding turn entries, the `session_end` pattern log, or the compact `trust_update` entry. Do not add semantic reasons, confidence, or external references to `trust_history`; use `emotion_log.source_refs` for adapter provenance.

## State Control

Pause state updates:

```bash
python3 scripts/emotion_engine_utils.py pause emotion-state.json
```

Resume:

```bash
python3 scripts/emotion_engine_utils.py resume emotion-state.json
```

Show user-friendly status:

```bash
python3 scripts/emotion_engine_utils.py status emotion-state.json
```

Show raw debug state:

```bash
python3 scripts/emotion_engine_utils.py status emotion-state.json --raw
```

## Privacy Guidance

Do not store full private transcripts in the emotion log. Store compact summaries and relational meaning.

Prefer:

```text
user challenged the design constructively and invited a stronger version
```

Avoid:

```text
full copied user message with private details
```
