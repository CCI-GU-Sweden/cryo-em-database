# Development roadmap — CCI Cryo-EM Grid Registry

**Version:** v0.1  
**Date:** 2026-11-02  
**Approach:** incremental vertical slices with demoable features, tests, and real staff feedback.

## Guiding priorities

1. **Science/data integrity**: no lost IDs, no fabricated measurements, no contradictory storage states.
2. **Adoption**: nontechnical staff can perform the Excel workflow in a browser.
3. **Secure, replaceable identity**: start with local accounts; keep access grants independent of login provider.
4. **Minimal infrastructure**: avoid nonessential services.
5. **Extensibility**: later OMERO and knowledge-base features must not require rewriting core identity and inventory concepts.

## Phase 0 — Repository and design baseline

**Deliverables**

- Confirm `docs/07_OPEN_DECISIONS.md` items that block code (identifier generation, staff editing policy, storage path conventions).
- Choose stack (recommended Django + PostgreSQL) and development environment.
- Scaffold repo, `.env.example`, dependency lock/pinning, formatter/linter and automated tests.
- Establish Git hygiene, secret handling, backups outline, and schema migration conventions.

**Done when:** project runs locally and tests run in one documented command; model decisions recorded.

## Phase 1 — Data model and authorization backbone

**Deliverables**

- Django user model (choose before initial migrations), `SampleOwner`, `PreparationSession`, `Grid` including structured preparation columns.
- `StorageLocation`, `GridEvent`, `OwnerAccessGrant`, `AuditEvent` and migrations.
- ID allocation service with collision/concurrency tests.
- Event/state service with valid transitions and occupied-slot rules.
- Server-side owner-grant authorization and admin/staff fixture accounts.

**Done when:** automated tests can create one session with N grids, guarantee independent preparation fields, reject duplicate IDs, and preserve inventory history correctly.

## Phase 2 — Usable registration & browse UI (first staff demo)

**Deliverables**

- Login/logout and restricted admin access.
- Owner management and new-session wizard with shared parameters and N-grid generation.
- Grid detail forms, owner/session registry lists, fast search/filter.
- Table view with column grouping, sorting, and editable permitted preparation columns (a simple first implementation is acceptable).
- Audit display and human-readable validation errors.

**Done when:** one less-technical staff member can create a preparation session, generate grids, and adjust two grid entries without a developer guiding them.

## Phase 3 — Physical handling and inventory operations

**Deliverables**

- Store, move, clip, remove for imaging, record imaging, return, ship, discard actions.
- Current state and current location read-only projections in UI.
- Location occupancy checking, movement history, event chronology.
- Bulk selection and safe targeted actions where genuinely useful.
- Search/filter availability, clipped state, and last location.

**Done when:** a test scenario covers grid preparation → storage → clipping → move → imaging → discard; another covers shipment directly from storage; every event has an accurate history.

## Phase 4 — Excel import/export & migration

**Deliverables**

- Import parser for exact workbook headers (row 3) and source rows.
- Preview/dry-run that skips preallocated identifiers without actual grid data.
- Raw-value preservation, warnings for ambiguous/unknown units, duplicate detection.
- Admin-approved import action with row-level result reports and rollback behavior.
- CSV/XLSX export with explicit headers and no implied scientific conversions.

**Done when:** the eight populated demonstration rows can be imported, inspected, searched, and exported without loss of their original information; repeated import cannot silently duplicate grids.

> Phase 4 parsing can start in parallel with earlier development, but production import must wait for model and event-validation stability.

## Phase 5 — Pilot with all six CCI staff

**Deliverables**

- Set up a protected internal deployment and backups.
- Run a real pilot with the colleague who maintains the Excel file and the remaining staff.
- Capture workflow friction (number of clicks, time to register 5–10 grids, edit, find, move, and clip).
- Review actual permission needs and optional field vocabulary.
- Iterate forms, table defaults, quick actions and documentation.

**Done when:** staff prefer the browser workflow for routine recording; data is correct; access controls have been tested; backup restore has been demonstrated.

## Phase 6 — Hardening and initial release

**Deliverables**

- Stable migrations and repeatable deploy process.
- Permission/race-condition tests, error handling, logging, time zones, user deactivation.
- Versioned release notes, operator manual, backup/runbook, export/restore pathway.
- Agree how to retire/retain the old Excel workbook to avoid dual sources of truth.

**Done when:** one supported application is the system of record; procedures for outages and export exist.

## Future milestones (not MVP commitments)

- Grid observation/outcome module for successful/failed preparations.
- OMERO image/dataset and OMERO.figure links, with access-control integration.
- External researcher accounts with limited read and lifecycle actions via institutional OIDC.
- Protocol documents and version/lineage records for LM/EM/cryo-EM.
- Local document extraction (e.g., Docling) and small local LLM for draft structured fields, subject to review.
- Public protocols.io export of selected reviewed protocols.

## Suggested Codex task breakdown

| Task | Dependencies | Concrete output |
|---|---|---|
| T01 | Phase 0 | Project scaffold, tests, local run instructions |
| T02 | T01 | Models/migrations, admin display, fixtures |
| T03 | T02 | Identifier/session creation service and tests |
| T04 | T02 | Permissions and queryset filtering tests |
| T05 | T02 | GridEvent state machine & storage occupancy tests |
| T06 | T03, T04 | Session wizard and grid form |
| T07 | T04, T05 | Lifecycle actions and event history UI |
| T08 | T06 | Editable table with safe batch updates |
| T09 | T02, T05 | Excel import dry-run, mapping and provenance |
| T10 | T08, T09 | Admin import, export and pilot validation |
| T11 | All | Production settings, backup/restore, documentation |

## Avoid these shortcuts

- No `owner_id` as sole authorization check at UI level.
- No auto-disposal on `imaged` without an explicit event.
- No rewriting historical IDs to new owner prefixes.
- No silent conversion of humidity `1` to `1%` or `100%`.
- No assuming workbook `JB002` identifies the real preparation session.
- No treating blank Excel rows with a grid number as real physical grids.
- No copying one session's live state across grids after creation.
