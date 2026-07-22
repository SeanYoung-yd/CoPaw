---
name: Memory Evaluation Session Dream 2026-07-15
description: Distillation of session 019f5999-f96b-7980-9970-0d7670b66568 about memory evaluation tests and UI/backend version mismatch.
type: project
---

Session `019f5999-f96b-7980-9970-0d7670b66568` established that the new memory strategy suite is valid in the current workspace, while failures in the running app usually come from stale backend or frontend builds.

**Why:** The session compared compact summary, session-dream, folded memory, and topic-file behavior; the important lesson is version alignment and stale-fact exclusion, not the individual troubleshooting steps.

**How to apply:** If memory eval results are empty or fields fail to deserialize, check whether the running service is the current `F:\CoPaw` source before changing the suite. If a result returns `profile-obsolete`, treat that as old-fact contamination.

**Decisions:**
- `profile-current` should win over `profile-obsolete`; obsolete facts are test fixtures for contamination, not current user truth.
- `must_not_return_ids` and `forbidden_terms` are necessary to distinguish retrieval quality from stale-fact and privacy failures.
- Use `keyword` backend for deterministic frontend and suite debugging; use `copaw` backend only after real memory dependencies are configured.

**Ruled out:**
- Treating `memory_strategy_discrimination_suite.json` as broken was ruled out because the current workspace CLI can run it.
- Rebuilding only the frontend is insufficient when the backend schema is old.
