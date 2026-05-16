# Emotion Engine Web Demo

This is the primary public demo for Emotion Engine: a standalone side-by-side comparison, not a live chatbot.
The page includes an English / Chinese language toggle in the top-right corner.

![Emotion Engine web demo](screenshot.png)

Chinese screenshot: [screenshot.zh-CN.png](screenshot.zh-CN.png)

The conversation is based on adapted traces from previous real LLM interactions. It is not a purely fabricated benchmark, but it is curated for presentation and privacy. The browser does not call an LLM, does not generate live replies, and does not claim to infer a real user's emotional state.

Open `index.html` in a browser, or serve the repository locally:

```bash
python3 -m http.server 4173 --bind 127.0.0.1
```

Then visit:

```text
http://127.0.0.1:4173/demo/
```

The demo reuses the repository-level logo assets from `../assets/`.

## Demo Story

The demo uses one shared composer to drive two chat tracks:

- Without Emotion Engine: the baseline assistant replies from the visible conversation only.
- With Emotion Engine: the assistant waits while the state layer updates what should carry forward.
- Each chat track shows the runtime context at the top, so the difference is visible before any message is sent.

Click Send to reveal one user turn in both tracks. The baseline side replies quickly. The Emotion Engine side waits while the state panel automatically shows the pre-reply work:

1. turn captured
2. tone appraised
3. state persisted

The state panel shows what Emotion Engine would persist:

- appraisal
- PAD state
- trust
- tone guidance
- compact emotional memory

The core message:

```text
The LLM decides. Emotion Engine remembers.
```

## Intended Use

This is meant for early launch screenshots, short screen recordings, and product explanation. It does not call an LLM, does not generate the sample reply, and does not claim to infer a real user's emotional state.
