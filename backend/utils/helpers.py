# project_path/backend/utils/helpers.py

import base64
import re
from typing import Optional, Tuple


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


def parse_api_error(error_message: str) -> Tuple[Optional[int], str]:
    """
    Parse API error message and return status code and Vietnamese message.

    Args:
        error_message: Error message from exception.

    Returns:
        Tuple[Optional[int], str]: (status_code, vietnamese_message)
    """
    # Map of status codes to Vietnamese messages
    error_messages = {
        400: "Yêu cầu không hợp lệ. Vui lòng kiểm tra lại dữ liệu đầu vào.",
        401: "API Key hết hạn hoặc không hợp lệ. Vui lòng kiểm tra lại API Key.",
        403: "Không có quyền truy cập. Vui lòng kiểm tra quyền của API Key.",
        404: "Không tìm thấy tài nguyên. Vui lòng kiểm tra lại đường dẫn API.",
        429: "Quá nhiều yêu cầu. Vui lòng thử lại sau.",
        500: "Lỗi máy chủ. Vui lòng thử lại sau.",
        502: "Lỗi gateway. Vui lòng thử lại sau.",
        503: "Dịch vụ tạm thời không khả dụng. Vui lòng thử lại sau.",
        504: "Hết thời gian chờ từ gateway. Vui lòng thử lại sau.",
    }

    # Try to extract status code from error message
    # Common patterns: "401 Unauthorized", "Client error '401'", etc.
    status_code = None
    
    # Pattern 1: "401 Unauthorized" or "Status 401"
    status_match = re.search(r'(\d{3})\s+(?:Unauthorized|Forbidden|Not Found|Bad Request|Internal Server Error|Service Unavailable|Gateway Timeout|Too Many Requests)', error_message, re.IGNORECASE)
    if status_match:
        status_code = int(status_match.group(1))
    
    # Pattern 2: "Client error '401'" or "Server error '500'"
    if not status_code:
        status_match = re.search(r"(?:Client|Server)\s+error\s+'(\d{3})'", error_message, re.IGNORECASE)
        if status_match:
            status_code = int(status_match.group(1))
    
    # Pattern 3: Just look for 3-digit number (status codes)
    if not status_code:
        status_match = re.search(r'\b(\d{3})\b', error_message)
        if status_match:
            code = int(status_match.group(1))
            if 400 <= code <= 599:
                status_code = code

    # Get Vietnamese message
    if status_code and status_code in error_messages:
        vietnamese_msg = error_messages[status_code]
    elif status_code:
        vietnamese_msg = f"Lỗi API (Mã {status_code}). Vui lòng thử lại sau."
    else:
        # Default message if we can't parse the error
        vietnamese_msg = "Đã xảy ra lỗi khi phân tích tài liệu. Vui lòng thử lại sau."

    return status_code, vietnamese_msg
