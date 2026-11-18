# Product brief — CCI Cryo-EM Grid Registry

## Purpose

The Centre for Cellular Imaging (CCI) uses the registry to track cryo-EM grids from preparation through storage, screening, disposal or transfer to another laboratory. The web app gives staff a shared inventory, validates grid identifiers and storage assignments, and records changes to preparation data and physical custody. Staff can export filtered records to Excel.

## Users and responsibilities

- **Staff** can register sample owners, create sessions, edit active grids and record physical actions across the registry. The preparation operator identifies who prepared the grids. Each subsequent edit records its own actor.
- **Admins** have the same registry access and can also manage existing owners and grants. The host manages user accounts. Standalone installations use local Django accounts. The dashboard uses ORCID and manages account approval and roles.
- **Sample owners** are people or groups associated with samples. They can be recorded without a login account.
- **Pending, Researcher and disabled accounts** have no registry access. Owner grants are reserved for future access rules.

## Core workflows

1. **Register a preparation.** Select one sample owner, enter shared preparation parameters and create a batch of uniquely identified grids. Each grid gets its own copy of the preparation values. The original session snapshot is preserved.
2. **Edit an individual grid.** Update sample preparation or clipping from grid detail. Changes are audited. Missing storage is flagged for review, and unknown measurements remain distinct from zero or an explicit absence.
3. **Record storage and outcomes.** Assign or move a grid to a compatible free slot. Record screening with recovery or discard, direct discard, or transfer a gridbox and its contents to another laboratory. Physical actions retain their history.
4. **Find and export records.** Search and filter the grid registry, browse sessions and owners, or inspect gridboxes and pucks. Export the matching grid records with their preparation and storage information.
5. **Correct mistakes.** Eligible physical actions can be corrected while preserving their history. A mistaken registration can be archived separately from a physical discard. Sensitive actions require the authorized user to type `approve`.

See the [README walkthrough](../README.md#use-the-registry) for screen-by-screen instructions.

## Scope

The registry supports individual grid editing and current-format Excel export. Excel import is future work. Bulk editing, external researcher access and tracking after transfer are outside the current scope.

The [schema reference](02_SCHEMA_V1_0.md) describes the data rules. See the [storage rules](08_STORAGE_LOCATIONS.md) and [acceptance checks](06_ACCEPTANCE_TESTS.md) for inventory behavior and verification.
