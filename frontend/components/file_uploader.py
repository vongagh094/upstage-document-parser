# project_path/frontend/components/file_uploader.py

from typing import Tuple, Any

from backend.services.file_processor import FileProcessor
from frontend.utils.async_utils import run_async


class FileUploader:
    """
    Streamlit component for uploading files to the backend API.
    """

    def __init__(self, processor: FileProcessor):
        """
        Initialize the uploader.

        Args:
            processor: FileProcessor instance.
        """
        self.processor = processor

    def upload_file(self, uploaded_file, api_key: str) -> Tuple[bool, Any]:
        """
        Upload a file to the backend API.

        Args:
            uploaded_file: Streamlit UploadedFile instance.

        Returns:
            Tuple[bool, Any]: (success, response data or error message)
        """
        if not api_key:
            return False, "Vui lòng nhập API key trước khi phân tích."
        try:
            self.processor.set_api_key(api_key)

            is_valid, error_message = self.processor.validate_file(
                uploaded_file.name, uploaded_file.size
            )
            if not is_valid:
                return False, error_message

            record = run_async(
                self.processor.process_file(
                    file_content=uploaded_file.getvalue(),
                    filename=uploaded_file.name,
                    content_type=uploaded_file.type or "application/octet-stream",
                    background=False,
                )
            )
            return True, record

        except Exception as e:
            return False, f"Lỗi phân tích: {str(e)}"
