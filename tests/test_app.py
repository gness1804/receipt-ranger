"""Tests for Receipt Ranger Streamlit app."""

import os
import time
from concurrent.futures import TimeoutError as FuturesTimeoutError
from unittest.mock import MagicMock, patch

import pytest

# ---------------------------------------------------------------------------
# TestSession — tests for session.py encryption helpers
# ---------------------------------------------------------------------------


class TestSession:
    """Tests for the Fernet-based session encryption helpers."""

    def test_encrypt_then_decrypt_round_trips(self):
        from session import decrypt_api_key, encrypt_api_key

        original = "sk-test-key-1234567890"
        token = encrypt_api_key(original)
        assert token != original
        assert decrypt_api_key(token) == original

    def test_decrypt_invalid_token_returns_none(self):
        from session import decrypt_api_key

        assert decrypt_api_key("this-is-not-a-valid-token") is None

    def test_decrypt_empty_string_returns_none(self):
        from session import decrypt_api_key

        assert decrypt_api_key("") is None

    def test_mask_api_key_normal_key(self):
        from session import mask_api_key

        assert mask_api_key("sk-abcdefghijklmnopwxyz") == "sk-abcd...wxyz"

    def test_mask_api_key_short_key(self):
        from session import mask_api_key

        assert mask_api_key("short") == "***"

    def test_encrypted_tokens_are_opaque(self):
        """Encrypted token should not contain the plaintext key."""
        from session import encrypt_api_key

        plaintext = "sk-secret-api-key"
        token = encrypt_api_key(plaintext)
        assert plaintext not in token


class TestGetMimeType:
    def test_jpg_extension(self):
        from app import get_mime_type

        assert get_mime_type("receipt.jpg") == "image/jpeg"
        assert get_mime_type("receipt.jpeg") == "image/jpeg"

    def test_png_extension(self):
        from app import get_mime_type

        assert get_mime_type("receipt.png") == "image/png"

    def test_case_insensitive(self):
        from app import get_mime_type

        assert get_mime_type("receipt.JPG") == "image/jpeg"
        assert get_mime_type("receipt.PNG") == "image/png"

    def test_unsupported_extension(self):
        from app import get_mime_type

        assert get_mime_type("receipt.pdf") is None
        assert get_mime_type("receipt.txt") is None


class TestIsOwnerApiKey:
    """Tests for the is_owner_api_key() function.

    session.decrypt_api_key is patched so tests are independent of the
    runtime Fernet key. The session_state mock supplies api_key_token.
    """

    @patch("app.st")
    @patch("app.OWNER_OPENAI_API_KEY", "sk-owner-openai-key")
    @patch("app.OWNER_ANTHROPIC_API_KEY", "sk-ant-owner-key")
    @patch("session.decrypt_api_key", return_value="sk-owner-openai-key")
    def test_matching_openai_key(self, mock_decrypt, mock_st):
        mock_st.session_state.get = lambda k, d="": {
            "api_key_token": "encrypted-openai-owner-token",
            "api_provider": "OpenAI",
        }.get(k, d)

        from app import is_owner_api_key

        assert is_owner_api_key() is True

    @patch("app.st")
    @patch("app.OWNER_OPENAI_API_KEY", "sk-owner-openai-key")
    @patch("app.OWNER_ANTHROPIC_API_KEY", "sk-ant-owner-key")
    @patch("session.decrypt_api_key", return_value="sk-ant-owner-key")
    def test_matching_anthropic_key(self, mock_decrypt, mock_st):
        mock_st.session_state.get = lambda k, d="": {
            "api_key_token": "encrypted-anthropic-owner-token",
            "api_provider": "Anthropic",
        }.get(k, d)

        from app import is_owner_api_key

        assert is_owner_api_key() is True

    @patch("app.st")
    @patch("app.OWNER_OPENAI_API_KEY", "sk-owner-openai-key")
    @patch("app.OWNER_ANTHROPIC_API_KEY", "sk-ant-owner-key")
    @patch("session.decrypt_api_key", return_value="sk-some-other-key")
    def test_non_matching_key(self, mock_decrypt, mock_st):
        mock_st.session_state.get = lambda k, d="": {
            "api_key_token": "encrypted-other-token",
            "api_provider": "OpenAI",
        }.get(k, d)

        from app import is_owner_api_key

        assert is_owner_api_key() is False

    @patch("app.st")
    @patch("app.OWNER_OPENAI_API_KEY", "sk-owner-openai-key")
    @patch("app.OWNER_ANTHROPIC_API_KEY", "sk-ant-owner-key")
    @patch("session.decrypt_api_key", return_value=None)
    def test_empty_token(self, mock_decrypt, mock_st):
        mock_st.session_state.get = lambda k, d="": {
            "api_key_token": "",
            "api_provider": "OpenAI",
        }.get(k, d)

        from app import is_owner_api_key

        assert is_owner_api_key() is False

    @patch("app.st")
    @patch("app.OWNER_OPENAI_API_KEY", "")
    @patch("app.OWNER_ANTHROPIC_API_KEY", "")
    @patch("session.decrypt_api_key", return_value="sk-some-key")
    def test_no_owner_keys_configured(self, mock_decrypt, mock_st):
        mock_st.session_state.get = lambda k, d="": {
            "api_key_token": "encrypted-token",
            "api_provider": "OpenAI",
        }.get(k, d)

        from app import is_owner_api_key

        assert is_owner_api_key() is False


class TestSheetsAvailability:
    """Tests for dynamic sheets availability based on owner key."""

    @patch("app.is_owner_api_key", return_value=True)
    @patch("app.GOOGLE_SHEETS_ENABLED", True)
    def test_sheets_available_when_both_conditions_met(self, mock_owner):
        from app import GOOGLE_SHEETS_ENABLED, is_owner_api_key

        sheets_available = GOOGLE_SHEETS_ENABLED and is_owner_api_key()
        assert sheets_available is True

    @patch("app.is_owner_api_key", return_value=False)
    @patch("app.GOOGLE_SHEETS_ENABLED", True)
    def test_sheets_unavailable_when_key_doesnt_match(self, mock_owner):
        from app import GOOGLE_SHEETS_ENABLED, is_owner_api_key

        sheets_available = GOOGLE_SHEETS_ENABLED and is_owner_api_key()
        assert sheets_available is False

    @patch("app.is_owner_api_key", return_value=True)
    @patch("app.GOOGLE_SHEETS_ENABLED", False)
    def test_sheets_unavailable_when_flag_off(self, mock_owner):
        from app import GOOGLE_SHEETS_ENABLED, is_owner_api_key

        sheets_available = GOOGLE_SHEETS_ENABLED and is_owner_api_key()
        assert sheets_available is False

    @patch("app.is_owner_api_key", return_value=False)
    @patch("app.GOOGLE_SHEETS_ENABLED", False)
    def test_sheets_unavailable_when_both_off(self, mock_owner):
        from app import GOOGLE_SHEETS_ENABLED, is_owner_api_key

        sheets_available = GOOGLE_SHEETS_ENABLED and is_owner_api_key()
        assert sheets_available is False


class TestCheckGoogleSheetsSetup:
    @patch("sheets.os.path.exists")
    def test_missing_service_account_file(self, mock_exists):
        mock_exists.return_value = False
        from app import check_google_sheets_setup

        success, message = check_google_sheets_setup()
        assert success is False
        assert "not found" in message

    @patch("sheets.os.path.exists")
    @patch("sheets.gspread.service_account")
    def test_successful_setup(self, mock_service_account, mock_exists):
        mock_exists.return_value = True
        mock_service_account.return_value = MagicMock()

        from app import check_google_sheets_setup

        success, message = check_google_sheets_setup()
        assert success is True


class TestProcessReceipts:
    @patch("app.extract_receipt_from_bytes")
    @patch("app.load_exclusion_criteria")
    def test_processes_single_file(self, mock_exclusion, mock_extract):
        mock_exclusion.return_value = "No exclusion criteria."
        mock_extract.return_value = {
            "isValidReceipt": True,
            "validationError": "",
            "id": "r1",
            "amount": 25.50,
            "date": "01/20/2026",
            "vendor": "Test Store",
            "category": ["Food & Restaurants"],
            "paymentMethod": ["Card"],
            "excludeFromTable": False,
            "exclusionReason": "",
        }

        from app import process_receipts

        files = {"test.jpg": (b"fake image bytes", "image/jpeg")}
        results = process_receipts(files)

        assert len(results) == 1
        assert results[0]["isValidReceipt"] is True
        assert results[0]["vendor"] == "Test Store"
        assert results[0]["source_file"] == "test.jpg"

    @patch("app.extract_receipt_from_bytes")
    @patch("app.load_exclusion_criteria")
    def test_handles_invalid_receipt(self, mock_exclusion, mock_extract):
        mock_exclusion.return_value = "No exclusion criteria."
        mock_extract.return_value = {
            "isValidReceipt": False,
            "validationError": "Not a receipt image",
            "id": "",
            "amount": 0.0,
            "date": "",
            "vendor": "",
            "category": [],
            "paymentMethod": [],
            "excludeFromTable": False,
            "exclusionReason": "",
        }

        from app import process_receipts

        files = {"landscape.jpg": (b"not a receipt", "image/jpeg")}
        results = process_receipts(files)

        assert len(results) == 1
        assert results[0]["isValidReceipt"] is False
        assert "Not a receipt" in results[0]["validationError"]

    @patch("app.extract_receipt_from_bytes")
    @patch("app.load_exclusion_criteria")
    def test_handles_processing_error(self, mock_exclusion, mock_extract):
        mock_exclusion.return_value = "No exclusion criteria."
        mock_extract.side_effect = Exception("API error")

        from app import process_receipts

        files = {"test.jpg": (b"fake image bytes", "image/jpeg")}
        results = process_receipts(files)

        assert len(results) == 1
        assert results[0]["isValidReceipt"] is False
        assert "Processing error" in results[0]["validationError"]


class TestUploadQueueing:
    @patch("app.st")
    def test_same_filename_different_content_gets_unique_name(self, mock_st):
        mock_st.session_state.uploaded_files = {}

        from app import queue_uploaded_file

        added_first = queue_uploaded_file("receipt.jpg", b"first", "image/jpeg")
        added_second = queue_uploaded_file("receipt.jpg", b"second", "image/jpeg")

        assert added_first is True
        assert added_second is True
        assert "receipt.jpg" in mock_st.session_state.uploaded_files
        assert "receipt (2).jpg" in mock_st.session_state.uploaded_files

    @patch("app.st")
    def test_exact_duplicate_content_is_ignored(self, mock_st):
        mock_st.session_state.uploaded_files = {}

        from app import queue_uploaded_file

        added_first = queue_uploaded_file("receipt.jpg", b"same", "image/jpeg")
        added_second = queue_uploaded_file("other-name.jpg", b"same", "image/jpeg")

        assert added_first is True
        assert added_second is False
        assert len(mock_st.session_state.uploaded_files) == 1


class TestCheckForDuplicates:
    @patch("sheets.get_gspread_client")
    @patch("sheets.check_receipts_for_duplicates")
    def test_returns_duplicates(self, mock_check, mock_client):
        mock_client.return_value = MagicMock()
        duplicate = {"date": "01/20/2026", "amount": 25.50, "vendor": "Test Store"}
        mock_check.return_value = [duplicate]

        from app import check_for_duplicates

        receipts = [duplicate]
        result = check_for_duplicates(receipts)

        assert len(result) == 1
        assert result[0]["vendor"] == "Test Store"

    @patch("sheets.get_gspread_client")
    def test_handles_sheets_error(self, mock_client):
        mock_client.side_effect = Exception("Auth error")

        from app import check_for_duplicates

        receipts = [{"date": "01/20/2026", "amount": 25.50, "vendor": "Test Store"}]
        result = check_for_duplicates(receipts)

        # Should return empty list on error
        assert result == []


class TestUploadToGoogleSheets:
    @patch("sheets.append_receipt")
    @patch("sheets.get_existing_receipts")
    @patch("sheets.get_or_create_worksheet")
    @patch("sheets.get_gspread_client")
    def test_uploads_new_receipts(
        self, mock_client, mock_worksheet, mock_existing, mock_append
    ):
        mock_client.return_value = MagicMock()
        mock_worksheet.return_value = MagicMock()
        mock_existing.return_value = set()
        mock_append.return_value = None

        from app import upload_to_google_sheets

        receipts = [
            {
                "date": "01/20/2026",
                "amount": 25.50,
                "vendor": "Test Store",
                "category": ["Food & Restaurants"],
                "excludeFromTable": False,
            }
        ]

        count, errors = upload_to_google_sheets(receipts)

        assert count == 1
        assert len(errors) == 0
        mock_append.assert_called_once()

    @patch("sheets.get_existing_receipts")
    @patch("sheets.get_or_create_worksheet")
    @patch("sheets.get_gspread_client")
    def test_skips_existing_receipts(self, mock_client, mock_worksheet, mock_existing):
        mock_client.return_value = MagicMock()
        mock_worksheet.return_value = MagicMock()
        # Receipt already exists in sheets
        mock_existing.return_value = {("01/20/2026", "25.5", "Test Store")}

        from app import upload_to_google_sheets

        receipts = [
            {
                "date": "01/20/2026",
                "amount": 25.5,
                "vendor": "Test Store",
                "category": [],
                "excludeFromTable": False,
            }
        ]

        count, errors = upload_to_google_sheets(receipts)

        assert count == 0  # Already exists, not uploaded

    @patch("sheets.get_gspread_client")
    def test_handles_auth_error(self, mock_client):
        mock_client.side_effect = Exception("Auth failed")

        from app import upload_to_google_sheets

        receipts = [
            {
                "date": "01/20/2026",
                "amount": 25.50,
                "vendor": "Test Store",
                "excludeFromTable": False,
            }
        ]

        count, errors = upload_to_google_sheets(receipts)

        assert count == 0
        assert len(errors) == 1
        assert "authenticate" in errors[0].lower()


class TestReceiptProcessingTimeout:
    """Tests for the 60-second LLM call timeout in process_and_display_results."""

    @patch("app.RECEIPT_PROCESSING_TIMEOUT", 0.1)
    @patch("app.st")
    @patch("app.load_exclusion_criteria", return_value="No exclusion criteria.")
    @patch("app.extract_receipt_from_bytes")
    def test_timeout_produces_error_result(self, mock_extract, mock_exc, mock_st):
        """When the LLM call exceeds RECEIPT_PROCESSING_TIMEOUT, the result
        should contain a timeout validation error instead of hanging."""
        # Use an Event to block the thread minimally — just long enough
        # to exceed the 0.1 s timeout, then release immediately.
        import threading

        event = threading.Event()

        def slow_extract(*args, **kwargs):
            event.wait(timeout=2)
            return {}

        mock_extract.side_effect = slow_extract

        mock_st.session_state = MagicMock()
        mock_st.session_state.uploaded_files = {
            "slow.jpg": (b"fake", "image/jpeg"),
        }
        mock_st.session_state.api_provider = "OpenAI"
        mock_st.session_state.processing_results = []
        mock_st.session_state.processing_complete = False

        from app import process_and_display_results

        process_and_display_results(sheets_available=False)

        # Unblock the orphaned thread so it cleans up quickly.
        event.set()

        results = mock_st.session_state.processing_results
        assert len(results) == 1
        assert results[0]["isValidReceipt"] is False
        assert "Timed out" in results[0]["validationError"]

    @patch("app.st")
    @patch("app.load_exclusion_criteria", return_value="No exclusion criteria.")
    @patch("app.extract_receipt_from_bytes")
    def test_fast_call_succeeds_normally(self, mock_extract, mock_exc, mock_st):
        """A fast LLM response should not be affected by the timeout."""
        mock_extract.return_value = {
            "isValidReceipt": True,
            "validationError": "",
            "id": "r1",
            "amount": 10.0,
            "date": "01/01/2026",
            "vendor": "Quick Store",
            "category": ["Food & Restaurants"],
            "paymentMethod": ["Card"],
            "excludeFromTable": False,
            "exclusionReason": "",
        }

        mock_st.session_state = MagicMock()
        mock_st.session_state.uploaded_files = {
            "fast.jpg": (b"fake", "image/jpeg"),
        }
        mock_st.session_state.api_provider = "Anthropic"
        mock_st.session_state.processing_results = []
        mock_st.session_state.processing_complete = False
        mock_st.session_state.duplicates_found = []

        from app import process_and_display_results

        process_and_display_results(sheets_available=False)

        results = mock_st.session_state.processing_results
        assert len(results) == 1
        assert results[0]["isValidReceipt"] is True
        assert results[0]["vendor"] == "Quick Store"

    @patch("app.RECEIPT_PROCESSING_TIMEOUT", 0.1)
    @patch("app.st")
    @patch("app.load_exclusion_criteria", return_value="No exclusion criteria.")
    @patch("app.extract_receipt_from_bytes")
    def test_timeout_on_first_file_does_not_block_second(
        self, mock_extract, mock_exc, mock_st
    ):
        """When the first file times out, the second should still be processed
        without waiting for the stalled thread to finish."""
        import threading

        event = threading.Event()
        call_count = 0

        def mixed_extract(*args, **kwargs):
            nonlocal call_count
            call_count += 1
            if call_count == 1:
                # First call: block (will be timed out)
                event.wait(timeout=2)
                return {}
            # Second call: return immediately
            return {
                "isValidReceipt": True,
                "validationError": "",
                "id": "r2",
                "amount": 5.0,
                "date": "02/02/2026",
                "vendor": "Fast Store",
                "category": [],
                "paymentMethod": [],
                "excludeFromTable": False,
                "exclusionReason": "",
            }

        mock_extract.side_effect = mixed_extract

        mock_st.session_state = MagicMock()
        mock_st.session_state.uploaded_files = {
            "slow.jpg": (b"fake1", "image/jpeg"),
            "fast.jpg": (b"fake2", "image/jpeg"),
        }
        mock_st.session_state.api_provider = "OpenAI"
        mock_st.session_state.processing_results = []
        mock_st.session_state.processing_complete = False

        from app import process_and_display_results

        process_and_display_results(sheets_available=False)
        event.set()

        results = mock_st.session_state.processing_results
        assert len(results) == 2
        assert results[0]["isValidReceipt"] is False
        assert "Timed out" in results[0]["validationError"]
        assert results[1]["isValidReceipt"] is True
        assert results[1]["vendor"] == "Fast Store"


class TestStartupTimeout:
    """Tests for the startup watchdog helpers."""

    @patch("app.st")
    def test_inject_startup_timeout_renders_script(self, mock_st):
        """The startup watchdog should inject a <script> tag."""
        from app import APP_STARTUP_TIMEOUT, _inject_startup_timeout

        _inject_startup_timeout()

        mock_st.markdown.assert_called_once()
        call_args = mock_st.markdown.call_args
        html_content = call_args[0][0]
        assert "<script>" in html_content
        assert "rr-app-loaded" in html_content
        assert str(APP_STARTUP_TIMEOUT) in html_content
        assert call_args[1]["unsafe_allow_html"] is True

    @patch("app.st")
    def test_inject_startup_sentinel_renders_hidden_div(self, mock_st):
        """The sentinel should be a hidden div with the expected id."""
        from app import _inject_startup_sentinel

        _inject_startup_sentinel()

        mock_st.markdown.assert_called_once()
        call_args = mock_st.markdown.call_args
        html_content = call_args[0][0]
        assert 'id="rr-app-loaded"' in html_content
        assert "display:none" in html_content

    @patch("app.st")
    def test_watchdog_and_sentinel_use_same_element_id(self, mock_st):
        """The watchdog script and the sentinel must reference the same
        element ID, otherwise the watchdog can never be cancelled."""
        from app import _inject_startup_sentinel, _inject_startup_timeout

        _inject_startup_timeout()
        watchdog_html = mock_st.markdown.call_args[0][0]

        mock_st.reset_mock()

        _inject_startup_sentinel()
        sentinel_html = mock_st.markdown.call_args[0][0]

        sentinel_id = "rr-app-loaded"
        assert sentinel_id in watchdog_html
        assert sentinel_id in sentinel_html

    @patch("app.st")
    def test_watchdog_uses_session_storage_guard(self, mock_st):
        """The watchdog should check sessionStorage to avoid firing on
        Streamlit rerenders after a successful initial load."""
        from app import _inject_startup_timeout

        _inject_startup_timeout()

        html_content = mock_st.markdown.call_args[0][0]
        assert "sessionStorage" in html_content
        assert "rr_loaded" in html_content


class TestSheetsIntegration:
    """Tests for sheets.py duplicate checking functions."""

    @patch("sheets.gspread")
    def test_get_all_existing_receipts(self, mock_gspread):
        from sheets import get_all_existing_receipts

        # Mock spreadsheet with worksheets
        mock_client = MagicMock()
        mock_spreadsheet = MagicMock()
        mock_worksheet = MagicMock()

        mock_client.open.return_value = mock_spreadsheet
        mock_spreadsheet.worksheets.return_value = [mock_worksheet]
        mock_worksheet.get_all_records.return_value = [
            {"Date": "01/20/2026", "Amount": "25.50", "Vendor": "Test Store"}
        ]

        result = get_all_existing_receipts(mock_client)

        assert len(result) == 1
        assert ("01/20/2026", "25.50", "Test Store") in result

    def test_check_receipts_for_duplicates(self):
        from sheets import check_receipts_for_duplicates

        mock_client = MagicMock()

        # Patch get_all_existing_receipts within the test
        with patch("sheets.get_all_existing_receipts") as mock_existing:
            mock_existing.return_value = {("01/20/2026", "25.5", "Test Store")}

            receipts = [
                {"date": "01/20/2026", "amount": 25.5, "vendor": "Test Store"},
                {"date": "01/21/2026", "amount": 30.0, "vendor": "Other Store"},
            ]

            duplicates = check_receipts_for_duplicates(mock_client, receipts)

            assert len(duplicates) == 1
            assert duplicates[0]["vendor"] == "Test Store"
