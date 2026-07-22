---
name: Memory Architecture Decision
description: CoPaw memory should combine a pointer-only MEMORY.md, topic files, session-dream distillation, compact summaries, and folded episodes.
type: project
---

CoPaw memory should use a layered architecture: `MEMORY.md` is a pointer-only index, durable details live in topic files, long sessions run session-dream, flat compaction restores active task state, and folded memory preserves older episodes plus semantic facts.

**Why:** A giant `MEMORY.md` is hard to scan and easy to pollute with stale facts; pure compact summaries lose topic routing and long-term decision rationale.

**How to apply:** Keep index lines short, put load-bearing metadata in topic frontmatter, treat old facts as obsolete instead of co-equal, and use folded memory when old episodes must stay recoverable.
