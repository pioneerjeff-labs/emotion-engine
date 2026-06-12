# Minimal Agent Example

This is the 5-minute developer path for wiring Emotion Engine into an agent loop.
It is not another UI demo, and it does not call a real LLM.

Run it from the repository root:

```bash
python3 examples/minimal-agent/run_demo.py
```

The script writes the final state to:

```text
examples/minimal-agent/out/emotion-state.json
```

The `out/` directory is generated output and should not be committed.

## What This Shows

`run_demo.py` demonstrates the smallest useful loop:

```text
load state
-> session_start
-> pre_turn_decay
-> build prompt prelude
-> advisory appraise
-> mock LLM final decision
-> record_turn
-> settle_trust
-> save final state
```

The important boundary is that Emotion Engine does not generate the assistant
reply. A real application still owns:

- the LLM call
- retrieval and memory context
- policy and permission checks
- the final assistant response
- the final appraisal and PAD choice
- which compact emotional memory should be recorded

The deterministic `appraise` helper is only a hint. In production, your LLM or
agent runtime should use full context to choose the final appraisal and PAD
values, then call `record_turn`.

## Files

- `run_demo.py` is the minimal reference loop.
- `turns.json` contains two scripted turns: one collaborative/warm turn and one boundary-pressure turn.
- `out/emotion-state.json` is created when you run the example.

If you use Codex, Claude Code, or another coding agent, you can point it at this
example and ask it to adapt the loop into your app.

## Adaptation Points

Replace the mock section with your own agent runtime:

1. Build a prompt prelude from `engine.public_status(state)` and recent compact memories.
2. Call your LLM with your normal system prompt, retrieval context, policy layer, and user message.
3. Ask the LLM or host policy to return the final appraisal and PAD values.
4. Pass those values to `engine.record_turn(...)`.
5. At session end, call `engine.settle_trust(...)` to extract patterns and apply one conservative, idempotent trust settlement for the current trajectory.
