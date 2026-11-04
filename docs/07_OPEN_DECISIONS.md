# Open decisions and assumptions log

**Version:** v0.1  
**Date:** 2026-11-02

This is a **decision register**, not a requirement to answer everything before writing code. Resolve blocker items before dependent features; record agreed outcomes with dates and update associated docs.

| ID | Priority | Decision to confirm | Default until confirmed | Why it matters |
|---|---|---|---|---|
| D01 | Confirmed 2026-11-04 | Four-character sample-owner prefix, independent per-owner sequence: 0001–9999, a001–a999, b001–z999 | Locked allocation per owner; existing matching grid suffixes reserved; old IDs preserved; stop at z999 | Chronological generation order per owner without collisions or wraparound |
| D02 | Updated and confirmed 2026-11-04 | All active CCI staff may view/edit every active grid and import/export current Excel workbooks | Operator identity is attribution; edits and imports are audited; archive read-only | Simplify collaboration for six staff; external access remains deferred |
| D03 | Blocks location validation | Actual cryo storage hierarchy for **clipped** vs **unclipped** grids; which positions hold exactly one grid | Support nullable hierarchy levels and canonical position key; verify in pilot | Avoid false conflicts or double occupancy |
| D04 | Blocks humidity conversion | Is Excel humidity `1` = 100% relative humidity, 1%, or an instrument-specific fraction? | No humidity wording field; `humidity_percent=null` until source convention confirmed | Scientific integrity |
| D05 | Blocks precise field labeling | Meaning of parenthetical grid-type number (`191846`, `224782`) | `grid_type_reference` as neutral label | Avoid incorrectly calling it box/catalog number |
| D06 | Pilot clarification | Blot force scale/unit and whether negative values are possible | Decimal field, source text preserved, no conversion | Correct validation and labels |
| D07 | Migration | How many physical preparation sessions produced eight example grids? Exact dates/operators unknown. | Provisional legacy groupings explicitly labeled unverified, never infer from `JB002` alone | Real session relationship must not be fabricated |
| D08 | Before external access | Which researcher actions are permitted (view, storage, imaging, shipment)? | No external accounts in v0.1 | Prevent overbroad data modification |
| D09 | Before deployment | Which institutional login provider/SSO is viable? | Local Django users initially; identity adapter/OIDC later | International users / future portability |
| D10 | UX pilot | Preferred storage and clipping workflows: separate actions or one compound step? | Both available as explicit service actions; one UI dialog may combine atomically | Reduce clicks without losing history |
| D11 | Import policy | Should legacy `Copy of CCI-00001` notes become verified `copied_from_grid` references? | Preserve notes; do not auto-convert | Avoid inferring scientific ancestry incorrectly |
| D12 | Data model | Should sample owners be people only or also research groups? | Name/affiliation/code generic enough for both | Owner life cycle and future sharing |
| D13 | Event rules | Can imaged grids be returned to storage at CCI? Can shipped grids return? | Model permits later exceptions; don't assume imaging consumes or shipping discards | Real-world lifecycle flexibility |
| D14 | UX | Preferred bulk editing: direct inline table edit vs select-grids update wizard? | Start with safe selected-row update and table browsing, validate with staff | Ease of use and auditability |

## Decisions already confirmed

| Item | Decision |
|---|---|
| Import versus export permissions (2026-11-04) | Import, preview and blank templates require the active CCI staff flag, even for administrators. Export follows existing registry visibility and filters through one shared row-access boundary. No new browsing/read-only access is enabled in this change. |
| Facility time and date-only imports (2026-11-04) | Use Europe/Stockholm throughout the application. Date-only YYYY-MM-DD strings or Excel date cells default to 12:00 local time with the date's daylight-saving offset, reported in preview. Blank dates remain unknown; full timestamps require an offset. |
| Owner visibility and session creation (2026-11-04) | All CCI staff see every owner and can create sessions for any active owner without grants. Updated during Excel work: all active CCI staff may edit all active grids; operator identity is attribution only. |
| Staff owner registration (2026-11-04) | Active CCI staff can create sample owners through the registry without administration-site access. Updated during Excel work: no automatic grants are created because all active CCI staff share editing rights. Existing-owner/grant administration remains admin-only. |
| Current Excel transfer and shared editing (2026-11-04) | Any active CCI staff member may import/export and edit every active grid. Export follows registry filters across pages with grouped atomic columns and supporting Owners/Sessions sheets. Preview missing owners, conflicts and unknown operators; create missing owners on confirmation; preserve original known operator attribution; audit the importer. Hand entry uses plain file-local Session labels, with automatic internal keys and unknown defaults; exports hide portable keys in supporting metadata. Group colours cycle across related columns. No accounts/grants or overwrites. This supersedes earlier operator/Editor restrictions. |
| Individual grid deletion archive (2026-11-04) | All active CCI staff may archive a specific mistaken registration after reviewing the displayed grid and re-entering their own password; no typed ID is required. Use the same PostgreSQL database with a separate read-only Deleted grids area; preserve IDs/history and exclude records from normal views. Permanent purge tooling is deferred. |
| Session ownership | One sample owner per actual preparation session |
| Defaults | Preserve session snapshot and copy parameters into each new grid |
| Experiment reference | Optional |
| Project | Optional descriptive field, not core permissions container |
| Initial users | CCI staff only |
| Visibility | All CCI staff see all grids; future external users restricted |
| Registration | Enter shared fields once, specify number of grids, then edit generated individuals |
| Storage | Full movement history, including unclipped and clipped states |
| Imaging and shipment | Imaging usually leads to discard but no automatic inference; shipment means leaving CCI custody |
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
