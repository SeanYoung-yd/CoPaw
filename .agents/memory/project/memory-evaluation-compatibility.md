---
name: Memory Evaluation Compatibility
description: memory_strategy_discrimination_suite requires the current backend schema and current console build; old services produce missing-field or stale-metric symptoms.
type: project
---

`tests/memory_strategy_discrimination_suite.json` depends on the current evaluator schema, including `must_not_return_ids` for stale-fact pollution checks and `forbidden_terms` for privacy/safety checks.

**Why:** In session `019f5999-f96b-7980-9970-0d7670b66568`, the suite ran from the current workspace with the keyword backend, but an old running backend returned `SearchCase.__init__() got an unexpected keyword argument 'must_not_return_ids'`.

**How to apply:** First verify the current source:

```powershell
cd F:\CoPaw
.\.venv\Scripts\python.exe -m copaw eval memory --suite tests\memory_strategy_discrimination_suite.json --backend keyword --format text
```

Then restart the backend from `F:\CoPaw`, rebuild `F:\CoPaw\console` if the UI still shows stale metrics, and use `Keyword baseline` before testing the real `CoPaw MemoryManager` backend.

The top metric cards are intentionally limited, while the detailed metric profile should include newer exclusion/safety metrics when the frontend build is current.
