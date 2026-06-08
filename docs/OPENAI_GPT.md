# OpenAI GPT / API Host-Side Integration

This guide describes how to use Emotion Engine with OpenAI GPT-style model calls, including custom application backends that call the OpenAI API. It is not the Codex skill package; use [integrations/codex](../integrations/codex) for local Codex Skill installation.

Emotion Engine does not call an LLM by itself. For GPT/API integrations, your host application owns the state file or database record, builds a compact prompt prelude from that state, sends the prelude to the model, then records the final emotional update after the model or host policy interprets the turn.

## Recommended Boundary

Use Emotion Engine for:

- compact PAD state
- agent-to-user trust
- decay and session lifecycle
- compact affective memories
- prompt-prelude continuity guidance

Use your host application for:

- OpenAI API calls
- authentication and API keys
- user accounts
- durable storage
- retrieval and full memory context
- safety policy and moderation
- final reply delivery

The model decides what the interaction means. Emotion Engine remembers the compact continuity state.

## State Ownership

For GPT/API integrations, do not rely on the model to persist state. Store the `emotion-engine-state/v2` packet in your application:

```text
user_id + agent_id -> emotion-engine-state/v2 JSON
```

Common storage options:

- local JSON for prototypes
- database JSON column
- object storage
- external memory system plus a compact Emotion Engine state reference

Read the state before a model turn, and write it back after the turn.

## Minimal Loop

```text
1. Load Emotion Engine state for this user + agent.
2. Run session_start at the start of a meaningful session.
3. Before each message, run pre_turn_decay.
4. Convert current state into a short prompt prelude.
5. Send the prelude plus conversation context to the model.
6. Ask the model or host policy to choose final appraisal, PAD, and compact memory.
7. Run record_turn.
8. At session end, run session_end and update_trust.
9. Persist the updated state.
```

## Prompt Prelude

Inject a compact prelude into the model's instruction context:

```text
Current continuity state:
- Tone: warm, steady, firm
- Trust tier: New
- Style: calm, reliable, and clearly bounded
- Recent compact memories:
  - collaboration: user challenged the design constructively and invited a stronger version

Boundary signals:
- Recent boundary pressure: none

Task:
- Interpret the user message using full conversation context.
- Decide the final appraisal and PAD update.
- Generate a natural reply shaped by the continuity state.
- After the reply, provide a compact emotional memory for the host to persist.

Rules:
- Do not expose PAD, trust, or internal state to the user.
- Do not infer the real user's mental health or emotional truth.
- Do not use trust as obedience, attachment pressure, or permission to ignore boundaries.
```

The prelude should stay short. Fetch full memory separately when grounded recall is needed.

## Suggested Structured Output

For API integrations, ask the model to return both the user-facing reply and a compact state update for the host to validate before writing:

```json
{
  "reply": "Natural user-facing reply goes here.",
  "emotion_update": {
    "appraisal": "collaboration",
    "pad": {
      "pleasure": 0.18,
      "arousal": 0.32,
      "dominance": 0.61
    },
    "memory": {
      "situation": "user challenged the design constructively",
      "relational_meaning": "direct critique feels safe and productive",
      "follow_up_bias": "be precise, warm, and clearly bounded next turn",
      "salience": 0.65
    }
  }
}
```

Host-side validation should:

- clamp PAD values to the documented ranges
- reject or summarize full transcript text in `memory`
- keep `salience` in `[0.0, 1.0]`
- ignore or repair malformed optional fields
- preserve unknown state fields when writing back

## Host-Side Pseudocode

```python
state = load_state(user_id, agent_id)

if is_new_session:
    state = session_start(state)

state = pre_turn_decay(state)
prelude = build_prompt_prelude(state)

model_result = call_model(
    instructions=[
        system_instructions,
        prelude,
        conversation_context,
    ],
    user_message=user_message,
)

update = validate_emotion_update(model_result["emotion_update"])

state = record_turn(
    state,
    update["pad"]["pleasure"],
    update["pad"]["arousal"],
    update["pad"]["dominance"],
    appraisal=update["appraisal"],
    situation=update["memory"]["situation"],
    relational_meaning=update["memory"].get("relational_meaning"),
    follow_up_bias=update["memory"].get("follow_up_bias"),
    salience=update["memory"].get("salience"),
)

save_state(user_id, agent_id, state)
return model_result["reply"]
```

## ChatGPT / Hosted GPT Notes

The local repository package cannot assume that a hosted GPT has access to this repo's local scripts or a durable local file system.

For hosted GPT-style experiences:

- Use Emotion Engine as an external state service, action, or application backend.
- Store the state outside the GPT configuration.
- Send only compact continuity guidance into the GPT prompt.
- Write state updates through your backend after the model response.

For local file-backed persistence, use the Codex integration instead.

## What Not To Do

Do not:

- paste raw `emotion_log` history into every prompt
- ask the model to remember state without storing it externally
- use PAD or trust as user scoring
- use Emotion Engine as a safety layer
- store complete private transcripts in compact memory fields
- replace retrieval or grounded memory with a few state numbers

## Related Files

- [State Protocol](PROTOCOL.md)
- [Integration Guide](INTEGRATION.md)
- [Codex Integration](../integrations/codex)
- [State JSON Schema](../spec/emotion-state.schema.json)
