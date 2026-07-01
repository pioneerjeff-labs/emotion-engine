# Install Emotion Engine With A Coding Agent

Use this if you are comfortable asking Codex, Claude Code, Cursor, or another coding agent to make a small local integration for you.

Emotion Engine should be installed as a local state sidecar. You describe the character or agent purpose; the host app and model decide how visible the emotional movement should be from the current event. You do not need to choose between mood and pulse as product modes.

## Copy This Prompt

```text
Install Emotion Engine into this project as a local state sidecar.
Use the minimal-agent example first.
For a generic app, keep state in .emotion-engine/emotion-state.json.
For a Codex or Agent Harness project, use .emotion-engine/codex-state.json.
Do not send state to any remote service.
Show me a prompt preview before changing my app code.
```

## What The Agent Should Do

1. Inspect this repository's [minimal-agent example](examples/minimal-agent).
2. Create or reuse the right local state file in your project.
   Use `.emotion-engine/emotion-state.json` for a generic app.
   Use `.emotion-engine/codex-state.json` for a Codex or Agent Harness target.
3. Run the local state flow before touching your app code.
4. Show the prompt prelude or preview that your LLM would receive.
5. If you register the MCP server, pass the same state path with `--state`.
6. Only then wire the state sidecar into your app's existing agent loop.

The minimal-agent example does not require an API key or live LLM call. It demonstrates the load, preview, record, trust-settle, and save cycle locally.

## State And Privacy

Keep the state file local unless you intentionally design a different persistence layer. The generic app path is:

```text
.emotion-engine/emotion-state.json
```

Codex and Agent Harness project targets use:

```text
.emotion-engine/codex-state.json
```

If you use both the shell wrapper and an MCP client, point both at the same state file. For Codex/Agent Harness targets, MCP registration should pass:

```bash
--state .emotion-engine/codex-state.json
```

Do not send the Emotion Engine state to a remote service by default. If your app later calls an LLM API, your host application decides what compact continuity guidance is included in the model prompt.

## Recommended First Style Prompt

Give your coding agent a one-sentence description of the agent you are building:

```text
This agent is calm, reliable, and concise, with clear boundaries.
```

or:

```text
This fictional character is warm and expressive, but should not become dramatic or clingy.
```

Emotion Engine keeps mood, affective pulse, trust, and compact emotional memories in one inspectable state package. Mood-only behavior is useful for demos and internal ablation comparisons, not as the normal installation path.
