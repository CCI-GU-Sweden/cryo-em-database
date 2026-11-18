# Open decisions and assumptions log

**Version:** v0.1\
**Last reviewed:** 2026-11-16

This is a **decision register**, not a requirement to answer everything before writing code. Resolve blocker items before dependent features; record agreed outcomes with dates and update associated docs.

| ID | Priority | Decision to confirm | Default until confirmed | Why it matters |
|---|---|---|---|---|
| D01 | Confirmed 2026-11-04 | Four-character sample-owner prefix, independent per-owner sequence: 0001–9999, a001–a999, b001–z999 | Locked allocation per owner; existing matching grid suffixes reserved; old IDs preserved; stop at z999 | Chronological generation order per owner without collisions or wraparound |
| D02 | Updated and confirmed 2026-11-04 | All active CCI staff may view/edit every active grid and import/export current Excel workbooks | Operator identity is attribution; edits and imports are audited; archive read-only | Simplify collaboration for six staff; external access remains deferred |
| D03 | Confirmed 2026-11-10; details open | CCI storage hierarchy and gridbox layouts | Dewar → Cane → Puck → Gridbox → Gridslot; enforce valid slots, clipping compatibility, unique occupancy and a maximum of 12 boxes per puck. See [storage requirements](08_STORAGE_LOCATIONS.md). | Avoid false conflicts or double occupancy; name normalization and box movement/retirement remain open |
| D04 | Blocks humidity conversion | Is Excel humidity `1` = 100% relative humidity, 1%, or an instrument-specific fraction? | No humidity wording field; `humidity_percent=null` until source convention confirmed | Scientific integrity |
| D05 | Open for legacy import | Meaning of parenthetical grid-type number (`191846`, `224782`) | Do not assign it to Batch; Grid type reference removed following staff feedback | Avoid incorrectly calling it box/catalog number |
| D06 | Pilot clarification | Blot force scale/unit and whether negative values are possible | Decimal field, source text preserved, no conversion | Correct validation and labels |
| D07 | Migration | How many physical preparation sessions produced eight example grids? Exact dates/operators unknown. | Provisional legacy groupings explicitly labeled unverified, never infer from `JB002` alone | Real session relationship must not be fabricated |
| D08 | Before external access | Which researcher actions are permitted (view, storage, imaging, shipment)? | No external accounts in v0.1 | Prevent overbroad data modification |
| D09 | Confirmed 2026-11-16 | Deployment login and shared user management | Dashboard-managed ORCID login, approval and Pending/Researcher/Staff/Admin roles. Standalone development retains local login with the same roles. See [plan](../plan.md). | One registry module and two supported hosts |
| D10 | UX pilot | Preferred storage and clipping workflows: separate actions or one compound step? | Grids are normally stored immediately and may be clipped first; show missing storage for review. A combined workflow may record distinct physical events; exact interaction remains open. | Reduce clicks without losing history |
| D11 | Future legacy import policy | Should legacy `Copy of CCI-00001` notes become verified `copied_from_grid` references? | Preserve notes; no auto-conversion. Copied-from links are excluded from the current UI/Excel format | Avoid inferring scientific ancestry incorrectly |
| D12 | Data model | Should sample owners be people only or also research groups? | Name/affiliation/code generic enough for both | Owner life cycle and future sharing |
| D13 | Partly confirmed 2026-11-16 | What are the screening, recovery and disposition outcomes? Can transferred/discarded grids return? | Screening starts from a recorded slot and recovery keeps that slot. Mistaken latest screening/discard actions can be corrected with password and reason; actual returns after transfer/discard and repeated screenings remain open. Do not infer disposal from screening or transfer. | Real-world lifecycle flexibility |
| D14 | UX | Preferred bulk editing: direct inline table edit vs select-grids update wizard? | Individual edit forms are implemented; choose a bulk workflow after staff review | Ease of use and auditability |
| D15 | Partly confirmed 2026-11-10 | Box placement, transfer, discard and corrections | Preserve identity/history; reject discard while occupied; record external destination/time and remove transferred boxes from active CCI inventory. Corrections and off-site returns remain open. | Reusable boxes, capacity and safe inventory handling |

## Decisions already confirmed

| Item | Decision |
|---|---|
| Dashboard integration (2026-11-16) | Follow [plan.md](../plan.md). Stage 1 aligns local roles one-to-one with the dashboard and replaces sensitive-action password re-entry with typed lowercase `approve`. Initially only active Staff/Admin users have registry access. Confirmation prevents accidental actions and does not reauthenticate. Required correction reasons and server authorization remain. Production starts with clean registry data/default locations; future backup/restore or API/Excel transfers are separate work. These decisions supersede older CCI-flag/password/SSO proposals; implementation is pending. |
| Unknown and device defaults (2026-11-06) | Use Unknown for missing or unverified values; None means confirmed absence. New-session forms prefill Quorum – GloCube+ for glow discharge and Vitrobot Mark IV for freezing, with editable values and blank meaning Unknown. Existing grids and imports with no device remain Unknown. Future screening for values needing review is tracked in #10. |
| Local stop/status behavior (2026-11-04) | Operate only on this checkout's cluster. Stop succeeds when uninitialized/already stopped, checks pg_ctl status codes, preserves genuine errors and never manually deletes PID/data files. A colleague confirmed that Ctrl+C stopped both app and PostgreSQL on the tested Windows setup, followed by successful repeated stop. The exact process/console mechanism was not investigated. |
| Local Windows launcher (2026-11-04) | Resolve PostgreSQL/Ruff inside the active Conda environment, handle Windows password-file reopening and avoid Unix socket arguments there. No environment/dependency changes. Layout tests and Linux integration pass; colleague confirmed native startup/repeated stop. Full Windows check and remaining acceptance are pending. |
| Copy relationships in Excel (2026-11-04) | Remove Copied from grid ID from exports, templates and importer logic. Existing internal links are retained, not transferred or inferred. The copying workflow remains deferred. |
| Git review workflow | For features, push a branch and provide the GitHub compare link with Markdown PR title/description. The user creates PRs through the website. Documentation-only work may go directly to main when explicitly authorized. |
| Import versus export permissions (2026-11-04) | Import, preview and blank templates require the active CCI staff flag, even for administrators. Export follows existing registry visibility and filters through one shared row-access boundary. No new browsing/read-only access is enabled in this change. |
| Facility time and date-only imports (2026-11-04) | Use Europe/Stockholm throughout the application. Date-only YYYY-MM-DD strings or Excel date cells default to 12:00 local time with the date's daylight-saving offset, reported in preview. Blank dates remain unknown; full timestamps require an offset. |
| Owner visibility and session creation (2026-11-04) | All CCI staff see every owner and can create sessions for any active owner without grants. Updated during Excel work: all active CCI staff may edit all active grids; operator identity is attribution only. |
| Staff owner registration (2026-11-04) | Active CCI staff can create sample owners through the registry without administration-site access. Updated during Excel work: no automatic grants are created because all active CCI staff share editing rights. Existing-owner/grant administration remains admin-only. |
| Current Excel transfer and shared editing (2026-11-04) | Any active CCI staff member may import/export and edit every active grid. Export follows registry filters across pages with grouped atomic columns and supporting Owners/Sessions sheets. Preview missing owners, conflicts and unknown operators; create missing owners on confirmation; preserve original known operator attribution; audit the importer. Hand entry uses plain file-local Session labels, with automatic internal keys and unknown defaults; exports hide portable keys in supporting metadata. Group colours cycle across related columns. No accounts/grants or overwrites. This supersedes earlier operator/Editor restrictions. |
| Grid screening and disposition outcomes (2026-11-16; issue #18) | The grid detail status actions record screening and discard as physical events. Status values are `In storage`, `Screened and recovered`, `Screened and discarded`, `Discarded`, `Transferred`, `Deleted`, and `Unknown — needs review`. Screening starts from a recorded slot and recovery keeps that slot; discard can include an optional reason. The box transfer action supplies the destination. Excel export includes a readable Grid status column. |
| Individual grid deletion archive (2026-11-04) | All active CCI staff may archive a specific mistaken registration after reviewing the displayed grid and re-entering their own password; no typed ID is required. Use the same PostgreSQL database with a separate read-only Deleted grids area; preserve IDs/history and exclude records from normal views. Permanent purge tooling is deferred. |
| Session ownership | One sample owner per actual preparation session |
| Defaults | Preserve session snapshot and copy parameters into each new grid |
| Experiment reference | Optional |
| Project | Optional descriptive field, not core permissions container |
| Initial users | CCI staff only |
| Visibility | All CCI staff see all grids; future external users restricted |
| Registration | Enter shared fields once, specify number of grids, then edit generated individuals |
| Storage | Full movement history, including unclipped and clipped states |
| Imaging and shipment | Screening does not imply discard. Box transfer means the contained grids leave CCI custody; see the issue #18 lifecycle plan above. |
| Input styles | Web forms and spreadsheet-like table |
| Existing IDs | Keep historical CCI IDs, allow future owner-prefix IDs |
| Authentication | Replaceable; local accounts acceptable for initial deployment |
| Preparation wording and counts (2026-11-04) | Carbon casing is normalized lowercase; glow atmosphere/polarity use capitalized words. Remove humidity wording. Replace Double blot with non-negative-integer Multiple blots, default 0. Explicitly approved cleanup of existing disposable test fields/snapshots, with no inferred historical counts. |
| Grid identifiers (2026-11-04) | Owner code + hyphen + four-character suffix, with a separate sequence per owner: 0001–9999, a001–z999. Stop when exhausted; preserve all existing IDs. |
| Automatic owner codes | Four lowercase characters: two letters each from first/last name (`rasi`), then one name letter + two surname letters + digit (`rsi1`), one letter each + two digits (`rs10`), then one name letter + three digits (`r100`). Checked before suggestion and transactionally at save; fixed afterward; existing codes preserved. |
| Registration prototype | Preparation fields first; storage later. Login accounts represent CCI operators; sample owners are separate people/group records and need no account. Owner-prefixed IDs follow the confirmed D01 rule; earlier DEMO identifiers are preserved. |
| Prototype delivery (2026-11-03) | Local Django/PostgreSQL prototype; forms and simple table first, storage next, advanced UI after workflow review; synthetic data until operational readiness |
| Future extensibility | OMERO, evidence, protocol documents, local LLM extraction, protocols.io later |

## Record format for subsequent decisions

```text
Decision ID:
Date:
Decided by:
Final choice:
Reason:
Affected documentation / migrations:
Tests required:
```

## Box inventory decisions (2026-11-10)

- A box containing any grid cannot be discarded. Empty boxes may be discarded;
  retain the box identity and history.
- Box movements preserve identity and contents. Box events retain source and
  destination pucks so future grid history can resolve physical movement.
- External transfers record receiving laboratory/destination and time; transferred
  boxes leave the active CCI inventory but remain inspectable. Off-site tracking
  and returns are deferred. Grid custody synchronization is required before grid
  placement is enabled.
