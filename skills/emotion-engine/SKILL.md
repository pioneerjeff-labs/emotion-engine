---
name: emotion-engine
description: Persistent PAD emotion state, trust, decay, and compact emotional memories for Hermes Agent conversations.
version: 0.1.0
author: PioneerJeff Labs
license: MIT
platforms: [macos, linux]
metadata:
  hermes:
    tags: [AI Agents, Memory, Emotional Continuity]
    category: AI Agents
    config:
      - key: emotion_engine.state_path
        description: Optional state file path for Emotion Engine.
        default: "~/.hermes/emotion-engine/emotion-state.json"
        prompt: Emotion Engine state file path
---

# Emotion Engine For Hermes

Use this skill when the user wants Hermes to maintain lightweight emotional continuity across sessions, character workflows, personal assistant interactions, or long-running agent relationships.

Emotion Engine is not a chatbot and does not generate replies by itself. Hermes still interprets the situation, decides the final emotional meaning, and writes the reply. Emotion Engine persists continuity: PAD state, trust, decay, and compact emotional memories.

## Quick Reference

Use the bundled wrapper:

```bash
${HERMES_SKILL_DIR}/scripts/hermes_emotion.sh status
${HERMES_SKILL_DIR}/scripts/hermes_emotion.sh configure --style "warm but not over-compliant, with clear boundaries"
${HERMES_SKILL_DIR}/scripts/hermes_emotion.sh tune "make it calmer"
```

The wrapper automatically initializes a state file if missing. State path priority:
1. `HERMES_EMOTION_STATE` environment variable
2. current project: `./.emotion-engine/hermes-state.json`
3. personal fallback: `~/.hermes/emotion-engine/emotion-state.json`

Use `status` for user-facing summaries and `status --raw` only for debugging.

## When To Use

Use this skill when the user asks for:

- emotional continuity
- persistent character mood
- relationship/trust memory
- SOUL.md-based character configuration
- a more consistent personal assistant or companion tone
- `/emotion-engine` status, tuning, pause, or resume

Do not use this as a mental health inference tool or a way to assess the real user's emotional state.

## Chat Controls

Map natural-language user requests to commands:

- "Set the style to warm but not over-compliant" -> `configure --style`
- "Configure it from SOUL.md" -> `configure --soul-file ./SOUL.md`
- "Make it gentler" / "make it calmer" / "make it less compliant" -> `tune`
- "What is the current status?" -> `status`
- "Pause emotion logging" -> `pause`
- "Resume Emotion Engine" -> `resume`

Only run `clear_log` or `reset` after the user explicitly asks. They erase local emotional history.

## Procedure

At the start of a new meaningful session:

```bash
${HERMES_SKILL_DIR}/scripts/hermes_emotion.sh session_start
```

Before responding to each user message:

```bash
${HERMES_SKILL_DIR}/scripts/hermes_emotion.sh pre_turn_decay
${HERMES_SKILL_DIR}/scripts/hermes_emotion.sh appraise "<user message>"
```

The appraisal helper is advisory. Hermes must use full context, memory, character profile, sarcasm/playfulness, and relationship history to decide the final emotional update.

After choosing final PAD values, record the turn:

```bash
${HERMES_SKILL_DIR}/scripts/hermes_emotion.sh record_turn <P> <A> <D> --appraisal <label> --situation <short emotional memory>
```

For important events, add only the memory fields that help future behavior:

```bash
${HERMES_SKILL_DIR}/scripts/hermes_emotion.sh record_turn <P> <A> <D> \
  --appraisal collaboration \
  --situation user challenged the design and invited a stronger version \
  --lens calm mentor treats direct critique as useful signal, not rejection \
  --meaning disagreement feels safe and productive \
  --impact pleasure rose, dominance stabilized \
  --open-loop false \
  --follow-up be more precise and structured next turn \
  --salience 0.65
```

At session end:

```bash
${HERMES_SKILL_DIR}/scripts/hermes_emotion.sh session_end
${HERMES_SKILL_DIR}/scripts/hermes_emotion.sh update_trust <trust_delta>
```

Suggested trust delta range is `-0.20` to `+0.05`. Increase trust slowly. Strong positives should usually require either sustained constructive interaction or genuine conflict repair.

## How State Should Shape Replies

Never expose raw PAD numbers in normal conversation. Let state shape tone:

- Higher Pleasure: warmer, more engaged, more affirming.
- Lower Pleasure: more guarded, cooler, less eager.
- Higher Arousal: more energetic, urgent, animated.
- Lower Arousal: calmer, slower, more measured.
- Higher Dominance: firmer, more bounded, more confident.
- Lower Dominance: softer, more tentative, more reassurance-seeking.

Blend this with Hermes memory, user preferences, and any SOUL.md character profile.

## Emotion Memory Rules

`emotion_log` should store situation-aware emotional memories, not transcripts.

Good memory:

```text
user challenged the design constructively; disagreement felt safe and productive
```

Avoid:

```text
full pasted user message or private transcript
```

Useful fields: `situation`, `appraisal`, `character_lens`, `relational_meaning`, `impact`, `open_loop`, `follow_up_bias`, and `salience`.

## Pitfalls

- Do not expose raw PAD values in normal user-facing replies.
- Do not treat the deterministic appraisal helper as the final emotional judge.
- Do not store full private transcripts in `emotion_log`; store compact emotional summaries.
- Do not use trust as obedience, sweetness, or attachment pressure.
- Do not run `reset`, `clear_log`, or other destructive commands unless the user explicitly asks.

## Verification

Run:

```bash
${HERMES_SKILL_DIR}/scripts/hermes_emotion.sh status
```

Expected: JSON with `enabled`, `summary`, `style`, `trust_tier`, and `log_entries`.

## Safety

Treat Emotion Engine as fictional or agent-internal continuity, not psychological truth. Do not use it to manipulate attachment, punish absence, infer real mental health state, or make consequential decisions about people.
