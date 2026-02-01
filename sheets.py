"""
Handles all interactions with Google Sheets.
"""

import gspread
import os
from typing import Dict, Any

# Name of the credentials file. This file should be in the project root.
SERVICE_ACCOUNT_FILE = "service_account.json"
# The name of the Google Sheet to use.
SPREADSHEET_NAME = "receipt-ranger"


def get_gspread_client():
    """
    Authenticates with Google Sheets using service account credentials.
    """
    if not os.path.exists(SERVICE_ACCOUNT_FILE):
        raise FileNotFoundError(
            f"Service account credentials file not found at: {SERVICE_ACCOUNT_FILE}. "
            f"Please follow the setup instructions in README.md."
        )

    gc = gspread.service_account(filename=SERVICE_ACCOUNT_FILE)
    return gc


def get_or_create_worksheet(client: gspread.Client, sheet_name: str):
    """
    Gets a worksheet by name, creating it if it doesn't exist.
    Ensures the worksheet has a header row.
    """
    spreadsheet = client.open(SPREADSHEET_NAME)
    try:
        worksheet = spreadsheet.worksheet(sheet_name)
    except gspread.WorksheetNotFound:
        worksheet = spreadsheet.add_worksheet(title=sheet_name, rows=100, cols=20)
        # Add header row to ensure proper table detection
        worksheet.append_row(
            ["Amount", "Date", "", "Vendor", "Category"],
            table_range="A1",
        )
    return worksheet


def get_existing_receipts(worksheet: gspread.Worksheet) -> set:
    """
    Reads a worksheet and returns a set of unique receipt identifiers.
    A unique identifier is a tuple of (Date, Amount, Vendor).
    """
    # Assuming the columns are: Amount, Date, '', Vendor, Category
    # We use indices 1 (Date), 0 (Amount), and 3 (Vendor)

    records = worksheet.get_all_records()  # This uses the first row as headers
    existing_receipts = set()
    for record in records:
        # The gspread get_all_records() method returns a list of dicts,
        # where the keys are the header values. Let's assume the headers are
        # "Amount", "Date", "Vendor", "Category".

        # To make it more robust, we check if the keys exist.
        date = record.get("Date")
        amount = record.get("Amount")
        vendor = record.get("Vendor")

        if date and amount and vendor:
            existing_receipts.add((str(date), str(amount), str(vendor)))

    return existing_receipts


def append_receipt(worksheet: gspread.Worksheet, receipt: Dict[str, Any]):
    """
    Appends a receipt as a new row in the worksheet.
    The row format is: Amount | Date | (blank) | Vendor | Category
    """
    # The category can be a list, so we join it into a string.
    category_str = ", ".join(receipt.get("category", []))

    row = [
        receipt.get("amount"),
        receipt.get("date"),
        "",  # Blank column
        receipt.get("vendor"),
        category_str,
    ]
    # Use table_range="A1" to ensure rows are appended starting at column A
    worksheet.append_row(row, table_range="A1")


def has_valid_headers(worksheet: gspread.Worksheet) -> bool:
    """Check if the worksheet has the expected header row."""
    try:
        first_row = worksheet.row_values(1)
        if not first_row:
            return False
        # Check if the first row matches our expected headers
        expected = ["Amount", "Date", "", "Vendor", "Category"]
        return first_row[:5] == expected
    except Exception:
        return False


def extract_receipts_from_misaligned_worksheet(
    worksheet: gspread.Worksheet,
) -> list[list]:
    """
    Extract receipt data from a worksheet with misaligned/diagonal data.
    Returns a list of rows, each containing [amount, date, '', vendor, category].
    """
    all_values = worksheet.get_all_values()
    extracted_rows = []

    for row in all_values:
        # Skip empty rows
        if not any(cell.strip() for cell in row):
            continue

        # Skip header row if present
        if row[:5] == ["Amount", "Date", "", "Vendor", "Category"]:
            continue

        # Find the first non-empty cell (this is where the data starts)
        start_idx = None
        for i, cell in enumerate(row):
            if cell.strip():
                start_idx = i
                break

        if start_idx is None:
            continue

        # Extract 5 cells starting from the first non-empty cell
        # Pattern: Amount, Date, (blank), Vendor, Category
        data_slice = row[start_idx : start_idx + 5]

        # Pad with empty strings if we don't have 5 values
        while len(data_slice) < 5:
            data_slice.append("")

        # Validate this looks like receipt data (amount should be numeric)
        amount_str = data_slice[0].strip()
        if not amount_str:
            continue

        # Try to parse as a number (could be "17.81" or "17,81")
        try:
            float(amount_str.replace(",", "."))
        except ValueError:
            # First cell isn't a number, might be header or invalid row
            continue

        extracted_rows.append(data_slice)

    return extracted_rows


def fix_misaligned_worksheet(worksheet: gspread.Worksheet) -> int:
    """
    Fix a worksheet with misaligned/diagonal data.
    Extracts all receipt data, clears the sheet, adds headers,
    and re-inserts all data properly aligned.

    Returns the number of receipts that were realigned.
    """
    # Extract data from the misaligned worksheet
    extracted_rows = extract_receipts_from_misaligned_worksheet(worksheet)

    if not extracted_rows:
        # No data to fix, just ensure headers exist
        if not has_valid_headers(worksheet):
            worksheet.clear()
            worksheet.append_row(
                ["Amount", "Date", "", "Vendor", "Category"],
                table_range="A1",
            )
        return 0

    # Clear the worksheet
    worksheet.clear()

    # Add header row
    worksheet.append_row(
        ["Amount", "Date", "", "Vendor", "Category"],
        table_range="A1",
    )

    # Re-add all the extracted data, properly aligned
    for row in extracted_rows:
        worksheet.append_row(row, table_range="A1")

    return len(extracted_rows)


def fix_all_worksheets(client: gspread.Client) -> dict[str, int]:
    """
    Fix all worksheets in the spreadsheet that have misaligned data.
    Returns a dict mapping worksheet names to the number of receipts fixed.
    """
    spreadsheet = client.open(SPREADSHEET_NAME)
    results = {}

    for worksheet in spreadsheet.worksheets():
        name = worksheet.title
        if has_valid_headers(worksheet):
            # Worksheet already has valid headers, skip
            results[name] = 0
            continue

        count = fix_misaligned_worksheet(worksheet)
        results[name] = count

    return results


def get_all_existing_receipts(client: gspread.Client) -> set:
    """
    Get all existing receipts across all worksheets in the spreadsheet.
    Returns a set of (date, amount, vendor) tuples.
    """
    try:
        spreadsheet = client.open(SPREADSHEET_NAME)
    except gspread.SpreadsheetNotFound:
        return set()

    all_receipts = set()
    for worksheet in spreadsheet.worksheets():
        try:
            existing = get_existing_receipts(worksheet)
            all_receipts.update(existing)
        except Exception:
            # Skip worksheets that can't be read
            continue

    return all_receipts


def check_receipts_for_duplicates(
    client: gspread.Client, receipts: list[dict]
) -> list[dict]:
    """
    Check a list of receipts against existing Google Sheets data.
    Returns a list of receipts that already exist in the sheets.

    Args:
        client: Authenticated gspread client
        receipts: List of receipt dicts to check

    Returns:
        List of receipt dicts that are duplicates (already in sheets)
    """
    existing = get_all_existing_receipts(client)
    duplicates = []

    for receipt in receipts:
        receipt_key = (
            str(receipt.get("date", "")),
            str(receipt.get("amount", "")),
            str(receipt.get("vendor", "")),
        )
        if receipt_key in existing:
            duplicates.append(receipt)

    return duplicates
