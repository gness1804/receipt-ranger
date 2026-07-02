"""Tests for Receipt Ranger Streamlit app."""

import os
from unittest.mock import MagicMock, patch

# Import app at module load time so app.py's top-level load_dotenv() runs during
# collection (in a normal frame) rather than lazily inside a test function. When
# the first `from app import ...` happens inside a pytest test frame, dotenv's
# find_dotenv() frame-walk hits an AssertionError; importing here avoids that.
import app  # noqa: E402,F401

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

    def test_decrypt_rejects_token_older_than_ttl(self):
        """An expired token (older than ttl) must decrypt to None."""
        import time

        import session
        from session import decrypt_api_key

        old_time = int(time.time()) - 1000
        token = session._fernet.encrypt_at_time(b"sk-old-key", old_time).decode()

        # 1000s old, ttl 500s -> expired -> None
        assert decrypt_api_key(token, ttl=500) is None
        # Same token within a larger ttl still decrypts.
        assert decrypt_api_key(token, ttl=2000) == "sk-old-key"

    def test_decrypt_ttl_none_disables_expiry(self):
        """Passing ttl=None decrypts even a very old token."""
        import time

        import session
        from session import decrypt_api_key

        old_time = int(time.time()) - (400 * 24 * 60 * 60)  # ~400 days old
        token = session._fernet.encrypt_at_time(b"sk-ancient-key", old_time).decode()

        assert decrypt_api_key(token, ttl=None) == "sk-ancient-key"

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


class TestApiKeyDeferredCookieSave:
    """Regression tests for issue #72: API key cookie not persisting.

    The cookie-controller iframe needs the current script run to complete
    so it can write document.cookie. Calling cookie.set() and then
    st.rerun() in the same run aborts before the iframe flushes, so saves
    have to be deferred to the next render.
    """

    def test_init_session_state_seeds_deferred_save_keys(self):
        """init_session_state must set both deferred-save keys to None.

        Without these defaults, the main_app deferred-save branch raises
        AttributeError on first render.
        """

        class FakeSessionState(dict):
            def __getattr__(self, k):
                if k in self:
                    return self[k]
                raise AttributeError(k)

            def __setattr__(self, k, v):
                self[k] = v

        fake = FakeSessionState()
        with patch("app.st") as mock_st:
            mock_st.session_state = fake
            from app import init_session_state

            init_session_state()

        assert fake["api_key_save_pending_token"] is None
        assert fake["api_key_save_pending_provider"] is None
        assert fake["api_key_token"] == ""
        assert fake["api_key_clear_pending"] is False

    def test_init_session_state_seeds_pending_max_age(self):
        """init_session_state must seed the deferred-save TTL (feature #14).

        main_app reads api_key_save_pending_max_age in the deferred-save
        branch, so it must default to the standard 7-day lifetime.
        """

        class FakeSessionState(dict):
            def __getattr__(self, k):
                if k in self:
                    return self[k]
                raise AttributeError(k)

            def __setattr__(self, k, v):
                self[k] = v

        fake = FakeSessionState()
        with patch("app.st") as mock_st:
            mock_st.session_state = fake
            from app import DEFAULT_KEY_MAX_AGE, init_session_state

            init_session_state()

        assert fake["api_key_save_pending_max_age"] == DEFAULT_KEY_MAX_AGE


class TestKeyPersistenceChoices:
    """Tests for the 'remember this device' persistence options (feature #14)."""

    def test_persistence_durations(self):
        from app import (
            DEFAULT_KEY_MAX_AGE,
            REMEMBER_DEVICE_MAX_AGE,
            SESSION_ONLY_MAX_AGE,
        )

        assert SESSION_ONLY_MAX_AGE is None
        assert DEFAULT_KEY_MAX_AGE == 7 * 24 * 60 * 60
        assert REMEMBER_DEVICE_MAX_AGE == 90 * 24 * 60 * 60

    def test_default_selection_is_seven_days(self):
        """The pre-selected option must preserve the prior 7-day behavior."""
        from app import (
            DEFAULT_KEY_MAX_AGE,
            DEFAULT_KEY_PERSISTENCE_INDEX,
            KEY_PERSISTENCE_LABELS,
            KEY_PERSISTENCE_MAX_AGES,
        )

        default_label = KEY_PERSISTENCE_LABELS[DEFAULT_KEY_PERSISTENCE_INDEX]
        assert KEY_PERSISTENCE_MAX_AGES[default_label] == DEFAULT_KEY_MAX_AGE

    def test_every_label_maps_to_a_max_age(self):
        from app import KEY_PERSISTENCE_LABELS, KEY_PERSISTENCE_MAX_AGES

        assert set(KEY_PERSISTENCE_LABELS) == set(KEY_PERSISTENCE_MAX_AGES)


class TestSetSessionCookie:
    """Tests for set_session_cookie: optional max_age handling (feature #14)."""

    def test_session_only_writes_no_cookie(self):
        """A None max_age must NOT write a cookie.

        streamlit-cookies-controller cannot create a true session cookie (its
        frontend always stamps an expires date), so the session-only choice
        keeps the token in session_state only and writes nothing.
        """
        from app import set_session_cookie

        cookie = MagicMock()
        set_session_cookie(cookie, "rr_session", "tok", None)

        cookie.set.assert_not_called()

    def test_explicit_max_age_is_passed_through(self):
        from app import REMEMBER_DEVICE_MAX_AGE, set_session_cookie

        cookie = MagicMock()
        set_session_cookie(cookie, "rr_session", "tok", REMEMBER_DEVICE_MAX_AGE)

        cookie.set.assert_called_once_with(
            "rr_session", "tok", max_age=REMEMBER_DEVICE_MAX_AGE, secure=True
        )

    def test_always_secure(self):
        """Every persistence cookie must be HTTPS-only (secure=True)."""
        from app import DEFAULT_KEY_MAX_AGE, set_session_cookie

        cookie = MagicMock()
        set_session_cookie(cookie, "rr_provider", "OpenAI", DEFAULT_KEY_MAX_AGE)

        _, kwargs = cookie.set.call_args
        assert kwargs["secure"] is True


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
    @patch.dict(os.environ, {"GOOGLE_SHEETS_CREDENTIALS": ""})
    @patch("sheets.os.path.exists")
    def test_missing_service_account_file(self, mock_exists):
        # No env-var credentials and no file on disk → setup should report failure.
        # GOOGLE_SHEETS_CREDENTIALS is cleared so get_gspread_client() falls through
        # to the file-existence check that this test mocks away.
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


class FakeUpload:
    """Minimal stand-in for Streamlit's UploadedFile."""

    def __init__(self, name: str, data: bytes):
        self.name = name
        self._data = data

    def getvalue(self) -> bytes:
        return self._data


class TestUploadQueue:
    """Tests for the widget-derived upload queue (issue #19).

    The queue is a pure projection of the uploader widget's current value,
    so thumbnails always match the native file chips one-to-one.
    """

    @patch("app.st")
    def test_queue_matches_widget_files_one_to_one(self, mock_st):
        mock_st.session_state.heic_cache = {}

        from app import build_upload_queue

        queue = build_upload_queue(
            [FakeUpload("a.jpg", b"one"), FakeUpload("b.png", b"two")]
        )

        assert [e["name"] for e in queue] == ["a.jpg", "b.png"]
        assert all(e["error"] is None for e in queue)
        assert all(e["duplicate"] is False for e in queue)

    @patch("app.st")
    def test_empty_or_none_widget_value_yields_empty_queue(self, mock_st):
        mock_st.session_state.heic_cache = {}

        from app import build_upload_queue

        assert build_upload_queue(None) == []
        assert build_upload_queue([]) == []

    @patch("app.st")
    def test_removing_a_file_removes_its_queue_entry(self, mock_st):
        """Simulates clicking the X on a native chip: the widget re-emits the
        remaining files and the derived queue (thus thumbnails) must match."""
        mock_st.session_state.heic_cache = {}

        from app import build_upload_queue

        first = build_upload_queue(
            [FakeUpload("a.jpg", b"one"), FakeUpload("b.jpg", b"two")]
        )
        after_remove = build_upload_queue([FakeUpload("b.jpg", b"two")])

        assert len(first) == 2
        assert [e["name"] for e in after_remove] == ["b.jpg"]

    @patch("app.st")
    def test_exact_duplicate_content_is_marked_but_still_listed(self, mock_st):
        mock_st.session_state.heic_cache = {}

        from app import build_upload_queue, files_to_process

        queue = build_upload_queue(
            [FakeUpload("receipt.jpg", b"same"), FakeUpload("other.jpg", b"same")]
        )

        # Both entries stay in the queue (matching both chips)...
        assert len(queue) == 2
        assert queue[0]["duplicate"] is False
        assert queue[1]["duplicate"] is True
        # ...but the duplicate is only processed once.
        assert list(files_to_process(queue).keys()) == ["receipt.jpg"]

    @patch("app.st")
    def test_same_filename_different_content_gets_unique_processing_name(self, mock_st):
        mock_st.session_state.heic_cache = {}

        from app import build_upload_queue, files_to_process

        queue = build_upload_queue(
            [FakeUpload("receipt.jpg", b"first"), FakeUpload("receipt.jpg", b"second")]
        )
        files = files_to_process(queue)

        assert set(files.keys()) == {"receipt.jpg", "receipt (2).jpg"}

    @patch("app.st")
    def test_unsupported_extension_is_flagged_and_skipped(self, mock_st):
        mock_st.session_state.heic_cache = {}

        from app import build_upload_queue, files_to_process

        queue = build_upload_queue([FakeUpload("notes.txt", b"hello")])

        assert queue[0]["error"] == "Unsupported file type"
        assert files_to_process(queue) == {}

    @patch("app.maybe_convert_heic")
    @patch("app.st")
    def test_heic_is_converted_and_cached_across_reruns(self, mock_st, mock_convert):
        mock_st.session_state.heic_cache = {}
        mock_convert.return_value = (b"jpeg-bytes", "image/jpeg")

        from app import build_upload_queue

        upload = [FakeUpload("photo.heic", b"heic-bytes")]
        queue = build_upload_queue(upload)
        # Second build simulates a Streamlit rerun with the same widget value.
        queue_again = build_upload_queue(upload)

        assert queue[0]["bytes"] == b"jpeg-bytes"
        assert queue[0]["mime"] == "image/jpeg"
        assert queue[0]["name"] == "photo.heic"  # caption matches the chip
        assert queue_again[0]["bytes"] == b"jpeg-bytes"
        mock_convert.assert_called_once()

    @patch("app.st")
    def test_three_identical_files_process_once(self, mock_st):
        mock_st.session_state.heic_cache = {}

        from app import build_upload_queue, files_to_process

        queue = build_upload_queue(
            [
                FakeUpload("a.jpg", b"same"),
                FakeUpload("b.jpg", b"same"),
                FakeUpload("c.jpg", b"same"),
            ]
        )

        assert len(queue) == 3
        assert [e["duplicate"] for e in queue] == [False, True, True]
        assert len(files_to_process(queue)) == 1

    @patch("app.st")
    def test_files_beyond_upload_limit_are_flagged_and_skipped(self, mock_st):
        mock_st.session_state.heic_cache = {}

        from app import MAX_UPLOAD_FILES, build_upload_queue, files_to_process

        uploads = [
            FakeUpload(f"r{i}.jpg", f"content-{i}".encode())
            for i in range(MAX_UPLOAD_FILES + 2)
        ]
        queue = build_upload_queue(uploads)

        # Every chip still gets a queue entry (1:1 preview invariant)...
        assert len(queue) == MAX_UPLOAD_FILES + 2
        over_limit = queue[MAX_UPLOAD_FILES:]
        assert all("Upload limit" in e["error"] for e in over_limit)
        # ...but over-limit files are never read or processed.
        assert all(e["bytes"] == b"" for e in over_limit)
        assert len(files_to_process(queue)) == MAX_UPLOAD_FILES

    @patch("app.maybe_convert_heic")
    @patch("app.st")
    def test_heic_cache_prunes_entries_for_removed_files(self, mock_st, mock_convert):
        """Removing a HEIC file's chip must also evict its cached conversion."""
        mock_st.session_state.heic_cache = {}
        mock_convert.return_value = (b"jpeg-bytes", "image/jpeg")

        from app import build_upload_queue

        build_upload_queue([FakeUpload("photo.heic", b"heic-bytes")])
        assert len(mock_st.session_state.heic_cache) == 1

        # Rerun after the user removed the chip: widget value is empty.
        build_upload_queue([])
        assert mock_st.session_state.heic_cache == {}

    def test_clear_all_files_resets_uploader_and_caches(self):
        class FakeSessionState(dict):
            def __getattr__(self, k):
                if k in self:
                    return self[k]
                raise AttributeError(k)

            def __setattr__(self, k, v):
                self[k] = v

        fake = FakeSessionState()
        fake["uploader_key"] = 3
        fake["heic_cache"] = {"digest": ("ok", b"x", "image/jpeg")}
        fake["upload_signature"] = ("digest",)
        fake["processing_results"] = [{"vendor": "Old"}]
        fake["processing_complete"] = True
        fake["duplicates_found"] = [{"vendor": "Old"}]

        with patch("app.st") as mock_st:
            mock_st.session_state = fake
            from app import clear_all_files

            clear_all_files()

        assert fake["uploader_key"] == 4  # widget reset clears the chips
        assert fake["heic_cache"] == {}
        assert fake["upload_signature"] is None
        assert fake["processing_results"] == []
        assert fake["processing_complete"] is False
        assert fake["duplicates_found"] == []

    @patch("app.maybe_convert_heic")
    @patch("app.st")
    def test_heic_conversion_failure_is_flagged_and_skipped(
        self, mock_st, mock_convert
    ):
        from image_conversion import HEICConversionError

        mock_st.session_state.heic_cache = {}
        mock_convert.side_effect = HEICConversionError("bad file")

        from app import build_upload_queue, files_to_process

        queue = build_upload_queue([FakeUpload("photo.heic", b"heic-bytes")])

        assert queue[0]["error"] is not None
        assert "bad file" in queue[0]["error"]
        assert files_to_process(queue) == {}


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

        count, errors, notices = upload_to_google_sheets(receipts)

        assert count == 1
        assert len(errors) == 0
        assert len(notices) == 0
        mock_append.assert_called_once()

    @patch("sheets.get_existing_receipts")
    @patch("sheets.get_or_create_worksheet")
    @patch("sheets.get_gspread_client")
    def test_skips_existing_receipts(self, mock_client, mock_worksheet, mock_existing):
        mock_client.return_value = MagicMock()
        mock_worksheet.return_value = MagicMock()
        # Receipt already exists in sheets. get_existing_receipts() normalizes
        # dates via _format_date_for_sheets (no leading zeros), so the stored key
        # is "1/20/2026", matching the key upload_to_google_sheets() builds.
        mock_existing.return_value = {("1/20/2026", "25.5", "Test Store")}

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

        count, errors, notices = upload_to_google_sheets(receipts)

        assert count == 0  # Already exists, not uploaded
        # Dated duplicates are skipped silently (a true duplicate).
        assert len(notices) == 0

    @patch("sheets.append_receipt")
    @patch("sheets.get_existing_receipts")
    @patch("sheets.get_or_create_worksheet")
    @patch("sheets.get_gspread_client")
    def test_warns_on_skipped_undated_duplicate(
        self, mock_client, mock_worksheet, mock_existing, mock_append
    ):
        mock_client.return_value = MagicMock()
        mock_worksheet.return_value = MagicMock()
        # An undated receipt with this vendor/amount already exists in the
        # "Unknown Date" tab (empty date token in the key).
        mock_existing.return_value = {("", "25.5", "Test Store")}

        from app import upload_to_google_sheets

        receipts = [
            {
                "date": "",
                "amount": 25.5,
                "vendor": "Test Store",
                "category": [],
                "excludeFromTable": False,
            }
        ]

        count, errors, notices = upload_to_google_sheets(receipts)

        assert count == 0  # Treated as a duplicate, not uploaded
        assert len(notices) == 1
        assert "undated receipt" in notices[0].lower()
        assert "Test Store" in notices[0]
        mock_append.assert_not_called()

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

        count, errors, notices = upload_to_google_sheets(receipts)

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
        mock_st.session_state.api_provider = "OpenAI"
        mock_st.session_state.processing_results = []
        mock_st.session_state.processing_complete = False

        from app import process_and_display_results

        process_and_display_results(
            sheets_available=False, files={"slow.jpg": (b"fake", "image/jpeg")}
        )

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
        mock_st.session_state.api_provider = "Anthropic"
        mock_st.session_state.processing_results = []
        mock_st.session_state.processing_complete = False
        mock_st.session_state.duplicates_found = []

        from app import process_and_display_results

        process_and_display_results(
            sheets_available=False, files={"fast.jpg": (b"fake", "image/jpeg")}
        )

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
        mock_st.session_state.api_provider = "OpenAI"
        mock_st.session_state.processing_results = []
        mock_st.session_state.processing_complete = False

        from app import process_and_display_results

        process_and_display_results(
            sheets_available=False,
            files={
                "slow.jpg": (b"fake1", "image/jpeg"),
                "fast.jpg": (b"fake2", "image/jpeg"),
            },
        )
        event.set()

        results = mock_st.session_state.processing_results
        assert len(results) == 2
        assert results[0]["isValidReceipt"] is False
        assert "Timed out" in results[0]["validationError"]
        assert results[1]["isValidReceipt"] is True
        assert results[1]["vendor"] == "Fast Store"


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
        # get_existing_receipts() normalizes the date via _format_date_for_sheets,
        # dropping leading zeros ("01/20/2026" -> "1/20/2026"), and casefolds the
        # vendor for case-insensitive dedupe ("Test Store" -> "test store").
        assert ("1/20/2026", "25.50", "test store") in result

    def test_check_receipts_for_duplicates(self):
        from sheets import check_receipts_for_duplicates

        mock_client = MagicMock()

        # Patch get_all_existing_receipts within the test
        with patch("sheets.get_all_existing_receipts") as mock_existing:
            # get_all_existing_receipts returns normalized dates (no leading
            # zeros) and casefolded vendors, so the stored key is
            # ("1/20/2026", "25.5", "test store") — matching the key that
            # check_receipts_for_duplicates builds from the receipt below.
            mock_existing.return_value = {("1/20/2026", "25.5", "test store")}

            receipts = [
                {"date": "01/20/2026", "amount": 25.5, "vendor": "Test Store"},
                {"date": "01/21/2026", "amount": 30.0, "vendor": "Other Store"},
            ]

            duplicates = check_receipts_for_duplicates(mock_client, receipts)

            assert len(duplicates) == 1
            assert duplicates[0]["vendor"] == "Test Store"
