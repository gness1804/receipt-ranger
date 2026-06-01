"""Tests for sheets.py helper functions."""

from unittest.mock import MagicMock

from sheets import (
    _format_date_for_sheets,
    _normalize_vendor,
    get_existing_receipts,
)


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
        # Vendor is normalized (casefolded) in the dedupe key.
        assert ("1/20/2026", "25.5", "walmart") in existing

    def test_tracks_dateless_receipts(self):
        """Rows with a blank date (Unknown Date tab) are still tracked."""
        worksheet = self._worksheet_with(
            [{"Date": "", "Amount": "25.5", "Vendor": "Walmart"}]
        )
        existing = get_existing_receipts(worksheet)
        assert ("", "25.5", "walmart") in existing

    def test_dateless_distinct_from_dated(self):
        """A blank-date receipt does not collide with a dated one."""
        worksheet = self._worksheet_with(
            [
                {"Date": "", "Amount": "25.5", "Vendor": "Walmart"},
                {"Date": "1/20/2026", "Amount": "25.5", "Vendor": "Walmart"},
            ]
        )
        existing = get_existing_receipts(worksheet)
        assert ("", "25.5", "walmart") in existing
        assert ("1/20/2026", "25.5", "walmart") in existing
        assert len(existing) == 2

    def test_vendor_casing_collapses_to_one_key(self):
        """Same receipt with different vendor casing dedupes to one entry."""
        worksheet = self._worksheet_with(
            [
                {
                    "Date": "5/27/2026",
                    "Amount": "27.86",
                    "Vendor": "BaanThai Thai Cuisine",
                },
                {
                    "Date": "5/27/2026",
                    "Amount": "27.86",
                    "Vendor": "BAANTHAI THAI CUISINE",
                },
            ]
        )
        existing = get_existing_receipts(worksheet)
        assert existing == {("5/27/2026", "27.86", "baanthai thai cuisine")}

    def test_vendor_whitespace_collapses_to_one_key(self):
        """Extra/internal whitespace in the vendor does not defeat dedupe."""
        worksheet = self._worksheet_with(
            [
                {"Date": "5/27/2026", "Amount": "27.86", "Vendor": "Baan Thai"},
                {"Date": "5/27/2026", "Amount": "27.86", "Vendor": "  Baan   Thai "},
            ]
        )
        existing = get_existing_receipts(worksheet)
        assert existing == {("5/27/2026", "27.86", "baan thai")}

    def test_skips_rows_missing_amount_or_vendor(self):
        worksheet = self._worksheet_with(
            [
                {"Date": "", "Amount": "", "Vendor": "Walmart"},
                {"Date": "", "Amount": "25.5", "Vendor": ""},
            ]
        )
        assert get_existing_receipts(worksheet) == set()


class TestNormalizeVendor:
    def test_casefolds(self):
        assert _normalize_vendor("BAANTHAI THAI CUISINE") == "baanthai thai cuisine"

    def test_collapses_internal_whitespace(self):
        assert _normalize_vendor("Baan   Thai") == "baan thai"

    def test_strips_surrounding_whitespace(self):
        assert _normalize_vendor("  Walmart  ") == "walmart"

    def test_casing_and_whitespace_variants_match(self):
        assert _normalize_vendor("BaanThai Thai Cuisine") == _normalize_vendor(
            "  BAANTHAI   THAI CUISINE "
        )

    def test_none_returns_empty_string(self):
        assert _normalize_vendor(None) == ""

    def test_non_string_is_coerced(self):
        assert _normalize_vendor(123) == "123"


class TestCheckReceiptsForDuplicates:
    """End-to-end dedupe: incoming receipts vs. existing sheet rows."""

    def _client_with_rows(self, rows):
        worksheet = MagicMock()
        worksheet.get_all_records.return_value = rows
        spreadsheet = MagicMock()
        spreadsheet.worksheets.return_value = [worksheet]
        client = MagicMock()
        client.open.return_value = spreadsheet
        return client

    def test_flags_vendor_casing_duplicate(self):
        """The reported bug: same receipt, vendor casing differs -> duplicate."""
        from sheets import check_receipts_for_duplicates

        client = self._client_with_rows(
            [
                {
                    "Date": "5/27/2026",
                    "Amount": "27.86",
                    "Vendor": "BaanThai Thai Cuisine",
                }
            ]
        )
        incoming = [
            {
                "date": "5/27/2026",
                "amount": "27.86",
                "vendor": "BAANTHAI THAI CUISINE",
            }
        ]
        dupes = check_receipts_for_duplicates(client, incoming)
        assert dupes == incoming

    def test_distinct_vendor_not_flagged(self):
        from sheets import check_receipts_for_duplicates

        client = self._client_with_rows(
            [{"Date": "5/27/2026", "Amount": "27.86", "Vendor": "BaanThai"}]
        )
        incoming = [
            {"date": "5/27/2026", "amount": "27.86", "vendor": "Sonic Drive-In"}
        ]
        assert check_receipts_for_duplicates(client, incoming) == []
