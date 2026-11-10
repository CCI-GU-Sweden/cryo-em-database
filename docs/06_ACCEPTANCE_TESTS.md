# Acceptance criteria and testing scenarios

**Version:** v0.1\
**Last reviewed:** 2026-11-04\
**Purpose:** Clear definition of done for model, services, UI, import, and security.

## Current validation and remaining acceptance

The last full Linux/WSL run passed **128 tests**, Django checks, migration-drift
checks, the generated field reference, Ruff lint and formatting. Sixteen tests cover
launcher portability and stop/status handling, and a fresh temporary PostgreSQL cluster passed initialization,
authentication and shutdown with spaces/apostrophe in its path.

| Area | Evidence / remaining work |
|---|---|
| Preparation, IDs and edits | Automated model/service/HTTP/concurrency/migration tests; independent grid values and audit history covered |
| Shared CCI editing | Cross-operator edits audited; inactive/non-CCI rejection and archive protections tested |
| Current Excel format | Filtered all-page export, hand-entry labels, missing owners, conflicts, atomic/repeated imports, colour groups and noon/Stockholm defaults tested |
| Import/export permissions | Explicit CCI flag for import, including admins; export shares registry visibility and checks direct calls |
| Session Enter key | Targeted JavaScript event checks passed; normal suggestions/newlines/button activation retained |
| Native Windows | Colleague confirmed app startup and repeated stop; Ctrl+C also stopped PostgreSQL on that setup. Full check/login/data-retention/path-space acceptance remains pending |
| Physical handling | StorageLocation/GridEvent, occupancy and lifecycle actions not implemented |
| Release readiness | Shared deployment, CI automation, backup schedule and tested restore are not configured |

### Planned CCI storage acceptance (not yet implemented)

- The initial UI fixes Dewar 1 and Cane 1; data structures can support further
  dewars and canes without redesign. Puck colour is selected from the configured
  list, and a puck is identified by its colour within its cane.
- A puck can contain up to 12 physical gridboxes. A thirteenth assignment is
  rejected, including concurrent attempts; the position of a box within its puck
  is not recorded. A two-sided box counts once.
- A gridbox name identifies one physical box across the registry. Reusing an
  existing name selects that box, while creating a duplicate is rejected.
- Box inventory distinguishes in-stock, in-puck and discarded boxes from grid
  slot occupancy. A box in a puck counts against capacity even when empty; a box
  in stock does not. A vacated grid slot can hold another grid while retaining
  the earlier occupant's history, including across projects.
- Each box type determines the valid grid slots, their sides and clipping
  compatibility. The four supplied SVGs represent the initial layouts. Reject
  invalid slots, incompatible grids, and concurrent double occupancy server-side.
- Storage actions preserve history, actor and event time; a grid can occupy at
  most one current slot. Shipping or disposal frees the slot without erasing its
  history. Storage remains optional when grids are registered.

Sections A–F are the **full v0.1 acceptance checklist**, not a claim that every
feature is implemented or manually signed off. Current-format transfer tests are
separate from the unimplemented original legacy importer in section D. Detailed
slice checks below record the implemented behavior; the [roadmap](04_DEVELOPMENT_ROADMAP.md)
tracks remaining work. Do not mark Windows or the six-staff pilot complete without
actual feedback from those runs.

## A. Registration and scientific parameters

- [ ] CCI staff enter an owner name, generate a currently unused code and save; collisions use the agreed four-character lowercase substitution sequence. Concurrent registrations cannot duplicate codes, and name changes preserve assigned codes.
- [ ] Authorized CCI staff can create a PreparationSession with **one** owner, operator, optional reference, and entered common preparation parameters.
- [ ] Creating N grids generates **exactly N unique IDs** in one transaction; no IDs/rows generated on failure.
- [ ] Concurrent requests under the same owner prefix never create duplicate IDs.
- [ ] Grids inherit a **copy** of initial session defaults; modifying one grid does not change any other grid or the immutable session snapshot.
- [ ] Experiment reference and project reference can remain empty.
- [ ] New grid initially has `unclipped`, `awaiting_storage`, `not_imaged`, current location null. Today these are display placeholders; event-backed state is future work.
- [ ] A user can modify individual preparation conditions in a detail form or authorized bulk table action; audit records preserve before/after values.
- [ ] Unknown measurements remain null, not zero. Multiple blots explicitly defaults to 0; imported date-only values explicitly default to noon and blank dates remain unknown.
- [ ] The UI groups glow discharge parameters but stores them separately and filters numerically; numeric sorting controls remain future UI work.
- [ ] Historical `CCI-00001` grid ID coexists with new owner-based ID without auto-renaming.

## B. Storage / clipping / imaging / transfer

- [ ] Storing an awaiting-storage grid creates a timestamped event and updates its current location.
- [ ] Moving an in-storage grid appends a new event, preserves old location and shows the new one as current.
- [ ] Cannot assign two available grids to the same uniquely identified physical slot, including under concurrent requests.
- [ ] Clipping records clip status and actor/time; optionally changing storage location is **atomic** with the clipping operation.
- [ ] An unclipped grid can be stored; a clipped grid can be stored; each uses appropriate location hierarchy without requiring nonexistent levels.
- [ ] Removed-for-imaging grid becomes unavailable in the `Stored at CCI` inventory, but retains its history.
- [ ] Imaging records an event and `imaged` state; it does **not** automatically discard the grid.
- [ ] Separate discard event marks grid permanently unavailable; a grid can also be discarded without imaging.
- [ ] Shipping records an external destination and sets `off_site` status; it does not imply imaging/discard.
- [ ] Shipped and discarded grids remain searchable but are excluded from the default available-inventory filter.
- [ ] Invalid event transitions are rejected with useful errors; derived state cannot be directly edited via HTTP or table cells.
- [ ] Event timestamps are distinguished from audit recording times; legacy unknown dates remain unknown.

## C. User access and administration

- [ ] All active CCI staff and facility superusers can view all owners and active grids, with archived records in a separate read-only area.
- [ ] CCI admin can create/deactivate accounts, create owners, manage codes, and assign/revoke owner access grants.
- [ ] All active CCI staff may edit every active grid and import/export current workbooks, without owner grants. Registration for any active owner requires no grant.
- [ ] Owner grants are reserved for future external access and do not restrict internal CCI editing.
- [ ] Unauthorized writes fail via detail page, table batch update, direct URL, and service endpoint.
- [ ] Request targeting multiple grids with a mix of authorized and unauthorized records does not silently modify the unauthorized records.
- [ ] Disabling a user immediately prevents further authenticated edits; existing event attribution remains intact.
- [ ] CSRF protection and session authorization work for every mutation.
- [ ] Changing an authentication backend later will not invalidate owner relationships or grants.

## D. Original legacy workbook migration and full export (not implemented)

This section covers the original private workbook and future physical/history
export. It is not the contract for the implemented atomic-column XLSX format;
see Current-format Excel and shared CCI editing below.

- [ ] Importer reads the exact multi-row header structure of `Cryo-EM_grids_example.xlsx`.
- [ ] Import preview identifies **8 populated grids** and skips identifier-only template rows.
- [ ] `Grid number` is preserved character-for-character and remains unique.
- [ ] Header columns AB/AC are correctly recognized from row 1 despite blank row-3 headings.
- [ ] Parsed example `Air, Negative, 15 mA, 20 s` yields 4 individual structured values.
- [ ] Parsed `6 mg/ml`, `3.5 µl`, `4 °C`, `4 s`, `0 s` yield correct typed values and units.
- [ ] Humidity `1` remains raw/unknown; no silent conversion to `1%` or `100%`.
- [ ] Blot force `0` remains zero; legacy Double blot wording does not become an inferred count. Multiple blots defaults to 0 or an explicitly entered non-negative integer.
- [ ] Unknown freeze dates and historical operators stay unknown, rather than today's date/current user.
- [ ] Source notes are retained verbatim. `too thick ice - throw away` does not automatically set discarded status.
- [ ] `JB002` is preserved without inventing a verified preparation session.
- [ ] Import can be run twice safely without duplicate grid records/events.
- [ ] Errors, parsing ambiguity, and duplicate IDs are visible in a reviewable import report.
- [ ] Export includes scientific fields and current state, plus full events in a separate export when requested.

## E. UI/usability pilot

Ask a less technical staff member (without developer coaching) to:

1. [ ] Find a grid by ID or owner.
2. [ ] Create a preparation session with a sample owner, shared settings, and 8 new grids.
3. [ ] Adjust blotting time for only 2 of those 8 grids.
4. [ ] Enter unique storage locations for the new grids.
5. [ ] Clip one grid and move it to a new location.
6. [ ] Record another grid as imaged and then discarded.
7. [ ] Ship a grid to an external site and find it later in search.
8. [ ] Export a filtered set of grids.

Capture usability notes and errors; prioritize removing friction before adding AI or other large features.

## F. Deployment readiness

- [x] A colleague confirmed native Windows app startup and repeated `python dev.py stop`.
  On that setup, Ctrl+C stopped both the app and PostgreSQL; already-stopped handling worked.
- [ ] Complete remaining native Windows acceptance: full `python dev.py check`,
  login, paths with spaces, and settings/data retention across subsequent starts.
- [ ] Stop/status handle an uninitialized or stopped checkout without a traceback.
  Repeat stop succeeds; permission/directory errors and a still-running server
  after failed shutdown remain failures. No unrelated cluster or PID file is changed.
- [ ] Automated test suite passes in CI/local environment.
- [ ] Documented database migrations and local startup.
- [ ] Production environment does not expose debug pages or secrets.
- [ ] Backups are scheduled and **at least one restore is tested**.
- [ ] Basic audit and error logs available without leaking passwords/private records.
- [ ] Installation, owner creation, grant administration, and operational recovery documented.

## Registration slice validation (2026-11-03)

The automated registration tests cover owner code uniqueness, eight-grid creation,
independent edits, preserved snapshots, rollback including ID allocation, concurrent
owner-prefixed batches, retries, stale edits, scientific validation, authorization via forms
and services, admin auditing and database history protection. These are scoped
prototype checks; the full criteria above remain the v0.1 release checklist.

Manual preparation-only pilot: add a synthetic owner, register eight grids, change
two blot times, compare the remaining six and original snapshot, then log in as a
second CCI member to verify shared editing and audit attribution. Storage and
lifecycle scenarios are deferred to the next slice.

## Preparation suggestions, columns and filters (2026-11-03)

- Box number is editable beside Grid type, copied into independent grids and the
  versioned session snapshot, and is separate from storage.
- Concentration omits unnecessary display zeros. The initial three-decimal input
  limit was replaced by the two-decimal policy below on 2026-11-04.
- Preparation fields suggest previous values while accepting novel entries.
  Private workbook suggestions are dry-run capable, idempotent and provenance-aware;
  they must not create physical records or convert unknown humidity to percentages.
- Staff can choose any registry preparation/session columns and retain their choice
  locally per account without changing data.
- Registry text filters use contains, numeric/date filters use inclusive bounds,
  and boolean filters distinguish Yes/No/Unknown. Multiple filters and free search
  combine with AND, including across pagination. Invalid fields and inverted ranges
  cannot expose arbitrary ORM lookups or silently broaden results.

## Staff owner registration (2026-11-04)

- Active CCI staff can generate a code and register a new owner without Django
  administration-site access or any existing owner grant.
- Owner creation is audited with the staff actor. No automatic grants are needed;
  all active CCI staff can immediately create sessions and edit active grids.
- No users receive automatic grants. Existing owners/grants cannot be
  changed through this creation endpoint, including via forged form fields.
- Anonymous, inactive and non-CCI accounts cannot register owners. CSRF is required.
- Administrative editing of existing owners and management of other grants remain
  restricted to facility administrators.

## Owner visibility and registration follow-up (2026-11-04)

- All CCI members can search the directory of active/inactive owners and see all
  active owners in the new-session selector, including owners created by colleagues.
- Staff without owner grants can create a session for any active owner and edit
  their own newly generated grids. This does not create an owner-wide grant.
- Another active CCI staff member can edit those grids without an Editor grant;
  inactive owners are excluded from new session registration and inactive users are denied.

## Owner-based identifiers (2026-11-04)

- Each owner starts independently at 0001; sessions continue the same owner counter.
- Numeric and letter rollover are correct, including batches crossing a boundary.
- The suffix stays four lowercase characters through z999. Exhausted batches fail
  atomically without consuming IDs or creating partial sessions/grids/audit entries.
- Counter allocation and duplicate retries are safe under concurrent requests.
- Existing CCI/DEMO identifiers remain unchanged, and recognized owner-prefixed
  historical IDs reserve their suffixes before subsequent generation.
- Legacy owner codes are never silently reformatted to enable generation.

## Preparation-field refinement (2026-11-04)

- Carbon case variants share lowercase storage/suggestions; glow atmosphere and
  polarity share capitalized-word storage/suggestions, without altering other text.
- Humidity wording is absent from model, form, table, suggestions and new snapshots.
- Multiple blots defaults to 0; blank input also becomes 0. Accept non-negative
  integers and reject negative, fractional and boolean input. Reject negative
  values in the database as well.
- Disposable test-data migration removes retired fields/keys, resets old blot
  booleans to the requested default 0, updates snapshot version, and restores both history
  guards. A populated migration test verifies cleanup and immutable behavior afterward.

## Measurement precision and registry date display (2026-11-04)

- All ten Grid DecimalFields use two decimal places and reject excess-precision
  new input. Existing disposable test values are rounded by the approved migration.
- Numeric suggestions are rounded/deduplicated consistently with the new inputs.
- Preparation dates in the registry show date only; stored time and session-detail
  display keep the full timestamp. Date-range filtering remains unchanged.
- The generated field/type reference matches the authoritative Django model.

## Session naming and browsing (2026-11-04)

- Session names use the existing session number, owner code and facility-local
  preparation date: `Session 1 - rasi - 261104`. Unknown dates use `undated`.
- Navigation includes a Sessions page, visible to all active CCI staff, with grid
  counts, detail links, search by owner/operator/reference/session number and
  owner/date filters. Invalid ranges fail clearly and pagination retains filters.
- Display naming handles timezone boundaries and does not modify stored timestamps,
  snapshots, IDs or audit history. Anonymous/non-CCI/inactive users cannot browse.

## Password-confirmed deletion archive (2026-11-04)

- Grid detail ends with a red Delete button, followed by a distinct confirmation
  showing the grid ID/owner/session and requiring only the actor's own password
  (no typed grid ID). GET/Cancel never mutate.
- Active CCI staff can archive individual grids even without owner editor grants;
  non-CCI, inactive and anonymous accounts are denied. Unusable-password accounts,
  incorrect passwords, missing CSRF and stale versions cannot archive records.
- Deletion atomically preserves scientific data and session history, creates one
  DeletedGrid marker and one AuditEvent, and increments the edit version. Audit
  failure rolls everything back; concurrent/repeated confirmations are idempotent.
- Active registry searches/filters, normal detail URLs, session rows/counts and
  admin Grid views exclude deleted records. A separate read-only archive supports
  inspection with actor/time, search and session filtering.
- Archived records cannot be edited through old endpoints, services or normal SQL
  updates; archive markers and IDs are immutable. IDs stay reserved and original
  batch retries do not recreate archived grids. No password enters history or
  rendered form responses. No physical disposal event is inferred.
- Permanent purge and restore remain deferred; any future purge must retain ID
  reservations instead of making historical IDs available for reuse.


## Current-format Excel and shared CCI editing (2026-11-04)

- Import/preview/template routes and services require current CCI membership,
  even for administrators. Revoked flags on stale actor objects cannot authorize
  import. Accounts with registry viewing access can export their visible filtered
  subset without import rights; direct callers cannot expand that subset.
- New-session inputs do not implicitly submit on Enter. Suggestion selection,
  textarea newlines and deliberate keyboard/button activation still work.
- All active CCI staff can edit every active grid via form and direct service,
  regardless of owner/operator/grants. Every edit records actor/time/before/after;
  stale versions and scientific validation still apply. Archived records,
  non-CCI/inactive accounts and administration restrictions remain protected.
- Filtered export includes all pages, excludes archives, and supplies all current
  atomic preparation columns with original-style grouped headings. Numeric cells
  retain values/units; text beginning '=' remains literal text.
- Owners/Sessions sheets preserve explicit codes, session UUIDs, metadata and
  original default snapshots independently of individually changed actual values.
- Read-only import preview lists new owners, grid/session counts, unchanged rows,
  skipped blank rows, warnings and row-numbered validation errors.
- Confirmation requires staff access, CSRF, the actor's current server-side preview
  token and an unexpired preview. Recheck conflicts when confirming.
- Missing owners are created with workbook name/code and no account/grants. Owner
  conflicts, duplicate/reserved IDs, inconsistent sessions, excess precision,
  negative constrained measurements and formulas cannot partially import data.
- Repeated imports skip unchanged grids. Failures roll back owners, sessions, grids
  and audit. Imported IDs cannot be allocated again by normal registration.
- Known operator accounts are preserved; unknown operator/date remain unknown,
  without assigning preparation to the importer. Import audit identifies the
  actual uploader and retains source filename/checksum/worksheet/row values.
- Malformed/oversized workbooks and expired confirmations return useful errors.
  Legacy combined-field files are outside this first format's scope.


## Hand entry and workbook group colours

- Date-only strings and Excel date cells default to noon in Europe/Stockholm,
  including correct winter/summer offsets independently of a viewer's timezone.
  Blank dates remain unknown; invalid dates and full times without offsets fail.
- Copied-from relationships are excluded from Excel columns and import matching.
  A subset can be re-imported without its source grid; existing links are untouched.
- Staff can download a blank template and enter plain Session labels without
  generating UUIDs or writing JSON. Sessions metadata may be omitted.
- Labels explicitly group rows within one file. New sessions receive internal keys
  automatically and unknown defaults remain unknown; preview warns about this.
- A manual re-import recognises existing grid/session relationships despite file
  checksum changes. Reusing a label for entirely new grid IDs creates a separate
  session. One label cannot combine different existing sessions.
- Exported portable keys remain authoritative and hidden in the supporting sheet.
- Teal/purple/amber group colours cycle across merged headings, column headings
  and pale data cells. Styling does not affect values or import parsing.
