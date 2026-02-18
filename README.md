# Receipt Ranger

A receipt scanner that extracts structured data from receipt images using LLM-powered analysis via [BAML](https://docs.boundaryml.com/). Outputs results as JSON and Google Sheets-compatible tables.

## Features

- Scans receipt images and extracts key data (amount, date, vendor, category, payment method)
- Uses BAML for structured LLM output with strict type validation
- Tracks previously processed receipts to avoid duplicate work
- Outputs JSON and tab-separated tables ready for Google Sheets
- Supports multiple LLM providers (OpenAI, Anthropic) via BAML client configuration

## Setup

### Prerequisites

- Python 3.10+
- An OpenAI or Anthropic API key (see `baml_src/clients.baml` for provider configuration)

### Installation

```bash
pip install -e .
```

Set your API key in `baml_src/.env`:

```
OPENAI_API_KEY=your-key-here
```

For the web interface, set a `SESSION_SECRET` in `.env` to encrypt user-submitted API keys at rest:

```
# Generate a Fernet key:
# python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"
SESSION_SECRET=your-fernet-key-here
```

If `SESSION_SECRET` is unset, a random key is generated at startup (fine for local dev, but tokens won't survive a server restart).

## Usage

### Web Interface (Recommended)

The easiest way to use Receipt Ranger is through the web interface:

```bash
streamlit run app.py
```

This launches a browser-based UI where you can:
- Upload one or multiple receipt images
- Preview and remove images before processing
- Enter your API key (Fernet-encrypted for the session — never stored as plaintext)
- Process receipts and view extracted data
- Automatically upload to Google Sheets
- Download results as TSV or JSON

**Note:** The web interface validates that uploaded images are actual receipts. Non-receipt images (photos, screenshots, etc.) will be rejected with an explanation.

### Command Line Interface

Place receipt images (`.jpg`, `.jpeg`, `.png`, `.gif`, `.bmp`, `.webp`, `.tiff`) in `data/receipts/`, then run:

```bash
python3 main.py
```

To reprocess all receipts (including previously processed ones):

```bash
python3 main.py --duplicates
```

To print a table from stored receipts without reprocessing:

```bash
python3 main.py --table
```

To print a TSV table of stored receipts with optional filters:

```bash
python3 main.py --tsv --month 2026-01 --vendor taco --min-amount 10 --max-amount 50 --category food
```

To print a TSV table of all stored receipts:

```bash
python3 main.py --tsv-all
```

### Canonical categories

Receipt categories are constrained to the following canonical values:

- Food & Restaurants
- Groceries
- Transportation
- Travel
- Lodging
- Utilities
- Housing & Rent
- Health & Medical
- Insurance
- Entertainment & Recreation
- Clothing & Shoes
- Electronics & Gadgets
- Home & Garden
- Office & Supplies
- Education
- Gifts & Donations
- Subscriptions & Memberships
- Fees & Services
- Taxes
- Childcare
- Pet Care
- Personal Care
- Other

### Output

Results are written to the `output/` directory:

- `receipts-{timestamp}.json` -- full structured data for the latest processing run
- `receipts-{timestamp}.tsv` -- tab-separated table for pasting into Google Sheets

The table format:

| Amount | Date | | Vendor | Category |
|--------|------|-|--------|----------|

The blank column is reserved for manual annotations.

The CLI tracks processed file hashes and extracted receipts in `processed_receipts.json` (gitignored) to avoid reprocessing unchanged files. The web interface does not use this file — it relies on Google Sheets for duplicate detection when available.

## Google Sheets Integration (Optional)

Receipt Ranger can directly upload processed receipts to a Google Sheet, automatically creating monthly tabs and preventing duplicate entries.

### 1. Set Up Google Cloud Credentials

1.  **Create a Google Cloud Project:**
    *   Go to the [Google Cloud Console](https://console.cloud.google.com/).
    *   Create a new project (or use an existing one).

2.  **Enable APIs:**
    *   In your project, go to **APIs & Services > Library**.
    *   Search for and enable both the **Google Drive API** and the **Google Sheets API**.

3.  **Create a Service Account:**
    *   Go to **APIs & Services > Credentials**.
    *   Click **Create credentials > Service account**.
    *   Give it a name (e.g., `receipt-ranger-updater`) and grant it the **Editor** role for the project.

4.  **Generate a JSON Key:**
    *   After creating the service account, click on it, go to the **Keys** tab.
    *   Click **ADD KEY > Create new key**, select **JSON**, and click **Create**.
    *   A JSON file will be downloaded. **Rename this file to `service_account.json`** and place it in the root directory of the `receipt-ranger` project.

    _**Important:** This file contains sensitive credentials. It is already listed in `.gitignore` to prevent it from being committed to version control._

### 2. Create and Share Your Google Sheet

1.  **Create a new Google Sheet.** You can name it whatever you like, but the application will look for a sheet named **`receipt-ranger`** by default.
2.  **Share the sheet** with your service account.
    *   Open the `service_account.json` file and find the `client_email` address (e.g., `...iam.gserviceaccount.com`).
    *   In your Google Sheet, click **Share**, paste the service account's email address, and give it **Editor** permissions.

### 3. Upload Receipts to Google Sheets

Once configured, use the `--upload-to-sheets` flag to upload all locally stored receipts:

```bash
python3 main.py --upload-to-sheets
```

The script will:
- Authenticate using your `service_account.json`.
- Find or create a worksheet for each month and year (e.g., "January 2026").
- Check for duplicate receipts (based on Date, Amount, and Vendor) and only add new ones.

You can also process new receipts and upload them in the same run:

```bash
python3 main.py --upload-to-sheets
```

If there are new receipts in the `data/receipts` folder, they will be processed first, and then all receipts (new and previously stored) will be uploaded.

## Deployment

Receipt Ranger can be deployed to AWS EC2 for access from any device (including mobile). See [`deploy/README.md`](deploy/README.md) for a comprehensive guide covering:

- AWS EC2 instance setup
- Nginx reverse proxy configuration
- CloudFlare DNS and SSL setup
- Security hardening (firewall, fail2ban)
- Auto-restart with systemd

The deployed app uses a "bring your own API key" model - users enter their OpenAI/Anthropic keys via the web interface. Keys are Fernet-encrypted immediately on entry and stored only as an opaque token for the duration of the session.

Set a stable `SESSION_SECRET` in your environment for production (see Setup below).

## Documentation

- Cloudflare bot protection enablement checklist: `docs/bot-protection-checklist.md`

## Development

### Running tests

```bash
pytest
```

### Versioning

This project uses [bump2version](https://github.com/c4urself/bump2version) for version management:

```bash
bump2version patch   # 0.1.0 -> 0.1.1
bump2version minor   # 0.1.0 -> 0.2.0
bump2version major   # 0.1.0 -> 1.0.0
```

## License

MIT
