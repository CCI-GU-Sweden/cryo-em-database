# Product brief — CCI Cryo-EM Grid Registry

**Version:** 0.1  
**Date:** 2026-11-02  
**Status:** Agreed operational scope; implementation details under review

## Problem

CCI currently tracks cryo-EM grids in an Excel workbook. Each row represents a physical grid, with fields for sample preparation, grid treatment, freezing conditions, unclipped/clipped storage, experiment reference, and notes. The workbook is flexible but does not provide reliable uniqueness enforcement, owner-based permissions, event-based inventory history, controlled entry, or a straightforward web workflow.

A preparation session normally produces several replicate grids. The operator begins by choosing the sample owner (e.g., Ketan Gupta, with prefix `kegu`), enters **common preparation conditions**, chooses how many grids to generate, and then **individually edits** grid-specific differences and storage positions. Grids begin **unclipped** with no storage assigned. Grids may be stored, moved, clipped, removed for imaging, imaged (usually followed by disposal), discarded directly, or shipped to another site. When shipped, CCI needs to know that the grid has left CCI custody; its later off-site fate is not required for the initial application.

## Primary goal

Replace the present manual Excel registry with a **simple, reliable, editable web-based registry**, designed for six CCI staff members with mixed technical skills, without losing useful flexibility or existing records.

## Specific goals

1. **Register real preparation sessions** (exactly one sample owner per session) and generate any reasonable number of unique, independent grid records from shared defaults.
2. **Browse and edit grids** through individual forms and a familiar spreadsheet-like table, including safe bulk modifications.
3. **Track physical lifecycle** with explicit actions, event history, location history, clipping and imaging events, shipment and disposal.
4. **Administer accounts and editing rights** by sample owner; all CCI staff can see all grids. Start with CCI accounts only.
5. **Import and export Excel**, preserving historical identifiers and original scientific wording when uncertain.
6. **Keep the system extensible** for OMERO evidence, protocol lineage, structured preparation knowledge, and optional local LLM processing.

## Users and responsibilities

| Actor | Day-one needs | Intended restrictions |
|---|---|---|
| CCI administrator | Create/manage accounts, owners and prefixes, access grants, import, troubleshoot | Facility-wide access and administration |
| CCI staff/preparation operator | Create sessions, generate grids, edit allowed preparation fields, record storage and lifecycle events | View all; write access determined by admin-defined owner assignments unless admin overrides |
| External researcher (later) | See assigned grids; possibly log limited handling actions | Not a day-one user; may not alter preparation parameters |
| Sample owner | Named person/group to whom physical grids belong | Does not automatically have an application login or editing permission |

## Primary workflows

### Workflow A — Create grids

1. Select an existing sample owner or create a new owner with a unique code/prefix.
2. Open **New preparation session**; enter date, operator, optionally experiment/project reference and notes.
3. Enter common sample-preparation, grid treatment, and freezing parameters (plain text or validated numeric fields).
4. Enter the number of grids to generate and preview their new IDs.
5. Confirm once: create the session with an immutable default snapshot and individual grids with copied initial parameters **in one transaction**.
6. Display the new grids in a table for rapid individual changes; storage remains empty until assigned.

### Workflow B — Edit an individual grid

- Open grid detail form or edit permitted preparation cells in the bulk table.
- Correct/adjust individual parameters independently of other grids.
- Preserve an audit record identifying what changed and by whom; distinguish data corrections from actual physical actions.
- A separate `copied_from_grid` relationship may record a deliberately copied preparation pattern; do not infer parenthood solely from similar values.

### Workflow C — Track storage and use

- Assign initial location; move to another position; clip and possibly relocate; remove for imaging; optionally return; record imaging; discard; or ship off-site.
- Each physical action creates an event with actual time, actor, and appropriate location/destination details.
- Current availability, clipping state, and current location are *derived from or transactionally synchronized with* event history; they are not independently editable arbitrary text fields.
- Imaged grids are **usually** discarded, but imaging does not by itself force disposal. Shipment does **not** imply imaging or discard.
- Shipped and discarded grids remain searchable as history but are excluded by default from the available-inventory view.

### Workflow D — Find and maintain records

- Search by grid ID, owner, experiment reference, sample, storage location, preparation date, and availability.
- Filter batch/session replicates; compare sample preparation differences.
- Admin imports previous workbook data via validation + dry-run + review; exports matching records to CSV/XLSX without overwriting history.

## Main screens

1. **Grid registry/table:** filter, search, sort, select rows, edit permitted preparation fields, export; read-only status/IDs.
2. **New preparation session / batch-generation wizard:** owner, shared parameters, number of grids, preview, confirm.
3. **Grid detail:** grouped `General`, `Preparation`, `Clipping & storage`, `Events/history` sections.
4. **Lifecycle action dialog:** explicit movement/clipping/imaging/disposal/shipping forms and confirmations.
5. **Admin:** users, owners, owner codes, access grants, source imports and audit review.

## UI and accessibility principles

- Simple language following existing lab concepts, with sensible defaults and input help.
- Preserve grouped display of composite operations (e.g. "Air · Negative · 15 mA · 20 s") while storing individual fields.
- Show units, allow nullable/unknown values, never interpret an empty value as zero.
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
- Unauthorized users cannot alter another owner's records, including through bulk requests or direct URLs.
- Daily workflows are faster or comparably easy to Excel; feedback from all six staff guides iteration.

## Constraints and decisions

- One owner per session: **confirmed**.
- Session defaults copied to each grid, with preserved snapshot: **confirmed**.
- Experiment reference optional: **confirmed**.
- Project is a descriptive optional field, not the permission boundary: **confirmed**.
- Django + PostgreSQL: **recommended, not yet formally locked**.
- Identity provider and detailed storage vocabulary: **deferred/open**.

See [`02_SCHEMA_V0_1.md`](02_SCHEMA_V0_1.md) and [`07_OPEN_DECISIONS.md`](07_OPEN_DECISIONS.md).
