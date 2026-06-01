# Emotion Engine State Protocol

Status: draft for `emotion-engine-state/v2`

Emotion Engine is a compact emotional-continuity state layer for LLM-powered agents. This document describes the state packet shape and integration contract so adapters can read, write, and map Emotion Engine state without reverse-engineering the helper script.

This is not a memory stack, retrieval system, vector database, graph memory, chatbot runtime, safety filter, or psychological assessment tool.

## Design Boundary

Emotion Engine keeps a small, inspectable continuity packet:

- current PAD emotion state
- personality baseline for decay
- trust and trust history
- compact emotion log
- per-session trajectory and patterns
- advisory boundary signals

The LLM remains responsible for contextual judgment. The helper persists state, clamps numeric ranges, applies decay, records compact memories, and extracts simple session patterns.

In short:

```text
The LLM decides.
Emotion Engine remembers.
```

## State And Explanation Invariant

Emotion Engine separates compact numeric state from the explanation for that state.

- `emotion` is the current PAD state.
- `emotion_trajectory` is the current-session PAD numeric trajectory.
- `trust` is the current agent-to-user trust coefficient.
- `trust_history` is a numeric ledger for applied trust changes.
- `emotion_log` is the explanation layer for both PAD and trust changes.

Do not move semantic reasons into `trust_history`. If trust changes because of repair, collaboration, hostility, boundary pressure, or any other relational evidence, keep that reason in the surrounding `emotion_log` entries and session patterns. `trust_history` should record only the applied numeric effect: `old`, `new`, `raw_delta`, and `effective_delta`.

Similarly, do not treat PAD numbers as self-explanatory. The reason a PAD state changed belongs in `emotion_log` through fields such as `situation`, `appraisal`, `relational_meaning`, `impact`, `before`, `after`, `delta`, `tags`, and optional `source_refs`.

Cryptographic auditability, hash chains, signed anchors, or tamper-evident provenance are backend-level guarantees. They can be provided by host systems or optional adapters, but they are not required by the core Emotion Engine state packet.

## Compatibility Rules

Readers and writers should follow these rules:

- Treat `_schema: "emotion-engine-state/v2"` as the current packet identifier.
- Use [`spec/emotion-state.schema.json`](../spec/emotion-state.schema.json) as the machine-readable schema for state packets and adapter envelopes.
- Ignore unknown top-level fields so optional extensions can be added safely.
- Treat missing known fields as defaultable. The Python helper fills missing fields through `ensure_state_shape`.
- Do not store full private transcripts in `emotion_log`.
- Do not treat deterministic `appraise` output as final emotional truth.
- Do not use trust or emotion values for consequential decisions about real people.

## Versioning

The current state packet version is:

```text
emotion-engine-state/v2
```

The state packet version is separate from helper script versions and package versions. Patch-level helper changes may add optional fields, improve normalization, or refine prompt wording without changing the state version.

Change the state packet version only when a reader or writer can no longer safely interpret the packet by ignoring unknown fields and filling documented defaults. Adapter envelopes currently use their own identifiers:

| Envelope | Current identifier |
|---|---|
| State packet | `emotion-engine-state/v2` |
| Adapter event input | `emotion-engine-adapter-event/v1` |
| Adapter output | `emotion-engine-adapter-output/v1` |

Adapters should preserve unknown fields when possible, and should include their own source or provenance fields for host-specific extensions.

## Canonical Packet

A minimal v2 packet looks like this:

```json
{
  "_schema": "emotion-engine-state/v2",
  "enabled": true,
  "emotion": {
    "pleasure": 0.0,
    "arousal": 0.3,
    "dominance": 0.5
  },
  "personality_baseline": {
    "pleasure": 0.0,
    "arousal": 0.3,
    "dominance": 0.5
  },
  "character_profile": {
    "source": "default",
    "description": "warm, steady, lightly bounded",
    "interpretation": "Warm enough to feel present, calm enough to stay stable, and balanced enough to avoid over-compliance.",
    "traits": ["warm", "steady", "balanced"]
  },
  "trust": 0.1,
  "trust_anchor": 0.1,
  "session_count": 0,
  "total_turns": 0,
  "last_interaction_iso": null,
  "emotion_trajectory": [],
  "emotion_log": [],
  "trust_history": [],
  "log_limit": 200
}
```

## Field Reference

### `_schema`

String schema identifier.

Current value:

```text
emotion-engine-state/v2
```

Adapters should not assume that every compatible packet has only the fields listed here. Unknown fields should be preserved when possible.

### `enabled`

Boolean switch for lifecycle updates.

When `enabled` is `false`, helper operations preserve the state but skip emotion lifecycle updates. This is for user control, debugging, or temporarily disabling continuity.

### `emotion`

Current PAD state.

| Field | Range | Meaning |
|---|---:|---|
| `pleasure` | `[-1.0, 1.0]` | Negative to positive valence. |
| `arousal` | `[0.0, 1.0]` | Calm to energized or tense. |
| `dominance` | `[0.0, 1.0]` | Soft or uncertain to firm and bounded. |

Notes:

- `arousal` is intensity, not automatically distress.
- `dominance` is boundedness or firmness, not control over the user.
- Values are clamped and rounded to 4 decimal places by the helper.

Short-form PAD keys are used in trajectory entries and command arguments:

| Short | Long |
|---|---|
| `P` | `pleasure` |
| `A` | `arousal` |
| `D` | `dominance` |

### `personality_baseline`

The PAD state that the agent naturally drifts toward over time.

This is not the same as the current emotion. It is a stable attractor used by time decay and in-session drift.

### `character_profile`

Human-readable style metadata derived from onboarding text, a style string, or a host runtime.

Current fields:

| Field | Meaning |
|---|---|
| `source` | Where the profile came from, such as `default`, `style`, or `soul-file`. |
| `description` | Original or compact style description. |
| `interpretation` | Helper-generated style summary for prompt guidance. |
| `traits` | Small list of inferred trait labels. |

Adapters may add host-specific profile fields, but should keep the profile compact.

### `trust`

Slow-moving agent-to-user relationship continuity coefficient.

Range:

```text
[0.05, 1.0]
```

Default:

```text
0.1
```

Trust is directional, but v1 only models one direction: agent-to-user. It is the agent or persona's internal estimate of whether this user has been cooperative, boundary-respecting, predictable, and safe enough for deeper persona continuity.

It does not infer the user's trust in the agent. Trust is separate from PAD emotion. It can affect decay and modulation, but it should not mean obedience, dependency, user value, user score, attachment pressure, safety permission, or permission to ignore boundaries.

Trust tiers used by `status`:

| Range | Tier |
|---:|---|
| `< 0.2` | `New` |
| `< 0.4` | `Acquaintance` |
| `< 0.6` | `Familiar` |
| `< 0.8` | `Close` |
| `>= 0.8` | `Intimate` |

Tier names are descriptive prompt guidance, not claims about a real relationship.

### `trust_anchor`

Highest agent-to-user trust level reached by the relationship, clamped to `[0.05, 1.0]`.

The helper uses this as a floor reference during time-based trust decay. It should be greater than or equal to `trust`.

### `session_count`

Number of sessions started through `session_start`.

### `total_turns`

Total number of recorded turns across sessions.

### `last_interaction_iso`

ISO timestamp for the last stateful interaction.

The Python helper writes timezone-aware UTC timestamps such as:

```text
2026-05-29T15:20:00.000000+00:00
```

Adapters should accept either `Z` or explicit UTC offsets when reading.

### `emotion_trajectory`

Current-session PAD trajectory.

Each `record_turn` appends a compact entry:

```json
{
  "turn": 1,
  "P": 0.18,
  "A": 0.32,
  "D": 0.61,
  "timestamp": "2026-05-29T15:20:00.000000+00:00",
  "appraisal": "collaboration",
  "situation": "user challenged the design in a constructive way"
}
```

`session_start` clears this list for the new session. Long-term compact memory belongs in `emotion_log`, not in `emotion_trajectory`.

### `emotion_log`

Compact affective memory log.

This is not a transcript. Entries should be short, interpretive, and useful for future tone or continuity.

Common fields:

| Field | Meaning |
|---|---|
| `timestamp` | ISO timestamp. |
| `event_type` | Event category, such as `turn`, `session_start`, `session_end`, `trust_update`, `configure`, or `time_decay`. |
| `trust` | Trust value at the time of the event. |
| `turn` | Optional current-session turn number. |
| `situation` | Compact description of what happened. |
| `character_lens` | How the agent character interpreted the event. |
| `relational_meaning` | What the event meant for the interaction. |
| `impact` | Short effect description. |
| `open_loop` | Boolean for unresolved emotional residue. |
| `follow_up_bias` | Suggested bias for future replies. |
| `salience` | `[0.0, 1.0]` importance score. |
| `appraisal` | Label such as `collaboration`, `repair`, or `boundary_pressure`. |
| `before` / `after` | Optional compact PAD snapshots with `P/A/D`. |
| `delta` | Optional PAD delta. |
| `tags` | Small list of labels for pattern extraction or filtering. |

Example:

```json
{
  "timestamp": "2026-05-29T15:20:00.000000+00:00",
  "event_type": "turn",
  "trust": 0.12,
  "turn": 2,
  "situation": "user challenged the design in a constructive way",
  "appraisal": "collaboration",
  "relational_meaning": "direct critique feels safe and productive",
  "follow_up_bias": "be precise, warm, and clearly bounded next turn",
  "salience": 0.65,
  "tags": ["collaboration"]
}
```

Good memory:

```text
user challenged the design constructively and invited a stronger version
```

Bad memory:

```text
full copied user message with private details
```

### `trust_history`

Compact history of applied trust changes.

Example:

```json
{
  "timestamp": "2026-05-29T15:24:00.000000+00:00",
  "old": 0.1,
  "new": 0.118,
  "raw_delta": 0.02,
  "effective_delta": 0.018
}
```

Positive deltas have diminishing returns as trust rises. Negative deltas can be softened when trust is already high, but major negative deltas still matter.

`trust_history` is intentionally not the explanation layer. It should stay a compact numeric ledger. The reason for a trust change should be recorded in `emotion_log`, usually through the preceding turn entries, `session_end` patterns, or a compact `trust_update` log entry that points back to the relevant relationship evidence.

### `log_limit`

Maximum retained `emotion_log` entries. Default is `200`, with a minimum of `25` enforced by the helper.

## Appraisal Labels

The deterministic helper currently recognizes these labels:

| Label | Meaning |
|---|---|
| `warmth` | Warmth or appreciation. |
| `repair` | Repair attempt or apology. |
| `collaboration` | Collaborative request or constructive challenge. |
| `vulnerability` | User vulnerability or distress. |
| `boundary_pressure` | Pressure on autonomy or boundaries. |
| `hostility` | Hostility or contempt. |
| `neutral` | Neutral or unclear emotional signal. |

The helper is advisory. In a real integration, the LLM should decide the final appraisal and PAD update using the full conversation context.

## Lifecycle Contract

A typical integration loop:

```text
load state
session_start
for each user message:
  pre_turn_decay
  build prompt prelude from current state
  optionally call appraise for advisory signal
  ask the LLM to interpret context and generate the reply
  ask the LLM or host policy to choose final PAD/appraisal/memory
  record_turn
session_end
choose trust delta from patterns plus LLM/session interpretation
update_trust
save state
```

The helper can perform the persistence steps through CLI commands:

```bash
python3 scripts/emotion_engine_utils.py init emotion-state.json
python3 scripts/emotion_engine_utils.py validate emotion-state.json
python3 scripts/emotion_engine_utils.py configure emotion-state.json --style "calm, reliable, and clearly bounded"
python3 scripts/emotion_engine_utils.py session_start emotion-state.json
python3 scripts/emotion_engine_utils.py pre_turn_decay emotion-state.json
python3 scripts/emotion_engine_utils.py appraise emotion-state.json "I want to challenge one part of the design."
python3 scripts/emotion_engine_utils.py record_turn emotion-state.json 0.18 0.32 0.61 \
  --appraisal collaboration \
  --situation user challenged the design in a constructive way \
  --meaning disagreement feels safe and productive \
  --follow-up be precise, warm, and clearly bounded \
  --salience 0.65
python3 scripts/emotion_engine_utils.py session_end emotion-state.json
python3 scripts/emotion_engine_utils.py update_trust emotion-state.json 0.02
```

## Adapter Event Contract

Host runtimes may map their own event stream into a small adapter envelope before updating Emotion Engine. The schema definition is exposed as `$defs.adapterEvent` in [`spec/emotion-state.schema.json`](../spec/emotion-state.schema.json).

The adapter event envelope is intentionally host-neutral:

```json
{
  "_schema": "emotion-engine-adapter-event/v1",
  "source": "celiums-memory",
  "event_type": "turn_after",
  "occurred_at": "2026-05-29T15:20:00.000000+00:00",
  "session_id": "session_123",
  "turn_id": "turn_456",
  "limbicState": {
    "pleasure": 0.18,
    "arousal": 0.32,
    "dominance": 0.61
  },
  "appraisal": "collaboration",
  "compact_memory": {
    "timestamp": "2026-05-29T15:20:00.000000+00:00",
    "event_type": "turn",
    "situation": "user challenged the design constructively",
    "relational_meaning": "direct critique feels safe and productive",
    "follow_up_bias": "be precise, warm, and clearly bounded",
    "salience": 0.65,
    "tags": ["collaboration"]
  },
  "source_refs": [
    {
      "type": "celiums_journal_id",
      "value": "journal_789"
    }
  ]
}
```

Recommended event types:

| Event type | Adapter behavior |
|---|---|
| `session_start` | Run Emotion Engine session start / time decay before the host turn loop. |
| `turn_after` | Map final host PAD or `limbicState` into `record_turn`; append compact memory only after the host/LLM finalizes the turn meaning. |
| `journal_append` | Append a compact `emotion_log` entry that points to the host journal via `source_refs`. |
| `session_end` | Extract patterns and optionally prepare a trust update. |
| `trust_update` | Apply a small trust delta chosen by host policy plus session interpretation. |
| `boundary_update` | Preserve or update optional `boundary_state` without turning Emotion Engine into a policy engine. |

Event input rules:

- Prefer final host interpretation over deterministic `appraise` output.
- Provide PAD as either long-form fields or compact `P/A/D` under `limbicState`, `limbic_state`, or `pad`.
- Put grounded details in the host memory or journal; put only compact affective summaries in `compact_memory`.
- Use `source_refs` to point back to external records instead of copying private text into Emotion Engine.
- Keep `trust_delta` small and slow-moving; do not update trust as a direct reward or punishment signal.

## Adapter Output Contract

After processing an adapter event, return a compact output envelope to the host runtime. The schema definition is exposed as `$defs.adapterOutput`.

Example:

```json
{
  "_schema": "emotion-engine-adapter-output/v1",
  "state_schema": "emotion-engine-state/v2",
  "state_patch": {
    "emotion": {
      "pleasure": 0.18,
      "arousal": 0.32,
      "dominance": 0.61
    },
    "trust": 0.12
  },
  "snapshot": {
    "tone": "warm, steady, balanced",
    "emotion": {
      "pleasure": 0.18,
      "arousal": 0.32,
      "dominance": 0.61
    },
    "trust": 0.12,
    "trust_tier": "New",
    "recent_memories": []
  },
  "prompt_prelude": "Current continuity state: ...",
  "journal_suggestion": {
    "timestamp": "2026-05-29T15:20:00.000000+00:00",
    "event_type": "turn",
    "situation": "user challenged the design constructively",
    "appraisal": "collaboration"
  }
}
```

The host may store the `snapshot`, write the `journal_suggestion`, or inject the `prompt_prelude` into turn context. The host remains responsible for long-term memory, retrieval, policy, and user-facing behavior.

## Celiums Memory Adapter Boundary

Celiums Memory already owns memory, journal, retrieval, ethics, `limbicState` / PAD, and turn context. A Celiums adapter should therefore be a thin bridge, not a replacement memory stack.

Recommended mapping:

| Celiums concept | Emotion Engine concept |
|---|---|
| `limbicState` PAD | `state.emotion` and `emotion_trajectory` PAD |
| Journal compact entry | `emotion_log` entry with `source_refs` back to Celiums |
| `turn_after` event | Adapter `turn_after` event, usually followed by `record_turn` |
| Celiums retrieval | External context fetched before prompt construction, not copied into Emotion Engine |
| Celiums ethics/policy | Host responsibility; Emotion Engine only emits advisory boundary signals |
| Celiums turn context | Consumer of Emotion Engine compact snapshot / prompt prelude |
| Celiums trust extension | Only map agent-to-user trust; do not map user-to-agent trust into Emotion Engine v1 |

Adapter non-goals:

- Do not replace Celiums memory, journal, retrieval, ethics, or turn context.
- Do not rewrite Celiums' existing emotion system.
- Do not infer clinical or real-user emotion from Celiums events.
- Do not store raw Celiums transcripts in `emotion_log`.
- Do not make trust or `boundary_state` drive consequential decisions.
- Do not treat Emotion Engine trust as mutual trust or as the user's trust in the agent.

## Prompt Prelude Contract

Adapters should convert the packet into a short prompt prelude. Avoid dumping raw JSON into the prompt unless the host model is expected to use structured fields directly.

Example:

```text
Current continuity state:
- Tone: warm, steady, firm
- Trust tier: New
- Style: mildly warm; calm; strongly bounded
- Recent compact memories:
  - collaboration: user challenged the design constructively and invited a stronger version

Boundary signals:
- Recent boundary pressure: none
- Standing boundary state: not provided in v2

LLM task:
- Interpret the user message using full conversation context.
- Decide the final appraisal and PAD update.
- Generate a natural reply shaped by the current continuity state.
- After responding, record a compact emotional memory without storing the full transcript.
```

The exact prose can vary by host runtime. The contract is that the LLM receives:

- current tone guidance from PAD
- trust tier or compact trust guidance
- compact recent memories
- advisory appraisal when available
- clear instruction that it must make the final contextual judgment

## External Memory Systems

Emotion Engine can sit beside full memory systems.

Use a full memory system for:

- factual recall
- semantic search
- graph memory
- audit trails
- complete event context
- user facts and durable knowledge

Use Emotion Engine for:

- compact relationship-state continuity
- prompt-prelude tone guidance
- stateful emotional inertia
- slow trust changes
- short affective memories

Do not compress full experiential memory into a few PAD or trust values when the agent needs grounded recall. In that case, retrieve lived context first and use Emotion Engine only as optional continuity guidance.

## Optional `source_refs`

Adapters that bridge to external memory systems may attach `source_refs` to `emotion_log` entries.

This is a recommended extension, not a field emitted by the current CLI.

Example:

```json
{
  "event_type": "turn",
  "situation": "user challenged the design constructively",
  "appraisal": "collaboration",
  "source_refs": [
    {
      "type": "memory_uri",
      "value": "core://project/design-review/turn-12"
    },
    {
      "type": "celiums_memory_id",
      "value": "mem_123"
    }
  ]
}
```

Rules:

- `source_refs` should point to external memory records, not duplicate them.
- References should be safe to ignore.
- Avoid placing private transcript text in `value`.
- If a referenced memory is deleted, the compact Emotion Engine entry should remain meaningful on its own.

## Boundary Signals And `boundary_state`

In `emotion-engine-state/v2`, boundary is represented indirectly through:

- PAD `dominance`
- `boundary_pressure` appraisal
- `boundary` tags in `emotion_log`
- `recent_boundary_events` in extracted session patterns
- profile descriptions such as "clearly bounded"

This is enough for advisory prompt guidance, but it is not a policy model. Adapters may also preserve an optional top-level `boundary_state` extension:

```json
{
  "boundary_state": {
    "status": "watch",
    "firmness": 0.7,
    "recent_pressure": 0.3,
    "standing_boundaries": [
      {
        "label": "do not over-comply with pressure to skip review",
        "status": "active",
        "source": "host_policy"
      }
    ],
    "last_updated_iso": "2026-05-29T15:20:00.000000+00:00",
    "provenance": "celiums-memory"
  }
}
```

Recommended `boundary_state.status` values:

| Status | Meaning |
|---|---|
| `unknown` | No stable boundary context is available. |
| `clear` | Boundaries are stable and not currently pressured. |
| `watch` | Mild pressure or ambiguity exists; keep responses more explicitly bounded. |
| `strained` | Repeated pressure or unresolved tension exists. |
| `repairing` | A prior boundary issue is being repaired or clarified. |

`firmness` and `recent_pressure` are prompt-guidance signals in `[0.0, 1.0]`. They are not safety policy decisions, user classifications, or permission systems.

Adapters should say "boundary signals" rather than "boundaries" when describing the v2 packet, unless their host runtime owns a real boundary or policy model outside Emotion Engine.

## Deterministic Helper Responsibilities

The Python helper may:

- normalize missing fields
- clamp PAD and trust ranges
- apply time decay
- apply in-session drift
- generate advisory appraisals
- record compact emotion memories
- extract simple session patterns
- apply trust deltas
- print user-friendly status summaries

The helper should not be treated as:

- the final emotional interpreter
- the assistant reply generator
- a user emotion detector
- a safety policy engine
- a replacement for long-term memory retrieval

## Writer Checklist

When writing state:

- Preserve unknown fields where possible.
- Clamp PAD and trust values to their documented ranges.
- Keep `emotion_log` entries compact.
- Store timestamps with timezone information.
- Use `session_start` to begin a session and clear `emotion_trajectory`.
- Use `record_turn` only after the final appraisal and PAD values are chosen.
- Update trust slowly, usually at session boundaries.
- Keep trust separate from obedience, affection, compliance, or entitlement.

## Reader Checklist

When reading state:

- Ignore unknown fields.
- Treat missing arrays as empty.
- Treat missing profile metadata as defaultable.
- Convert PAD into prose guidance before prompting the LLM.
- Treat deterministic appraisal as a hint.
- Fetch external memory separately when grounded context is needed.

## Privacy And Safety

Emotion Engine models fictional or agent-internal emotional continuity. It does not infer, verify, diagnose, or assess a real person's emotional or mental state.

Do not use this state packet to:

- manipulate attachment
- punish absence
- pressure users into engagement
- infer mental health status
- make consequential decisions about people
- replace consent, policy, or safety systems

The packet should remain inspectable, compact, and user-controllable.
