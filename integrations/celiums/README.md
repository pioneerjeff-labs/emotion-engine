# Celiums Adapter

Bridges Emotion Engine's local `emotion-state.json` with [Celiums
Memory](https://github.com/terrizoaguimor/celiums-memory)'s server-side
limbic state and model-scoped journal.

## When to use this

Use the Celiums adapter if you already run Celiums (or want to) **and**
want Emotion Engine's continuity layer to share state with it across
sessions, agents, or hosts. Concretely:

- you want emotional state to persist on a server instead of a JSON file
- you want multiple Emotion Engine instances (different hosts, different
  clients) to converge on one continuity record per user
- you want a single audit trail (Celiums' append-only journal) for both
  the agent's emotional log and the rest of its experience

## When NOT to use this

Skip this adapter if:

- a single local `emotion-state.json` per agent is enough — that is the
  default and recommended path for most projects
- you do not want to introduce Postgres / Qdrant / Valkey dependencies
- your project is a single-user, single-host agent where Emotion Engine's
  native persistence already does the job

This adapter is opt-in. The rest of Emotion Engine has no runtime
dependency on Celiums.

## What it does

Two directions, pure functions, no I/O of its own:

| Direction | Function | Purpose |
|---|---|---|
| Emotion Engine → Celiums | `to_celiums_limbic_state(state)` | Build the payload for Celiums' `turn_after` / limbic update |
| Emotion Engine → Celiums | `to_celiums_turn_context(state)` | Build the prelude block Celiums injects into the next turn |
| Emotion Engine → Celiums | `to_celiums_journal_entries(state, agent_id)` | Convert `emotion_log[]` into `journal_write` payloads, tagged `emotion-engine` |
| Celiums → Emotion Engine | `from_celiums_limbic_state(state, limbic)` | Ingest a Celiums `limbicState` snapshot into local `emotion` field |
| Celiums → Emotion Engine | `from_celiums_journal(state, entries)` | Append Celiums journal entries (filtered to `emotion-engine`) back into local `emotion_log` |

You decide when to call them. The adapter does not own the HTTP client,
the file I/O, or the scheduling.

## Field mapping

| `emotion-engine-state/v2` | Celiums |
|---|---|
| `emotion.{pleasure,arousal,dominance}` | `limbicState.{pleasure,arousal,dominance}` (same names) |
| `personality_baseline` | No direct equivalent; Celiums baseline is implicit in modulation |
| `character_profile.{description,interpretation,traits}` | `turn_context` channels `limbic_style` and `character_traits` |
| `trust` / `trust_anchor` | Exposed via `turn_context.trust.{value,tier}` today; first-class field on `user_profiles` is in scope for a future Celiums change |
| `trust_history` | `journal_*` entries with `entry_type="trust_change"` (planned) |
| `emotion_trajectory` | Current `pad` channel snapshot; history is reconstructed via `journal_recall` |
| `emotion_log[]` | `journal_write` with `entry_type="emotion"` and tag `emotion-engine` |
| `session_patterns` | `turn_after` event payload (conflict, repair, etc.) |
| `last_interaction_iso` | Inferred from last journal entry's `written_at` |

## Minimal usage

```python
from scripts.emotion_engine_utils import load_state, save_state, record_turn
from integrations.celiums.emotion_engine_celiums import (
    to_celiums_limbic_state,
    to_celiums_journal_entries,
    from_celiums_limbic_state,
)

state = load_state("emotion-state.json")

# After the LLM has chosen the final PAD update:
record_turn(state, 0.18, 0.32, 0.61,
            appraisal="collaboration",
            situation="user challenged the design constructively",
            meaning="disagreement feels safe and productive",
            follow_up="be precise, warm, clearly bounded",
            salience=0.65)

# Push to Celiums (you bring your own HTTP client):
limbic_payload = to_celiums_limbic_state(state)
journal_payloads = to_celiums_journal_entries(state, agent_id="my-agent")
# requests.post("https://memory.celiums.ai/v1/limbic/update",
#               json=limbic_payload, headers={"Authorization": f"Bearer {KEY}"})
# for p in journal_payloads:
#     requests.post("https://memory.celiums.ai/v1/journal/write",
#                   json=p, headers={"Authorization": f"Bearer {KEY}"})

save_state("emotion-state.json", state)
```

To pull back from Celiums (e.g. at session start, in case another host
updated state):

```python
# limbic = requests.get(".../v1/limbic/state").json()
# journal = requests.get(".../v1/journal/recall?agent_id=my-agent").json()
state = from_celiums_limbic_state(state, limbic)
state = from_celiums_journal(state, journal)
```

## What this adapter does NOT do

- It does not provide an HTTP client. Bring your own (`httpx`, `requests`,
  `urllib`).
- It does not handle authentication or token refresh.
- It does not adapt Celiums' long-term memory (`remember`/`recall`/`forage`).
  That layer is outside Emotion Engine's scope and stays in Celiums.
- It does not import anything from Celiums. The Celiums side is contacted
  through whatever client you wire up; the adapter only shapes payloads.

## Protocol spec (in progress)

A backend-independent JSON schema for emotional-continuity state is being
discussed [in this thread](https://github.com/terrizoaguimor/celiums-memory/discussions/45).
The goal is that any backend (Emotion Engine local file, Celiums server,
Redis, SQLite, etc.) can implement the same contract. This adapter is the
first concrete bridge while that spec stabilises.
