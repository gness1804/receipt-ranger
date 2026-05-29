"""Tests for sheets.py helper functions."""

from unittest.mock import MagicMock

from sheets import _format_date_for_sheets, get_existing_receipts


class TestFormatDateForSheets:
    def test_removes_leading_zero_from_month(self):
        assert _format_date_for_sheets("02/12/2026") == "2/12/2026"

    def test_removes_leading_zero_from_day(self):
        assert _format_date_for_sheets("12/05/2026") == "12/5/2026"

    def test_removes_leading_zeros_from_both(self):
        assert _format_date_for_sheets("02/05/2026") == "2/5/2026"

    def test_no_change_when_no_leading_zeros(self):
        assert _format_date_for_sheets("2/6/2026") == "2/6/2026"

    def test_iso_date_format(self):
        assert _format_date_for_sheets("2026-02-12") == "2/12/2026"

    def test_two_digit_year(self):
        assert _format_date_for_sheets("02/05/26") == "2/5/2026"

    def test_empty_string_returns_empty(self):
        assert _format_date_for_sheets("") == ""

    def test_invalid_date_returns_original(self):
        assert _format_date_for_sheets("not-a-date") == "not-a-date"

    def test_double_digit_month_and_day(self):
        assert _format_date_for_sheets("12/31/2026") == "12/31/2026"


class TestGetExistingReceipts:
    """Existing-receipt tracking, including the "Unknown Date" tab (issue #49)."""

    def _worksheet_with(self, records):
        worksheet = MagicMock()
        worksheet.get_all_records.return_value = records
        return worksheet

    def test_tracks_dated_receipts(self):
        worksheet = self._worksheet_with(
            [{"Date": "1/20/2026", "Amount": "25.5", "Vendor": "Walmart"}]
        )
        existing = get_existing_receipts(worksheet)
        assert ("1/20/2026", "25.5", "Walmart") in existing

    def test_tracks_dateless_receipts(self):
        """Rows with a blank date (Unknown Date tab) are still tracked."""
        worksheet = self._worksheet_with(
            [{"Date": "", "Amount": "25.5", "Vendor": "Walmart"}]
        )
        existing = get_existing_receipts(worksheet)
        assert ("", "25.5", "Walmart") in existing

    def test_dateless_distinct_from_dated(self):
        """A blank-date receipt does not collide with a dated one."""
        worksheet = self._worksheet_with(
            [
                {"Date": "", "Amount": "25.5", "Vendor": "Walmart"},
                {"Date": "1/20/2026", "Amount": "25.5", "Vendor": "Walmart"},
            ]
        )
        existing = get_existing_receipts(worksheet)
        assert ("", "25.5", "Walmart") in existing
        assert ("1/20/2026", "25.5", "Walmart") in existing
        assert len(existing) == 2

    def test_skips_rows_missing_amount_or_vendor(self):
        worksheet = self._worksheet_with(
            [
                {"Date": "", "Amount": "", "Vendor": "Walmart"},
                {"Date": "", "Amount": "25.5", "Vendor": ""},
            ]
        )
        assert get_existing_receipts(worksheet) == set()
