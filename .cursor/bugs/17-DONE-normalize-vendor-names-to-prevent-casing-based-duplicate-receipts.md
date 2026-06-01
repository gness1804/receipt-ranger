---
github_issue: 84
---
# Normalize Vendor Names To Prevent Casing Based Duplicate Receipts

## Working directory

`~/Desktop/receipt-ranger`

## Contents

## Summary

Google Sheets duplicate detection fails to flag receipts that are identical
except for the **casing of the vendor name**. The same receipt uploaded twice
(once with the vendor in mixed case, once in all caps) is written to the sheet
twice instead of being flagged as a duplicate.

## How it was found

While validating HEIC→JPEG conversion, I uploaded a receipt that had previously
been processed (manually converted to JPEG). I expected Receipt Ranger to flag
it as a duplicate and refuse to write it to Google Sheets. Instead it wrote a
second row.

The two rows are identical apart from vendor casing:

| Row | Amount | Date      | Vendor                  |
|-----|--------|-----------|-------------------------|
| 38  | 27.86  | 5/27/2026 | `BaanThai Thai Cuisine` |
| 47  | 27.86  | 5/27/2026 | `BAANTHAI THAI CUISINE` |

Same amount, same date — only the vendor case differs.

## Root cause

Duplicate detection keys receipts on `(date, amount, vendor)` but compares the
vendor as a raw string with no normalization, on **both** sides of the check:

- `sheets.py:97` — existing-sheet receipts keyed on `str(vendor)`
- `sheets.py:290` — incoming receipt keyed on `str(receipt.get("vendor", ""))`

Because the LLM extraction can return the vendor in different casing across runs
(and different source images), the two keys don't match and the duplicate slips
through.

## Proposed fix

Normalize the vendor before building the dedupe key, applied consistently on
both sides (`get_all_existing_receipts` and `check_receipts_for_duplicates`).
At minimum: `vendor.strip().casefold()`. Consider also collapsing internal
whitespace (`" ".join(vendor.split())`) so e.g. double spaces don't defeat the
match. Normalization should affect **only the comparison key**, not the value
written to the sheet — the displayed vendor name should keep its original
casing.

## Acceptance criteria

- Uploading the same receipt where the only difference is vendor casing is
  flagged as a duplicate and not written to Google Sheets.
- The vendor name written to the sheet retains its original (LLM-extracted)
  casing — normalization is comparison-only.
- Unit tests cover case-insensitive and whitespace-insensitive vendor matching
  in both `get_all_existing_receipts` and `check_receipts_for_duplicates`.

## Notes

- This affects the Google Sheets dedup path (owner / `ENABLE_GOOGLE_SHEETS`),
  not the CLI's `processed_receipts.json` content-hash path.

## Acceptance criteria

<!-- DONE -->
