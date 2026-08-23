---
name: emotion-engine-codex
description: Add lightweight emotional continuity to Codex workflows using PAD state, agent-to-user trust, decay, and compact emotional memories.
---

# Emotion Engine For Codex

Use this skill when the user wants Codex to maintain lightweight emotional continuity across local projects, fictional character tests, companion-style demos, or long-running personal assistant workflows.

Emotion Engine is not a chatbot and does not generate replies by itself. Codex still interprets the situation, decides the final emotional meaning, and writes the reply. Emotion Engine persists continuity: PAD state, agent-to-user trust, decay, compact emotional memories, and session patterns.

Trust is agent-to-user only: it is the agent/persona's internal continuity estimate of whether this user has been cooperative, boundary-respecting, predictable, and safe enough for deeper persona continuity. It does not infer the user's trust in Codex or in the agent.

## Quick Reference

Use the project wrapper when Agent Harness installed one:

```bash
scripts/codex_emotion.sh status
scripts/codex_emotion.sh audit_state
scripts/codex_emotion.sh audit_log
scripts/codex_emotion.sh compact_log --dry-run
scripts/codex_emotion.sh record_policy --mode light --subject task --event-type work_checkpoint --memory-owner project "that migration was handled well"
scripts/codex_emotion.sh configure --style "warm but not over-compliant, with clear boundaries"
scripts/codex_emotion.sh tune "make it calmer"
```

If the target only has this skill folder and no project wrapper, use:

```bash
.codex/skills/emotion-engine-codex/scripts/codex_emotion.sh status
```

MCP is optional. Use it when a local MCP-capable client should expose Emotion Engine as native tools instead of shell commands. Register the bundled stdio server with the same Codex state file used by the wrapper:

```bash
python3 .codex/skills/emotion-engine-codex/scripts/emotion_engine_mcp.py --state .emotion-engine/codex-state.json
```

For local client setup, prefer the registration helper:

```bash
python3 .codex/skills/emotion-engine-codex/scripts/register_mcp_client.py codex --project-dir . --state-profile codex
```

The MCP server exposes runtime/protocol tools only. Agent Harness owns install refresh, doctor, repair, manifest checks, and sidecar drift checks.

The wrapper automatically initializes an unbound v3 state file if missing. Before the first emotional mutation, bind it explicitly:

```bash
scripts/codex_emotion.sh bind_identity --character-id <character-id> --relationship-id <relationship-id>
```

Existing v2 packets are read-only. Preview `migrate_state` first, then rerun it with `--apply`; never guess either owner id. State path priority:

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
- "Audit emotion logging" -> `scripts/codex_emotion.sh audit_log`
- "Preview emotion log compaction" -> `scripts/codex_emotion.sh compact_log --dry-run`
- "Pause emotion logging" -> `scripts/codex_emotion.sh pause`
- "Resume Emotion Engine" -> `scripts/codex_emotion.sh resume`

Only run `clear_log` or `reset` after the user explicitly asks. They erase local emotional history.

## Runtime Modes And Record Policy

Emotion Engine is a modulation layer with an identity binding guard; it does not define the persona itself. Do not edit `AGENTS.md`, `CLAUDE.md`, or durable memory just because PAD changes.

Use `record_policy` before deciding whether to persist a turn:

```bash
scripts/codex_emotion.sh record_policy --mode light \
  --subject task --event-type work_checkpoint --memory-owner project \
  "老登夸了刚完成的迁移"
```

The command is deterministic and side-effect free. It returns `respond_only`, `route_host_memory`, `state_only`, or `record_emotion`. `host_approved` is a hard gate. Keyword appraisal cannot override `subject` or semantic `event_type`.

Mode contract:

- `light`: event-triggered. Task progress, concrete work feedback, and durable preferences go to host memory. Relationship repair, calibration, boundary pressure, or explicit emotional-continuity events remain candidates until the host approves them.
- `always`: per-meaningful-turn tracking. Compact turn records are allowed more often, but habituation, salience, low-value duplicate compaction, and trust-settlement rules still apply.
- `paused`: preserve local state but do not record lifecycle updates or modulate replies.

`always` does not mean every neutral task turn belongs in `emotion_log`. Ordinary neutral turns and low-value in-session drift should usually affect only current state/reply. Emotion Engine owns retention policy and compact continuity signals; the host owns factual memory routing.

Habituation rules:

- Repeated generic praise loses weight across recent turns.
- Work milestones and stable preferences never bypass semantic ownership.
- Trust does not grow from praise, collaboration tags, or PAD patterns. Settlement consumes explicit eligible evidence only.

## Session Flow

At the start of a new meaningful conversation/session:

```bash
scripts/codex_emotion.sh session_start --session-id <native-session-id> --event-id <unique-start-event-id> --character-id <character-id> --relationship-id <relationship-id>
```

Before responding to each user message:

```bash
scripts/codex_emotion.sh pre_turn_decay --session-id <native-session-id> --event-id <unique-decay-event-id> --character-id <character-id> --relationship-id <relationship-id>
scripts/codex_emotion.sh appraise "<user message>"
```

The appraisal helper is advisory. Codex must use full context, project context, character profile, sarcasm/playfulness, and relationship history to decide the final emotional update.

After choosing final PAD values, record the turn:

```bash
scripts/codex_emotion.sh record_turn <P> <A> <D> \
  --session-id <native-session-id> --event-id <unique-turn-event-id> --character-id <character-id> --relationship-id <relationship-id> \
  --subject relationship --event-type <semantic-event-type> --host-approved \
  --appraisal <label> --situation <short emotional memory>
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
  --salience 0.65 \
  --session-id <native-session-id> --event-id <unique-turn-event-id> --character-id <character-id> --relationship-id <relationship-id> \
  --subject relationship --event-type relationship_calibration --host-approved
```

At session end:

```bash
scripts/codex_emotion.sh session_end --session-id <native-session-id> --event-id <unique-end-event-id> --character-id <character-id> --relationship-id <relationship-id>
scripts/codex_emotion.sh settle_trust --session-id <native-session-id> --event-id <unique-settlement-event-id> --character-id <character-id> --relationship-id <relationship-id>
```

Lifecycle calls are idempotent. A different session cannot replace an active one, and settlement never closes a session implicitly. `settle_trust` uses only explicit, unconsumed evidence attached to host-approved turns; without it, the command returns `no_eligible_evidence` and writes no settlement housekeeping. Use `update_trust <trust_delta>` only for an explicit host override.

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

`trust_history` stays numeric and references consumed evidence ids. The authoritative settlement inputs live in `trust_evidence`; `emotion_log` remains compact PAD/continuity explanation, not factual or trust evidence storage.

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
- Do not record task checkpoints, project progress, or durable preferences as emotional memory.
- Do not mutate a v2 or identity-unbound packet.
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
