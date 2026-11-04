# CCI Cryo-EM Grid Registry — Codex Handoff

**Specification baseline:** v0.1  
**Prepared:** 2026-11-02  
**Status:** Local prototype with preparation-session registration and individual grid editing

This directory contains a **repo-ready handoff** for building a small web application to register, edit, locate, and track cryo-electron microscopy (cryo-EM) grids prepared at the Centre for Cellular Imaging (CCI). The initial user population is CCI staff; the data model should support tightly restricted external accounts later.

## Local development environment

Use Conda for this prototype. The human-maintained dependency list is
[`environment.yml`](environment.yml). From the repository root:

```bash
conda env create --file environment.yml --prefix ./.conda
conda activate ./.conda
```

The environment lives in the ignored `.conda/` directory. It includes Python 3.13,
Django 5.2 LTS, psycopg 3, PostgreSQL 17, python-dotenv, openpyxl and Ruff. PostgreSQL is
included so local development can work without Docker; installing it does not
start a server. The commands below initialize a private loopback database.

After deliberately changing `environment.yml`, update the environment with:

```bash
conda env update --file environment.yml --prefix ./.conda --prune
```

Keep secrets in a private `.env` file, never in the environment YAML. Use synthetic
data while the prototype model is being evaluated.

### Run the local prototype

With the Conda environment activated, run from the repository root:

```bash
python dev.py
```

The launcher prepares configuration and the database, applies migrations, and
prompts you to create an administrator if none exists. On later runs it preserves
your settings, accounts and records, then starts the app directly.

Open **http://127.0.0.1:8000/** and sign in with your administrator account.
The home page links to preparation-session registration and the grid registry.
`configure_local.py` generates private local secrets and keeps an existing `.env`
unchanged. The database helper initializes `.local/postgres/` on its first run,
then starts PostgreSQL on loopback port 5433 and creates `cci_prototype` if absent.
Changing credentials in `.env` does not change credentials inside an existing
cluster; keep those values consistent. Stop the application with Ctrl+C, then:

```bash
python dev.py stop
```

The helper retains the database on stop. Use `status` to check whether it is
running. This setup targets local Linux/WSL development and uses disposable
synthetic data. It is not a shared or production deployment.

For ordinary staff accounts, use `/admin/` to add a user and enable **CCI staff
member**. That flag permits registry access; Django's separate **Administration site access**
flag permits entry to the administration site. The initial superuser has both
administrative and registry access. Accounts can be deactivated rather than
deleted. All active CCI staff can edit every active grid. The preparation operator
is attribution, not an editing restriction; each change records its actor, time
and before/after values. Archived grids remain read-only.

If Docker is preferred, use `docker compose up -d db` **instead of** the database
helper, after running `python scripts/configure_local.py`. Use the individual Django
commands (`migrate`, `createsuperuser`, `runserver`, `test`) with Docker; `dev.py`
manages the Conda PostgreSQL server. The same connection settings apply.
Docker is optional and its configuration has not been executed in this WSL setup.

### Try preparation registration

Use synthetic names and samples while evaluating this prototype:

1. Sign in as an active CCI staff member or administrator and select **New preparation session**.
2. Select **Register a sample owner**, enter a person or group name, then click
   **Create unique code** beside the name field. The application checks existing codes and
   shows a four-character lowercase code in a read-only field below the name.
   The first two letters of the first and last name are used: `Rafael Silva`
   becomes `rasi`. If taken, the candidates are `rsi1`–`rsi9`, `rs10`–`rs99`,
   then `r100`–`r999`. Review affiliation/notes and save to continue with that
   owner preselected. All CCI staff can immediately register and edit preparations;
   owner registration creates no login account or access grant. Codes are checked under a database lock on save; the
   displayed code is kept if still available, otherwise the next unused one is
   assigned. Codes remain fixed after name changes. Existing owners can also be
   managed through **Account administration → Sample owners**. The admin Add
   screen also has **Create unique code** beside Name and a read-only code field
   below it. Code previews do not reserve identifiers; save rechecks uniqueness.
   Existing-owner changes and managing other people's grants remain admin-only.
3. For another operator, open **Account administration** and create an account
   under **Accounts → Users**, enable
   **CCI staff member**, and set their password. First and last names are optional
   display information. All CCI staff can browse every owner and create sessions
   for any active owner, and edit every active grid. Ordinary operators do not
   need Django's **Administration site access** flag. Administrators can edit all active owners.
4. Open **New preparation session**, select the owner, enter preparation date/time
   and shared conditions, and choose eight grids. The logged-in operator is
   recorded as **Prepared by**. Session notes apply to the session; grid notes are
   copied to each grid. Unknown measurements can stay empty.
5. Click **Create grids**. Open two of the resulting grids and change their blot
   times. Confirm the other six are unchanged and expand the session's original
   settings to inspect the preserved snapshot.
6. Use **Grids** to search by ID, sample, owner or experiment. Every CCI member can
   view all grids and owners, and edit every active grid. All edits record who
   changed what and when. Deactivating a user prevents all login and editing. **Owners** lists active and inactive owners, with
   search and preparation links for active owners.

This slice focuses on preparation, with no location-entry or physical-event
controls. Grids remain unclipped, not imaged and awaiting storage. Each sample owner has an independent grid sequence starting at `0001`:
`rasi-0001` … `rasi-9999`, then `rasi-a001` … `rasi-a999`,
`rasi-b001` … `rasi-z999`. These reflect database generation order, not the
preparation date. The sequence has 35,973 IDs per owner and stops explicitly when
exhausted; batches never wrap around or partially succeed. Existing matching IDs
are reserved automatically, and historical `CCI-…`/`DEMO-…` IDs remain unchanged.
New generation requires a four-character lowercase owner code. A legacy owner
with a longer code must be reviewed explicitly rather than silently renamed.
Set `GRID_REGISTRATION_ENABLED=false` to disable registration. An old local
`REGISTRY_DEMO_MODE=false` setting is still honored when the new setting is absent.
The prototype limit remains 100 grids per session.

Repeated submissions reuse the original session rather than duplicate grids.
Edits preserve before/after audit history, and stale edit forms cannot overwrite a
newer edit. Grid IDs, original session membership, snapshots and audit history
are protected in PostgreSQL; scientific records are read-only in Django admin.
All preparation measurements accept up to two decimal places. Displays omit unnecessary trailing zeros. Snapshots store decimal
strings with field names defining the units. Extra precision is rejected for
review rather than silently rounded. The two-place migration rounds existing disposable test measurements and
updates numeric suggestions to match; earlier snapshots retain their entered values.

### Preparation suggestions and registry display

**Box number** is beside Grid type and refers to the preparation grid box, not
physical storage. The separate neutral Grid type reference field is retained
until the meaning of the old workbook's parenthetical references is confirmed.

Preparation text, multiline and numeric fields offer **Previous values**. Click
that button to browse, or type to search the suggestions. Use arrow keys and Enter
to select, or keep typing an entirely new value. Saved values become reusable;
**Multiple blots** defaults to `0` and accepts non-negative whole numbers;
blank input becomes `0`, while negatives and fractions are rejected. Carbon descriptions are case-insensitive and
stored lowercase; glow atmosphere and polarity use capitalized words, with
case variants merged in suggestions. Suggestions only change
the selected field, so selecting a sample never silently fills its buffer or units.

To seed suggestions from a private workbook (no grids, sessions or owners imported):

```bash
python manage.py seed_preparation_suggestions private-data/Cryo-EM_grids_example.xlsx --dry-run
python manage.py seed_preparation_suggestions private-data/Cryo-EM_grids_example.xlsx
```

Seeding is repeatable. Raw source text and cell/checksum provenance stay in the
local database; private vocabulary is never committed as fixtures or source code.
Uncertain source humidity is not converted to a percentage. The old humidity
wording field has been removed. Formulas are not evaluated, and ambiguous grid-type
references do not become box numbers automatically.

In **Grids**, expand **Choose columns** to select any preparation or session
columns, show all, or reset to defaults. The browser remembers column preferences
separately for each account. Wide tables scroll horizontally; scientific data is
unaffected by display choices.

Use **Filter by property** to add one or more conditions: case-insensitive text
contains, inclusive numeric ranges, inclusive preparation/recording dates, or
boolean values where available. Multiple blot is a numeric range property.
Conditions combine with AND and the existing search. Filters work
on hidden columns too and remain in the URL when paging; **Clear filters** resets
the search. Invalid ranges show errors and no records, rather than silently
returning a broader result set. The prototype supports up to 20 filter conditions.

### Verify changes

Run all checks with:

```bash
python dev.py check
```

This prepares the local database if necessary, checks Django configuration and
missing migrations, runs the tests, and checks linting and formatting. It stops
at the first failed command. PostgreSQL stays running until `python dev.py stop`.

Django creates and removes a separate test database. The local database role
needs permission to create it; the prototype cluster's initial role has this.
Tests cover login, logout, CSRF, unsafe redirects, deactivated accounts, and
registry/admin access boundaries, atomic batch creation, independent grid
values, unknown/zero/false handling, audit integrity, retry safety, stale edits
and concurrent ID allocation. The custom user model is established in the
initial migration so later authentication changes retain stable user IDs.

For an exact recreation of the tested **Linux x86-64** environment, use
`conda create --prefix ./.conda --file environment-linux-64.lock` instead of the
YAML create command. Other platforms should resolve `environment.yml`. After an
intentional dependency update, regenerate the platform snapshot:

```bash
conda list --prefix ./.conda --explicit --md5 > environment-linux-64.lock
```

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

> Read AGENTS.md and docs/01–07. Implement roadmap Phases 0–1: a local Django/PostgreSQL prototype with login, owner administration, session registration, generated-grid table and individual grid editing. Preserve independent preparation values, immutable session defaults, stable identities and audit history. Use synthetic data with the agreed owner-prefixed ID sequence. Include model, service, permission and form tests. Demonstrate registration before adding physical storage and advanced table interactions.

## Working rule

Keep documentation updated when an implementation decision is approved. Schema changes should get a migration, a test, and a short explanation of impact on Excel import and future knowledge-base extension.

The preparation-field refinement on 2026-11-04 is an explicitly approved cleanup
of disposable prototype data: obsolete humidity wording and Double blot columns,
snapshot keys, suggestion entries and audit keys are removed without archival.
Existing blot booleans are not interpreted as counts; Multiple blots starts at `0`.
Snapshots move to version 3 and case variants are normalized. The migration briefly
suspends snapshot/audit guards inside its transaction and restores them afterward;
normal application edits still preserve immutable snapshots and audit history.

The Django model in `registry/models.py` is the authoritative field/type definition,
not a separate YAML configuration. Migrations apply those changes to PostgreSQL.
The current type table in `docs/02_SCHEMA_V0_1.md` is generated from that model:

```bash
python manage.py describe_grid_fields
python manage.py describe_grid_fields --update-docs
```

`python dev.py check` verifies that the generated reference still matches the model.
Model bounds in that table describe application validators; database constraints,
service rules and casing behavior are documented separately in the schema.
The registry Preparation date column shows only the local date; its full timestamp
is retained in the session and remains visible on the session detail screen.

### Browse preparation sessions

Use **Sessions** in the main navigation to browse preparations from all CCI staff.
Search by session number, owner name/code, operator login/full name, experiment or
project; optionally filter by owner and inclusive preparation dates. Results show
newest registrations first, include grid counts and link to session details.

Session labels are derived from existing fields: **Session 1 - rasi - 261104**.
The number is the existing internal session ID, `rasi` is the sample owner's code,
and `261104` is the preparation date in YYMMDD format, using the facility timezone
(Europe/Stockholm). Unknown historical dates display `undated`. The label is not a
new database identifier; foreign keys and immutable grid IDs remain unchanged.
Session detail retains the preparation time; browse tables show the date only.

### Delete a mistaken grid registration

From **Grids → View / edit**, scroll to the bottom and click the red **Delete**
button. The confirmation page identifies the grid, owner and session. Enter
**your own current account password**, then select **Delete grid**. No grid ID
needs to be typed again.
Cancel or simply viewing the page does not change records. Incorrect credentials
or a grid changed since opening the page prevent deletion.

Any active CCI staff member can perform this deliberate correction, independently
of preparation-edit grants. The record moves to **Grids → Deleted grids**, a
read-only archive in the same PostgreSQL database. Its scientific fields, session
link, original ID and history remain intact; actor/time and an audit entry record
the deletion. Main registry searches, session grids and active grid counts exclude
it. Session pages link to any deleted records. Grid IDs are never recycled, and
retrying the original session submission cannot recreate archived grids.

This archives a database record, not a physical disposal event. Accounts without
a usable local password cannot confirm deletion in this local-password prototype.
Passwords are neither stored in archive/audit entries nor echoed on failed forms.
The archive and grid data are read-only in both application services and ordinary
database updates. Django admin provides no bulk or hard-delete shortcut.

Previous-value suggestions are independent reusable vocabulary, so archiving a
grid does not erase a value already remembered there. Full restoration and a
permanent purge command are later work. Purging will need to preserve a minimal
identifier reservation so a removed ID can never be reused.


### Excel import and export

On **Grids**, apply search/property filters and choose **Export filtered grids to
Excel**. The download contains all matching active grids across every page, with
all preparation columns regardless of the browser's column-display preferences.
Grouped headings follow the original workbook: Info, Sample conditions, Grid
treatment, Freezing conditions, Experiment reference and Additional notes. A
repeating teal/purple/amber palette colours each heading and its data columns.
Individual parameters occupy separate columns; numeric measurements use two
fractional places. Supporting Owners and Sessions sheets preserve owner details,
explicit session membership and original session-default snapshots.

Any active CCI staff member can choose **Import Excel workbook**, upload a current
export, review the preview, then confirm within 20 minutes. Missing owners are
listed by name/code and created on confirmation. Import never creates accounts or
access grants. Known preparation operators are preserved; unknown logins stay
unknown and produce a warning. Every import records the importing staff member.
Unchanged records are skipped; conflicting IDs, owner details or session metadata
stop the entire import without overwriting anything. Archived IDs remain reserved.

This first format supports current registry exports (.xlsx, at most 5 MB/5,000
rows). It does not parse the original legacy combined-field workbook, store
physical locations/events, or restore complete audit history. It transfers a
selection of records, not a database backup. Keep exports private, for example
under the ignored `data/exports/` directory. No new dependencies or database
migration are required for this feature.

Copied-from relationships are excluded from the workbook. A filtered subset does
not need to include a source grid, and importing does not change existing links.


For hand entry, use **Import Excel workbook → Download a blank import template**.
Fill in Grids and Owners. The **Session** column accepts simple labels such as
`session-1` and `session-2`; rows with one label must describe the same preparation
and owner. Labels belong to the workbook and do not need to match existing session
numbers. Leave the supporting Sessions sheet empty (or remove it). Internal keys
are generated automatically; original shared defaults stay unknown instead of
being guessed from the first grid. Exported files retain their portable keys in a
hidden supporting column so ordinary re-imports still preserve session identity.

Preparation dates accept `YYYY-MM-DD` text or an Excel date cell, defaulting to
**12:00 Europe/Stockholm** on that date. Preview reports the default. Blank dates
remain unknown; full timestamps must include a UTC offset. The entire application
uses Europe/Stockholm for facility-local time; stored timestamps remain UTC-aware.
