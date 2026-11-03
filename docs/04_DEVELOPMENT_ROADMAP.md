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

## Local prototype decision — 2026-11-03

Start with a small local prototype to validate the data model through staff-facing forms. Full v0.1 acceptance criteria remain the release target; the first demo only needs the registration slice. Evolve the schema through migrations after feedback.

| Layer | Start with | Add after validation |
|---|---|---|
| Backend | Python 3.13, Django 5.2 LTS, psycopg 3; lock compatible patch versions when scaffolding | Supported-version upgrades as maintenance |
| Database | PostgreSQL 17 from the first migration, including tests | Indexes based on actual queries; shared hosting later |
| UI | Django forms/templates, plain HTML table and minimal CSS | HTMX or a spreadsheet library if staff trials demonstrate a need |
| Authentication | Local Django username/password login, session cookies, custom AbstractUser before first migration | Institutional SSO and explicit external identity mapping |
| Administration | Django admin for users, owners and access grants | Custom administration screens if useful |
| Runtime | Python virtual environment and Compose-managed PostgreSQL with persistent volume and loopback-only database port | Internal HTTPS deployment with production app server |
| Verification | Django tests on PostgreSQL, Ruff and locked dependencies | Browser tests for advanced table interactions |
| Excel | Synthetic fixtures | openpyxl import/export after schema review |

Django 5.2 has extended support through April 2028; schedule an upgrade before then. Sources: [Django supported releases](https://www.djangoproject.com/download/), [Django PostgreSQL backend](https://docs.djangoproject.com/en/5.2/ref/databases/#postgresql-notes).

Local means browser and application on the same machine, bound to loopback. Create individual accounts administratively; keep password hashing, CSRF and authenticated mutations. Keep CCI staff membership separate from Django's admin-access flag. An admin account can run the initial demonstration; also test a restricted account against the existing owner-grant policy. SSO, public signup and email password recovery are unnecessary for this stage.

Use a clearly labeled prototype database and synthetic data. Excel remains authoritative until operational readiness. Resets require explicit agreement and apply only to disposable data; retain migrations in Git. Before retaining real records, establish backup/restore and correction procedures. Shared LAN access is a separate deployment step.

## Phase 0 — Local scaffold

- Configure Django/PostgreSQL, the custom user model, dependency locking, Ruff and test commands.
- Document database startup, migrations, account creation and loopback app startup.
- Provide `.env.example` and repeatable synthetic demonstration data.

**Done when:** a developer starts the application, logs in and runs tests against PostgreSQL using documented commands.

## Phase 1 — First staff demo: register and inspect grids

- Implement SampleOwner, PreparationSession, Grid, OwnerAccessGrant and AuditEvent with the services needed for registration.
- Provide a simple session form: owner, preparation date/operator, optional reference, shared parameters and grid count.
- Atomically save the session, immutable defaults snapshot and independent grids.
- Display generated grids in a plain table; edit individual preparation fields through detail forms and display audit history.
- Preserve structured measurements, explicit units and unknown values. Storage remains unassigned in this slice.
- Route mutations through services, including admin actions; prevent generic admin edits to IDs and immutable snapshots.
- Test copying, failed-transaction rollback, unique IDs under concurrency, permissions and create/edit forms.

**Identifier dependency:** resolve D01 before allocating operational owner-prefixed IDs. If needed for an earlier demo, use a reserved synthetic `DEMO-` namespace in the disposable database, visibly labeled and blocked from operational use. This does not settle owner numbering conventions.

**Done when:** a colleague logs in, creates eight grids, edits two, reloads and confirms that the other six and the session snapshot are unchanged. Demonstrate validation failure without partial creation and rejection of an unauthorized edit.

## Phase 2 — Model review and initial physical storage

- Review real fields, required inputs, session boundaries, units and form usability with staff; record decisions and migrations.
- Confirm D03 with examples of actual clipped and unclipped locations.
- Add StorageLocation and the initial GridEvent subset: store and move, with read-only current location and append-only history.
- Enforce occupancy in the database and update events/location atomically.
- Test occupied destinations, concurrent assignments, rollback and permissions.
- Add stale-edit detection before simultaneous staff editing, so a second save cannot silently overwrite another user's changes.

**Done when:** staff can assign and move a synthetic grid, see both locations in history and cannot double-book a slot. Review whether real storage fits the schema comfortably.

**Review gate:** proceed after registration and storage fit staff practice. Record observed friction and unresolved domain questions. Trial spreadsheet tooling only against concrete editing tasks.

## Phase 3 — Physical handling and inventory operations

**Deliverables**

- Extend store/move with clip, remove for imaging, record imaging, return, ship and discard actions.
- Define corrections, backdated events and exceptional transition rules before exposing those operations.
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
| T02 | T01 | Registration models, grants, audit, admin and fixtures |
| T03 | T02 | Identifier/session creation service and tests |
| T04 | T02 | Permissions and queryset filtering tests |
| T05 | T06, storage review | Initial store/move models, services, UI and concurrency tests |
| T06 | T03, T04 | Session wizard and grid form |
| T07 | T04, T05 | Lifecycle actions and event history UI |
| T08 | Prototype review | Trial table tooling; implement safe batch updates |
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
