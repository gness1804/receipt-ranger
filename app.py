"""Receipt Ranger - Streamlit Frontend"""

import base64
import os
from concurrent.futures import ThreadPoolExecutor, TimeoutError as FuturesTimeoutError

from dotenv import load_dotenv

load_dotenv()

import streamlit as st  # noqa: E402
from datetime import datetime  # noqa: E402

from design import (  # noqa: E402
    current_theme,
    get_logo_path,
    get_logo_svg,
    init_theme,
    inject_design_system,
    toggle_theme,
)

st.set_page_config(
    page_title="Receipt Ranger",
    page_icon=get_logo_path(),
    layout="centered",
    initial_sidebar_state="expanded",
)

# Hide Streamlit's default chrome for a cleaner production look.
st.markdown(
    """
    <style>
        #MainMenu {visibility: hidden;}
        footer {visibility: hidden;}
        [data-testid="stMainMenu"] {visibility: hidden;}
        [data-testid="stAppDeployButton"] {visibility: hidden;}
        [data-testid="stToolbarActions"] {visibility: hidden;}
    </style>
    """,
    unsafe_allow_html=True,
)

import main  # noqa: E402
from main import (  # noqa: E402
    MIME_TYPES,
    PromptInjectionError,
    extract_receipt_from_bytes,
    load_exclusion_criteria,
    _filter_excluded_receipts,
)
from image_conversion import (  # noqa: E402
    HEICConversionError,
    is_heic_filename,
    maybe_convert_heic,
)

# Constants
SUPPORTED_TYPES = [
    "jpg",
    "jpeg",
    "png",
    "gif",
    "bmp",
    "webp",
    "tiff",
    "heic",
    "heif",
]
GOOGLE_SHEETS_ENABLED = os.environ.get("ENABLE_GOOGLE_SHEETS", "true").lower() == "true"
OWNER_OPENAI_API_KEY = os.environ.get("OWNER_OPENAI_API_KEY", "")
OWNER_ANTHROPIC_API_KEY = os.environ.get("OWNER_ANTHROPIC_API_KEY", "")

# Timeout (in seconds) for a single LLM receipt-processing call.
RECEIPT_PROCESSING_TIMEOUT = 60

# API-key cookie persistence durations (in seconds). The Fernet-encrypted key
# token is stored in a browser cookie; these control how long it survives.
# SESSION_ONLY_MAX_AGE is None: no cookie is written at all (the library cannot
# create a true session cookie), so the key lives only in the active session.
SESSION_ONLY_MAX_AGE = None
DEFAULT_KEY_MAX_AGE = 7 * 24 * 60 * 60  # 7 days
REMEMBER_DEVICE_MAX_AGE = 90 * 24 * 60 * 60  # 90 days ("remember this device")

# Ordered persistence choices shown in the API-key UI. "7 days" is the default
# selection (preserves prior behavior); the other two are deliberate opt-ins.
KEY_PERSISTENCE_LABELS = [
    "This session only",
    "7 days",
    "Remember this device (90 days)",
]
KEY_PERSISTENCE_MAX_AGES = {
    "This session only": SESSION_ONLY_MAX_AGE,
    "7 days": DEFAULT_KEY_MAX_AGE,
    "Remember this device (90 days)": REMEMBER_DEVICE_MAX_AGE,
}
DEFAULT_KEY_PERSISTENCE_INDEX = 1


def is_owner_api_key() -> bool:
    """Check if the current session's API key matches the owner's key."""
    import hmac

    from session import decrypt_api_key

    token = st.session_state.get("api_key_token", "")
    api_key = decrypt_api_key(token)
    if not api_key:
        return False
    provider = st.session_state.get("api_provider", "OpenAI")
    # Use a constant-time compare so response timing can't reveal the owner key.
    if provider == "OpenAI":
        return bool(OWNER_OPENAI_API_KEY) and hmac.compare_digest(
            api_key, OWNER_OPENAI_API_KEY
        )
    else:
        return bool(OWNER_ANTHROPIC_API_KEY) and hmac.compare_digest(
            api_key, OWNER_ANTHROPIC_API_KEY
        )


def set_session_cookie(cookie, name: str, value: str, max_age: int | None) -> None:
    """Write a persistence cookie, honoring an optional max_age.

    max_age=None creates a true browser-session cookie (cleared when the
    browser closes); a positive integer sets an explicit lifetime in seconds.
    secure=True keeps the cookie HTTPS-only in production — browsers exempt
    localhost from the Secure requirement, so local dev still works.

    NOTE: streamlit-cookies-controller cannot create a true browser-session
    cookie — its frontend always coerces ``options.expires`` to a Date, so
    omitting it throws. For the session-only case we therefore write no cookie
    at all: the encrypted token lives only in ``st.session_state`` for the
    active session and is gone once that session ends.
    """
    if max_age is None:
        return
    cookie.set(name, value, max_age=max_age, secure=True)


def get_mime_type(filename: str) -> str | None:
    """Get MIME type from filename extension."""
    _, ext = os.path.splitext(filename)
    ext = ext.lower()
    return MIME_TYPES.get(ext)


def init_session_state():
    """Initialize session state variables."""
    if "uploaded_files" not in st.session_state:
        st.session_state.uploaded_files = {}
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
    if "api_key_save_pending_token" not in st.session_state:
        st.session_state.api_key_save_pending_token = None
    if "api_key_save_pending_provider" not in st.session_state:
        st.session_state.api_key_save_pending_provider = None
    if "api_key_save_pending_max_age" not in st.session_state:
        st.session_state.api_key_save_pending_max_age = DEFAULT_KEY_MAX_AGE
    if "api_provider" not in st.session_state:
        st.session_state.api_provider = "OpenAI"


def remove_file(filename: str):
    """Remove a file from the upload queue."""
    if filename in st.session_state.uploaded_files:
        del st.session_state.uploaded_files[filename]
    # Reset the uploader widget so Streamlit doesn't re-emit removed files.
    st.session_state.uploader_key += 1
    reset_processing()


def clear_all_files():
    """Clear all uploaded files."""
    st.session_state.uploaded_files = {}
    st.session_state.uploader_key += 1
    st.session_state.processing_results = []
    st.session_state.processing_complete = False
    st.session_state.duplicates_found = []


def reset_processing():
    """Reset processing state for new uploads."""
    st.session_state.processing_results = []
    st.session_state.processing_complete = False
    st.session_state.duplicates_found = []


def queue_uploaded_file(filename: str, file_bytes: bytes, mime_type: str) -> bool:
    """Queue an uploaded file with collision-safe naming.

    Returns:
        True when a new file was queued, False when it was an exact duplicate.
    """
    # Skip exact duplicate content already in the queue.
    for existing_bytes, _ in st.session_state.uploaded_files.values():
        if existing_bytes == file_bytes:
            return False

    base, ext = os.path.splitext(filename)
    candidate = filename
    suffix = 2
    while candidate in st.session_state.uploaded_files:
        candidate = f"{base} ({suffix}){ext}"
        suffix += 1

    st.session_state.uploaded_files[candidate] = (file_bytes, mime_type)
    return True


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
        from sheets import get_gspread_client

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


def upload_to_google_sheets(receipts: list[dict]) -> tuple[int, list[str], list[str]]:
    """Upload receipts to Google Sheets.

    Returns:
        Tuple of (count of uploaded receipts, list of error messages,
        list of advisory notices).
    """
    try:
        from sheets import (
            get_gspread_client,
            get_or_create_worksheet,
            get_existing_receipts,
            append_receipt,
            _format_date_for_sheets,
        )
    except ImportError:
        return 0, ["gspread library not installed"], []

    errors = []
    notices = []
    uploaded_count = 0

    try:
        client = get_gspread_client()
    except Exception as e:
        return 0, [f"Could not authenticate with Google Sheets: {str(e)}"], []

    # Filter out excluded receipts
    receipts_to_upload, _ = _filter_excluded_receipts(receipts, print_warnings=False)

    worksheets = {}

    for receipt in receipts_to_upload:
        date_str = receipt.get("date") or ""

        # Receipts with a missing/unparseable date go to the "Unknown Date"
        # worksheet (issue #49) instead of being skipped, so the user only has
        # to fill in the date manually rather than re-enter the whole receipt.
        worksheet_title, normalized_date = main._resolve_worksheet_for_date(date_str)

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
            _format_date_for_sheets(normalized_date),
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
        elif not normalized_date:
            # Undated receipts dedupe on (vendor, amount) alone, so a genuinely
            # distinct purchase can be mistaken for a duplicate. Advise the user
            # instead of dropping it silently (issue #49).
            vendor = receipt.get("vendor") or "Unknown vendor"
            amount = receipt.get("amount") or 0
            notices.append(
                f"Skipped an undated receipt matching an existing "
                f"'Unknown Date' entry ({vendor}, ${amount:.2f}). If this is a "
                f"distinct purchase, add it manually — undated receipts with "
                f"the same vendor and amount can't be told apart."
            )

    return uploaded_count, errors, notices


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
    """Render the app header — editorial hero with eyebrow + serif headline."""
    if GOOGLE_SHEETS_ENABLED and is_owner_api_key():
        lede = (
            "Upload receipt images. I extract the vendor, date, amount, and "
            "category, then sync to Google Sheets and export TSV or JSON."
        )
    else:
        lede = (
            "Upload receipt images. I extract the vendor, date, amount, and "
            "category, then export the results as TSV or JSON."
        )

    st.markdown(
        (
            '<div class="gn-welcome">'
            '<div class="eyebrow">Receipt Ranger</div>'
            "<h1>Turn receipts into structured data.</h1>"
            f'<p class="lede">{lede}</p>'
            "</div>"
        ),
        unsafe_allow_html=True,
    )


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


def render_sidebar(cookie=None) -> bool:
    """Render the sidebar: brand header, theme toggle, API key, Sheets status.

    Returns True if Google Sheets is available (owner-only).
    """
    from session import decrypt_api_key, encrypt_api_key, mask_api_key

    with st.sidebar:
        st.markdown(
            (
                '<div class="gn-sidebar-header">'
                f"{get_logo_svg()}"
                '<div class="gn-wordmark">Receipt '
                '<span class="accent">Ranger</span></div>'
                "</div>"
            ),
            unsafe_allow_html=True,
        )

        # Sun icon when dark is active (click to switch to light), moon when
        # light is active (click to switch to dark). Material icons keep us
        # within the brand rule that forbids emoji in production UI.
        theme = current_theme()
        toggle_label = "Light theme" if theme == "dark" else "Dark theme"
        toggle_icon = (
            ":material/light_mode:" if theme == "dark" else ":material/dark_mode:"
        )
        if st.button(
            toggle_label,
            key="theme_toggle",
            use_container_width=True,
            icon=toggle_icon,
        ):
            toggle_theme()
            st.rerun()

        st.divider()

        # API key configuration
        has_token = bool(st.session_state.api_key_token)
        with st.expander("API key", expanded=not has_token):
            st.markdown(
                "Your key is encrypted with Fernet symmetric encryption and "
                "stored only as an opaque token — never as plaintext. Choose "
                "how long to keep it on this device below."
            )

            provider = st.selectbox(
                "Provider",
                ["OpenAI", "Anthropic"],
                index=0 if st.session_state.api_provider == "OpenAI" else 1,
            )
            st.session_state.api_provider = provider

            if has_token:
                decrypted = decrypt_api_key(st.session_state.api_key_token)
                masked = mask_api_key(decrypted) if decrypted else "Invalid token"
                st.success(f"Key configured · `{masked}`")
                if st.button("Change API key", key="change_api_key_btn"):
                    st.session_state.api_key_token = ""
                    # Drop any in-flight deferred save so the cookie can't be
                    # re-written on the next render after the user just asked
                    # to clear it.
                    st.session_state.api_key_save_pending_token = None
                    st.session_state.api_key_save_pending_provider = None
                    if cookie is not None:
                        st.session_state.api_key_clear_pending = True
                    st.rerun()
            else:
                persistence_label = st.selectbox(
                    "Keep my key on this device",
                    KEY_PERSISTENCE_LABELS,
                    index=DEFAULT_KEY_PERSISTENCE_INDEX,
                    key="key_persistence_choice",
                    help=(
                        "Choose 'This session only' on a shared or public "
                        "computer — nothing is saved, so the key is dropped "
                        "when you reload the page or close the browser. "
                        "'7 days' and 'Remember this device (90 days)' save an "
                        "encrypted cookie so you don't have to re-enter your "
                        "key; pick 90 days for a personal phone or laptop you "
                        "trust."
                    ),
                )
                api_key = st.text_input(
                    "API key",
                    type="password",
                    placeholder="sk-..." if provider == "OpenAI" else "sk-ant-...",
                    key="api_key_input",
                )
                if api_key:
                    token = encrypt_api_key(api_key)
                    st.session_state.api_key_token = token
                    # Defer cookie.set to the next render. Calling cookie.set
                    # immediately followed by st.rerun() in the same script
                    # run aborts before the cookie-controller iframe can
                    # execute document.cookie = ... on the frontend, so the
                    # browser cookie never gets written and the key fails to
                    # persist across refreshes.
                    if cookie is not None:
                        st.session_state.api_key_save_pending_token = token
                        st.session_state.api_key_save_pending_provider = provider
                        st.session_state.api_key_save_pending_max_age = (
                            KEY_PERSISTENCE_MAX_AGES[persistence_label]
                        )
                    st.rerun()

        # Google Sheets status — owner only
        sheets_available = False
        if GOOGLE_SHEETS_ENABLED and is_owner_api_key():
            sheets_ok, sheets_msg = check_google_sheets_setup()
            with st.expander("Google Sheets", expanded=not sheets_ok):
                if sheets_ok:
                    st.success(sheets_msg)
                else:
                    st.warning(sheets_msg)
                    st.markdown(
                        "Set up: create a Google Cloud project, enable the "
                        "Sheets API, create a service account, save the JSON "
                        "credentials as `service_account.json`, and share "
                        "your sheet with the service account email."
                    )
            sheets_available = sheets_ok

        return sheets_available


def render_file_upload():
    """Render the file upload section."""
    st.subheader("Upload receipts")

    st.markdown(
        """
        <style>
        /* Hide native file list rendered by Streamlit's file uploader.
           We render our own thumbnail grid in render_file_preview(). */
        [data-testid="stFileUploader"] [data-testid="stFileUploaderFile"] {
            display: none !important;
        }
        [data-testid="stFileUploader"] [data-testid="stFileUploaderFileName"] {
            display: none !important;
        }
        [data-testid="stFileUploader"] [data-testid="stFileUploaderDeleteBtn"] {
            display: none !important;
        }
        [data-testid="stFileUploaderFileList"] {
            display: none !important;
        }
        [data-testid="stFileUploaderFileList"] img {
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
        help="Supported formats: JPG, PNG, GIF, BMP, WebP, TIFF, HEIC",
    )

    # Process newly uploaded files
    any_added = False
    if uploaded:
        for file in uploaded:
            mime_type = get_mime_type(file.name)
            if not mime_type:
                continue
            file_bytes = file.getvalue()
            display_name = file.name

            # HEIC isn't reliably decoded by the upstream LLM providers, so
            # convert it to JPEG transparently before queueing. The user sees
            # the converted filename in the preview so it's clear what will
            # be sent for processing.
            if is_heic_filename(file.name):
                try:
                    file_bytes, mime_type = maybe_convert_heic(
                        file_bytes, file.name, mime_type
                    )
                except HEICConversionError as e:
                    st.error(f"Could not convert HEIC file `{file.name}`: {e}")
                    continue
                base, _ = os.path.splitext(file.name)
                display_name = f"{base}.jpg"

            any_added = (
                queue_uploaded_file(display_name, file_bytes, mime_type) or any_added
            )

    if any_added:
        reset_processing()


def render_file_preview():
    """Render preview of uploaded files with remove buttons."""
    if not st.session_state.uploaded_files:
        return

    st.subheader("Selected files")

    if st.button("Clear all", key="clear_all", icon=":material/delete_sweep:"):
        clear_all_files()
        st.rerun()

    cols = st.columns(3)

    for idx, (filename, (file_bytes, mime_type)) in enumerate(
        st.session_state.uploaded_files.items()
    ):
        col = cols[idx % 3]

        with col:
            with st.container():
                caption = filename[:20] + "..." if len(filename) > 20 else filename
                st.image(file_bytes, caption=caption, width=150)

                if st.button(
                    "Remove", key=f"remove_{filename}", icon=":material/close:"
                ):
                    remove_file(filename)
                    st.rerun()


def render_submit_section(sheets_available: bool):
    """Render the submit button and processing section."""
    if not st.session_state.uploaded_files:
        st.info("Upload receipt images to get started.")
        return

    if not st.session_state.api_key_token:
        st.warning("Add your API key in the sidebar to process receipts.")
        return

    st.divider()

    num_files = len(st.session_state.uploaded_files)
    submit_label = f"Process {num_files} receipt{'s' if num_files > 1 else ''}"

    if st.button(
        submit_label,
        type="primary",
        key="submit_btn",
        icon=":material/play_arrow:",
    ):
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
        st.markdown("### Processing receipts")

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

            executor = ThreadPoolExecutor(max_workers=1)
            try:
                # Encode to base64
                image_data = base64.standard_b64encode(file_bytes).decode("utf-8")

                # Run the LLM call in a thread with a timeout so a
                # stalled provider cannot block the UI indefinitely.
                provider = st.session_state.api_provider
                future = executor.submit(
                    extract_receipt_from_bytes,
                    image_data,
                    mime_type,
                    exclusion_criteria,
                    provider=provider,
                )
                receipt_data = future.result(timeout=RECEIPT_PROCESSING_TIMEOUT)

                # Add source info
                receipt_data["source_file"] = filename

                # Compute hash for state tracking
                import hashlib

                h = hashlib.sha256()
                h.update(file_bytes)
                receipt_data["source_hash"] = h.hexdigest()

                results.append(receipt_data)

            except FuturesTimeoutError:
                st.error(
                    f"**Timeout:** Processing `{filename}` took longer "
                    f"than {RECEIPT_PROCESSING_TIMEOUT} seconds and was "
                    f"cancelled. The LLM provider may be experiencing "
                    f"issues — please try again later."
                )
                results.append(
                    {
                        "source_file": filename,
                        "isValidReceipt": False,
                        "validationError": (
                            f"Timed out after " f"{RECEIPT_PROCESSING_TIMEOUT}s"
                        ),
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
            except PromptInjectionError as e:
                st.error(
                    f"**Security Alert:** Processing halted for `{filename}`. " f"{e}"
                )
                results.append(
                    {
                        "source_file": filename,
                        "isValidReceipt": False,
                        "validationError": f"Blocked: {str(e)}",
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
            finally:
                # Always shut down the executor to prevent orphaned
                # threads from accumulating across files/requests.
                executor.shutdown(wait=False, cancel_futures=True)

        progress_bar.progress(1.0)
        status_text.markdown("**Processing complete.**")

        st.session_state.processing_results = results
        st.session_state.processing_complete = True

    valid_receipts = [r for r in results if r.get("isValidReceipt", False)]
    invalid_receipts = [r for r in results if not r.get("isValidReceipt", False)]

    if invalid_receipts:
        st.error(f"{len(invalid_receipts)} file(s) were not valid receipts:")
        for receipt in invalid_receipts:
            st.warning(
                f"**{receipt.get('source_file', 'Unknown')}** — "
                f"{receipt.get('validationError', 'Unknown error')}"
            )

    if not valid_receipts:
        st.error("No valid receipts were found in the uploaded images.")
        return

    if sheets_available:
        duplicates = check_for_duplicates(valid_receipts)
        st.session_state.duplicates_found = duplicates

        if duplicates:
            st.warning(f"{len(duplicates)} receipt(s) already exist in Google Sheets:")
            for dup in duplicates:
                st.info(
                    f"{dup.get('vendor', 'Unknown')} — "
                    f"${dup.get('amount', 0):.2f} on {dup.get('date', 'Unknown')}"
                )

    st.success(f"Processed {len(valid_receipts)} receipt(s).")

    # Show results table
    render_results_table(valid_receipts)

    # NOTE: Duplicate detection in the web app relies on Google Sheets
    # (owner-only). The CLI still uses processed_receipts.json for local
    # dedup. A per-user persistence layer (e.g. DynamoDB) would be needed
    # if the app scales beyond casual use without Google Sheets.

    if sheets_available:
        st.divider()
        st.subheader("Google Sheets upload")

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
                uploaded_count, errors, notices = upload_to_google_sheets(new_receipts)

            if uploaded_count > 0:
                st.success(
                    f"Uploaded {uploaded_count} new receipt(s) to Google Sheets."
                )

            for notice in notices:
                st.warning(notice)

            if errors:
                for error in errors:
                    st.error(f"Upload error: {error}")
        else:
            st.info("All receipts already exist in Google Sheets. Nothing to upload.")


def render_results_table(receipts: list[dict]):
    """Render a table of processed receipts."""
    st.subheader("Extracted data")

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

    excluded_receipts = [r for r in receipts if r.get("excludeFromTable")]
    if excluded_receipts:
        with st.expander(f"{len(excluded_receipts)} receipt(s) excluded from table"):
            for r in excluded_receipts:
                st.write(
                    f"**{r.get('vendor', 'Unknown')}** — "
                    f"{r.get('exclusionReason', 'No reason')}"
                )


def render_download_section(receipts: list[dict]):
    """Render download buttons for results."""
    if not receipts:
        return

    st.divider()
    st.subheader("Download results")

    col1, col2 = st.columns(2)

    with col1:
        tsv_lines = main._build_tsv_lines(receipts)
        tsv_content = "\n".join(tsv_lines)

        st.download_button(
            label="Download TSV",
            data=tsv_content,
            file_name=f"receipts-{datetime.now().strftime('%Y%m%d-%H%M%S')}.tsv",
            mime="text/tab-separated-values",
            icon=":material/download:",
        )

    with col2:
        import json

        json_content = json.dumps(receipts, indent=2)

        st.download_button(
            label="Download JSON",
            data=json_content,
            file_name=f"receipts-{datetime.now().strftime('%Y%m%d-%H%M%S')}.json",
            mime="application/json",
            icon=":material/download:",
        )


def main_app():
    """Main application entry point."""
    from streamlit_cookies_controller import CookieController

    init_theme()
    inject_design_system()
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

    # Deferred cookie save: the API-key input handler sets these flags and
    # reruns so that cookie.set() runs here (in a script that completes
    # without a trailing st.rerun()), letting the iframe actually write
    # document.cookie before being torn down.
    save_token = st.session_state.api_key_save_pending_token
    save_provider = st.session_state.api_key_save_pending_provider
    save_max_age = st.session_state.api_key_save_pending_max_age
    if save_token:
        # save_max_age comes from the user's persistence choice: None for a
        # session-only cookie, or a lifetime in seconds (7 or 90 days). The
        # provider cookie uses the same lifetime as the key cookie.
        set_session_cookie(cookie, "rr_session", save_token, save_max_age)
        if save_provider:
            set_session_cookie(cookie, "rr_provider", save_provider, save_max_age)
        st.session_state.api_key_save_pending_token = None
        st.session_state.api_key_save_pending_provider = None
        st.session_state.api_key_save_pending_max_age = DEFAULT_KEY_MAX_AGE

    if not clear_pending and not save_token:
        _load_cookie_to_session(cookie)

    sheets_available = render_sidebar(cookie)

    render_header()

    render_file_upload()
    render_file_preview()
    render_submit_section(sheets_available)

    if st.session_state.processing_complete and st.session_state.processing_results:
        valid_receipts = [
            r
            for r in st.session_state.processing_results
            if r.get("isValidReceipt", False)
        ]
        if valid_receipts:
            render_download_section(valid_receipts)

    st.markdown(
        (
            '<div class="gn-footer">'
            'Receipt Ranger · <span class="version">v0.14.0</span> · '
            "Structured data from receipt images."
            "</div>"
        ),
        unsafe_allow_html=True,
    )


if __name__ == "__main__":
    main_app()
