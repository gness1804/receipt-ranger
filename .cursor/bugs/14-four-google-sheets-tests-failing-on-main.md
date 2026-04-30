---
github_issue: 68
---
# Four Google Sheets tests failing on main

## Working directory

`~/Desktop/receipt-ranger`

## Contents

Four tests in `tests/test_app.py` have been failing on `main` for a while (predate the Render migration; surfaced again during post-migration cleanup on 2026-04-29). The full pytest run shows 151 passing and 4 failing, all in Google Sheets / service account mocking territory:

- `tests/test_app.py::TestCheckGoogleSheetsSetup::test_missing_service_account_file` (line 194)
- `tests/test_app.py::TestUploadToGoogleSheets::test_skips_existing_receipts` (line 376)
- `tests/test_app.py::TestSheetsIntegration::test_get_all_existing_receipts` (line 561)
- `tests/test_app.py::TestSheetsIntegration::test_check_receipts_for_duplicates` (line 580)

### Why they appear to be failing

These look like stale tests left behind after a refactor of the sheets / credentials code, not real bugs in the app:

1. **`test_missing_service_account_file`** patches `sheets.os.path.exists` to return `False` and expects `check_google_sheets_setup()` to return `(False, "...not found...")`. The function appears to have been refactored to resolve credentials from env var first and fall back to the file (per the agent memory note: "Don't pre-check for service_account.json before calling get_gspread_client() — let the function handle credential resolution (env var first, then file)"). The pre-existence check the test mocks is no longer the path the function takes, so the function returns success regardless of the patched `os.path.exists`.

2. **`test_check_receipts_for_duplicates`** patches `sheets.get_all_existing_receipts` to return a one-item set, then calls `check_receipts_for_duplicates(mock_client, receipts)` and expects 1 duplicate. It returns 0, suggesting either the function's call signature/lookup strategy changed, or the patched function is no longer the one actually called.

3. The two `TestUploadToGoogleSheets::test_skips_existing_receipts` and `TestSheetsIntegration::test_get_all_existing_receipts` failures likely share the same root cause as 1 and 2 (drifted mocks vs current implementation).

A side note: at least one failure also surfaces an `AssertionError` deep inside the `dotenv` library's frame-walking code (`dotenv/main.py:309`), which suggests `load_dotenv()` is being called inside the function under test in a context where pytest's frame layout doesn't match what `dotenv` expects. This may be a separate dotenv/pytest interaction worth understanding, or just a downstream effect of the mocking issue.

### App-level impact

None observed. The application works correctly in production on Render. These are test-suite hygiene issues only — but they cause `pytest` to report 4 failures every run, which is noisy and erodes trust in the suite.

## Acceptance criteria

- All 4 failing tests pass on a clean `main` checkout
- Fix should update tests to match current implementation (preferred), not change app behavior just to satisfy the tests
- If a test is found to be testing a code path that no longer exists, the test should be deleted rather than rewritten to test something else
- Confirm no other tests regress as a result of the changes
- Note in the PR description what each test was actually testing before vs after, so future readers understand the drift
