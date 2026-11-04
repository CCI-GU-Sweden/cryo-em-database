# Source Excel workbook — field map and migration plan

**Version:** v0.1  
**Source file inspected:** `Cryo-EM_grids_example.xlsx`  
**Sheet:** `Sheet1`  
**Used range:** `A1:AC724`  
**Header row:** 3 (rows 1–2 are grouped display headers)

## 1. Actual source observations

- **29 columns (A–AC)**.
- **Eight populated physical grid records**, row 4 (`CCI-00001`) through row 11 (`CCI-00008`).
- From row 12 onwards, the source has **pre-filled sequential grid numbers** and blank scientific data. Treat these as **reserved/blank template rows**, not actual grids.
- Existing populated grid owner (`Name`) is **`Jens`**; do not invent an owner code or map automatically to a login.
- Existing experiment references are **`JB002`**; this is **not proof** that the eight grids were made in one physical preparation session.
- All eight example records show **unclipped** storage position fields, but the clipped-storage fields and clipping dates are blank.
- The `Freeze date` source field is blank in the eight populated records; do not fabricate a preparation date.
- Humidity is entered as numeric **`1`**, with interpretation unresolved.
- Notes include `looked okay`, `looked great - collection`, `too thick ice - throw away`, and `Copy of CCI-00001` etc. These are **free-text remarks**, not reliable machine-executed state transitions.

## 2. Complete field map

| Excel | Exact row-3 header | Target / transformation | Import caveats |
|---|---|---|---|
| A | `Grid number` | `Grid.grid_number` | Keep literal string, no regeneration. Unique globally. |
| B | `Name` | `SampleOwner.name` via `PreparationSession.owner_id` | Owner account/code not inferred. |
| C | `Sample` | `Grid.sample_description` | Preserve original text, including annotations/IDs. |
| D | `Concentration` | `Grid.sample_concentration_value` + `_unit` | Parse `6 mg/ml` to `6`, `mg/mL`; retain raw value. |
| E | `Buffer` | `Grid.buffer_description` | Preserve full reagent list and pH as free text. |
| F | `Grid type (type, boxnumber)` | `Grid.grid_type` + `grid_type_reference` | The parenthetical number is ambiguous; do not label definitively as a catalogue/box number. |
| G | `Carbon (type, thickness)` | `Grid.carbon_description` + optional `carbon_thickness_nm` | `No` is not a thickness; keep text. |
| H | `Glow discharge (atmosphere, polarity, current, time)` | `glow_atmosphere`, `glow_polarity`, `glow_current_ma`, `glow_duration_s` | Example `Air, Negative, 15 mA, 20 s`. Parse conservatively. |
| I | `Amount` | `Grid.sample_volume_ul` | Example `3.5 µl`; normalize unit display only after verifying unit. |
| J | `Temperature` | `Grid.temperature_c` | Example `4 °C`. |
| K | `Humidity` | No active wording field; `humidity_percent` only after confirmation | Example `1` is ambiguous; **leave percentage null** and do not seed it. Original workbook remains private. |
| L | `Blot time` | `Grid.blot_time_s` | Example `4 s`. |
| M | `Hold time` | `Grid.hold_time_s` | Example `0 s`; zero is meaningful, not null. |
| N | `Blot force` | `Grid.blot_force` | Example `0`; force scale/unit needs clarification. |
| O | `Double blot` | Legacy boolean column is not a Multiple blot count | Do not infer counts; `Grid.multiple_blot` uses default 0 unless an explicit non-negative integer is supplied. |
| P | `Dewar` (unclipped) | `StorageLocation.dewar` for initial `stored` event | See parent group heading row 2. |
| Q | `Cane` (unclipped) | `StorageLocation.cane` | Numeric IDs can be converted to string safely. |
| R | `Puck (number/color)` (unclipped) | `StorageLocation.puck`, optional `puck_color` | Distinguish number versus color when present. |
| S | `Box (Boxslot)` (unclipped) | `StorageLocation.box` | Example `CCI-UC-001`; not the same as grid type reference. |
| T | `Grid slot` (unclipped) | `StorageLocation.slot` | Example positions 1–4. |
| U | `Freeze date` | `PreparationSession.prepared_at` **only if session membership verified** | Unknown in example; preserve grid-specific raw value if sessions are ambiguous. |
| V | `Dewar` (clipped) | `StorageLocation.dewar` for clipping/move event | Blank in examples. |
| W | `Cane` (clipped) | `StorageLocation.cane` | Blank in examples. |
| X | `Puck` (clipped) | `StorageLocation.puck` | Blank in examples. |
| Y | `Box (Boxslot)` (clipped) | `StorageLocation.box` | Blank in examples. |
| Z | `Grid slot` (clipped) | `StorageLocation.slot` | Blank in examples. |
| AA | `Clip date` | `GridEvent.occurred_at` (`clipped`) | Only record event if clipping supported by source evidence. |
| AB | *(blank row-3 cell; row-1 label `Experiment reference`)* | `PreparationSession.experiment_reference` where verified; otherwise preserve grid-level legacy metadata | Optional. Do not group sessions automatically from this alone. |
| AC | *(blank row-3 cell; row-1 label `Additional notes`)* | `Grid.notes` | Preserve literal text; do not infer disposal/imaging without confirmation. |

**Important:** Columns AB and AC have titles in row 1, while row 3 is blank. The importer should read the fixed positional mapping and/or handle this multirow header, rather than assume every field has a row-3 title.

## 3. Session identification during import

A preparation session is **one actual real-world preparation event**, not an arbitrary set of adjacent spreadsheet rows. The example lacks confirmed session dates/operator identity. `JB002` denotes an experiment reference but does not establish shared session membership. Therefore:

1. In dry-run, group **candidate** rows by owner/reference for staff review only.
2. Require an explicit **session assignment** or choose a documented **provisional legacy session** per imported grouping with `prepared_at = null` and `prepared_by = null`, clearly flagged as *unverified grouping*.
3. Never claim an imported provisional session is a verified same-day preparation session.
4. Preserve individual imported grid parameters exactly and separately, even if candidate records appear to share common values.
5. For unknown historical defaults, a session's snapshot may be a minimal empty or explicitly `legacy_unverified` snapshot; do not set shared scientific defaults from the first row and imply they applied to all.

If later staff confirm true session membership, create/adjust grouping through an audited correction process.

## 4. Physical event reconstruction

For the populated examples, initial *unclipped storage location* exists. Create one `stored` event per grid **only after the import strategy explicitly permits a historical event with unknown time and actor**. Set `occurred_at = null`, `performed_by = null`, `recorded_at` to import time, and capture the source row/column. Such events should display **'date unknown (imported)'**, not today's date as if the transfer happened today.

Do **not** create `clipped`, `imaged`, `discarded`, or `shipped` events based solely on remarks like `too thick ice - throw away` or `looked great - collection`. Treat these as notes until verified.

If source data contain *both* unclipped and clipped locations, create historical events only when sequence/evidence is sufficient. Unknown details must be explicitly marked unresolved for review.

## 5. Parsing rules

- **Conservative and reversible:** keep source workbook unchanged and retain original row/text values in a private import log/report.
- Preserve Unicode micro sign `µ`, degree symbol `°`, capitalization, spaces, and comments in the archival raw value.
- Use `Decimal` after safely extracting number and **verified** unit. Do not transform units silently.
- Empty ≠ zero ≠ false; map blanks to `null`, literal `0` to numeric zero, and `No` to boolean false only in a field whose semantics actually are boolean. The retired Double blot column must not be treated as an integer count.
- Use exact/controlled parser rules for composite columns. If a cell does not match expected pattern, flag `needs_review`, preserve raw text, and do not guess.
- Treat identifier strings as text, including leading zeroes (`CCI-00001`).
- Deduplicate by normalized `grid_number`, report conflicts with existing rows, and never silently overwrite existing grid records.
- Verify that each populated grid has enough physical/sample information to count as a real grid. A row with **only** a prefilled grid number must not be imported.

## 6. Import UX and technical behavior

1. Admin uploads private workbook or points importer to local data file.
2. **Dry-run** shows candidate physical rows, empty template rows skipped, known values, unresolved parsing and owner/session issues.
3. Admin resolves mapping decisions (or imports under flagged legacy grouping).
4. Transactional import inserts records, events, locations, and import provenance. Conflicts cause a clear report and no accidental overwrite.
5. Rerun of same source produces no duplicated grids or duplicate storage events; ideally use file checksum + row identity and/or per-record import keys.
6. Export can recreate a flat grid view, but historical event details may require an additional `GridEvents` export sheet/table.

## 7. Example import expectations

- `CCI-00001`: sample description `Appoferritin (100260, Q9408)` **exactly as written**, 6 mg/mL, glow discharge Air/Negative/15 mA/20 s, storage `CCI-large / 1 / 1 / CCI-UC-001 / 1`, note `looked okay`.
- `CCI-00002`: 3 mg/mL, 3 µl, notes `looked great - collection`.
- `CCI-00003`: grid type `Q-foil R2/2 Cu300 (224782)`; note `too thick ice - throw away` (note only; **not** a definitive disposal record).
- `CCI-00005` to `CCI-00008`: notes refer to copied earlier grids; do not automatically assert parent FK without an explicit verified rule.

## 8. Data privacy / Git

Do not commit the original workbook, raw import reports, or exported experimental records to a public repository. Place source data under a private ignored directory such as `data/raw/` and use synthetic redacted fixtures in tests.

## 9. Prototype vocabulary seeding (2026-11-03)

The separate `seed_preparation_suggestions` management command reads the same
private multirow workbook to seed optional preparation choices. It creates no
Grid, PreparationSession, SampleOwner or physical events. It conservatively parses
explicit units, preserves raw source/cell/checksum provenance locally, skips
identifier-only rows and formulas, reports unknown formats, and supports dry-run
and repeat execution. Ambiguous parenthetical grid references remain references;
they are not assigned to the new preparation box field without D05 confirmation.
The full migration/import workflow above remains future work.


## 10. Implemented current-format transfer (2026-11-04)

The sections above describe the original legacy workbook migration, which is
still deferred. The first implemented importer accepts the application's own
current export. It deliberately uses today's atomic fields rather than adding
compatibility with the old combined columns.

- Any active CCI staff member may export/import. Export uses the same search and
  property filters as the registry, includes all matching active rows across all
  pages and all preparation fields, and excludes archived grids.
- **Grids:** merged group headings in row 1 (Info, Sample conditions, Grid
  treatment, Freezing conditions, Experiment reference, Additional notes), unique
  atomic column headings in row 2, data from row 3. Numeric measurements are Excel
  numbers displayed with two fractional places; IDs/text remain literal text.
  A repeating teal/purple/amber palette links each group heading, column headings
  and pale data-cell backgrounds.
- **Owners:** row-1 headings; explicit owner code/name/affiliation/notes/active
  status. Missing owners are listed by name/code in preview and created only on
  confirmation. Existing code/profile conflicts reject the import. No login
  accounts or access grants are created.
- **Sessions:** optional for hand entry; row-1 headings link a visible Session
  label to a hidden portable UUID, snapshot schema version and original defaults JSON. Treat this as supporting transfer information; actual
  grid values stay in separate columns. Never infer sessions from owner/date alone.
- **Read me:** optional format marker and user instructions. When present, the
  marker must match; column headings must always match the template. Group decorations do not become scientific data.
- Operator login in Grids resolves to an existing account when possible. Missing
  logins stay unknown with a warning; no account is fabricated. All CCI staff can
  edit regardless of operator. Import audit records the acting staff member and
  preserves the original exported operator string.
- Date-only strings `YYYY-MM-DD` and date-only Excel cells default to 12:00 in
  `Europe/Stockholm`, with the offset for that date (including daylight saving).
  Preview reports this default. Full timestamps use ISO 8601 including a UTC offset;
  timestamps with a time but no offset are rejected. Blank historical dates remain
  unknown. Null numeric values remain unknown and explicit zero remains zero.
- A read-only preview validates owner/session consistency, scientific types and
  precision and duplicate/reserved IDs. Copied-from relationships are outside
  this workbook format; no source grid is needed to transfer a filtered subset.
  Identifier-only preallocated rows are skipped.
- Confirmation within 20 minutes rebuilds the plan against current database state
  and atomically creates owners, sessions, grids and import audit/provenance.
  Unchanged existing grids are skipped; conflicts stop the entire import. Imported
  IDs are reserved by existing uniqueness/allocation rules. Repeat import is safe.
- Limits: .xlsx, 5 MB compressed, 50 MB expanded, 5,000 data rows per worksheet.
  Formula/error cells are rejected; formula-like text is exported as literal text.
- This format transfers selected current records, not accounts, grants, deleted
  archives, physical events, audit history or a full database backup. New database
  internal row numbers/session display numbers may differ after transfer.


### Hand-made workbooks and plain session labels

The import page supplies a blank template. A colleague fills Grids and Owners,
using a simple **Session** label (`session-1`, `morning`, etc.) to explicitly group
one preparation. A label is required, up to 100 characters, case-insensitive and
local to that workbook. Do not infer sessions merely from owner/date/reference.
The Sessions worksheet may be left empty or omitted. Read me may be omitted;
when present, keep its template marker. New internal UUIDs are allocated automatically. If
original defaults are not supplied, use an explicitly unknown empty snapshot and
warn in preview; never copy a grid's actual values into alleged session defaults.

For a manual file imported again, its existing grid IDs may identify the explicitly
labelled group's previous session. Reject labels that combine IDs from different
existing sessions. Preserve existing metadata/defaults and reject conflicts. The
same label in a different file with entirely new grid IDs creates a new session,
even if owner/date/operator happen to match. Exported metadata takes precedence
and preserves portable identity without these manual-file matching rules.
