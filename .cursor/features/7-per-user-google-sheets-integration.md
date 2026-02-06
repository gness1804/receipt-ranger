---
github_issue: 19
---
# Per-User Google Sheets Integration

## Working directory

`~/Desktop/receipt-ranger`

## Contents

Currently, Google Sheets integration is disabled on the production deployment (via the `ENABLE_GOOGLE_SHEETS` env var) because the app uses a single hardcoded service account (`service_account.json`) and spreadsheet name (`receipt-ranger`). Any public user would write to the owner's personal Google Sheet.

This feature should implement a system where each user can optionally set up their own Google Sheets integration.

## Background

Three options were evaluated. The user's preferred option is **Option 2**.

### Option 1: Disable Google Sheets on Public Deployment

- **Status:** Already implemented (v0.6.0) as a stopgap.
- **Pros:** Simple, no security risk.
- **Cons:** Feature is unavailable to all public users. Only works locally.

### Option 2: Per-User Google Sheets Setup (Preferred)

Each user provides their own Google service account JSON and specifies their own target spreadsheet through the Streamlit UI.

- **Pros:**
  - Each user's data goes to their own Google Sheet — full isolation.
  - No shared credentials on the server.
  - Users have full ownership of their data.
- **Cons:**
  - Requires users to go through Google Cloud setup (create project, enable Sheets API, create service account, download JSON, share spreadsheet).
  - Setup friction may deter casual users.
- **Implementation notes:**
  - Add a file uploader in the UI for the service account JSON (session-only, never saved to disk).
  - Add a text input for the target spreadsheet name.
  - Refactor `sheets.py` to accept credentials and spreadsheet name as parameters instead of using hardcoded constants.
  - Consider adding a step-by-step setup guide within the app UI.

### Option 3: Add Authentication to the App

Put the app behind a login (e.g., Streamlit's `st.secrets` password protection) so only the owner can access it.

- **Pros:** Simple to implement, protects the owner's credentials.
- **Cons:**
  - Only the owner can use the app — defeats the purpose of a public deployment.
  - Not suitable if the owner wants to demo the app to others (e.g., potential employers).

## Acceptance Criteria

- Users can upload their own Google service account JSON through the UI.
- Users can specify their own target spreadsheet name.
- Uploaded credentials are stored only in the browser session — never persisted to disk or server.
- The `ENABLE_GOOGLE_SHEETS` feature flag should remain, controlling whether the Google Sheets UI is shown at all.
- When Google Sheets is enabled and a user provides credentials, the existing upload/duplicate-check flow should work with the user's own spreadsheet.
- Include a clear setup guide within the app for users who want to use this feature.
