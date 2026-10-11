# Import manifest

- Source URL: `https://github.com/COMP5703-TUT04-GROUP02/WorkShop-AI.git`
- Source commit: `af12a84a0e06f38e9664784f859e3635aca78b44`
- Import date: `2026-10-09`
- Export method: `git archive` of the pinned tracked tree, extracted into a new directory.
- SHA verification: the temporary source clone's `HEAD` was verified as exactly `af12a84a0e06f38e9664784f859e3635aca78b44` before export.
- Isolation verification: no `.git`, `.env`, `*.pem`, or `*.sqlite*` paths existed before the new repository was initialised. Source Git objects, remotes, ignored uploads, local environments, and untracked files were not copied.

## Removed paths

- `.github/PULL_REQUEST_TEMPLATE.md`
- `pr-screenshots/` (all six reusable screenshots retained under the scenario names below)
- `docs/superpowers/plans/`
- `docs/superpowers/specs/`
- `CONTRIBUTING.md` (internal branch, Jira, pull-request, and merge instructions)

The README's internal contribution instructions and links to the removed contribution document were also removed. The documentation index's contribution link was removed.

## Screenshot relocation

| Original path | Product asset path |
| --- | --- |
| `pr-screenshots/01-verify-email.png` | `showcase/assets/product/account-verify-email.png` |
| `pr-screenshots/02-verify-phone.png` | `showcase/assets/product/account-verify-phone.png` |
| `pr-screenshots/03-change-password.png` | `showcase/assets/product/account-change-password.png` |
| `pr-screenshots/04-change-email.png` | `showcase/assets/product/account-change-email.png` |
| `pr-screenshots/ws-78-filter-panel-expanded.png` | `showcase/assets/product/provider-search-filters-expanded.png` |
| `pr-screenshots/ws-78-search-results-collapsed.png` | `showcase/assets/product/provider-search-results.png` |

The relocated screenshots retain their original bytes. Functional source, automated tests, database migrations, Docker configuration, API documentation, and the remaining product assets were retained. No remote was configured for the new repository.
