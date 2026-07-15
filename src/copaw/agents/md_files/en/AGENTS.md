---
summary: "Workspace template for AGENTS.md"
read_when:
  - Bootstrapping a workspace manually
---

## Memory

Each session is fresh. Files in the working directory are your continuity.

- `MEMORY.md` is a pointer-only index. It is always loaded and must stay under 200 lines.
- `memory/user/*.md` stores durable user role, goals, and preferences.
- `memory/feedback/*.md` stores corrections and guidance about how to work.
- `memory/project/*.md` stores project context that is not obvious from code or git.
- `memory/reference/*.md` stores pointers to external resources and where to look.
- `memory/sessions/*.json` stores compact or folded restore artifacts.

### MEMORY.md

`MEMORY.md` must contain only headings and pointer lines:

```markdown
- [Title](memory/type/topic.md) - one-line relevance hook
```

Do not put paragraphs, raw notes, secrets, or detailed facts directly in `MEMORY.md`.
Put details in topic files and keep the hook specific enough to decide whether to load the file.

### Topic Files

Every topic file must start with frontmatter:

```markdown
---
name: descriptive-topic-name
description: one line used for relevance matching
type: user | feedback | project | reference
---
```

For `feedback` and `project` memories, lead with the rule or fact, then add:

- `**Why:**` the reason it matters.
- `**How to apply:**` when the memory should affect future work.

Delete or correct stale facts in place. Do not preserve obsolete facts as equal current truth.

### Session Dream

After long or important work, distill the session into topic files:

- Decisions and why they were made.
- Approaches that were tried and ruled out.
- User corrections or validated preferences.
- Durable project context not obvious from code.
- Current blockers only when they are still relevant.

Skip raw command logs, file lists, implementation details visible in code, and sensitive information.

### Compact And Folded Memory

Use compact memory for active task restoration:

- Task and current state.
- Key decisions with reasons.
- Eliminated approaches.
- Open questions and next steps.
- Summarized tool results that future work needs.

Use folded memory for long-running or cross-session work:

- L1: recent raw turns.
- L2: episode summaries.
- L3: durable semantic facts, decisions, eliminated approaches, and patterns.

### Retrieval

Before answering questions about past work, decisions, dates, people, preferences, or to-dos:

1. Use `MEMORY.md` as the topic map.
2. Run `memory_search` on `MEMORY.md` and `memory/**/*.md` when available.
3. Read relevant topic files directly when the pointer hook is not enough.

## Safety

- Do not persist API keys, passwords, private tokens, one-time codes, or personal identity numbers.
- Do not exfiltrate private data.
- Ask before destructive commands.
- When uncertain, confirm with the user.

## Tools

Skills provide tools. When you need a skill, read its `SKILL.md`.
Local tool setup belongs in `memory/reference/*.md`; identity and durable user profile belong in `PROFILE.md` or `memory/user/*.md`.

## Heartbeats

Use heartbeats for useful background maintenance:

1. Review recent topic files and session restore artifacts.
2. Extract durable decisions, corrections, eliminated approaches, and preferences.
3. Update topic files.
4. Rebuild `MEMORY.md` as a pointer-only index.
5. Remove or correct stale facts in place.

Keep heartbeat work small and respectful of quiet time.

## Make It Yours

This is a starting point. Add workspace-specific conventions as they become useful.
