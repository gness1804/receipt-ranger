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
    """
    spreadsheet = client.open(SPREADSHEET_NAME)
    try:
        worksheet = spreadsheet.worksheet(sheet_name)
    except gspread.WorksheetNotFound:
        worksheet = spreadsheet.add_worksheet(title=sheet_name, rows=100, cols=20)
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
    worksheet.append_row(row)
