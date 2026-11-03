# CCI Cryo-EM Grid Registry — Codex Handoff

**Specification baseline:** v0.1  
**Prepared:** 2026-11-02  
**Status:** Agreed conceptual schema; local prototype-first plan selected 2026-11-03, implementation not started

This directory contains a **repo-ready handoff** for building a small web application to register, edit, locate, and track cryo-electron microscopy (cryo-EM) grids prepared at the Centre for Cellular Imaging (CCI). The initial user population is CCI staff; the data model should support tightly restricted external accounts later.

## Start here

1. [`docs/01_PRODUCT_BRIEF.md`](docs/01_PRODUCT_BRIEF.md) — problem, operational workflow, goals, scope, and design principles.
2. [`docs/02_SCHEMA_V0_1.md`](docs/02_SCHEMA_V0_1.md) — agreed entities, field-level structure, invariants, lifecycle, and relationships.
3. [`docs/03_ARCHITECTURE_AND_SECURITY.md`](docs/03_ARCHITECTURE_AND_SECURITY.md) — candidate Django implementation, forms and bulk editing, identity, authorization, and audit requirements.
4. [`docs/04_DEVELOPMENT_ROADMAP.md`](docs/04_DEVELOPMENT_ROADMAP.md) — vertical slices, milestones, dependencies, and delivery criteria.
5. [`docs/05_EXCEL_IMPORT_SPEC.md`](docs/05_EXCEL_IMPORT_SPEC.md) — exact workbook column map, data-quality issues, and import behavior.
6. [`docs/06_ACCEPTANCE_TESTS.md`](docs/06_ACCEPTANCE_TESTS.md) — scenarios and tests Codex should implement.
7. [`docs/07_OPEN_DECISIONS.md`](docs/07_OPEN_DECISIONS.md) — bounded unresolved details; do not silently invent a scientific convention.
8. [`AGENTS.md`](AGENTS.md) — instructions for Codex or another repository-based coding assistant.

## Agreed scientific/operational model

A **preparation session** is a real laboratory session, belongs to **exactly one sample owner**, and creates multiple individual **grids** with a saved snapshot of the shared preparation settings. At creation, each grid gets its own independent copy of the preparation fields. The user may subsequently modify individual grids, assign their storage locations, clip/move/image/discard them, or ship them outside CCI. The physical history is append-only. **Grid number is a permanent, globally unique natural identifier.**

The initial Excel example uses `CCI-00001` etc. The new application should also support owner-based identifiers such as `kegu-1234`, without rewriting historical IDs.

## Important distinction

- **Already agreed:** schema concepts, one owner per preparation session, copied defaults, optional experiment reference, staff-only initial access, complete history, both forms and table editing.
- **Prototype baseline:** Django + PostgreSQL, local Django accounts, server-rendered forms and a plain table. Advanced table tooling and shared hosting follow workflow review.
- **Unresolved:** some values/units in the source Excel, exact prefixes/sequences, whether staff may edit every owner's records, and detailed storage hierarchy rules. See `docs/07_OPEN_DECISIONS.md`.

## Source workbook

The uploaded source workbook was inspected for this handoff: **`Cryo-EM_grids_example.xlsx`**, worksheet `Sheet1`, used range `A1:AC724`, headers in row 3, eight populated grid records in rows 4–11, and prefilled identifiers below. The workbook is **not duplicated in this documentation package**. Place a privately held copy under `data/raw/` for actual import tests; never commit identifying laboratory data to a public repository.

## Recommended first Codex task

> Read AGENTS.md and docs/01–07. Implement roadmap Phases 0–1: a local Django/PostgreSQL prototype with login, owner administration, session registration, generated-grid table and individual grid editing. Preserve independent preparation values, immutable session defaults, stable identities and audit history. Use synthetic data and the documented DEMO identifier fallback until D01 is resolved. Include model, service, permission and form tests. Demonstrate registration before adding physical storage and advanced table interactions.

## Working rule

Keep documentation updated when an implementation decision is approved. Schema changes should get a migration, a test, and a short explanation of impact on Excel import and future knowledge-base extension.
