# Changelog

## Unreleased

- Prepared the project for an initial open-source release.
- Aligned project metadata with PioneerJeff Labs.
- Added repository-level license, ignore rules, contribution notes, and security policy.
- Updated README usage paths for a GitHub repository root.
- Added a minimal standard-library test suite.
- Clarified that the lifecycle checker is not an AI chat demo and that LLMs make the final contextual emotion judgment.
- Reworked README positioning for a clearer public launch story and added a launch kit.
- Added separate English and Chinese README files, concept docs, integration docs, and prompt guidance preview.
- Added a Claude Skill integration package.
- Added initial project and lab logo assets.
- Removed the previous lab acronym from launch-facing copy.
- Moved platform-specific packages under `integrations/openclaw` and `integrations/claude-skill`.
- Removed duplicate integration copies of the shared core; package scripts now assemble self-contained release zips from the root source.
- Refined PioneerJeff Labs positioning around reusable infrastructure layers for creative AI applications.

## 0.1.0

- Initial experimental OpenClaw skill.
- Added PAD emotion state, trust coefficient, decay, appraisal helper, compact emotion log, chat-first configuration, and session pattern extraction.
