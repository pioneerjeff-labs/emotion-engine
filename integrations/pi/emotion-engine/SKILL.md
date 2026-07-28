---
name: emotion-engine
description: Add lightweight emotional continuity to Pi Agent workflows using PAD mood, affective pulse, agent-to-user trust, decay, and compact emotional memories. Use for long-running assistants, fictional characters, companion demos, or relationship-state tests.
license: MIT
compatibility: Requires Python 3.9+ and local filesystem access.
---

# Emotion Engine For Pi Agent

Use this skill when the user wants Pi to maintain lightweight emotional continuity across local projects, fictional character tests, companion-style demos, or long-running personal assistant workflows.

Emotion Engine is not a chatbot and does not generate replies by itself. Pi still interprets the situation, decides the final emotional meaning, and writes the reply. Emotion Engine persists continuity: PAD mood, short-lived affective pulse, agent-to-user trust, decay, compact emotional memories, and session patterns.

Trust is agent-to-user only: it is the agent/persona's internal continuity estimate of whether this user has been cooperative, boundary-respecting, predictable, and safe enough for deeper persona continuity. It does not infer the user's trust in Pi or in the agent.

## Resolve The Wrapper

Pi loads this file with its absolute path. Treat the directory containing this `SKILL.md` as `<skill-directory>` and use:

```bash
<skill-directory>/scripts/pi_emotion.sh status
<skill-directory>/scripts/pi_emotion.sh audit_log
<skill-directory>/scripts/pi_emotion.sh compact_log --dry-run
<skill-directory>/scripts/pi_emotion.sh record_policy --mode light --context milestone "that migration was handled well"
<skill-directory>/scripts/pi_emotion.sh configure --style "warm but not over-compliant, with clear boundaries"
<skill-directory>/scripts/pi_emotion.sh tune "make it calmer"
```

Do not assume the current working directory is the skill directory. Resolve the wrapper from the loaded `SKILL.md` path.

The wrapper automatically initializes a state file if missing. State path priority:

1. `PI_EMOTION_STATE` environment variable
2. `PI_PROJECT_DIR/.emotion-engine/pi-state.json`
3. nearest current/ancestor project with `.git` or `.pi`: `<project-root>/.emotion-engine/pi-state.json`
4. personal fallback: `~/.pi/agent/emotion-engine/emotion-state.json`

Use `status` for user-facing summaries and `status --raw` only for debugging.

## When To Use

Use this skill when the user asks for:

- emotional continuity
- persistent character mood
- agent-to-user relationship/trust memory
- SOUL.md-based character configuration
- a more consistent project-local assistant tone
- Emotion Engine status, tuning, pause, or resume
- no-state vs relationship-state comparisons

Do not use this as a mental health inference tool or a way to assess the real user's emotional state.

## Chat Controls

Map natural-language user requests to wrapper commands:

- "Set the style to warm but not over-compliant" -> `configure --style "warm but not over-compliant"`
- "Configure it from this SOUL.md" -> `configure --soul-file ./SOUL.md`
- "Make it gentler" / "make it calmer" / "make it less compliant" -> `tune "<request>"`
- "What is the current status?" -> `status`
- "Audit emotion logging" -> `audit_log`
- "Preview emotion log compaction" -> `compact_log --dry-run`
- "Pause emotion logging" -> `pause`
- "Resume Emotion Engine" -> `resume`

Only run `clear_log` or `reset` after the user explicitly asks. They erase local emotional history.

## Runtime Modes And Record Policy

Emotion Engine state is a modulation layer, not an identity or factual-memory layer. Do not edit `AGENTS.md`, durable memory, or project documentation just because PAD changes. Use compact state only as temporary turn context.

Use `record_policy` before deciding whether to persist a turn:

```bash
<skill-directory>/scripts/pi_emotion.sh record_policy --mode light --context milestone "the user approved the completed migration"
```

The command is deterministic and side-effect free. It returns a JSON decision such as `record_turn` or `respond_only`, plus `reason`, `appraisal`, `salience`, `trust_eligible`, and structured `reply_bias`. It does not call an LLM and does not write state.

Mode contract:

- `light`: event-triggered. Generic praise, small talk, and ordinary task progress should usually be `respond_only`; concrete feedback, milestones, repair, stable preferences, boundary pressure, or explicit emotional-continuity discussion may be recorded.
- `always`: per-meaningful-turn tracking. Compact turn records are allowed more often, but habituation, salience, low-value duplicate compaction, and trust-settlement rules still apply.
- `paused`: preserve local state but do not record lifecycle updates or modulate replies.

`always` does not mean every neutral task turn belongs in `emotion_log`. Ordinary neutral turns and low-value in-session drift should usually affect only current state/reply. Emotion Engine owns retention policy and compact continuity signals; Pi or another host owns factual memory routing.

## Session Flow

At the start of a new meaningful conversation or session:

```bash
<skill-directory>/scripts/pi_emotion.sh session_start
```

Before responding to each user message:

```bash
<skill-directory>/scripts/pi_emotion.sh pre_turn_decay
<skill-directory>/scripts/pi_emotion.sh appraise "<user message>"
```

The appraisal helper is advisory. Pi must use full conversation context, project context, character profile, sarcasm/playfulness, and relationship history to decide the final emotional update.

After choosing final PAD values, record the turn:

```bash
<skill-directory>/scripts/pi_emotion.sh record_turn <P> <A> <D> --appraisal <label> --situation <short emotional memory>
```

For important events, add only the memory fields that help future behavior:

```bash
<skill-directory>/scripts/pi_emotion.sh record_turn <P> <A> <D> \
  --appraisal collaboration \
  --situation user challenged the design and invited a stronger version \
  --lens calm mentor treats direct critique as useful signal, not rejection \
  --meaning disagreement feels safe and productive \
  --impact pleasure rose, dominance stabilized \
  --open-loop false \
  --follow-up be more precise and structured next turn \
  --salience 0.65
```

At session or milestone close:

```bash
<skill-directory>/scripts/pi_emotion.sh settle_trust
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

For long-running agents, use `audit_log` to inspect retention pressure and `compact_log --dry-run` before applying safe low-value compaction. `compact_log --apply` writes through the normal state backup path. Do not use `clear_log` or `reset` as routine maintenance.

## Pitfalls

- Do not expose raw PAD values in normal user-facing replies.
- Do not treat the deterministic appraisal helper as the final emotional judge.
- Do not store full private transcripts in `emotion_log`; store compact emotional summaries.
- Do not use trust as obedience, sweetness, user scoring, safety permission, user-to-agent trust, or attachment pressure.
- Do not run `reset`, `clear_log`, or other destructive commands unless the user explicitly asks.

## Verification

Run:

```bash
<skill-directory>/scripts/pi_emotion.sh status
```

Expected: JSON with `enabled`, `summary`, `style`, `trust_tier`, and `log_entries`.

## Safety

Treat Emotion Engine as fictional or agent-internal continuity, not psychological truth. Do not use it to manipulate attachment, punish absence, infer real mental health state, or make consequential decisions about people.
