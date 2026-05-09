# Contributing

Thanks for considering a contribution to Emotion Engine.

Emotion Engine is maintained by PioneerJeff Labs, an open-source lab building reusable infrastructure layers for creative AI applications.

## Project Goals

Emotion Engine aims to stay small, inspectable, and easy to adapt. Changes should make agent emotional continuity clearer, safer, or easier to integrate.

Good contributions include:

- Better documentation and examples.
- Tests for state transitions, appraisal behavior, decay, trust updates, and configuration.
- Small fixes to command-line behavior.
- Safer defaults and clearer ethical guardrails.
- New appraisal patterns when they remain deterministic and explainable.

## Local Checks

Run the test suite before opening a pull request:

```bash
python3 -m unittest discover -s tests
```

You can also run a quick manual flow:

```bash
python3 scripts/emotion_engine_utils.py init emotion-state.json
python3 scripts/emotion_engine_utils.py configure emotion-state.json --style "calm, reliable, and clearly bounded"
python3 scripts/emotion_engine_utils.py appraise emotion-state.json "thank you for the help"
python3 scripts/emotion_engine_utils.py validate emotion-state.json
```

## Contribution Guidelines

- Keep emotion logs compact and avoid storing full transcripts.
- Do not add hidden network calls or telemetry.
- Keep the command-line interface usable with the Python standard library.
- Include tests for behavior changes.
- Prefer clear, deterministic behavior over opaque heuristics.

## Safety

Do not add features intended to manipulate user attachment, punish absence, infer real mental health state, or make consequential decisions about people.
