"""Tests for Receipt Ranger main module."""

import json
import os
from unittest.mock import MagicMock, patch

import main


def _set_output_paths(monkeypatch, output_dir):
    """Helper to monkeypatch output directory and file paths."""
    monkeypatch.setattr(main, "OUTPUT_DIR", output_dir)
    json_path = os.path.join(output_dir, "receipts.json")
    tsv_path = os.path.join(output_dir, "receipts.tsv")
    monkeypatch.setattr(main, "OUTPUT_JSON", json_path)
    monkeypatch.setattr(main, "OUTPUT_TSV", tsv_path)


class TestIsValidImage:
    def test_valid_extensions(self):
        for ext in [".jpg", ".jpeg", ".png", ".gif", ".bmp", ".webp", ".tiff"]:
            assert main.is_valid_image(f"receipt{ext}") is True

    def test_case_insensitive(self):
        assert main.is_valid_image("receipt.JPG") is True
        assert main.is_valid_image("receipt.Png") is True

    def test_invalid_extensions(self):
        assert main.is_valid_image("receipt.pdf") is False
        assert main.is_valid_image("receipt.txt") is False
        assert main.is_valid_image("receipt.doc") is False
        assert main.is_valid_image("no_extension") is False


class TestFileHash:
    def test_consistent_hash(self, tmp_path):
        f = tmp_path / "test.txt"
        f.write_bytes(b"hello world")
        h1 = main.file_hash(str(f))
        h2 = main.file_hash(str(f))
        assert h1 == h2

    def test_different_content_different_hash(self, tmp_path):
        f1 = tmp_path / "a.txt"
        f2 = tmp_path / "b.txt"
        f1.write_bytes(b"hello")
        f2.write_bytes(b"world")
        assert main.file_hash(str(f1)) != main.file_hash(str(f2))


class TestLoadSaveState:
    def test_load_missing_file(self, tmp_path, monkeypatch):
        monkeypatch.setattr(main, "STATE_FILE", str(tmp_path / "missing.json"))
        assert main.load_state() == {"files": {}, "receipts": {}}

    def test_roundtrip(self, tmp_path, monkeypatch):
        state_file = str(tmp_path / "state.json")
        monkeypatch.setattr(main, "STATE_FILE", state_file)
        state = {"receipt.jpg": "abc123"}
        main.save_state(state)
        loaded = main.load_state()
        assert loaded == {"files": {"receipt.jpg": "abc123"}, "receipts": {}}


class TestGetReceiptsToProcess:
    def test_skips_already_processed(self, tmp_path, monkeypatch):
        receipts_dir = tmp_path / "receipts"
        receipts_dir.mkdir()
        img = receipts_dir / "test.jpg"
        img.write_bytes(b"fake image data")

        state_file = tmp_path / "state.json"
        file_h = main.file_hash(str(img))
        state_file.write_text(json.dumps({"files": {"test.jpg": file_h}}))

        monkeypatch.setattr(main, "RECEIPTS_DIR", str(receipts_dir))
        monkeypatch.setattr(main, "STATE_FILE", str(state_file))

        result = main.get_receipts_to_process(allow_duplicates=False, files=None)
        assert result == []

    def test_processes_new_files(self, tmp_path, monkeypatch):
        receipts_dir = tmp_path / "receipts"
        receipts_dir.mkdir()
        img = receipts_dir / "new.png"
        img.write_bytes(b"new image data")

        monkeypatch.setattr(main, "RECEIPTS_DIR", str(receipts_dir))
        monkeypatch.setattr(main, "STATE_FILE", str(tmp_path / "empty.json"))

        result = main.get_receipts_to_process(allow_duplicates=False, files=None)
        assert len(result) == 1
        assert result[0][0] == "new.png"

    def test_duplicates_flag_reprocesses(self, tmp_path, monkeypatch):
        receipts_dir = tmp_path / "receipts"
        receipts_dir.mkdir()
        img = receipts_dir / "test.jpg"
        img.write_bytes(b"fake image data")

        state_file = tmp_path / "state.json"
        file_h = main.file_hash(str(img))
        state_file.write_text(json.dumps({"files": {"test.jpg": file_h}}))

        monkeypatch.setattr(main, "RECEIPTS_DIR", str(receipts_dir))
        monkeypatch.setattr(main, "STATE_FILE", str(state_file))

        result = main.get_receipts_to_process(allow_duplicates=True, files=None)
        assert len(result) == 1

    def test_skips_non_image_files(self, tmp_path, monkeypatch):
        receipts_dir = tmp_path / "receipts"
        receipts_dir.mkdir()
        (receipts_dir / "notes.txt").write_bytes(b"not an image")
        (receipts_dir / "data.pdf").write_bytes(b"not an image")
        (receipts_dir / "valid.jpg").write_bytes(b"image data")

        monkeypatch.setattr(main, "RECEIPTS_DIR", str(receipts_dir))
        monkeypatch.setattr(main, "STATE_FILE", str(tmp_path / "empty.json"))

        result = main.get_receipts_to_process(allow_duplicates=False, files=None)
        assert len(result) == 1
        assert result[0][0] == "valid.jpg"

    def test_detects_changed_file(self, tmp_path, monkeypatch):
        receipts_dir = tmp_path / "receipts"
        receipts_dir.mkdir()
        img = receipts_dir / "test.jpg"
        img.write_bytes(b"original data")

        state_file = tmp_path / "state.json"
        state_file.write_text(json.dumps({"files": {"test.jpg": "old_hash_value"}}))

        monkeypatch.setattr(main, "RECEIPTS_DIR", str(receipts_dir))
        monkeypatch.setattr(main, "STATE_FILE", str(state_file))

        result = main.get_receipts_to_process(allow_duplicates=False, files=None)
        assert len(result) == 1

    def test_missing_directory(self, tmp_path, monkeypatch):
        monkeypatch.setattr(main, "RECEIPTS_DIR", str(tmp_path / "nonexistent"))
        result = main.get_receipts_to_process(allow_duplicates=False, files=None)
        assert result == []

    def test_processes_specific_files(self, tmp_path):
        img1 = tmp_path / "img1.jpg"
        img1.write_bytes(b"img1")
        img2 = tmp_path / "img2.png"
        img2.write_bytes(b"img2")
        # This one should be ignored by the logic
        receipts_dir_img = tmp_path / "receipts" / "img3.jpg"
        receipts_dir_img.parent.mkdir()
        receipts_dir_img.write_bytes(b"img3")

        file_paths = [str(img1), str(img2)]
        result = main.get_receipts_to_process(allow_duplicates=False, files=file_paths)

        assert len(result) == 2
        filenames = {r[0] for r in result}
        assert "img1.jpg" in filenames
        assert "img2.png" in filenames
        assert "img3.jpg" not in filenames

    def test_skips_non_existent_files(self, tmp_path, capsys):
        img1 = tmp_path / "img1.jpg"
        img1.write_bytes(b"img1")

        file_paths = [str(img1), "non_existent_file.jpg"]
        result = main.get_receipts_to_process(allow_duplicates=False, files=file_paths)

        assert len(result) == 1
        assert result[0][0] == "img1.jpg"
        captured = capsys.readouterr()
        assert "WARNING: File not found" in captured.out
        assert "non_existent_file.jpg" in captured.out

    def test_skips_invalid_image_files_from_list(self, tmp_path, capsys):
        img1 = tmp_path / "img1.jpg"
        img1.write_bytes(b"img1")
        not_img = tmp_path / "file.txt"
        not_img.write_bytes(b"not an image")

        file_paths = [str(img1), str(not_img)]
        result = main.get_receipts_to_process(allow_duplicates=False, files=file_paths)

        assert len(result) == 1
        assert result[0][0] == "img1.jpg"
        captured = capsys.readouterr()
        assert "WARNING: File is not a valid image" in captured.out
        assert "file.txt" in captured.out


class TestWriteTsv:
    def test_tsv_format(self, tmp_path, monkeypatch):
        output_dir = str(tmp_path / "output")
        _set_output_paths(monkeypatch, output_dir)

        results = [
            {
                "amount": 12.50,
                "date": "01/15/2026",
                "vendor": "Taco Cabana",
                "category": ["Food/restaurants"],
            }
        ]
        main.write_tsv(results)

        with open(os.path.join(output_dir, "receipts.tsv")) as f:
            content = f.read()

        lines = content.strip().split("\n")
        assert lines[0] == "Amount\tDate\t\tVendor\tCategory"
        assert lines[1] == "12.50\t01/15/2026\t\tTaco Cabana\tFood/restaurants"

    def test_tsv_multiple_categories(self, tmp_path, monkeypatch):
        output_dir = str(tmp_path / "output")
        _set_output_paths(monkeypatch, output_dir)

        results = [
            {
                "amount": 99.99,
                "date": "02/01/2026",
                "vendor": "Amazon",
                "category": ["Electronics", "Entertainment"],
            }
        ]
        main.write_tsv(results)

        with open(os.path.join(output_dir, "receipts.tsv")) as f:
            lines = f.read().strip().split("\n")

        assert "Electronics, Entertainment" in lines[1]

    def test_tsv_empty_category(self, tmp_path, monkeypatch):
        output_dir = str(tmp_path / "output")
        _set_output_paths(monkeypatch, output_dir)

        results = [
            {
                "amount": 5.00,
                "date": "03/01/2026",
                "vendor": "Unknown",
                "category": [],
            }
        ]
        main.write_tsv(results)

        with open(os.path.join(output_dir, "receipts.tsv")) as f:
            lines = f.read().strip().split("\n")

        # With empty category, line ends with vendor (trailing tab stripped by strip())
        assert "5.00" in lines[1]
        assert "\tUnknown" in lines[1]


class TestWriteJson:
    def test_json_output(self, tmp_path, monkeypatch):
        output_dir = str(tmp_path / "output")
        _set_output_paths(monkeypatch, output_dir)

        results = [{"amount": 10.0, "vendor": "Test"}]
        main.write_json(results)

        with open(os.path.join(output_dir, "receipts.json")) as f:
            loaded = json.load(f)

        assert loaded == results


class TestExtractReceipt:
    @patch("main.b")
    def test_extract_calls_baml(self, mock_b, tmp_path):
        img = tmp_path / "receipt.jpg"
        img.write_bytes(b"fake image bytes")

        mock_receipt = MagicMock()
        mock_receipt.id = "r1"
        mock_receipt.amount = 25.50
        mock_receipt.date = "01/20/2026"
        mock_receipt.vendor = "Test Store"
        mock_receipt.category = ["Food/restaurants"]
        mock_receipt.paymentMethod = ["Card"]
        mock_receipt.excludeFromTable = False
        mock_receipt.exclusionReason = ""
        mock_b.ExtractReceiptFromImage.return_value = mock_receipt

        result = main.extract_receipt(str(img), "No exclusion criteria.")

        assert result["amount"] == 25.50
        assert result["vendor"] == "Test Store"
        assert result["category"] == ["Food & Restaurants"]
        assert result["excludeFromTable"] is False
        assert result["exclusionReason"] == ""
        mock_b.ExtractReceiptFromImage.assert_called_once()

    @patch("main.b")
    def test_extract_captures_exclusion_fields(self, mock_b, tmp_path):
        img = tmp_path / "receipt.jpg"
        img.write_bytes(b"fake image bytes")

        mock_receipt = MagicMock()
        mock_receipt.id = "r2"
        mock_receipt.amount = 100.00
        mock_receipt.date = "01/25/2026"
        mock_receipt.vendor = "Excluded Vendor"
        mock_receipt.category = []
        mock_receipt.paymentMethod = ["Card"]
        mock_receipt.excludeFromTable = True
        mock_receipt.exclusionReason = "Vendor is on exclusion list"
        mock_b.ExtractReceiptFromImage.return_value = mock_receipt

        result = main.extract_receipt(str(img), "Exclude Excluded Vendor")

        assert result["excludeFromTable"] is True
        assert result["exclusionReason"] == "Vendor is on exclusion list"


class TestDedupeReceipts:
    def test_dedupes_by_source_hash(self):
        receipts = [
            {"source_hash": "abc", "amount": 1.0},
            {"source_hash": "abc", "amount": 2.0},
            {"source_hash": "def", "amount": 3.0},
        ]
        deduped = main.dedupe_receipts(receipts)
        assert len(deduped) == 2
        assert any(r["amount"] == 2.0 for r in deduped)


class TestFilterReceipts:
    def test_filters_by_month_vendor_amount_category(self):
        receipts = [
            {
                "amount": 12.50,
                "date": "01/15/2026",
                "vendor": "Taco Cabana",
                "category": ["Food & Restaurants"],
            },
            {
                "amount": 55.00,
                "date": "02/20/2026",
                "vendor": "Target",
                "category": ["Clothing & Shoes"],
            },
        ]
        filtered = main._filter_receipts(
            receipts,
            month="2026-01",
            vendor="taco",
            min_amount=10.0,
            max_amount=20.0,
            category="Food & Restaurants",
        )
        assert len(filtered) == 1
        assert filtered[0]["vendor"] == "Taco Cabana"


class TestNormalizeCategories:
    def test_maps_legacy_categories(self):
        assert main.normalize_categories(["Food/restaurants"]) == ["Food & Restaurants"]

    def test_maps_unknown_to_other(self):
        assert main.normalize_categories(["Random"]) == ["Other"]


class TestParseCategory:
    def test_parse_category_accepts_alias(self):
        assert main._parse_category("food and restaurants") == "Food & Restaurants"


class TestLoadExclusionCriteria:
    def test_returns_default_when_file_missing(self, tmp_path, monkeypatch):
        monkeypatch.setattr(
            main, "EXCLUSION_CRITERIA_FILE", str(tmp_path / "nonexistent.txt")
        )
        result = main.load_exclusion_criteria()
        assert result == "No exclusion criteria configured."

    def test_returns_default_when_file_empty(self, tmp_path, monkeypatch):
        criteria_file = tmp_path / "exclusion_criteria.txt"
        criteria_file.write_text("")
        monkeypatch.setattr(main, "EXCLUSION_CRITERIA_FILE", str(criteria_file))
        result = main.load_exclusion_criteria()
        assert result == "No exclusion criteria configured."

    def test_returns_default_when_file_only_whitespace(self, tmp_path, monkeypatch):
        criteria_file = tmp_path / "exclusion_criteria.txt"
        criteria_file.write_text("   \n\n  ")
        monkeypatch.setattr(main, "EXCLUSION_CRITERIA_FILE", str(criteria_file))
        result = main.load_exclusion_criteria()
        assert result == "No exclusion criteria configured."

    def test_returns_content_when_file_exists(self, tmp_path, monkeypatch):
        criteria_file = tmp_path / "exclusion_criteria.txt"
        criteria_file.write_text("Exclude receipts from Test Vendor")
        monkeypatch.setattr(main, "EXCLUSION_CRITERIA_FILE", str(criteria_file))
        result = main.load_exclusion_criteria()
        assert result == "Exclude receipts from Test Vendor"


class TestFilterExcludedReceipts:
    def test_separates_excluded_receipts(self):
        receipts = [
            {"vendor": "Store A", "amount": 10.0, "excludeFromTable": False},
            {
                "vendor": "Store B",
                "amount": 20.0,
                "excludeFromTable": True,
                "exclusionReason": "Test reason",
            },
            {"vendor": "Store C", "amount": 30.0, "excludeFromTable": False},
        ]
        included, excluded = main._filter_excluded_receipts(
            receipts, print_warnings=False
        )
        assert len(included) == 2
        assert len(excluded) == 1
        assert excluded[0]["vendor"] == "Store B"

    def test_handles_missing_excludeFromTable_field(self):
        receipts = [
            {"vendor": "Store A", "amount": 10.0},
            {
                "vendor": "Store B",
                "amount": 20.0,
                "excludeFromTable": True,
                "exclusionReason": "Excluded",
            },
        ]
        included, excluded = main._filter_excluded_receipts(
            receipts, print_warnings=False
        )
        assert len(included) == 1
        assert len(excluded) == 1
        assert included[0]["vendor"] == "Store A"

    def test_prints_warnings_when_enabled(self, capsys):
        receipts = [
            {
                "vendor": "Excluded Store",
                "amount": 50.0,
                "excludeFromTable": True,
                "exclusionReason": "Card number match",
            },
        ]
        main._filter_excluded_receipts(receipts, print_warnings=True)
        captured = capsys.readouterr()
        assert "WARNING: Receipt excluded from table" in captured.out
        assert "Excluded Store" in captured.out
        assert "Card number match" in captured.out

    def test_no_warnings_when_disabled(self, capsys):
        receipts = [
            {
                "vendor": "Excluded Store",
                "amount": 50.0,
                "excludeFromTable": True,
                "exclusionReason": "Card number match",
            },
        ]
        main._filter_excluded_receipts(receipts, print_warnings=False)
        captured = capsys.readouterr()
        assert "WARNING" not in captured.out

    def test_all_receipts_included_when_none_excluded(self):
        receipts = [
            {"vendor": "Store A", "amount": 10.0, "excludeFromTable": False},
            {"vendor": "Store B", "amount": 20.0, "excludeFromTable": False},
        ]
        included, excluded = main._filter_excluded_receipts(
            receipts, print_warnings=False
        )
        assert len(included) == 2
        assert len(excluded) == 0

    def test_all_receipts_excluded(self):
        receipts = [
            {
                "vendor": "Store A",
                "amount": 10.0,
                "excludeFromTable": True,
                "exclusionReason": "Reason 1",
            },
            {
                "vendor": "Store B",
                "amount": 20.0,
                "excludeFromTable": True,
                "exclusionReason": "Reason 2",
            },
        ]
        included, excluded = main._filter_excluded_receipts(
            receipts, print_warnings=False
        )
        assert len(included) == 0
        assert len(excluded) == 2
