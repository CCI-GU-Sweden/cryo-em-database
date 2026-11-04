# Acceptance criteria and testing scenarios

**Version:** v0.1  
**Purpose:** Clear definition of done for model, services, UI, import, and security.

## A. Registration and scientific parameters

- [ ] Admin enters an owner name, generates a currently unused code and saves; collisions use the agreed four-character lowercase substitution sequence. Concurrent registrations cannot duplicate codes, and name changes preserve assigned codes.
- [ ] Authorized CCI staff can create a PreparationSession with **one** owner, operator, optional reference, and entered common preparation parameters.
- [ ] Creating N grids generates **exactly N unique IDs** in one transaction; no IDs/rows generated on failure.
- [ ] Concurrent requests under the same owner prefix never create duplicate IDs.
- [ ] Grids inherit a **copy** of initial session defaults; modifying one grid does not change any other grid or the immutable session snapshot.
- [ ] Experiment reference and project reference can remain empty.
- [ ] New grid initially has `unclipped`, `awaiting_storage`, `not_imaged`, current location null.
- [ ] A user can modify individual preparation conditions in a detail form or authorized bulk table action; audit records preserve before/after values.
- [ ] Null concentration/temperature/humidity and other unknown values remain null, not zero.
- [ ] The UI groups glow discharge parameters but stores them separately and allows filtering/sorting numerically where appropriate.
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

- [ ] All authenticated CCI staff can view all owners and all grids.
- [ ] CCI admin can create/deactivate accounts, create owners, manage codes, and assign/revoke owner access grants.
- [ ] Non-admin CCI staff without a grant cannot edit a different owner's grid (unless broader staff editing is explicitly approved).
- [ ] Owner-granted editor can edit allowed preparation fields; operator can invoke allowed lifecycle actions but not change preparations.
- [ ] Unauthorized writes fail via detail page, table batch update, direct URL, and service endpoint.
- [ ] Request targeting multiple grids with a mix of authorized and unauthorized records does not silently modify the unauthorized records.
- [ ] Disabling a user immediately prevents further authenticated edits; existing event attribution remains intact.
- [ ] CSRF protection and session authorization work for every mutation.
- [ ] Changing an authentication backend later will not invalidate owner relationships or grants.

## D. Excel import and export

- [ ] Importer reads the exact multi-row header structure of `Cryo-EM_grids_example.xlsx`.
- [ ] Import preview identifies **8 populated grids** and skips identifier-only template rows.
- [ ] `Grid number` is preserved character-for-character and remains unique.
- [ ] Header columns AB/AC are correctly recognized from row 1 despite blank row-3 headings.
- [ ] Parsed example `Air, Negative, 15 mA, 20 s` yields 4 individual structured values.
- [ ] Parsed `6 mg/ml`, `3.5 µl`, `4 °C`, `4 s`, `0 s` yield correct typed values and units.
- [ ] Humidity `1` remains raw/unknown; no silent conversion to `1%` or `100%`.
- [ ] Blot force `0` remains zero and double blot `No` becomes false.
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

- [ ] Automated test suite passes in CI/local environment.
- [ ] Documented database migrations and local startup.
- [ ] Production environment does not expose debug pages or secrets.
- [ ] Backups are scheduled and **at least one restore is tested**.
- [ ] Basic audit and error logs available without leaking passwords/private records.
- [ ] Installation, owner creation, grant administration, and operational recovery documented.

## Registration slice validation (2026-11-03)

The automated registration tests cover owner code uniqueness, eight-grid creation,
independent edits, preserved snapshots, rollback including ID allocation, concurrent
DEMO batches, retries, stale edits, scientific validation, authorization via forms
and services, admin auditing and database history protection. These are scoped
prototype checks; the full criteria above remain the v0.1 release checklist.

Manual preparation-only pilot: add a synthetic owner, register eight grids, change
two blot times, compare the remaining six and original snapshot, then log in as a
second CCI member to verify visibility and Editor-grant behavior. Storage and
lifecycle scenarios are deferred to the next slice.

## Preparation suggestions, columns and filters (2026-11-03)

- Box number is editable beside Grid type, copied into independent grids and the
  versioned session snapshot, and is separate from storage.
- Concentration accepts three decimal places and omits unnecessary display zeros.
  Excess input precision is rejected; existing significant digits are protected
  during migration.
- Preparation fields suggest previous values while accepting novel entries.
  Private workbook suggestions are dry-run capable, idempotent and provenance-aware;
  they must not create physical records or convert unknown humidity to percentages.
- Staff can choose any registry preparation/session columns and retain their choice
  locally per account without changing data.
- Registry text filters use contains, numeric/date filters use inclusive bounds,
  and boolean filters distinguish Yes/No/Unknown. Multiple filters and free search
  combine with AND, including across pagination. Invalid fields and inverted ranges
  cannot expose arbitrary ORM lookups or silently broaden results.
