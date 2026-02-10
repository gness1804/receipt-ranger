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

Three options were evaluated. The user's preferred option is ~~**Option 2**~~. Option 1 with Enhanced implementation. 

### Option 1: Disable Google Sheets on Public Deployment

- **Status:** Already implemented (v0.6.0) as a stopgap.
- **Pros:** Simple, no security risk.
- **Cons:** Feature is unavailable to all public users. Only works locally.
- **Enhanced Implementation:**: Right now, we're using a simple feature flag to enable Google Sheets running locally but disable it on the public deployment. We can take this a step further by adding logic to the application that checks if the API key being used is my API key for either OpenAI or Anthropic. If it is, AND if the Google feature flag is set to true, then the Google feature should be enabled. If one or both of these is false, then the Google feature should not be enabled, and the app should run without any Google-related messaging or features. Same behavior of the app today with the Google feature flag turned off. This new implementation will split the difference between my wanting to make the app as useful as possible for my own use, but also having a good portfolio piece to show potential employers.  

### Option 2: Per-User Google Sheets Setup (Not preferred. Too cumbersome.)

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

- When the Enable Google Sheets feature flag is turned on and the API key used is one of my own API keys, then the Google feature should work on the deployed application as it does locally. 
- In this scenario described above, when I scan a new receipt and process it, the data should be added to the relevant Google Sheet as is the case now locally. 
- By contrast, if the Google Sheets feature flag is off or the API key used is not one of my API keys, then the Google functionality should not appear at all. In other words, the application should be as it is today with no Google messaging or functionality. In this case, the user should only be able to upload and process recipes, download the TSV and JSON files, and see the table output of the recipe data on the screen. 
- The `ENABLE_GOOGLE_SHEETS` feature flag should remain, controlling whether the Google Sheets UI is shown at all (along with API key check).
