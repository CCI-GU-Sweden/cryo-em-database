# Product brief — CCI Cryo-EM Grid Registry

**Version:** 0.1\
**Last reviewed:** 2026-11-04\
**Status:** Agreed v0.1 scope; preparation and current Excel transfer implemented, physical handling deferred

This brief describes the full intended workflow, including future screens/actions.
The [roadmap](04_DEVELOPMENT_ROADMAP.md#current-implementation--2026-11-04) distinguishes
the implemented prototype from the remaining v0.1 scope. The current table supports
browsing/filtering and links to individual editing; bulk/inline editing and physical
state tracking are not implemented.

## Problem

CCI currently tracks cryo-EM grids in an Excel workbook. Each row represents a physical grid, with fields for sample preparation, grid treatment, freezing conditions, unclipped/clipped storage, experiment reference, and notes. The workbook is flexible but does not provide reliable uniqueness enforcement, owner-based permissions, event-based inventory history, controlled entry, or a straightforward web workflow.

A preparation session normally produces several replicate grids. The operator begins by choosing the sample owner (e.g., Ketan Gupta, with prefix `kegu`), enters **common preparation conditions**, chooses how many grids to generate, and then **individually edits** grid-specific differences and storage positions. Grids begin **unclipped** with no storage assigned. Grids may be stored, moved, clipped, removed for imaging, imaged (usually followed by disposal), discarded directly, or shipped to another site. When shipped, CCI needs to know that the grid has left CCI custody; its later off-site fate is not required for the initial application.

## Primary goal

Replace the present manual Excel registry with a **simple, reliable, editable web-based registry**, designed for six CCI staff members with mixed technical skills, without losing useful flexibility or existing records.

## Specific goals

1. **Register real preparation sessions** (exactly one sample owner per session) and generate any reasonable number of unique, independent grid records from shared defaults.
2. **Browse and edit grids** through individual forms and a familiar spreadsheet-like table, including safe bulk modifications.
3. **Track physical lifecycle** with explicit actions, event history, location history, clipping and imaging events, shipment and disposal.
4. **Administer accounts**, with all active CCI staff able to view and edit all active grids; owner-scoped rights remain a future external-access concern. Start with CCI accounts only.
5. **Import and export Excel**, preserving historical identifiers and original scientific wording when uncertain.
6. **Keep the system extensible** for OMERO evidence, protocol lineage, structured preparation knowledge, and optional local LLM processing.

## Users and responsibilities

| Actor | Day-one needs | Intended restrictions |
|---|---|---|
| CCI administrator | Create/manage accounts, owners and prefixes, access grants, troubleshoot | Facility-wide administration; Excel import additionally requires the CCI staff flag |
| CCI staff/preparation operator | Create sessions, generate grids, edit allowed preparation fields, record storage and lifecycle events | View all owners/grids; create sessions for any active owner; edit every active grid with a full change audit |
| External researcher (later) | See assigned grids; possibly log limited handling actions | Not a day-one user; may not alter preparation parameters |
| Sample owner | Named person/group to whom physical grids belong | Does not automatically have an application login or editing permission |

## Primary workflows

### Workflow A — Create grids

1. Select an existing sample owner or create a new owner with a unique code/prefix.
2. Open **New preparation session**; enter date, operator, optionally experiment/project reference and notes.
3. Enter common sample-preparation, grid treatment, and freezing parameters (plain text or validated numeric fields).
4. Enter the number of grids to generate (currently 1–100). ID preview is future UI work.
5. Confirm once: create the session with an immutable default snapshot and individual grids with copied initial parameters **in one transaction**.
6. Display the new grids in a table with individual View/edit links; storage remains empty until assigned. Inline/bulk editing remains future work.

### Workflow B — Edit an individual grid

- Open grid detail form or edit permitted preparation cells in the bulk table.
- Correct/adjust individual parameters independently of other grids. All active CCI staff may edit every active grid. The preparation operator records attribution, while the audit identifies each editor and their changes.
- Preserve an audit record identifying what changed and by whom; distinguish data corrections from actual physical actions.
- Active CCI staff may delete an individual mistaken registration through a password-confirmed archive action. Deleted records leave normal views but retain their IDs, session links and history in a read-only Deleted grids area. This is separate from physical disposal.
- A reserved `copied_from_grid` relationship may support a future deliberate copy workflow. It is not exposed in the UI or current Excel format; do not infer it from similar values or notes.

### Workflow C — Track storage and use

- Assign initial location; move to another position; clip and possibly relocate; remove for imaging; optionally return; record imaging; discard; or ship off-site.
- Each physical action creates an event with actual time, actor, and appropriate location/destination details.
- Current availability, clipping state, and current location are *derived from or transactionally synchronized with* event history; they are not independently editable arbitrary text fields.
- Imaged grids are **usually** discarded, but imaging does not by itself force disposal. Shipment does **not** imply imaging or discard.
- Shipped and discarded grids remain searchable as history but are excluded by default from the available-inventory view.

### Workflow D — Find and maintain records

- Search by grid ID, owner, experiment reference, sample, storage location, preparation date, and availability.
- Filter batch/session replicates; compare sample preparation differences.
- Accounts marked CCI staff import current-format workbook data via preview and confirmation. Any account with registry viewing access can export its visible filtered subset to XLSX. Legacy workbook parsing and CSV export remain future work.

## Main screens

1. **Grid registry/table:** filter, search, sort, select rows, edit permitted preparation fields, export; read-only status/IDs.
2. **New preparation session / batch-generation wizard:** owner, shared parameters, number of grids, preview, confirm.
3. **Grid detail:** grouped `General`, `Preparation`, `Clipping & storage`, `Events/history` sections.
4. **Lifecycle action dialog:** explicit movement/clipping/imaging/disposal/shipping forms and confirmations.
5. **Admin:** users, owners, owner codes, access grants, source imports and audit review.

## UI and accessibility principles

- Simple language following existing lab concepts, with sensible defaults and input help.
- Preserve grouped display of composite operations (e.g. "Air · Negative · 15 mA · 20 s") while storing individual fields.
- Show units and preserve unknown measurements. Multiple blots explicitly defaults to 0, including blank input; date-only imports explicitly default to noon in Europe/Stockholm, while blank dates remain unknown.
- Use contextual dropdowns and validation for constrained values, but do not block legitimate uncommon workflows.
- Make routine events fast to record; do not require staff to think about underlying tables or authentication technologies.
- Prevent destructive actions, accidental batch-wide editing, and editing of derived status directly.

## Non-goals for v0.1

- General microscopy protocol repository or document editor.
- Local LLM inference, automatic scientific recommendations, embeddings, or document mining.
- Public protocols.io publication, OMERO integration, OMERO.figure reporting.
- External-user login or detailed per-grid sharing exceptions.
- Full external-shipment tracking or automatic detection of off-site imaging.
- Inventory procurement, billing, instrument scheduling, or a general LIMS.

## Longer-term context

The grid registry may later join a broader sample preparation knowledge base, linking protocols and protocol versions to real preparation attempts, outcome annotations, OMERO images/figures, and community publication. A locally hosted document-parsing/LLM service could propose structured protocol fields, **subject to human review and source provenance**. Nothing about that future work should complicate using the first registry.

## Success measures for the first pilot

- A less technical colleague can register a session with multiple grids and individual adjustments without assistance.
- Existing populated Excel rows can be imported with no lost source values and no phantom grids.
- Search and export work for all grid records.
- A grid's current physical location and complete history remain consistent after clipping and transfers.
- Inactive accounts and non-CCI non-administrators cannot alter records through direct URLs or services. Future bulk writes must enforce the same rules; import explicitly requires the CCI flag even for administrators.
- Daily workflows are faster or comparably easy to Excel; feedback from all six staff guides iteration.

## Constraints and decisions

- One owner per session: **confirmed**.
- New grid IDs: **confirmed 2026-11-04**, four-character owner prefix and a separate per-owner sequence, `0001`–`9999`, then `a001`–`z999`; preserve historical IDs.
- Session defaults copied to each grid, with preserved snapshot: **confirmed**.
- Experiment reference optional: **confirmed**.
- Project is a descriptive optional field, not the permission boundary: **confirmed**.
- Django + PostgreSQL with local Django accounts: **selected for the local prototype, 2026-11-03**; advanced UI and shared hosting follow review.
- Identity provider and detailed storage vocabulary: **deferred/open**.

See [`02_SCHEMA_V0_1.md`](02_SCHEMA_V0_1.md) and [`07_OPEN_DECISIONS.md`](07_OPEN_DECISIONS.md).
