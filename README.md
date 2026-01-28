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
pip install baml-py
```

Set your API key in `baml_src/.env`:

```
OPENAI_API_KEY=your-key-here
```

## Usage

Place receipt images (`.jpg`, `.jpeg`, `.png`, `.gif`, `.bmp`, `.webp`, `.tiff`) in `.cursor/data/receipts/`, then run:

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

### Output

Results are written to the `output/` directory:

- `receipts-{timestamp}.json` -- full structured data for the latest processing run
- `receipts-{timestamp}.tsv` -- tab-separated table for pasting into Google Sheets

The table format:

| Amount | Date | | Vendor | Category |
|--------|------|-|--------|----------|

The blank column is reserved for manual annotations.

Stored receipt metadata (including processed hashes and extracted receipts) is tracked in `processed_receipts.json`.

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
