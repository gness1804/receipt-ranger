---
github_issue: 85
---
# Normalize Amount Formatting To Prevent Duplicate Receipts 255 Vs 2550

## Working directory

`~/Desktop/receipt-ranger`

## Contents

## Summary

Google Sheets duplicate detection compares the **amount** as a raw string, so
two receipts with the same numeric amount but different string formatting do
not match. For example an incoming receipt with amount `25.5` (float) builds
the key `"25.5"`, while the same receipt already in the sheet is read back by
gspread as `"25.50"` — the keys differ and the duplicate is not flagged.

## Background

Found during the QA review of the vendor-casing dedupe fix (CFS bug #17 /
GitHub #84). That fix normalized the **vendor** component of the dedupe key.
The **amount** component has an analogous latent gap that predates the vendor
fix and was left out of scope intentionally.

## Root cause

Both sides of the dedupe key stringify the amount without numeric
normalization:

- `sheets.py` `get_existing_receipts` — existing rows keyed on `str(amount)`
  (gspread returns sheet values as strings such as `"25.50"`).
- `sheets.py` `check_receipts_for_duplicates` — incoming receipts keyed on
  `str(receipt.get("amount", ""))` (the LLM/Pydantic amount is a float, so
  `25.5` -> `"25.5"`).

`"25.5" != "25.50"`, so the duplicate slips through. Trailing zeros,
integer-vs-float (`25` vs `25.0`), and currency symbols / thousands separators
would all defeat the match the same way.

## Proposed fix

Normalize the amount to a canonical numeric form before building the dedupe
key, applied consistently on both sides (mirroring how `_normalize_vendor`
was added for the vendor). Suggested approach: a `_normalize_amount` helper
that parses to a number and formats to a fixed precision, e.g.
`f"{float(amount):.2f}"`, with a safe fallback (return the stripped raw string)
when the value can't be parsed. As with the vendor fix, normalization should
affect **only the comparison key**, not the value written to the sheet.

## Acceptance criteria

- A receipt with amount `25.5` is flagged as a duplicate of an existing sheet
  row showing `25.50` (same date + vendor).
- Integer/float variants (`25` vs `25.0` vs `25.00`) dedupe to one key.
- Unparseable amounts degrade gracefully (no crash; fall back to string compare).
- The amount written to the sheet is unchanged (normalization is
  comparison-only).
- Unit tests cover amount normalization in both `get_existing_receipts` and
  `check_receipts_for_duplicates`.

## Notes

- This affects the Google Sheets dedup path, not the CLI's
  `processed_receipts.json` content-hash path.

## Acceptance criteria
