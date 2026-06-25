# Changelog

## Unreleased

## 0.2.0 - 2026-06-25

- Added an expressiveness layer: slow PAD mood remains the stable continuity state, while `affective_pulse` captures short-lived visible per-turn movement.
- Added `volatility_profile` (`steady`, `expressive`, `dramatic_test`) so work assistants and companion-style agents can use different movement envelopes without changing the core trust model.
- Improved style onboarding so warm, intimate, playful, and assertive profiles infer a more appropriate personality baseline instead of always drifting back to the generic default.
- Updated protocol/schema, prompt preview, and the minimal agent example to expose affective pulse separately from PAD mood.
- Preserved existing state baselines during shape upgrades; hosts can still recalibrate character baselines explicitly through configuration.

## 0.1.2 - 2026-06-12

- Added `settle_trust`, a conservative host-side trust settlement command that reuses session patterns, checks recent turn-level evidence, applies trust deltas once per trajectory, and returns `already_settled` on repeat execution.
- Kept `trust_history` as a numeric ledger while writing settlement evidence and reasons to `emotion_log`.
- Added trust tier progress fields to `status` without removing existing status fields.
- Updated Codex, Hermes, Claude, OpenClaw, GPT/API, protocol, and concept docs to use `settle_trust` as the default session-end trust path.
- Expanded tests for trust settlement policy, idempotency, evidence placement, and minimal-agent lifecycle behavior.

## 0.1.1 - 2026-06-11

- Added a user-level Codex skill integration package.
- Added an OpenAI GPT / API host-side integration guide.
- Added the v2 state protocol schema, documented the thin-adapter boundary for Celiums Memory-style integrations, and included the schema in generated skill packages.
- Clarified that trust v1 is agent-to-user only and that `trust_history` is a numeric ledger while `emotion_log` carries explanations and provenance.
- Added a GitHub Pages root redirect to the live demo.

## 0.1.0 - 2026-05-25

- Initial public release of Emotion Engine.
- Added the side-by-side web demo with English / Chinese support.
- Added English and Chinese README files, concept docs, integration docs, and prompt guidance preview.
- Added repository-level license, ignore rules, contribution notes, and security policy.
- Added OpenClaw, Claude Skill / Claude Code, and Hermes Agent integration packages.
- Added project logo assets and PioneerJeff Labs positioning.
- Added release packaging scripts that assemble self-contained skill zips from the root source.
- Added a minimal standard-library test suite.
- Initial experimental OpenClaw skill.
- Added PAD emotion state, trust coefficient, decay, appraisal helper, compact emotion log, chat-first configuration, and session pattern extraction.
