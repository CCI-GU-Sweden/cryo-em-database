# Acceptance checks

Run `python dev.py check` for standalone verification and the [dashboard integration checks](09_DASHBOARD_INTEGRATION.md#review-before-deployment) for the installed module. The checklist describes expected behavior and manual release checks.

## A. Registration and scientific parameters

- [ ] CCI staff enter an owner name, generate a currently unused code and save; collisions use the agreed four-character lowercase substitution sequence. Concurrent registrations cannot duplicate codes, and name changes preserve assigned codes.
- [ ] Authorized CCI staff can create a PreparationSession with **one** owner, operator, optional reference, and entered common preparation parameters.
- [ ] Creating N grids generates **exactly N unique IDs** in one transaction; no IDs/rows generated on failure.
- [ ] Concurrent requests under the same owner prefix never create duplicate IDs.
- [ ] Grids inherit a **copy** of initial session defaults; modifying one grid does not change any other grid or the immutable session snapshot.
- [ ] Experiment reference and project reference can remain empty.
- [ ] New grid initially has `unclipped`, `not screened`, and no recorded location; until a box/slot is recorded its displayed status is `Unknown — needs review`.
- [ ] A user can modify individual preparation conditions in a detail form; audit records preserve before/after values.
- [ ] Unknown measurements remain null, not zero. Multiple blots defaults to 0.
- [ ] The UI groups glow discharge parameters but stores them separately and filters numerically; numeric sorting controls remain future UI work.
- [ ] Historical `CCI-00001` grid ID coexists with new owner-based ID without auto-renaming.

## B. Storage / clipping / imaging / transfer

- [ ] Storing an awaiting-storage grid creates a timestamped event and updates its current location.
- [ ] Moving an in-storage grid appends a new event, preserves old location and shows the new one as current.
- [ ] Cannot assign two available grids to the same uniquely identified physical slot, including under concurrent requests.
- [ ] Clipping records clip status and actor/time; optionally changing storage location is **atomic** with the clipping operation.
- [ ] An unclipped grid can be stored; a clipped grid can be stored; each uses appropriate location hierarchy without requiring nonexistent levels.
- [ ] Screening can be recorded only for a grid with a recorded box and slot; recording the screening outcome preserves that same location and does not make the slot available to another grid.
- [ ] `Screened and recovered` records the completed screening and keeps the grid at its original box and slot; staff do not select the location again.
- [ ] `Screened and discarded` records both screening and discard; `Discarded` records discard without screening. Both are terminal; an optional free-text discard reason is retained when supplied.
- [ ] Transferring a box containing grids through Location and storage actions makes each contained grid show `Transferred to [destination]` and removes it from the CCI inventory state.
- [ ] A grid with no recorded box/slot remains `Unknown — needs review`, not `In storage`.
- [ ] Screened/recovered, screened/discarded, discarded and transferred grids remain searchable; discarded and transferred grids are excluded from default available inventory.
- [ ] Export includes a readable lifecycle status; its final Excel formatting remains subject to UX review and must not rely on strikethrough alone.
- [ ] Invalid event transitions are rejected with useful errors; derived state cannot be directly edited via HTTP or table cells.
- [ ] Event timestamps are distinguished from audit recording times; legacy unknown dates remain unknown.

## C. User access and administration

- [ ] Active Staff and Admin users can view all owners and active grids, with archived records in a separate read-only area.
- [ ] CCI admin can manage accounts through the host and update existing owners or grants while preserving assigned owner codes.
- [ ] All active CCI staff may edit every active grid and export matching grid records, without owner grants. Registration for any active owner requires no grant.
- [ ] Owner grants are reserved for future external access and do not restrict internal CCI editing.
- [ ] Unauthorized writes fail via detail page, direct URL, and service calls.
- [ ] Disabling a user immediately prevents further authenticated edits; existing event attribution remains intact.
- [ ] CSRF protection and session authorization work for every mutation.
- [ ] Changing an authentication backend later will not invalidate owner relationships or grants.

## D. Excel and dashboard

- [ ] Export includes all matching grids across pages, with storage information and lifecycle status.
- [ ] Pending, Researcher and disabled users cannot access registry pages or dashboard metrics. Sensitive actions require typed `approve`.
- [ ] Verify ORCID login, the registry card and both inventory counts. Disabling the module removes its routes and card and preserves its data.

## E. UI/usability pilot

Ask a less technical staff member (without developer coaching) to:

1. [ ] Find a grid by ID or owner.
2. [ ] Create a preparation session with a sample owner, shared settings, and 8 new grids.
3. [ ] Adjust blotting time for only 2 of those 8 grids.
4. [ ] Enter unique storage locations for the new grids.
5. [ ] Clip one grid and move it to a new location.
6. [ ] Record a grid as screened and recovered to its original box/slot, then another as screened and discarded, and one discarded without screening with an optional reason.
7. [ ] Transfer a box containing a grid to another lab and find that grid later in search with the transfer destination.
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
