Receipt Ranger

Project-specific instructions for AI agents working on this codebase.

## Project Overview

Receipt Ranger is a backend receipt scanning application. It processes receipt images through an LLM (via BAML) to extract structured data, then outputs JSON and Google Sheets-compatible TSV tables.

Current status: **MVP** (backend only, no frontend).

## Project Structure

```
receipt-ranger/
├── main.py                     # Entry point - orchestrates the full pipeline
├── pyproject.toml              # Project metadata, dependencies, tool config
├── .bumpversion.cfg            # bump2version configuration
├── README.md                   # User-facing documentation
│
├── baml_src/                   # BAML source definitions (DO NOT auto-generate)
│   ├── receipt.baml            # Receipt data model + ExtractReceiptFromImage function
│   ├── clients.baml            # LLM provider configurations (OpenAI, Anthropic, etc.)
│   ├── generators.baml         # Code generation config (targets Python/Pydantic)
│   ├── resume.baml             # Example resume extraction (not part of MVP)
│   ├── .env                    # API keys (gitignored, not committed)
│   └── taco_cabana.jpeg        # Test receipt image for BAML tests
│
├── baml_client/                # Auto-generated Python client (DO NOT edit manually)
│   ├── __init__.py             # Exports `b` (sync client singleton)
│   ├── sync_client.py          # b.ExtractReceiptFromImage(image) -> Receipt
│   ├── async_client.py         # Async variants
│   ├── types.py                # Pydantic models: Receipt, Resume
│   └── ...                     # Runtime, parsing, streaming utilities
│
├── tests/                      # Test suite
│   └── test_main.py            # Unit tests for main.py logic
│
├── output/                     # Generated at runtime (gitignored)
│   ├── receipts.json           # Full JSON output of processed receipts
│   └── receipts.tsv            # Google Sheets-compatible tab-separated table
│
├── processed_receipts.json     # State file tracking processed receipts (gitignored)
│
└── .cursor/
    ├── data/
    │   └── receipts/           # Drop receipt images here for processing
    ├── features/               # Feature specs (CFS)
    ├── progress/               # Handoff documents for agent continuity
    └── tmp/                    # Temporary/debug files (gitignored)
```

## Key Concepts

### BAML Pipeline

BAML enforces structured LLM output. The flow is:

1. `baml_src/receipt.baml` defines the `Receipt` class and `ExtractReceiptFromImage` function
2. `baml-cli generate` produces the Python client in `baml_client/`
3. Application code calls `b.ExtractReceiptFromImage(image)` which returns a typed `Receipt` object

**Never edit files in `baml_client/` directly.** Edit `baml_src/*.baml` and regenerate with `baml-cli generate`.

### Receipt Data Model

From `baml_src/receipt.baml`:

- `id` (string) -- internal reference, not in output table
- `amount` (float) -- total including tips/taxes
- `date` (string) -- MM/DD/YYYY format
- `vendor` (string) -- merchant name
- `category` (string[]) -- e.g., Food/restaurants, Clothing, Entertainment
- `paymentMethod` (string[]) -- e.g., Cash, Card, Check

### State Tracking

`processed_receipts.json` is used by the **CLI only** (`main.py`). It maps filenames to content hashes so only new/changed files are processed. The `--duplicates` flag bypasses this and reprocesses everything.

The **web interface** (`app.py`) does not use this file. Duplicate detection in the web app relies on Google Sheets (available only when the owner API key is detected). Non-owner web users currently have no persistent duplicate detection.

### Output Table Format

The TSV output matches this Google Sheets layout:

```
Amount | Date | (blank column) | Vendor | Category
```

The blank column is intentional -- reserved for manual user input.

## Development Guidelines

### Running the application

```bash
python3 main.py              # Process new receipts only
python3 main.py --duplicates # Reprocess all receipts
```

### Testing

```bash
pytest
```

Tests mock the BAML client to avoid real LLM calls.

### Regenerating BAML client

After editing any `.baml` file in `baml_src/`:

```bash
baml-cli generate
```

### Versioning

Uses bump2version. Version is tracked in `pyproject.toml` and `.bumpversion.cfg`.

```bash
bump2version patch   # bug fixes
bump2version minor   # new features
bump2version major   # breaking changes
```

### LLM Client Configuration

`baml_src/clients.baml` defines available LLM providers. The receipt function currently uses `CustomGPT5Mini`. To switch providers, edit the `client` field in `baml_src/receipt.baml`.

## Rules

- Do not edit anything in `baml_client/`. It is auto-generated.
- Keep `baml_src/.env` out of version control.
- Output files go in `output/`, debug/temp files go in `.cursor/tmp/`.
- Follow PEP 8 for all Python code.
- The `pyproject.toml` excludes `baml_client/` and `baml_src/` from ruff and black linting.
