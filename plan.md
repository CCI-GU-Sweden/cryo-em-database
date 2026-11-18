# Project roadmap

The registry currently supports standalone development and installation as a dashboard module with ORCID sign-in. Preparation, storage, screening, transfers and Excel export have been exercised in the local dashboard workflow. See the [README](README.md) for current usage.

## Next milestone: dashboard deployment

- Review the dashboard registration change and the registry package pin with the dashboard maintainers.
- Verify a clean build and deployment using the target PostgreSQL configuration. Check migrations, static assets, ORCID sign-in, role enforcement and the registry workflow in the deployed environment.
- Agree on backup and recovery procedures and test a restore before keeping research records in the deployment.
- Gather staff feedback on routine preparation and inventory work. Complete the remaining native Windows checks for standalone use.

The [integration guide](docs/09_DASHBOARD_INTEGRATION.md) covers deployment setup. The [acceptance checks](docs/06_ACCEPTANCE_TESTS.md) describe what to verify.

## Future work

- Make it easier to find grids and preparation fields that need review.
- Evaluate bulk grid editing and placement against staff workflows.
- Define researcher access and ownership rules before enabling external access.
- Define how to handle off-site returns and repeated screening while preserving physical history.
- Develop and validate Excel import and cross-installation data transfer, including user attribution and legacy field conventions.
