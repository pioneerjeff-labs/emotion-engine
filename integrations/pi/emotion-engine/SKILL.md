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
<skill-directory>/scripts/pi_emotion.sh record_policy --mode light --subject task --event-type work_checkpoint --memory-owner project "that migration was handled well"
<skill-directory>/scripts/pi_emotion.sh configure --style "warm but not over-compliant, with clear boundaries"
<skill-directory>/scripts/pi_emotion.sh tune "make it calmer"
```

Do not assume the current working directory is the skill directory. Resolve the wrapper from the loaded `SKILL.md` path.

The wrapper initializes an unbound v3 packet if missing. Bind it once before emotional mutation:

```bash
<skill-directory>/scripts/pi_emotion.sh bind_identity --character-id <character-id> --relationship-id <relationship-id>
```

Treat v2 as read-only; preview `migrate_state` with explicit owner ids before `--apply`. State path priority:

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

Emotion Engine is a modulation layer with an identity binding guard, not a factual-memory layer or persona definition. Do not edit durable memory just because PAD changes.

Use `record_policy` before deciding whether to persist a turn:

```bash
<skill-directory>/scripts/pi_emotion.sh record_policy --mode light --subject task --event-type work_checkpoint --memory-owner project "the user approved the completed migration"
```

The command is deterministic and side-effect free. It returns `respond_only`, `route_host_memory`, `state_only`, or `record_emotion`. Host approval is a hard gate; keywords cannot override structured ownership.

Mode contract:

- `light`: event-triggered. Work progress, concrete work feedback, and stable preferences route to host memory. Only host-approved relationship/self events may affect Emotion Engine.
- `always`: per-meaningful-turn tracking. Compact turn records are allowed more often, but habituation, salience, low-value duplicate compaction, and trust-settlement rules still apply.
- `paused`: preserve local state but do not record lifecycle updates or modulate replies.

`always` does not mean every neutral task turn belongs in `emotion_log`. Ordinary neutral turns and low-value in-session drift should usually affect only current state/reply. Emotion Engine owns retention policy and compact continuity signals; Pi or another host owns factual memory routing.

## Session Flow

At the start of a new meaningful conversation or session:

```bash
<skill-directory>/scripts/pi_emotion.sh session_start --session-id <native-session-id> --event-id <unique-start-event-id> --character-id <character-id> --relationship-id <relationship-id>
```

Before responding to each user message:

```bash
<skill-directory>/scripts/pi_emotion.sh pre_turn_decay --session-id <native-session-id> --event-id <unique-decay-event-id> --character-id <character-id> --relationship-id <relationship-id>
<skill-directory>/scripts/pi_emotion.sh appraise "<user message>"
```

The appraisal helper is advisory. Pi must use full conversation context, project context, character profile, sarcasm/playfulness, and relationship history to decide the final emotional update.

After choosing final PAD values, record the turn:

```bash
<skill-directory>/scripts/pi_emotion.sh record_turn <P> <A> <D> --session-id <native-session-id> --event-id <unique-turn-event-id> --character-id <character-id> --relationship-id <relationship-id> --subject relationship --event-type <semantic-event-type> --host-approved --appraisal <label> --situation <short emotional memory>
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
  --salience 0.65 \
  --session-id <native-session-id> --event-id <unique-turn-event-id> --character-id <character-id> --relationship-id <relationship-id> \
  --subject relationship --event-type relationship_calibration --host-approved
```

At session close:

```bash
<skill-directory>/scripts/pi_emotion.sh session_end --session-id <native-session-id> --event-id <unique-end-event-id> --character-id <character-id> --relationship-id <relationship-id>
<skill-directory>/scripts/pi_emotion.sh settle_trust --session-id <native-session-id> --event-id <unique-settlement-event-id> --character-id <character-id> --relationship-id <relationship-id>
```

Lifecycle calls are idempotent. Settlement requires a closed session and explicit unconsumed evidence; praise, task completion, appraisal tags, and PAD shape are not evidence. Without evidence it returns `no_eligible_evidence` without housekeeping writes.

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

`trust_history` stays numeric and references consumed `trust_evidence` ids. `emotion_log` is compact emotional continuity, not factual or trust-evidence storage.

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
- Do not record work checkpoints or durable host preferences as emotional memory.
- Do not mutate v2 or identity-unbound state.
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
