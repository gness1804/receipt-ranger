"""Image format conversion helpers.

Receipt Ranger accepts a broad set of image formats but BAML/the LLM providers
do not all handle HEIC/HEIF reliably. iPhones produce HEIC by default, so we
convert any HEIC input to JPEG transparently before processing.
"""

import io
import os

HEIC_EXTENSIONS = {".heic", ".heif"}
HEIC_MIME_TYPES = {"image/heic", "image/heif"}


class HEICConversionError(Exception):
    """Raised when an HEIC image cannot be converted to JPEG."""


def is_heic_filename(filename: str) -> bool:
    """Return True if the filename has a HEIC/HEIF extension."""
    _, ext = os.path.splitext(filename)
    return ext.lower() in HEIC_EXTENSIONS


def is_heic_mime_type(mime_type: str) -> bool:
    """Return True if the MIME type is HEIC/HEIF."""
    return mime_type.lower() in HEIC_MIME_TYPES if mime_type else False


def convert_heic_to_jpeg(image_bytes: bytes, quality: int = 95) -> bytes:
    """Convert HEIC/HEIF image bytes to JPEG bytes.

    Args:
        image_bytes: Raw HEIC/HEIF image bytes.
        quality: JPEG quality (1-95). Defaults to 95 to preserve receipt
            legibility for OCR.

    Returns:
        JPEG-encoded image bytes.

    Raises:
        HEICConversionError: If Pillow/pillow-heif aren't available or if the
            image can't be decoded.
    """
    try:
        from PIL import Image
        import pillow_heif
    except ImportError as e:
        raise HEICConversionError(
            "HEIC support requires Pillow and pillow-heif. "
            f"Install with: pip install Pillow pillow-heif. ({e})"
        ) from e

    pillow_heif.register_heif_opener()

    try:
        with Image.open(io.BytesIO(image_bytes)) as img:
            # JPEG does not support alpha; flatten to RGB to avoid encoder errors.
            if img.mode != "RGB":
                img = img.convert("RGB")
            buf = io.BytesIO()
            img.save(buf, format="JPEG", quality=quality)
            return buf.getvalue()
    except Exception as e:
        raise HEICConversionError(f"Failed to convert HEIC image to JPEG: {e}") from e


def maybe_convert_heic(
    image_bytes: bytes, filename: str = "", mime_type: str = ""
) -> tuple[bytes, str]:
    """Convert image bytes to JPEG if they appear to be HEIC, else return as-is.

    Detection uses the filename extension and/or the provided MIME type. Returns
    a tuple of the (possibly converted) bytes and the resulting MIME type.
    """
    if is_heic_filename(filename) or is_heic_mime_type(mime_type):
        return convert_heic_to_jpeg(image_bytes), "image/jpeg"
    return image_bytes, mime_type
