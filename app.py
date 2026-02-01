"""Receipt Ranger - Streamlit Frontend"""

import base64
import os
import streamlit as st
from datetime import datetime

# Must set page config first, before any other st commands
st.set_page_config(
    page_title="Receipt Ranger",
    page_icon="🧾",
    layout="centered",
    initial_sidebar_state="collapsed",
)

import main  # noqa: E402
from main import (  # noqa: E402
    VALID_EXTENSIONS,
    MIME_TYPES,
    extract_receipt_from_bytes,
    load_exclusion_criteria,
    load_state,
    save_state,
    dedupe_receipts,
    _merge_receipts_into_state,
    _filter_excluded_receipts,
    file_hash,
)

# Constants
SUPPORTED_TYPES = ["jpg", "jpeg", "png", "gif", "bmp", "webp", "tiff"]


def get_mime_type(filename: str) -> str | None:
    """Get MIME type from filename extension."""
    _, ext = os.path.splitext(filename)
    ext = ext.lower()
    return MIME_TYPES.get(ext)


def init_session_state():
    """Initialize session state variables."""
    if "uploaded_files" not in st.session_state:
        st.session_state.uploaded_files = {}
    if "processing_results" not in st.session_state:
        st.session_state.processing_results = []
    if "processing_complete" not in st.session_state:
        st.session_state.processing_complete = False
    if "duplicates_found" not in st.session_state:
        st.session_state.duplicates_found = []
    if "api_key" not in st.session_state:
        st.session_state.api_key = ""
    if "api_provider" not in st.session_state:
        st.session_state.api_provider = "OpenAI"


def remove_file(filename: str):
    """Remove a file from the upload queue."""
    if filename in st.session_state.uploaded_files:
        del st.session_state.uploaded_files[filename]


def clear_all_files():
    """Clear all uploaded files."""
    st.session_state.uploaded_files = {}
    st.session_state.processing_results = []
    st.session_state.processing_complete = False
    st.session_state.duplicates_found = []


def reset_processing():
    """Reset processing state for new uploads."""
    st.session_state.processing_results = []
    st.session_state.processing_complete = False
    st.session_state.duplicates_found = []


def set_api_key_env():
    """Set the API key in the environment based on provider selection."""
    if st.session_state.api_key:
        if st.session_state.api_provider == "OpenAI":
            os.environ["OPENAI_API_KEY"] = st.session_state.api_key
        else:
            os.environ["ANTHROPIC_API_KEY"] = st.session_state.api_key


def check_google_sheets_setup() -> tuple[bool, str]:
    """Check if Google Sheets is properly configured."""
    try:
        from sheets import get_gspread_client, SERVICE_ACCOUNT_FILE

        if not os.path.exists(SERVICE_ACCOUNT_FILE):
            return False, f"Service account file not found: {SERVICE_ACCOUNT_FILE}"

        # Try to authenticate
        client = get_gspread_client()
        return True, "Google Sheets configured successfully"
    except ImportError:
        return False, "gspread library not installed"
    except Exception as e:
        return False, f"Google Sheets error: {str(e)}"


def check_for_duplicates(receipts: list[dict]) -> list[dict]:
    """Check if any receipts already exist in Google Sheets."""
    try:
        from sheets import get_gspread_client, check_receipts_for_duplicates

        client = get_gspread_client()
        return check_receipts_for_duplicates(client, receipts)
    except Exception:
        return []


def upload_to_google_sheets(receipts: list[dict]) -> tuple[int, list[str]]:
    """Upload receipts to Google Sheets.

    Returns:
        Tuple of (count of uploaded receipts, list of error messages)
    """
    try:
        from sheets import (
            get_gspread_client,
            get_or_create_worksheet,
            get_existing_receipts,
            append_receipt,
        )
    except ImportError:
        return 0, ["gspread library not installed"]

    errors = []
    uploaded_count = 0

    try:
        client = get_gspread_client()
    except Exception as e:
        return 0, [f"Could not authenticate with Google Sheets: {str(e)}"]

    # Filter out excluded receipts
    receipts_to_upload, _ = _filter_excluded_receipts(receipts, print_warnings=False)

    worksheets = {}

    for receipt in receipts_to_upload:
        date_str = receipt.get("date")
        if not date_str:
            continue

        try:
            parsed_date = main._parse_date(date_str)
            if not parsed_date:
                errors.append(f"Could not parse date '{date_str}'")
                continue

            worksheet_title = parsed_date.strftime("%B %Y")
        except (ValueError, TypeError):
            errors.append(f"Invalid date format for '{date_str}'")
            continue

        if worksheet_title not in worksheets:
            try:
                worksheet = get_or_create_worksheet(client, worksheet_title)
                existing_receipts = get_existing_receipts(worksheet)
                worksheets[worksheet_title] = (worksheet, existing_receipts)
            except Exception as e:
                errors.append(f"Could not access worksheet '{worksheet_title}': {e}")
                continue

        worksheet, existing_receipts = worksheets[worksheet_title]

        receipt_key = (
            str(receipt.get("date")),
            str(receipt.get("amount")),
            str(receipt.get("vendor")),
        )

        if receipt_key not in existing_receipts:
            try:
                append_receipt(worksheet, receipt)
                existing_receipts.add(receipt_key)
                uploaded_count += 1
            except Exception as e:
                errors.append(f"Could not append receipt: {e}")

    return uploaded_count, errors


def process_receipts(files_to_process: dict, provider: str = "Anthropic") -> list[dict]:
    """Process uploaded receipt files.

    Args:
        files_to_process: Dict mapping filename to (bytes, mime_type)
        provider: LLM provider to use ("Anthropic" or "OpenAI")

    Returns:
        List of processed receipt dicts
    """
    exclusion_criteria = load_exclusion_criteria()
    results = []

    for filename, (file_bytes, mime_type) in files_to_process.items():
        try:
            # Encode to base64
            image_data = base64.standard_b64encode(file_bytes).decode("utf-8")

            # Extract receipt data
            receipt_data = extract_receipt_from_bytes(
                image_data, mime_type, exclusion_criteria, provider=provider
            )

            # Add source info
            receipt_data["source_file"] = filename

            # Compute hash for state tracking
            import hashlib

            h = hashlib.sha256()
            h.update(file_bytes)
            receipt_data["source_hash"] = h.hexdigest()

            results.append(receipt_data)

        except Exception as e:
            results.append(
                {
                    "source_file": filename,
                    "isValidReceipt": False,
                    "validationError": f"Processing error: {str(e)}",
                    "id": "",
                    "amount": 0.0,
                    "date": "",
                    "vendor": "",
                    "category": [],
                    "paymentMethod": [],
                    "excludeFromTable": False,
                    "exclusionReason": "",
                }
            )

    return results


def render_header():
    """Render the app header."""
    st.title("🧾 Receipt Ranger")
    st.markdown(
        """
        Upload receipt images to extract structured data and sync to Google Sheets.
        """
    )


def render_api_key_section():
    """Render the API key input section."""
    with st.expander("🔑 API Configuration", expanded=not st.session_state.api_key):
        st.markdown(
            """
            Enter your API key to process receipts. Your key is stored only in
            your browser session and is never saved to disk.
            """
        )

        col1, col2 = st.columns([1, 2])

        with col1:
            provider = st.selectbox(
                "Provider",
                ["OpenAI", "Anthropic"],
                key="api_provider_select",
                index=0 if st.session_state.api_provider == "OpenAI" else 1,
            )
            st.session_state.api_provider = provider

        with col2:
            api_key = st.text_input(
                "API Key",
                type="password",
                value=st.session_state.api_key,
                placeholder="sk-..." if provider == "OpenAI" else "sk-ant-...",
                key="api_key_input",
            )
            st.session_state.api_key = api_key

        if st.session_state.api_key:
            st.success("✓ API key configured")


def render_google_sheets_status():
    """Render Google Sheets connection status."""
    sheets_ok, sheets_msg = check_google_sheets_setup()

    with st.expander("📊 Google Sheets Status", expanded=not sheets_ok):
        if sheets_ok:
            st.success(f"✓ {sheets_msg}")
        else:
            st.warning(f"⚠ {sheets_msg}")
            st.markdown(
                """
                **To set up Google Sheets integration:**
                1. Create a Google Cloud project and enable the Sheets API
                2. Create a service account and download the JSON credentials
                3. Save the credentials as `service_account.json` in the project root
                4. Share your Google Sheet with the service account email

                See the README for detailed instructions.
                """
            )

    return sheets_ok


def render_file_upload():
    """Render the file upload section."""
    st.subheader("📤 Upload Receipts")

    uploaded = st.file_uploader(
        "Drop receipt images here",
        type=SUPPORTED_TYPES,
        accept_multiple_files=True,
        key="file_uploader",
        help="Supported formats: JPG, PNG, GIF, BMP, WebP, TIFF",
    )

    # Process newly uploaded files
    if uploaded:
        for file in uploaded:
            if file.name not in st.session_state.uploaded_files:
                mime_type = get_mime_type(file.name)
                if mime_type:
                    st.session_state.uploaded_files[file.name] = (
                        file.getvalue(),
                        mime_type,
                    )
                    reset_processing()


def render_file_preview():
    """Render preview of uploaded files with remove buttons."""
    if not st.session_state.uploaded_files:
        return

    st.subheader("📋 Selected Files")

    # Clear all button
    if st.button("🗑️ Clear All", key="clear_all"):
        clear_all_files()
        st.rerun()

    # Display files in a grid
    cols = st.columns(3)

    for idx, (filename, (file_bytes, mime_type)) in enumerate(
        st.session_state.uploaded_files.items()
    ):
        col = cols[idx % 3]

        with col:
            # Create a container for each file
            with st.container():
                # Display thumbnail
                caption = filename[:20] + "..." if len(filename) > 20 else filename
                st.image(file_bytes, caption=caption, width=150)

                # Remove button
                if st.button("✕ Remove", key=f"remove_{filename}"):
                    remove_file(filename)
                    st.rerun()


def render_submit_section(sheets_available: bool):
    """Render the submit button and processing section."""
    if not st.session_state.uploaded_files:
        st.info("Upload receipt images to get started.")
        return

    if not st.session_state.api_key:
        st.warning("Please enter your API key above to process receipts.")
        return

    st.divider()

    # Submit button
    num_files = len(st.session_state.uploaded_files)
    submit_label = f"🚀 Process {num_files} Receipt{'s' if num_files > 1 else ''}"

    if st.button(submit_label, type="primary", key="submit_btn"):
        process_and_display_results(sheets_available)


def process_and_display_results(sheets_available: bool):
    """Process receipts and display results."""
    # Set the API key in environment
    set_api_key_env()

    num_files = len(st.session_state.uploaded_files)

    # Create a prominent processing container
    processing_container = st.container()

    with processing_container:
        st.markdown("---")
        st.markdown("### Processing Receipts...")

        # Progress bar
        progress_bar = st.progress(0)
        status_text = st.empty()

        # Process files one by one with progress updates
        results = []
        exclusion_criteria = load_exclusion_criteria()

        for idx, (filename, (file_bytes, mime_type)) in enumerate(
            st.session_state.uploaded_files.items()
        ):
            # Update progress
            progress = (idx) / num_files
            progress_bar.progress(progress)
            status_text.markdown(
                f"**Processing {idx + 1} of {num_files}:** `{filename}`"
            )

            try:
                # Encode to base64
                image_data = base64.standard_b64encode(file_bytes).decode("utf-8")

                # Extract receipt data using the selected provider
                receipt_data = extract_receipt_from_bytes(
                    image_data,
                    mime_type,
                    exclusion_criteria,
                    provider=st.session_state.api_provider,
                )

                # Add source info
                receipt_data["source_file"] = filename

                # Compute hash for state tracking
                import hashlib

                h = hashlib.sha256()
                h.update(file_bytes)
                receipt_data["source_hash"] = h.hexdigest()

                results.append(receipt_data)

            except Exception as e:
                results.append(
                    {
                        "source_file": filename,
                        "isValidReceipt": False,
                        "validationError": f"Processing error: {str(e)}",
                        "id": "",
                        "amount": 0.0,
                        "date": "",
                        "vendor": "",
                        "category": [],
                        "paymentMethod": [],
                        "excludeFromTable": False,
                        "exclusionReason": "",
                    }
                )

        # Complete progress
        progress_bar.progress(1.0)
        status_text.markdown("**Processing complete!**")

        st.session_state.processing_results = results
        st.session_state.processing_complete = True

    # Separate valid and invalid results
    valid_receipts = [r for r in results if r.get("isValidReceipt", False)]
    invalid_receipts = [r for r in results if not r.get("isValidReceipt", False)]

    # Display invalid receipt warnings
    if invalid_receipts:
        st.error(f"⚠ {len(invalid_receipts)} file(s) were not valid receipts:")
        for receipt in invalid_receipts:
            st.warning(
                f"**{receipt.get('source_file', 'Unknown')}**: "
                f"{receipt.get('validationError', 'Unknown error')}"
            )

    if not valid_receipts:
        st.error("No valid receipts were found in the uploaded images.")
        return

    # Check for duplicates in Google Sheets
    if sheets_available:
        duplicates = check_for_duplicates(valid_receipts)
        st.session_state.duplicates_found = duplicates

        if duplicates:
            st.warning(
                f"⚠ {len(duplicates)} receipt(s) already exist in Google Sheets:"
            )
            for dup in duplicates:
                st.info(
                    f"• {dup.get('vendor', 'Unknown')} - "
                    f"${dup.get('amount', 0):.2f} on {dup.get('date', 'Unknown')}"
                )

    # Display results
    st.success(f"✓ Successfully processed {len(valid_receipts)} receipt(s)")

    # Show results table
    render_results_table(valid_receipts)

    # Save to state file
    state = load_state()
    _merge_receipts_into_state(state, valid_receipts)
    save_state(state)

    # Upload to Google Sheets
    if sheets_available:
        st.divider()
        st.subheader("📊 Google Sheets Upload")

        # Filter out receipts that already exist
        existing_keys = {
            (str(d.get("date")), str(d.get("amount")), str(d.get("vendor")))
            for d in st.session_state.duplicates_found
        }

        new_receipts = [
            r
            for r in valid_receipts
            if (str(r.get("date")), str(r.get("amount")), str(r.get("vendor")))
            not in existing_keys
        ]

        if new_receipts:
            with st.spinner("Uploading to Google Sheets..."):
                uploaded_count, errors = upload_to_google_sheets(new_receipts)

            if uploaded_count > 0:
                st.success(
                    f"✓ Uploaded {uploaded_count} new receipt(s) to Google Sheets"
                )

            if errors:
                for error in errors:
                    st.error(f"Upload error: {error}")
        else:
            st.info("All receipts already exist in Google Sheets. Nothing to upload.")


def render_results_table(receipts: list[dict]):
    """Render a table of processed receipts."""
    st.subheader("📝 Extracted Data")

    # Prepare data for display
    table_data = []
    for r in receipts:
        categories = ", ".join(r.get("category", [])) if r.get("category") else ""
        excluded = "Yes" if r.get("excludeFromTable") else "No"

        table_data.append(
            {
                "File": r.get("source_file", "")[:25],
                "Amount": f"${r.get('amount', 0):.2f}",
                "Date": r.get("date", ""),
                "Vendor": r.get("vendor", ""),
                "Category": categories,
                "Excluded": excluded,
            }
        )

    st.table(table_data)

    # Show excluded receipts info
    excluded_receipts = [r for r in receipts if r.get("excludeFromTable")]
    if excluded_receipts:
        with st.expander(f"ℹ️ {len(excluded_receipts)} receipt(s) excluded from table"):
            for r in excluded_receipts:
                st.write(
                    f"**{r.get('vendor', 'Unknown')}**: "
                    f"{r.get('exclusionReason', 'No reason')}"
                )


def render_download_section(receipts: list[dict]):
    """Render download buttons for results."""
    if not receipts:
        return

    st.divider()
    st.subheader("💾 Download Results")

    col1, col2 = st.columns(2)

    # TSV download
    with col1:
        tsv_lines = main._build_tsv_lines(receipts)
        tsv_content = "\n".join(tsv_lines)

        st.download_button(
            label="📄 Download TSV",
            data=tsv_content,
            file_name=f"receipts-{datetime.now().strftime('%Y%m%d-%H%M%S')}.tsv",
            mime="text/tab-separated-values",
        )

    # JSON download
    with col2:
        import json

        json_content = json.dumps(receipts, indent=2)

        st.download_button(
            label="📋 Download JSON",
            data=json_content,
            file_name=f"receipts-{datetime.now().strftime('%Y%m%d-%H%M%S')}.json",
            mime="application/json",
        )


def main_app():
    """Main application entry point."""
    init_session_state()

    render_header()

    st.divider()

    # Configuration sections
    render_api_key_section()
    sheets_available = render_google_sheets_status()

    st.divider()

    # File upload and management
    render_file_upload()
    render_file_preview()

    # Submit and results
    render_submit_section(sheets_available)

    # Show download options if we have results
    if st.session_state.processing_complete and st.session_state.processing_results:
        valid_receipts = [
            r
            for r in st.session_state.processing_results
            if r.get("isValidReceipt", False)
        ]
        if valid_receipts:
            render_download_section(valid_receipts)

    # Footer
    st.divider()
    st.caption("Receipt Ranger v0.4.2 | Process receipt images with AI")


if __name__ == "__main__":
    main_app()
