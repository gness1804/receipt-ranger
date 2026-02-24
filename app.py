"""Receipt Ranger - Streamlit Frontend"""

import base64
import os

from dotenv import load_dotenv

load_dotenv()

import streamlit as st  # noqa: E402
from datetime import datetime  # noqa: E402

# Must set page config first, before any other st commands
st.set_page_config(
    page_title="Receipt Ranger",
    page_icon="🧾",
    layout="centered",
    initial_sidebar_state="collapsed",
)

# Sync Streamlit Cloud secrets into os.environ so all modules that use
# os.environ.get() work in both local (.env) and Streamlit Cloud (st.secrets)
# contexts without modification.
try:
    for _k, _v in st.secrets.items():
        if isinstance(_v, str):
            os.environ.setdefault(_k, _v)
except Exception:
    pass

import main  # noqa: E402
from main import (  # noqa: E402
    MIME_TYPES,
    extract_receipt_from_bytes,
    load_exclusion_criteria,
    _filter_excluded_receipts,
)

# Constants
SUPPORTED_TYPES = ["jpg", "jpeg", "png", "gif", "bmp", "webp", "tiff"]
GOOGLE_SHEETS_ENABLED = os.environ.get("ENABLE_GOOGLE_SHEETS", "true").lower() == "true"
OWNER_OPENAI_API_KEY = os.environ.get("OWNER_OPENAI_API_KEY", "")
OWNER_ANTHROPIC_API_KEY = os.environ.get("OWNER_ANTHROPIC_API_KEY", "")


def is_owner_api_key() -> bool:
    """Check if the current session's API key matches the owner's key."""
    from session import decrypt_api_key

    token = st.session_state.get("api_key_token", "")
    api_key = decrypt_api_key(token)
    if not api_key:
        return False
    provider = st.session_state.get("api_provider", "OpenAI")
    if provider == "OpenAI":
        return bool(OWNER_OPENAI_API_KEY) and api_key == OWNER_OPENAI_API_KEY
    else:
        return bool(OWNER_ANTHROPIC_API_KEY) and api_key == OWNER_ANTHROPIC_API_KEY


def get_mime_type(filename: str) -> str | None:
    """Get MIME type from filename extension."""
    _, ext = os.path.splitext(filename)
    ext = ext.lower()
    return MIME_TYPES.get(ext)


def init_session_state():
    """Initialize session state variables."""
    if "uploaded_files" not in st.session_state:
        st.session_state.uploaded_files = {}
    if "removed_files" not in st.session_state:
        st.session_state.removed_files = set()
    if "current_upload_names" not in st.session_state:
        st.session_state.current_upload_names = set()
    if "uploader_key" not in st.session_state:
        st.session_state.uploader_key = 0
    if "processing_results" not in st.session_state:
        st.session_state.processing_results = []
    if "processing_complete" not in st.session_state:
        st.session_state.processing_complete = False
    if "duplicates_found" not in st.session_state:
        st.session_state.duplicates_found = []
    if "api_key_token" not in st.session_state:
        st.session_state.api_key_token = ""
    if "api_key_clear_pending" not in st.session_state:
        st.session_state.api_key_clear_pending = False
    if "api_provider" not in st.session_state:
        st.session_state.api_provider = "OpenAI"


def remove_file(filename: str):
    """Remove a file from the upload queue."""
    if filename in st.session_state.uploaded_files:
        del st.session_state.uploaded_files[filename]
    st.session_state.removed_files.add(filename)
    reset_processing()


def clear_all_files():
    """Clear all uploaded files."""
    st.session_state.uploaded_files = {}
    st.session_state.removed_files = set()
    st.session_state.current_upload_names = set()
    st.session_state.uploader_key += 1
    st.session_state.processing_results = []
    st.session_state.processing_complete = False
    st.session_state.duplicates_found = []


def reset_processing():
    """Reset processing state for new uploads."""
    st.session_state.processing_results = []
    st.session_state.processing_complete = False
    st.session_state.duplicates_found = []


def set_api_key_env():
    """Set the API key in the environment based on provider selection.

    Decrypts the stored token on demand; plaintext never persists in session_state.
    """
    from session import decrypt_api_key

    token = st.session_state.get("api_key_token", "")
    api_key = decrypt_api_key(token)
    if api_key:
        if st.session_state.api_provider == "OpenAI":
            os.environ["OPENAI_API_KEY"] = api_key
        else:
            os.environ["ANTHROPIC_API_KEY"] = api_key


def check_google_sheets_setup() -> tuple[bool, str]:
    """Check if Google Sheets is properly configured."""
    try:
        from sheets import get_gspread_client, SERVICE_ACCOUNT_FILE

        if not os.path.exists(SERVICE_ACCOUNT_FILE):
            return False, f"Service account file not found: {SERVICE_ACCOUNT_FILE}"

        # Try to authenticate
        get_gspread_client()
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
    if GOOGLE_SHEETS_ENABLED and is_owner_api_key():
        description = (
            "Upload receipt images to extract structured data and "
            "sync to Google Sheets (some setup required). "
            "Also outputs data to TSV and CSV tables."
        )
    else:
        description = (
            "Upload receipt images to extract structured data. "
            "Outputs data as TSV and CSV tables."
        )
    st.markdown(description)


def _load_cookie_to_session(cookie) -> None:
    """Load persisted encrypted token and provider from browser cookies.

    Only loads the token if the session doesn't already have one and the cookie
    contains a valid (decryptable) Fernet token.
    """
    if st.session_state.api_key_token:
        return
    stored = cookie.get("rr_session")
    if stored:
        from session import decrypt_api_key

        if decrypt_api_key(stored) is not None:
            st.session_state.api_key_token = stored
            saved_provider = cookie.get("rr_provider")
            if saved_provider in ("OpenAI", "Anthropic"):
                st.session_state.api_provider = saved_provider


def render_api_key_section(cookie=None):
    """Render the API key input section."""
    from session import decrypt_api_key, encrypt_api_key, mask_api_key

    has_token = bool(st.session_state.api_key_token)
    with st.expander("🔑 API Configuration", expanded=not has_token):
        st.markdown(
            """
            Enter your API key to process receipts. Your key is encrypted with
            Fernet symmetric encryption and saved as a secure browser cookie for
            7 days — it is never stored as plaintext.
            """
        )

        col1, col2 = st.columns([1, 2])

        with col1:
            provider = st.selectbox(
                "Provider",
                ["OpenAI", "Anthropic"],
                index=0 if st.session_state.api_provider == "OpenAI" else 1,
            )
            st.session_state.api_provider = provider

        with col2:
            if has_token:
                decrypted = decrypt_api_key(st.session_state.api_key_token)
                masked = mask_api_key(decrypted) if decrypted else "Invalid token"
                st.success(f"✓ API key configured: `{masked}`")
                if st.button("Change API key", key="change_api_key_btn"):
                    st.session_state.api_key_token = ""
                    if cookie is not None:
                        # Defer cookie.remove() to the next render via the flag.
                        # Calling cookie.remove() + st.rerun() inline would abort
                        # this render before the component JS could execute.
                        st.session_state.api_key_clear_pending = True
                    st.rerun()
            else:
                api_key = st.text_input(
                    "API Key",
                    type="password",
                    placeholder="sk-..." if provider == "OpenAI" else "sk-ant-...",
                    key="api_key_input",
                )
                if api_key:
                    token = encrypt_api_key(api_key)
                    st.session_state.api_key_token = token
                    if cookie is not None:
                        cookie.set("rr_session", token, max_age=7 * 24 * 60 * 60)
                        cookie.set("rr_provider", provider, max_age=7 * 24 * 60 * 60)
                    # Show immediate feedback without waiting for the cookie
                    # component's async rerun. Don't call st.rerun() here — it
                    # would abort this render before the component JS executes.
                    masked = mask_api_key(decrypt_api_key(token) or "")
                    st.success(f"✓ API key configured: `{masked}`")


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

    st.markdown(
        """
        <style>
        [data-testid="stFileUploader"] ul { display: none !important; }
        [data-testid="stFileUploader"] li { display: none !important; }
        [data-testid="stFileUploader"] [data-testid="stFileUploaderFile"] {
            display: none !important;
        }
        </style>
        """,
        unsafe_allow_html=True,
    )

    uploaded = st.file_uploader(
        "Drop receipt images here",
        type=SUPPORTED_TYPES,
        accept_multiple_files=True,
        key=f"file_uploader_{st.session_state.uploader_key}",
        help="Supported formats: JPG, PNG, GIF, BMP, WebP, TIFF",
    )

    # Process newly uploaded files
    if uploaded:
        st.session_state.current_upload_names = {f.name for f in uploaded}
        for file in uploaded:
            if file.name in st.session_state.removed_files:
                continue
            if file.name not in st.session_state.uploaded_files:
                mime_type = get_mime_type(file.name)
                if mime_type:
                    st.session_state.uploaded_files[file.name] = (
                        file.getvalue(),
                        mime_type,
                    )
                    reset_processing()
    else:
        st.session_state.current_upload_names = set()


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

    if not st.session_state.api_key_token:
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

    # NOTE: Duplicate detection in the web app relies on Google Sheets
    # (owner-only). The CLI still uses processed_receipts.json for local
    # dedup. A per-user persistence layer (e.g. DynamoDB) would be needed
    # if the app scales beyond casual use without Google Sheets.

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
    from streamlit_cookies_controller import CookieController

    init_session_state()

    # Cookie-based session persistence (mirrors FAC's 7-day session cookie)
    cookie = CookieController()

    # Deferred cookie removal: "Change API key" sets this flag on the previous
    # render so that cookie.remove() is called here (after rerun) rather than
    # inline with st.rerun(), which would abort the render before the component
    # JS could execute and actually remove the cookie.
    clear_pending = st.session_state.api_key_clear_pending
    if clear_pending:
        cookie.remove("rr_session")
        cookie.remove("rr_provider")
        st.session_state.api_key_clear_pending = False

    if not clear_pending:
        _load_cookie_to_session(cookie)

    render_header()

    st.divider()

    # Configuration sections
    render_api_key_section(cookie)
    if GOOGLE_SHEETS_ENABLED and is_owner_api_key():
        sheets_available = render_google_sheets_status()
    else:
        sheets_available = False

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
    st.caption("Receipt Ranger v0.7.1 | Process receipt images with AI")


if __name__ == "__main__":
    main_app()
