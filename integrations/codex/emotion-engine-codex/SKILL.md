---
name: emotion-engine-codex
description: Add lightweight emotional continuity to Codex workflows using PAD state, agent-to-user trust, decay, and compact emotional memories.
---

# Emotion Engine For Codex

Use this skill when the user wants Codex to maintain lightweight emotional continuity across local projects, fictional character tests, companion-style demos, or long-running personal assistant workflows.

Emotion Engine is not a chatbot and does not generate replies by itself. Codex still interprets the situation, decides the final emotional meaning, and writes the reply. Emotion Engine persists continuity: PAD state, agent-to-user trust, decay, compact emotional memories, and session patterns.

Trust is agent-to-user only: it is the agent/persona's internal continuity estimate of whether this user has been cooperative, boundary-respecting, predictable, and safe enough for deeper persona continuity. It does not infer the user's trust in Codex or in the agent.

## Quick Reference

Use the bundled wrapper:

```bash
scripts/codex_emotion.sh status
scripts/codex_emotion.sh configure --style "warm but not over-compliant, with clear boundaries"
scripts/codex_emotion.sh tune "make it calmer"
```

The wrapper automatically initializes a state file if missing. State path priority:

1. `CODEX_EMOTION_STATE` environment variable
2. `CODEX_PROJECT_DIR/.emotion-engine/codex-state.json`
3. current project: `./.emotion-engine/codex-state.json`
4. personal fallback: `~/.codex/emotion-engine/emotion-state.json` when `~/.codex` exists, otherwise `~/.agents/emotion-engine/emotion-state.json` when `~/.agents` exists

Use `status` for user-facing summaries and `status --raw` only for debugging.

## When To Use

Use this skill when the user asks for:

- emotional continuity
- persistent character mood
- agent-to-user relationship/trust memory
- SOUL.md-based character configuration
- a more consistent project-local assistant tone
- `/emotion-engine` status, tuning, pause, or resume
- no-state vs relationship-state prompt comparison

Do not use this as a mental health inference tool or a way to assess the real user's emotional state.

## Chat Controls

Map natural-language user requests to commands:

- "Set the style to warm but not over-compliant" -> `scripts/codex_emotion.sh configure --style "warm but not over-compliant"`
- "Configure it from this SOUL.md" -> `scripts/codex_emotion.sh configure --soul-file ./SOUL.md`
- "Make it gentler" / "make it calmer" / "make it less compliant" -> `scripts/codex_emotion.sh tune "<request>"`
- "What is the current status?" -> `scripts/codex_emotion.sh status`
- "Pause emotion logging" -> `scripts/codex_emotion.sh pause`
- "Resume Emotion Engine" -> `scripts/codex_emotion.sh resume`

Only run `clear_log` or `reset` after the user explicitly asks. They erase local emotional history.

## Session Flow

At the start of a new meaningful conversation/session:

```bash
scripts/codex_emotion.sh session_start
```

Before responding to each user message:

```bash
scripts/codex_emotion.sh pre_turn_decay
scripts/codex_emotion.sh appraise "<user message>"
```

The appraisal helper is advisory. Codex must use full context, project context, character profile, sarcasm/playfulness, and relationship history to decide the final emotional update.

After choosing final PAD values, record the turn:

```bash
scripts/codex_emotion.sh record_turn <P> <A> <D> --appraisal <label> --situation <short emotional memory>
```

For important events, add only the memory fields that help future behavior:

```bash
scripts/codex_emotion.sh record_turn <P> <A> <D> \
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
scripts/codex_emotion.sh settle_trust
```

`settle_trust` extracts session patterns, checks recent turn-level emotion logs and the current trajectory, chooses a conservative raw delta in `-0.20` to `+0.05`, and applies it once for the same trajectory. Repeating it should return `already_settled` with `raw_delta: 0.0`. Use `session_end` only to inspect patterns without changing trust, and `update_trust <trust_delta>` only for an explicit host-side override.

## How State Should Shape Replies

Never expose raw PAD numbers in normal conversation. Let state shape tone:

- Higher Pleasure: warmer, more engaged, more affirming.
- Lower Pleasure: more guarded, cooler, less eager.
- Higher Arousal: more energetic, urgent, animated.
- Lower Arousal: calmer, slower, more measured.
- Higher Dominance: firmer, more bounded, more confident.
- Lower Dominance: softer, more tentative, more reassurance-seeking.

Blend this with the user's instructions, repository context, and any SOUL.md character profile.

## Nora Demo Prompt Packets

For isolated comparison prompts:

```bash
scripts/codex_emotion.sh nora-demo --packet all
scripts/codex_emotion.sh nora-demo --packet low --reply-prompt
scripts/codex_emotion.sh nora-demo --packet high --reply-prompt
```

The demo prints prompt packets for:

- `no-state`: Nora persona only; no yesterday memory.
- `factual`: Nora persona plus factual memory only.
- `low`: Emotion Engine continuity with early/low trust.
- `high`: Emotion Engine continuity with established trust.

Generate one reply prompt at a time. This keeps model comparisons clean and avoids mixing cases.

## Emotion Memory Rules

`emotion_log` should store situation-aware emotional memories, not transcripts.

`trust_history` should stay a numeric ledger for applied trust changes. Keep reasons and provenance in `emotion_log`, including turn entries, session patterns, compact `trust_update` entries, or optional `source_refs`.

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
- Do not use trust as obedience, sweetness, user scoring, safety permission, user-to-agent trust, or attachment pressure.
- Do not run `reset`, `clear_log`, or other destructive commands unless the user explicitly asks.

## Verification

Run:

```bash
scripts/codex_emotion.sh status
```

Expected: JSON with `enabled`, `summary`, `style`, `trust_tier`, and `log_entries`.

## Safety

Treat Emotion Engine as fictional or agent-internal continuity, not psychological truth. Do not use it to manipulate attachment, punish absence, infer real mental health state, or make consequential decisions about people.
