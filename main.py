"""Receipt Ranger MVP -- process receipt images into structured data."""

import argparse
import base64
import hashlib
import json
import os
import sys
from datetime import datetime

import baml_py

from baml_client import b

# Paths
RECEIPTS_DIR = os.path.join("data", "receipts")
OUTPUT_DIR = "output"
STATE_FILE = "processed_receipts.json"
OUTPUT_JSON = os.path.join(OUTPUT_DIR, "receipts.json")
OUTPUT_TSV = os.path.join(OUTPUT_DIR, "receipts.tsv")
EXCLUSION_CRITERIA_FILE = os.path.join("data", "exclusion_criteria.txt")

# Supported image extensions
VALID_EXTENSIONS = {".jpg", ".jpeg", ".png", ".gif", ".bmp", ".webp", ".tiff"}

# Extension to MIME type mapping
MIME_TYPES = {
    ".jpg": "image/jpeg",
    ".jpeg": "image/jpeg",
    ".png": "image/png",
    ".gif": "image/gif",
    ".bmp": "image/bmp",
    ".webp": "image/webp",
    ".tiff": "image/tiff",
}

CATEGORY_ENUM_TO_LABEL = {
    "FOOD_RESTAURANTS": "Food & Restaurants",
    "GROCERIES": "Groceries",
    "TRANSPORTATION": "Transportation",
    "TRAVEL": "Travel",
    "LODGING": "Lodging",
    "UTILITIES": "Utilities",
    "HOUSING_RENT": "Housing & Rent",
    "HEALTH_MEDICAL": "Health & Medical",
    "INSURANCE": "Insurance",
    "ENTERTAINMENT_RECREATION": "Entertainment & Recreation",
    "CLOTHING_SHOES": "Clothing & Shoes",
    "ELECTRONICS_GADGETS": "Electronics & Gadgets",
    "HOME_GARDEN": "Home & Garden",
    "OFFICE_SUPPLIES": "Office & Supplies",
    "EDUCATION": "Education",
    "GIFTS_DONATIONS": "Gifts & Donations",
    "SUBSCRIPTIONS_MEMBERSHIPS": "Subscriptions & Memberships",
    "FEES_SERVICES": "Fees & Services",
    "TAXES": "Taxes",
    "CHILDCARE": "Childcare",
    "PET_CARE": "Pet Care",
    "PERSONAL_CARE": "Personal Care",
    "OTHER": "Other",
}

CANONICAL_CATEGORIES = list(CATEGORY_ENUM_TO_LABEL.values())
CATEGORY_ALIASES = {
    "food/restaurants": "Food & Restaurants",
    "food and restaurants": "Food & Restaurants",
    "food & restaurants": "Food & Restaurants",
    "restaurants": "Food & Restaurants",
    "clothing": "Clothing & Shoes",
    "clothes": "Clothing & Shoes",
    "entertainment": "Entertainment & Recreation",
    "housing": "Housing & Rent",
    "rent": "Housing & Rent",
}


def _category_key(value: str) -> str:
    return " ".join(value.strip().lower().split())


def _build_category_lookup() -> dict[str, str]:
    lookup = {}
    for enum_value, label in CATEGORY_ENUM_TO_LABEL.items():
        lookup[_category_key(enum_value)] = label
        lookup[_category_key(label)] = label
    for alias, label in CATEGORY_ALIASES.items():
        lookup[_category_key(alias)] = label
    return lookup


CATEGORY_LOOKUP = _build_category_lookup()


def is_valid_image(filename: str) -> bool:
    """Check if a filename has a supported image extension."""
    _, ext = os.path.splitext(filename)
    return ext.lower() in VALID_EXTENSIONS


def file_hash(filepath: str) -> str:
    """Compute SHA-256 hash of a file's contents."""
    h = hashlib.sha256()
    with open(filepath, "rb") as f:
        for chunk in iter(lambda: f.read(8192), b""):
            h.update(chunk)
    return h.hexdigest()


def load_state() -> dict:
    """Load the processed receipts state file."""
    if os.path.exists(STATE_FILE):
        with open(STATE_FILE, "r") as f:
            return _normalize_state(json.load(f))
    return _normalize_state({})


def save_state(state: dict) -> None:
    """Save the processed receipts state file."""
    state = _normalize_state(state)
    with open(STATE_FILE, "w") as f:
        json.dump(state, f, indent=2)


def load_exclusion_criteria() -> str:
    """Load exclusion criteria from file.

    Returns the file contents as a string, or a default message if the file
    doesn't exist or is empty.
    """
    if not os.path.exists(EXCLUSION_CRITERIA_FILE):
        return "No exclusion criteria configured."
    try:
        with open(EXCLUSION_CRITERIA_FILE, "r") as f:
            content = f.read().strip()
        if not content:
            return "No exclusion criteria configured."
        return content
    except OSError:
        return "No exclusion criteria configured."


def _normalize_state(state: dict) -> dict:
    if not isinstance(state, dict):
        return {"files": {}, "receipts": {}}
    if "files" in state or "receipts" in state:
        return {
            "files": state.get("files", {}),
            "receipts": state.get("receipts", {}),
        }
    return {"files": state, "receipts": {}}


def _receipt_key(receipt: dict) -> str:
    for key in ("source_hash", "id"):
        value = receipt.get(key)
        if value:
            return str(value)
    amount = receipt.get("amount", "")
    date = receipt.get("date", "")
    vendor = receipt.get("vendor", "")
    category = receipt.get("category") or []
    category_str = ",".join(str(c) for c in category)
    return f"{amount}|{date}|{vendor}|{category_str}"


def dedupe_receipts(receipts: list[dict]) -> list[dict]:
    deduped = {}
    for receipt in receipts:
        deduped[_receipt_key(receipt)] = receipt
    return list(deduped.values())


def normalize_categories(categories: list) -> list[str]:
    if not categories:
        return []

    normalized = []
    seen = set()
    for raw in categories:
        if raw is None:
            continue
        value = raw.value if hasattr(raw, "value") else str(raw)
        if not value.strip():
            continue
        key = _category_key(value)
        canonical = CATEGORY_LOOKUP.get(key, "Other")
        if canonical not in seen:
            normalized.append(canonical)
            seen.add(canonical)
    return normalized


def _normalize_receipt(receipt: dict) -> dict:
    receipt["category"] = normalize_categories(receipt.get("category"))
    return receipt


def _parse_date(date_str: str) -> datetime | None:
    if not date_str:
        return None
    for fmt in ("%m/%d/%Y", "%Y-%m-%d", "%m/%d/%y"):
        try:
            return datetime.strptime(date_str, fmt)
        except ValueError:
            continue
    return None


def _filter_receipts(
    receipts: list[dict],
    month: str | None,
    vendor: str | None,
    min_amount: float | None,
    max_amount: float | None,
    category: str | None,
) -> list[dict]:
    results = []
    target_month = None
    if month:
        try:
            target_month = datetime.strptime(month, "%Y-%m")
        except ValueError:
            print("Invalid --month format. Use YYYY-MM.", file=sys.stderr)
            return []

    vendor_filter = vendor.lower() if vendor else None
    category_filter = category if category else None

    for receipt in receipts:
        if vendor_filter and vendor_filter not in receipt.get("vendor", "").lower():
            continue

        if category_filter:
            categories = receipt.get("category") or []
            if category_filter not in categories:
                continue

        amount = receipt.get("amount")
        if min_amount is not None and (amount is None or amount < min_amount):
            continue
        if max_amount is not None and (amount is None or amount > max_amount):
            continue

        if target_month:
            parsed_date = _parse_date(receipt.get("date", ""))
            if not parsed_date:
                continue
            if (
                parsed_date.year != target_month.year
                or parsed_date.month != target_month.month
            ):
                continue

        results.append(receipt)

    return results


def _load_receipts_from_output(output_dir: str) -> list[dict]:
    if not os.path.isdir(output_dir):
        return []
    receipts = []
    for filename in sorted(os.listdir(output_dir)):
        if not (filename.startswith("receipts") and filename.endswith(".json")):
            continue
        path = os.path.join(output_dir, filename)
        try:
            with open(path, "r") as f:
                data = json.load(f)
            if isinstance(data, list):
                receipts.extend(_normalize_receipt(r) for r in data)
        except (OSError, json.JSONDecodeError):
            continue
    return receipts


def _filter_excluded_receipts(
    receipts: list[dict], print_warnings: bool = True
) -> tuple[list[dict], list[dict]]:
    """Separate receipts into included and excluded lists.

    Args:
        receipts: List of receipt dicts to filter
        print_warnings: If True, print warning messages for excluded receipts

    Returns:
        Tuple of (included_receipts, excluded_receipts)
    """
    included = []
    excluded = []
    for receipt in receipts:
        if receipt.get("excludeFromTable", False):
            excluded.append(receipt)
            if print_warnings:
                reason = receipt.get("exclusionReason", "No reason provided")
                vendor = receipt.get("vendor", "Unknown")
                amount = receipt.get("amount", 0)
                print(
                    f"  WARNING: Receipt excluded from table - "
                    f"Vendor: {vendor}, Amount: ${amount:.2f}, Reason: {reason}"
                )
        else:
            included.append(receipt)
    return included, excluded


def _build_tsv_lines(results: list[dict]) -> list[str]:
    header = "Amount\tDate\t\tVendor\tCategory"
    lines = [header]
    for receipt in results:
        category = ", ".join(receipt["category"]) if receipt.get("category") else ""
        amount = f"{receipt['amount']:.2f}"
        line = f"{amount}\t{receipt['date']}\t\t{receipt['vendor']}\t{category}"
        lines.append(line)
    return lines


def _print_tsv(results: list[dict]) -> None:
    print("\n".join(_build_tsv_lines(results)))


def _merge_receipts_into_state(state: dict, receipts: list[dict]) -> None:
    for receipt in receipts:
        state["receipts"][_receipt_key(receipt)] = receipt


def _load_stored_receipts(state: dict) -> list[dict]:
    receipts = [_normalize_receipt(r) for r in state.get("receipts", {}).values()]
    receipts.extend(_load_receipts_from_output(OUTPUT_DIR))
    return dedupe_receipts(receipts)


def get_receipts_to_process(
    allow_duplicates: bool, files: list[str] | None = None
) -> list[tuple[str, str, str]]:
    """Return list of (filename, filepath, file_hash) tuples for receipts to process.

    If `files` is provided, it will process that list of files.
    Otherwise, it scans RECEIPTS_DIR, skipping already-processed files
    unless allow_duplicates is True.
    """
    if files:
        to_process = []
        print(f"Attempting to reprocess {len(files)} specified receipt(s)...")
        for filepath in files:
            if not os.path.exists(filepath):
                print(f"  WARNING: File not found, skipping: {filepath}")
                continue
            if not is_valid_image(filepath):
                print(f"  WARNING: File is not a valid image, skipping: {filepath}")
                continue

            filename = os.path.basename(filepath)
            current_hash = file_hash(filepath)
            to_process.append((filename, filepath, current_hash))
        return to_process

    if not os.path.isdir(RECEIPTS_DIR):
        print(f"Receipts directory not found: {RECEIPTS_DIR}")
        return []

    state = load_state()
    seen_files = state.get("files", {})
    to_process = []

    for filename in sorted(os.listdir(RECEIPTS_DIR)):
        if not is_valid_image(filename):
            continue

        filepath = os.path.join(RECEIPTS_DIR, filename)
        if not os.path.isfile(filepath):
            continue

        current_hash = file_hash(filepath)
        if not allow_duplicates:
            if filename in seen_files and seen_files[filename] == current_hash:
                continue

        to_process.append((filename, filepath, current_hash))

    return to_process


def extract_receipt(filepath: str, exclusion_criteria: str) -> dict:
    """Run BAML extraction on a receipt image and return the result as a dict."""
    _, ext = os.path.splitext(filepath)
    mime_type = MIME_TYPES[ext.lower()]

    with open(filepath, "rb") as f:
        image_data = base64.standard_b64encode(f.read()).decode("utf-8")

    image = baml_py.Image.from_base64(mime_type, image_data)
    receipt = b.ExtractReceiptFromImage(image, exclusion_criteria)

    return {
        "id": receipt.id,
        "amount": receipt.amount,
        "date": receipt.date,
        "vendor": receipt.vendor,
        "category": normalize_categories(receipt.category),
        "paymentMethod": receipt.paymentMethod,
        "excludeFromTable": receipt.excludeFromTable,
        "exclusionReason": receipt.exclusionReason,
    }


def write_json(results: list[dict], output_path: str | None = None) -> None:
    """Write results to JSON output file."""
    output_path = output_path or OUTPUT_JSON
    os.makedirs(OUTPUT_DIR, exist_ok=True)
    with open(output_path, "w") as f:
        json.dump(results, f, indent=2)


def write_tsv(results: list[dict], output_path: str | None = None) -> None:
    """Write results to a TSV file compatible with Google Sheets.

    Columns: Amount | Date | (blank) | Vendor | Category
    """
    output_path = output_path or OUTPUT_TSV
    os.makedirs(OUTPUT_DIR, exist_ok=True)
    lines = _build_tsv_lines(results)
    with open(output_path, "w") as f:
        f.write("\n".join(lines) + "\n")


def print_table(results: list[dict]) -> None:
    """Print a formatted table of results to stdout."""
    if not results:
        return

    # Column widths
    amt_w = max(len(f"{r['amount']:.2f}") for r in results)
    amt_w = max(amt_w, len("Amount"))
    date_w = max((len(r["date"]) for r in results), default=10)
    date_w = max(date_w, len("Date"))
    vend_w = max((len(r["vendor"]) for r in results), default=7)
    vend_w = max(vend_w, len("Vendor"))
    cats = [", ".join(r["category"]) if r["category"] else "" for r in results]
    cat_w = max((len(c) for c in cats), default=8)
    cat_w = max(cat_w, len("Category"))
    blank_w = 5  # blank column

    header = (
        f"{'Amount':<{amt_w}}  "
        f"{'Date':<{date_w}}  "
        f"{'':<{blank_w}}  "
        f"{'Vendor':<{vend_w}}  "
        f"{'Category':<{cat_w}}"
    )
    separator = (
        f"{'-' * amt_w}  {'-' * date_w}  {'-' * blank_w}  {'-' * vend_w}  {'-' * cat_w}"
    )

    print(header)
    print(separator)
    for r, cat in zip(results, cats):
        print(
            f"{r['amount']:<{amt_w}.2f}  "
            f"{r['date']:<{date_w}}  "
            f"{'':<{blank_w}}  "
            f"{r['vendor']:<{vend_w}}  "
            f"{cat:<{cat_w}}"
        )


def _timestamp() -> str:
    return datetime.now().strftime("%Y%m%d-%H%M%S")


def _build_output_paths(timestamp: str) -> tuple[str, str]:
    json_path = os.path.join(OUTPUT_DIR, f"receipts-{timestamp}.json")
    tsv_path = os.path.join(OUTPUT_DIR, f"receipts-{timestamp}.tsv")
    return json_path, tsv_path


def _parse_category(value: str) -> str:
    key = _category_key(value)
    canonical = CATEGORY_LOOKUP.get(key)
    if not canonical:
        options = ", ".join(CANONICAL_CATEGORIES)
        raise argparse.ArgumentTypeError(
            f"Invalid category: {value}. Choose from: {options}"
        )
    return canonical


def fix_google_sheets():
    """Fix misaligned data in existing Google Sheets worksheets."""
    try:
        from sheets import get_gspread_client, fix_all_worksheets
    except ImportError:
        print(
            "\n[Sheets] `gspread` library not found. "
            "Please install it with: pip install gspread"
        )
        return

    print("[Sheets] Checking for misaligned worksheets...")

    try:
        client = get_gspread_client()
    except FileNotFoundError as e:
        print(f"[Sheets] ERROR: {e}")
        return
    except Exception as e:
        print(f"[Sheets] ERROR: Could not authenticate with Google Sheets: {e}")
        return

    try:
        results = fix_all_worksheets(client)
    except Exception as e:
        print(f"[Sheets] ERROR: Could not fix worksheets: {e}")
        return

    fixed_count = 0
    for worksheet_name, count in results.items():
        if count > 0:
            print(f"  [Sheets] Fixed '{worksheet_name}': realigned {count} receipt(s)")
            fixed_count += count
        else:
            print(f"  [Sheets] '{worksheet_name}': already properly aligned")

    if fixed_count > 0:
        print(f"\n[Sheets] Done. Fixed {fixed_count} total receipt(s).")
    else:
        print("\n[Sheets] All worksheets are already properly aligned.")


def upload_to_sheets(receipts: list[dict]):
    """Uploads receipts to Google Sheets."""
    try:
        from sheets import (
            get_gspread_client,
            get_or_create_worksheet,
            get_existing_receipts,
            append_receipt,
        )
    except ImportError:
        print(
            "\n[Sheets] `gspread` library not found. "
            "Please install it with: pip install gspread"
        )
        return

    print("\n[Sheets] Starting upload to Google Sheets...")

    try:
        client = get_gspread_client()
    except FileNotFoundError as e:
        print(f"[Sheets] ERROR: {e}")
        return
    except Exception as e:
        print(f"[Sheets] ERROR: Could not authenticate with Google Sheets: {e}")
        return

    worksheets = {}
    new_receipts_count = 0

    # Filter out receipts that are excluded from the table
    receipts_to_upload, _ = _filter_excluded_receipts(receipts, print_warnings=False)

    for receipt in receipts_to_upload:
        date_str = receipt.get("date")
        if not date_str:
            continue

        try:
            # Use the existing _parse_date function
            parsed_date = _parse_date(date_str)
            if not parsed_date:
                warning_message = (
                    f"[Sheets] WARNING: Could not parse date '{date_str}', "
                    "skipping receipt."
                )
                print(warning_message)
                continue

            # Format: "January 2026"
            worksheet_title = parsed_date.strftime("%B %Y")
        except (ValueError, TypeError):
            warning_message = (
                f"[Sheets] WARNING: Invalid date format for '{date_str}', "
                "skipping receipt."
            )
            print(warning_message)
            continue

        if worksheet_title not in worksheets:
            print(f"[Sheets] Accessing worksheet: '{worksheet_title}'...")
            try:
                worksheet = get_or_create_worksheet(client, worksheet_title)
                existing_receipts = get_existing_receipts(worksheet)
                worksheets[worksheet_title] = (worksheet, existing_receipts)
            except Exception as e:
                error_message = (
                    f"[Sheets] ERROR: Could not access or create worksheet "
                    f"'{worksheet_title}': {e}"
                )
                print(error_message)
                continue

        worksheet, existing_receipts = worksheets[worksheet_title]

        # Create a unique key for the receipt to check for duplicates
        receipt_key = (
            str(receipt.get("date")),
            str(receipt.get("amount")),
            str(receipt.get("vendor")),
        )

        if receipt_key not in existing_receipts:
            try:
                append_receipt(worksheet, receipt)
                existing_receipts.add(receipt_key)
                new_receipts_count += 1
                vendor = receipt.get("vendor")
                date = receipt.get("date")
                print(f"  [Sheets] Added new receipt: {vendor} on {date}")
            except Exception as e:
                print(f"[Sheets] ERROR: Could not append receipt to worksheet: {e}")

    print(f"\n[Sheets] Upload complete. Added {new_receipts_count} new receipt(s).")


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Receipt Ranger -- extract structured data from receipt images."
    )
    parser.add_argument(
        "--files",
        nargs="*",
        help="One or more paths to specific receipt files to reprocess.",
    )
    parser.add_argument(
        "--duplicates",
        action="store_true",
        help="Reprocess all receipts, including previously processed ones.",
    )
    parser.add_argument(
        "--table",
        action="store_true",
        help="Print a table from stored receipts without reprocessing.",
    )
    parser.add_argument(
        "--tsv",
        action="store_true",
        help="Print a TSV table from stored receipts (filters apply).",
    )
    parser.add_argument(
        "--tsv-all",
        action="store_true",
        help="Print a TSV table of all stored receipts.",
    )
    parser.add_argument(
        "--upload-to-sheets",
        action="store_true",
        help="Uploads all processed receipts to Google Sheets.",
    )
    parser.add_argument(
        "--fix-sheets",
        action="store_true",
        help="Fix misaligned data in existing Google Sheets worksheets.",
    )
    parser.add_argument(
        "--month",
        help="Filter stored receipts by month (YYYY-MM).",
    )
    parser.add_argument(
        "--vendor",
        help="Filter stored receipts by vendor substring.",
    )
    parser.add_argument(
        "--min-amount",
        type=float,
        help="Filter stored receipts with amount >= value.",
    )
    parser.add_argument(
        "--max-amount",
        type=float,
        help="Filter stored receipts with amount <= value.",
    )
    parser.add_argument(
        "--category",
        type=_parse_category,
        choices=CANONICAL_CATEGORIES,
        help="Filter stored receipts by category.",
    )
    args = parser.parse_args()

    if args.files and (
        args.table
        or args.tsv
        or args.tsv_all
        or args.upload_to_sheets
        or args.fix_sheets
    ):
        parser.error(
            "Cannot specify files to reprocess when using viewing-only or "
            "upload options like --table, --tsv, --tsv-all, --upload-to-sheets, "
            "or --fix-sheets."
        )

    if args.fix_sheets:
        fix_google_sheets()
        sys.exit(0)

    if args.table or args.tsv or args.tsv_all or args.upload_to_sheets:
        state = load_state()
        receipts = _load_stored_receipts(state)
        if not receipts:
            print("No stored receipts found.")
            sys.exit(0)

        # Filter out excluded receipts from table display
        table_receipts, excluded = _filter_excluded_receipts(
            receipts, print_warnings=False
        )
        if excluded and not args.upload_to_sheets:
            print(f"Note: {len(excluded)} receipt(s) excluded from table output.\n")

        if args.tsv or args.tsv_all:
            if args.tsv_all:
                filtered = table_receipts
            else:
                filtered = _filter_receipts(
                    table_receipts,
                    month=args.month,
                    vendor=args.vendor,
                    min_amount=args.min_amount,
                    max_amount=args.max_amount,
                    category=args.category,
                )
            _print_tsv(dedupe_receipts(filtered))

        if args.table:
            print_table(dedupe_receipts(table_receipts))

        if args.upload_to_sheets:
            upload_to_sheets(receipts)

        sys.exit(0)

    to_process = get_receipts_to_process(
        allow_duplicates=args.duplicates, files=args.files
    )

    if not to_process:
        if not args.files:
            print("No new receipts to process.")
        sys.exit(0)

    print(f"Processing {len(to_process)} receipt(s)...\n")

    # Load exclusion criteria for LLM evaluation
    exclusion_criteria = load_exclusion_criteria()

    results = []
    state = load_state()

    for filename, filepath, file_h in to_process:
        print(f"  Extracting: {filename}...")
        try:
            receipt_data = extract_receipt(filepath, exclusion_criteria)
            receipt_data["source_file"] = filename
            receipt_data["source_hash"] = file_h
            results.append(receipt_data)
            state["files"][filename] = file_h
        except Exception as e:
            print(f"  ERROR processing {filename}: {e}")

    if not results:
        print("\nNo receipts were successfully processed.")
        sys.exit(1)

    deduped_results = dedupe_receipts(results)
    timestamp = _timestamp()
    output_json, output_tsv = _build_output_paths(timestamp)

    # Write all receipts (including excluded) to JSON for record-keeping
    write_json(deduped_results, output_json)

    # Filter excluded receipts from table output (with warnings)
    print()  # Blank line before warnings
    table_receipts, excluded_receipts = _filter_excluded_receipts(
        deduped_results, print_warnings=True
    )

    # Write only non-excluded receipts to TSV
    write_tsv(table_receipts, output_tsv)

    # Merge all receipts (including excluded) into state for deduplication
    _merge_receipts_into_state(state, deduped_results)
    save_state(state)

    excluded_count = len(excluded_receipts)
    table_count = len(table_receipts)
    total_count = len(deduped_results)

    print(f"\nProcessed {total_count} receipt(s). Output saved to {OUTPUT_DIR}/")
    if excluded_count > 0:
        print(f"  - {table_count} receipt(s) included in table")
        print(f"  - {excluded_count} receipt(s) excluded from table")
    print()
    print_table(table_receipts)


if __name__ == "__main__":
    main()
