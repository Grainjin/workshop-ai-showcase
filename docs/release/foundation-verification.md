# Foundation verification

The baseline is checked by three independent CI jobs in
`.github/workflows/ci.yml`. All actions use immutable commit references, all jobs
use Ubuntu 24.04, and the frontend uses Node 24.19.0 and the committed npm lockfile.

| Job | Required checks |
| --- | --- |
| `backend` | Fresh PostgreSQL migration upgrade, one-step downgrade and re-upgrade; onboarding pause, migration-owned Booking manifest and schema contracts; real customer/provider/admin booking API reads on migrated tables; Ruff over backend, tests and scripts; complete pytest suite. |
| `mobile` | `npm ci`; TypeScript; favourites, locations, provider search, payment, booking actions/service, reference prices, marketplace, booking attachments and IBAN regressions; production Expo Web export. |
| `public-copy` | Tracked-file publication policy; Gitleaks 8.24.3 over the checked-out working tree, with redacted findings and a failing exit code for leaks. |

The [secret-scanner setup action](https://github.com/gacts/gitleaks/blob/a606754f644d9def4dd7fed01c3962ba08863ca8/action.yml) is pinned to
`gacts/gitleaks@a606754f644d9def4dd7fed01c3962ba08863ca8`. Its automatic Git-history
scan is disabled so the explicit `dir` command checks the current published tree.
The scanner version is fixed independently of the action revision. The job needs
only read access to repository contents.

## Reproduce the checks

Install the declared Python requirements and provide a disposable PostgreSQL
database. Application test fixtures recreate their tables, so the database must
belong solely to the test run.

```sh
pip install -r backend/requirements.txt
export WORKSHOP_DATABASE_URL=postgresql+psycopg://workshop:workshop@localhost:5432/workshop_test
export WORKSHOP_REQUIRE_POSTGRES_MIGRATION_TESTS=1
python scripts/generate_jwt_keys.py
alembic upgrade head
alembic downgrade -1
alembic upgrade head
pytest tests/test_onboarding_pause_migration.py tests/test_model_migration_contract.py -v
ruff check backend tests scripts
pytest -q --durations=20
python scripts/check_public_copy.py .
```

The migration fixtures create and remove random test-owned PostgreSQL schemas.
They require schema creation permission. `WORKSHOP_MIGRATION_TEST_DATABASE_URL`
can point them to a separate disposable PostgreSQL database when application
fixtures use SQLite. The required-tests flag turns an unavailable PostgreSQL
contract into a failure instead of a skip.

The literal Booking column list in `migrations/contracts/booking_columns.json`
is independent of model metadata. Update it explicitly alongside future schema
migrations. This guards against the inherited initial migration creating a new
model column automatically and hiding a missing migration. The three-role HTTP
smoke fixture uses the migrated schema directly and forbids table recreation
after migration; it also checks unauthorized roles and customer ownership.

Payment retries create a replacement only after an explicit uncharged failure
without an external payment ID, transaction ID, checkout token, or checkout URL.
Provider-success mismatches, pending review, unknown responses, expired checkouts,
and initialization timeouts require reconciliation. Same-key requests retain the
original attempt; an expiry alone no longer authorizes another checkout.

```sh
cd frontend/mobile
npm ci
npm run typecheck
npm run test:ci
npm run build:web
```

Run the secret check on a clean checkout with Gitleaks 8.24.3:

```sh
gitleaks dir . --redact --no-banner --exit-code 1
```

## Baseline evidence before the final-review fix, 10 October 2026

The following results describe commit `9361c1d`, before the reconciliation,
policy and migration-contract changes. They are retained as historical baseline
evidence and do not establish verification of the final fix.

- Clean `npm ci` installed 576 packages using the committed lockfile; the lockfile
  is unchanged.
- TypeScript passed. All 58 tests in the ten frontend regression scripts passed,
  with no failures or skips.
- Production Expo Web export succeeded: 2,572 modules, 11 assets, one 3.4 MB
  JavaScript bundle, and the generated HTML, favicon and metadata in ignored
  `frontend/mobile/dist/`.
- A new PostgreSQL 17.4 database completed the Alembic upgrade/downgrade/upgrade
  sequence and ended at the single head `0018_booking_onboarding_pause`.
- All seven explicit PostgreSQL migration/model contract tests passed, including
  the five legacy partial-schema variants, with no failures or skips.
- The complete backend suite passed: 324 tests, no failures or skips. This run
  used SQLite application fixtures and real PostgreSQL migration contracts.
- A second complete backend run used PostgreSQL for both application fixtures
  and migration contracts: 324 passed, no failures or skips, in 385.77 seconds.
  Both runs reported one existing Redis deprecation warning.
- Ruff over `backend tests scripts` and the public-copy policy passed.
- Gitleaks 8.24.3 found no leaks in a tracked-tree export. The downloaded native
  binary archive matched the release's published SHA-256 checksum.
- Actionlint 1.7.7 accepted the workflow, and a parsed-workflow check confirmed
  the three required jobs and immutable references for every action.

## Final-review fix evidence, 10 October 2026

- The focused payment, publication-policy, and PostgreSQL migration/API suite
  passed all 138 tests without failures or skips.
- The complete backend suite passed all 401 tests with PostgreSQL application
  fixtures and real PostgreSQL migration contracts, without failures or skips,
  in 579.02 seconds. It reported the existing Redis deprecation warning.
- The standalone publication-policy suite passed all 54 tests. Ruff over
  `backend tests scripts`, the tracked-file scanner, and syntax checks for all
  seven retained capture helpers passed.
- The new disposable application database completed the migration
  upgrade/downgrade/upgrade sequence. The immutable column contract rejected a
  simulated future Booking model column without a manifest update.
- Gitleaks 8.24.3 found no leaks in a staged tracked-tree export.
- The screenshots under `docs/testing/` remain historical captures. Their
  functional paths and current prerequisites were reviewed; no new browser
  captures, live-vendor checks, or frontend export are claimed by this fix.

## Verification limits

Local checks use Python 3.13.5, Node 24.19.0 and PostgreSQL 17.4. CI declares
Python 3.12 and PostgreSQL 16. The workflow has not run on a hosted runner because
this repository has no configured remote. Existing Python requirement ranges and
PostgreSQL/Redis major-version image tags remain unchanged; this is not a fully
locked Python or container supply chain.

Local npm and PostgreSQL access initially failed inside the restricted runtime;
approved external access enabled the clean install and real database checks.
The local Anaconda pytest debugger plugin crashes during import, so local runs
disable plugin autoload and the debugging plugin while explicitly enabling the
AnyIO plugin to retain asynchronous test coverage. CI keeps normal plugin loading.
The npm install reports an existing UUID deprecation, and Expo reports a harmless
color-environment warning. These warnings did not fail their checks.

The production export confirms the application bundles successfully. It does not
verify deployed configuration, live vendors, interactive browser journeys or
runtime feature changes.
