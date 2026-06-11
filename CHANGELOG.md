# Changelog

## Unreleased

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
