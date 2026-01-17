# project_path/frontend/components/file_uploader.py

import requests
from typing import Tuple, Any


class FileUploader:
    """
    Streamlit component for uploading files to the backend API.
    """

    def __init__(self, api_base_url: str):
        """
        Initialize the uploader.

        Args:
            api_base_url: Backend API base URL.
        """
        self.api_base_url = api_base_url

    def upload_file(self, uploaded_file) -> Tuple[bool, Any]:
        """
        Upload a file to the backend API.

        Args:
            uploaded_file: Streamlit UploadedFile instance.

        Returns:
            Tuple[bool, Any]: (success, response data or error message)
        """
        try:
            files = {"file": (uploaded_file.name, uploaded_file.getvalue(), uploaded_file.type)}

            response = requests.post(
                f"{self.api_base_url}/upload",
                files=files,
                timeout=300,  # 5 minute timeout for large files
            )

            if response.status_code == 200:
                return True, response.json()
            error_detail = "Lỗi không xác định"
            try:
                error_data = response.json()
                error_detail = error_data.get("detail", error_detail)
            except Exception:
                error_detail = response.text
            return False, f"Tải lên thất bại ({response.status_code}): {error_detail}"

        except requests.exceptions.Timeout:
            return False, "Tải lên bị hết thời gian. Vui lòng thử tệp nhỏ hơn."
        except requests.exceptions.ConnectionError:
            return False, "Không thể kết nối máy chủ API. Vui lòng kiểm tra máy chủ."
        except Exception as e:
            return False, f"Lỗi tải lên: {str(e)}"
