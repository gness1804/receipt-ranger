"""Tests for Receipt Ranger Streamlit app."""

import os
from unittest.mock import MagicMock, patch

import pytest


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
