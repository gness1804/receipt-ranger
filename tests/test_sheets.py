"""Tests for sheets.py helper functions."""

from sheets import _format_date_for_sheets


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
