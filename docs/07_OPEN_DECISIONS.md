# Open decisions and assumptions log

**Version:** v0.1  
**Date:** 2026-11-02

This is a **decision register**, not a requirement to answer everything before writing code. Resolve blocker items before dependent features; record agreed outcomes with dates and update associated docs.

| ID | Priority | Decision to confirm | Default until confirmed | Why it matters |
|---|---|---|---|---|
| D01 | Blocks ID generation | Operational grid numbering using generated owner codes (globally continuous vs per-owner; starting number; imported reservations) | New IDs shown as examples only; implement configurable locked per-owner counter after approval | Avoid collisions, unexpectedly changing numbering conventions |
| D02 | Blocks permissions | Can every CCI staff user edit all owners, or only owners with grants? | CCI staff view all; only admins or owner-granted staff edit | Prevent unintended modifications |
| D03 | Blocks location validation | Actual cryo storage hierarchy for **clipped** vs **unclipped** grids; which positions hold exactly one grid | Support nullable hierarchy levels and canonical position key; verify in pilot | Avoid false conflicts or double occupancy |
| D04 | Blocks humidity conversion | Is Excel humidity `1` = 100% relative humidity, 1%, or an instrument-specific fraction? | `humidity_raw="1"`, `humidity_percent=null` | Scientific integrity |
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
| Automatic owner codes | Four lowercase characters: two letters each from first/last name (`rasi`), then one name letter + two surname letters + digit (`rsi1`), one letter each + two digits (`rs10`), then one name letter + three digits (`r100`). Checked before suggestion and transactionally at save; fixed afterward; existing codes preserved. |
| Registration prototype | Preparation fields first; storage later. Login accounts represent CCI operators; sample owners are separate people/group records and need no account. DEMO identifiers only while D01 remains open. |
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
