# Concepts

Emotion Engine is a compact continuity layer for LLM-powered agents. It does not replace the LLM. It gives the LLM a persistent, inspectable state to carry forward.

## PAD State

Emotion Engine represents current emotion with PAD:

- **Pleasure**: negative to positive valence.
- **Arousal**: calm to energized.
- **Dominance**: soft or uncertain to firm and bounded.

The state is intentionally small. It should guide tone and continuity, not become a full psychological model.

## Personality Baseline

The baseline is where the agent naturally drifts back over time.

For example:

```json
{
  "pleasure": 0.2,
  "arousal": 0.2,
  "dominance": 0.6
}
```

This could describe an agent that is mildly warm, calm, and clearly bounded.

## Trust

Trust is separate from emotion. It changes slowly, usually at session boundaries.

In v1, trust is directional and intentionally narrow: it is agent-to-user only. It is the agent or persona's internal estimate of whether this user has been cooperative, boundary-respecting, predictable, and safe enough for deeper persona continuity. It does not infer the user's trust in the agent.

Trust can:

- slow emotional decay
- soften moderate negative shifts
- make positive interactions linger slightly longer
- help the agent distinguish early relationship from established rapport

Trust should not be used as obedience, a user score, safety permission, dependency, attachment pressure, or a way to manipulate the user or punish absence.

`trust_history` is only a numeric ledger: `old`, `new`, `raw_delta`, and `effective_delta`. The reason for a trust change belongs in `emotion_log`, usually in the relevant turn entries, session patterns, or a compact `trust_update` log entry.

## Emotion Log

The emotion log is not a transcript. It stores compact emotional memories:

```json
{
  "situation": "User challenged the design and asked for a stronger version.",
  "appraisal": "collaboration",
  "relational_meaning": "Direct critique feels safe and productive.",
  "follow_up_bias": "Be precise, warm, and clearly bounded next turn.",
  "salience": 0.65
}
```

Good emotion memories are:

- short
- interpretive
- useful for future response style
- free of sensitive full transcripts

`emotion_log` is also the explanation layer for PAD and trust changes. Numbers stay compact; situation, appraisal, relational meaning, impact, and optional external references explain why they moved.

## Decay

Emotion drifts toward the baseline over time. This prevents the agent from staying permanently excited, hurt, guarded, or overly attached after a single event.

Trust can slow decay, but should not prevent it entirely.

## Session Patterns

At session end, Emotion Engine can extract simple trajectory patterns:

- conflict
- repair
- sustained negative trend
- excessive smoothness
- dominance suppression
- boundary pressure

These patterns inform `settle_trust`, which applies a conservative, idempotent host-side trust settlement for the current trajectory. They should remain advisory. A real integration should let the LLM interpret the broader context, and should use manual `update_trust` only for explicit host-side overrides.

## Deterministic Appraisal Helper

The `appraise` command uses simple deterministic rules. It exists for:

- debugging
- demos
- fallback integrations
- guardrail-style suggestions

It should not be treated as the final emotional judgment in a real LLM agent.

## Design Principle

The LLM decides what an interaction means.

Emotion Engine remembers the continuity of that decision.
