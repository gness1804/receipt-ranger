"""Receipt Ranger MVP -- process receipt images into structured data."""

import argparse
import base64
import hashlib
import json
import os
import sys

import baml_py

from baml_client import b

# Paths
RECEIPTS_DIR = os.path.join("data", "receipts")
OUTPUT_DIR = "output"
STATE_FILE = "processed_receipts.json"
OUTPUT_JSON = os.path.join(OUTPUT_DIR, "receipts.json")
OUTPUT_TSV = os.path.join(OUTPUT_DIR, "receipts.tsv")

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
            return json.load(f)
    return {}


def save_state(state: dict) -> None:
    """Save the processed receipts state file."""
    with open(STATE_FILE, "w") as f:
        json.dump(state, f, indent=2)


def get_receipts_to_process(allow_duplicates: bool) -> list[tuple[str, str]]:
    """Return list of (filename, filepath) tuples for receipts to process.

    Skips already-processed files unless allow_duplicates is True.
    """
    if not os.path.isdir(RECEIPTS_DIR):
        print(f"Receipts directory not found: {RECEIPTS_DIR}")
        return []

    state = load_state()
    to_process = []

    for filename in sorted(os.listdir(RECEIPTS_DIR)):
        if not is_valid_image(filename):
            continue

        filepath = os.path.join(RECEIPTS_DIR, filename)
        if not os.path.isfile(filepath):
            continue

        if not allow_duplicates:
            current_hash = file_hash(filepath)
            if filename in state and state[filename] == current_hash:
                continue

        to_process.append((filename, filepath))

    return to_process


def extract_receipt(filepath: str) -> dict:
    """Run BAML extraction on a receipt image and return the result as a dict."""
    _, ext = os.path.splitext(filepath)
    mime_type = MIME_TYPES[ext.lower()]

    with open(filepath, "rb") as f:
        image_data = base64.standard_b64encode(f.read()).decode("utf-8")

    image = baml_py.Image.from_base64(mime_type, image_data)
    receipt = b.ExtractReceiptFromImage(image)

    return {
        "id": receipt.id,
        "amount": receipt.amount,
        "date": receipt.date,
        "vendor": receipt.vendor,
        "category": receipt.category,
        "paymentMethod": receipt.paymentMethod,
    }


def write_json(results: list[dict]) -> None:
    """Write results to JSON output file."""
    os.makedirs(OUTPUT_DIR, exist_ok=True)
    with open(OUTPUT_JSON, "w") as f:
        json.dump(results, f, indent=2)


def write_tsv(results: list[dict]) -> None:
    """Write results to a TSV file compatible with Google Sheets.

    Columns: Amount | Date | (blank) | Vendor | Category
    """
    os.makedirs(OUTPUT_DIR, exist_ok=True)
    header = "Amount\tDate\t\tVendor\tCategory"
    lines = [header]

    for r in results:
        category = ", ".join(r["category"]) if r["category"] else ""
        amount = f"{r['amount']:.2f}"
        line = f"{amount}\t{r['date']}\t\t{r['vendor']}\t{category}"
        lines.append(line)

    with open(OUTPUT_TSV, "w") as f:
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


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Receipt Ranger -- extract structured data from receipt images."
    )
    parser.add_argument(
        "--duplicates",
        action="store_true",
        help="Reprocess all receipts, including previously processed ones.",
    )
    args = parser.parse_args()

    to_process = get_receipts_to_process(allow_duplicates=args.duplicates)

    if not to_process:
        print("No new receipts to process.")
        sys.exit(0)

    print(f"Processing {len(to_process)} receipt(s)...\n")

    results = []
    state = load_state()

    for filename, filepath in to_process:
        print(f"  Extracting: {filename}...")
        try:
            receipt_data = extract_receipt(filepath)
            receipt_data["source_file"] = filename
            results.append(receipt_data)
            state[filename] = file_hash(filepath)
        except Exception as e:
            print(f"  ERROR processing {filename}: {e}")

    if not results:
        print("\nNo receipts were successfully processed.")
        sys.exit(1)

    write_json(results)
    write_tsv(results)
    save_state(state)

    print(f"\nProcessed {len(results)} receipt(s). Output saved to {OUTPUT_DIR}/\n")
    print_table(results)


if __name__ == "__main__":
    main()
