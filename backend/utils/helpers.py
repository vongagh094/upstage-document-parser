# project_path/backend/utils/helpers.py

import base64
from typing import Optional


def get_image_mime_type_from_base64(base64_string: str) -> Optional[str]:
    """
    Determine image MIME type from a base64-encoded string.

    Uses magic numbers (file signatures) to detect the actual image format.

    Args:
        base64_string: Base64-encoded image data.

    Returns:
        Optional[str]: MIME type (image/png, image/jpeg, etc.), or None if unknown.
    """
    try:
        decoded_data = base64.b64decode(base64_string[:20])

        if decoded_data.startswith(b"\x89PNG\r\n\x1a\n"):
            return "image/png"
        if decoded_data.startswith(b"\xff\xd8\xff"):
            return "image/jpeg"
        if decoded_data.startswith(b"GIF87a") or decoded_data.startswith(b"GIF89a"):
            return "image/gif"
        if decoded_data.startswith(b"BM"):
            return "image/bmp"
        if decoded_data.startswith(b"RIFF") and decoded_data[8:12] == b"WEBP":
            return "image/webp"
        # Default to jpeg as a common fallback
        return "image/jpeg"
    except (base64.binascii.Error, IndexError):
        # Decode failed (not valid base64)
        return None
