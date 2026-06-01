"""Tests for HEIC -> JPEG image conversion."""

import io

import pytest

from image_conversion import (
    HEICConversionError,
    convert_heic_to_jpeg,
    is_heic_filename,
    is_heic_mime_type,
    maybe_convert_heic,
)


class TestIsHeicFilename:
    def test_heic_extension(self):
        assert is_heic_filename("receipt.heic") is True
        assert is_heic_filename("receipt.HEIC") is True
        assert is_heic_filename("receipt.heif") is True
        assert is_heic_filename("receipt.HEIF") is True

    def test_non_heic_extension(self):
        assert is_heic_filename("receipt.jpg") is False
        assert is_heic_filename("receipt.png") is False
        assert is_heic_filename("receipt.tiff") is False
        assert is_heic_filename("receipt") is False

    def test_path_with_directories(self):
        assert is_heic_filename("/tmp/receipts/iphone.heic") is True
        assert is_heic_filename("./local/photo.jpg") is False


class TestIsHeicMimeType:
    def test_heic_mime_types(self):
        assert is_heic_mime_type("image/heic") is True
        assert is_heic_mime_type("image/heif") is True
        assert is_heic_mime_type("IMAGE/HEIC") is True

    def test_non_heic_mime_types(self):
        assert is_heic_mime_type("image/jpeg") is False
        assert is_heic_mime_type("image/png") is False
        assert is_heic_mime_type("") is False


def _make_heic_bytes() -> bytes:
    """Encode a small image as HEIC for round-trip testing."""
    pytest.importorskip("PIL")
    pillow_heif = pytest.importorskip("pillow_heif")
    from PIL import Image

    pillow_heif.register_heif_opener()

    img = Image.new("RGB", (10, 10), color=(255, 0, 0))
    buf = io.BytesIO()
    img.save(buf, format="HEIF")
    return buf.getvalue()


class TestConvertHeicToJpeg:
    def test_roundtrip_produces_jpeg(self):
        """Encoding HEIC then converting should yield valid JPEG bytes."""
        from PIL import Image

        heic_bytes = _make_heic_bytes()
        jpeg_bytes = convert_heic_to_jpeg(heic_bytes)

        # JPEG files begin with the SOI marker 0xFFD8.
        assert jpeg_bytes[:2] == b"\xff\xd8"

        # And Pillow should be able to read the result back as a JPEG.
        with Image.open(io.BytesIO(jpeg_bytes)) as img:
            assert img.format == "JPEG"
            assert img.size == (10, 10)

    def test_invalid_bytes_raises(self):
        with pytest.raises(HEICConversionError):
            convert_heic_to_jpeg(b"not a real image")


class TestMaybeConvertHeic:
    def test_passes_through_non_heic(self):
        original = b"\x89PNG\r\n\x1a\n" + b"\x00" * 100
        out_bytes, out_mime = maybe_convert_heic(
            original, "receipt.png", "image/png"
        )
        assert out_bytes is original
        assert out_mime == "image/png"

    def test_converts_heic_by_extension(self):
        heic_bytes = _make_heic_bytes()
        out_bytes, out_mime = maybe_convert_heic(
            heic_bytes, "receipt.heic", "image/heic"
        )
        assert out_mime == "image/jpeg"
        assert out_bytes[:2] == b"\xff\xd8"

    def test_converts_heic_by_mime_type_only(self):
        """A .jpg-looking filename with image/heic MIME should still convert."""
        heic_bytes = _make_heic_bytes()
        out_bytes, out_mime = maybe_convert_heic(
            heic_bytes, filename="weird-name.bin", mime_type="image/heic"
        )
        assert out_mime == "image/jpeg"
        assert out_bytes[:2] == b"\xff\xd8"
