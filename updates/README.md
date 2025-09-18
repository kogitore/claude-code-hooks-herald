# Updates Index

This folder contains design decisions, experiments, and monthly notes.
Documents are grouped by **type** first, then tagged by language suffix.

- **Types**:
  - `decisions/` — Architectural/Design decisions (ADR-like)
  - `experiments/` — Spikes, prototypes, measurements
  - `monthly/` — Monthly digest / progress notes
- **Language suffix**: English files have no suffix; Traditional Chinese uses `_zh-TW`.

## Index

### Decisions
- 0001 — Audio mapping  
  [en](./decisions/0001-audio-mapping.md) · [zh-TW](./decisions/0001-audio-mapping_zh-TW.md)
- 0002 — Throttling strategy  
  [en](./decisions/0002-throttling-strategy.md) · [zh-TW](./decisions/0002-throttling-strategy_zh-TW.md)

### Experiments
- Windows volume control  
  [en](./experiments/windows-volume-control.md) · [zh-TW](./experiments/windows-volume-control_zh-TW.md)

### Monthly
- 2025-09 · [en](./monthly/2025-09.md) · [zh-TW](./monthly/2025-09_zh-TW.md)

## Authoring Rules
1. Keep English and Traditional Chinese files in sync (structure & headings).
2. Each file’s header must link to its counterpart language version.
3. Write short, scannable sections. Put data/tables under experiments.
4. If a change impacts users, summarize it in `CHANGELOG.md` and link back here.
