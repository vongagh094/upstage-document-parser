# project_path/frontend/app.py

import streamlit as st
import requests
import time
from pathlib import Path
import sys

# Add project root to Python path
current_dir = Path(__file__).parent
root_dir = current_dir.parent
sys.path.append(str(root_dir))

from frontend.components.file_uploader import FileUploader
from frontend.components.document_viewer import DocumentViewer
from frontend.utils.config import config

# Streamlit page configuration
st.set_page_config(
    page_title="Playground Phân tích tài liệu Upstage",
    layout="wide",
    initial_sidebar_state="expanded",
)

# API endpoint
API_BASE_URL = f"http://localhost:{config.PORT}/api/v1"


class StreamlitApp:
    """
    Main Streamlit application for the Upstage Document Parser Playground.

    Handles file uploads, document list, and document viewer pages.
    """

    STATUS_LABELS = {
        "pending": "Đang chờ",
        "processing": "Đang xử lý",
        "completed": "Hoàn tất",
        "failed": "Thất bại",
    }
    STATUS_FILTER_OPTIONS = {
        "Tất cả": None,
        "Hoàn tất": "completed",
        "Đang xử lý": "processing",
        "Thất bại": "failed",
    }

    def __init__(self):
        """
        Initialize the Streamlit app and session state.
        """
        self.file_uploader = FileUploader(API_BASE_URL)
        self.document_viewer = DocumentViewer(API_BASE_URL)

        # Session state initialization
        if "selected_doc_id" not in st.session_state:
            st.session_state.selected_doc_id = None

    def run(self):
        """
        Run the Streamlit app UI and route between pages.
        """
        # Header
        st.title("Playground Phân tích tài liệu Upstage")
        st.info("Liên hệ: https://www.linkedin.com/in/lsjsj92/")

        # Sidebar menu
        with st.sidebar:
            st.header("Danh mục")
            page = st.radio(
                "Chọn trang",
                [
                    "Tải tệp lên",
                    "Danh sách tài liệu đã phân tích",
                    "Trình xem tài liệu",
                ],
            )

            # API status check
            self._render_api_status_sidebar()

        # Page routing
        if page == "Tải tệp lên":
            self._render_upload_page()
        elif page == "Danh sách tài liệu đã phân tích":
            self._render_document_list()
        elif page == "Trình xem tài liệu":
            self._render_document_viewer()

    def _render_api_status_sidebar(self):
        """
        Render API status and system summary in the sidebar.
        """
        st.markdown("---")
        st.markdown("#### Trạng thái API")

        try:
            response = requests.get(
                f"{API_BASE_URL.replace('/api/v1', '')}/health", timeout=5
            )
            if response.status_code == 200:
                health_data = response.json()
                st.success("API đã kết nối")

                if "features" in health_data:
                    features = health_data["features"]
                    if "hybrid_parsing" in features:
                        st.success("Hybrid Parsing khả dụng")
                    if "ocr_text_extraction" in features:
                        st.success("Trích xuất văn bản OCR")
            else:
                st.error("Lỗi API")
        except Exception:
            st.error("Không thể kết nối API")

        try:
            response = requests.get(f"{API_BASE_URL}/analytics/summary", timeout=5)
            if response.status_code == 200:
                analytics = response.json()
                summary = analytics.get("summary", {})

                st.metric("Tổng tài liệu", summary.get("total_documents", 0))
                st.metric("Đã hoàn tất", summary.get("completed_documents", 0))
        except Exception:
            pass

    def _render_upload_page(self):
        """
        Render the file upload and parsing page.
        """
        st.header("Tải tệp và phân tích")

        st.info(
            "Tệp hỗ trợ: PDF, DOCX, PPTX, JPG, JPEG, PNG (Tối đa 50MB)"
        )
        st.markdown("**Tự động**: Trích xuất văn bản trong ảnh")

        uploaded_file = st.file_uploader(
            "Chọn tệp để tải lên.",
            type=["pdf", "docx", "pptx", "jpg", "jpeg", "png"],
            accept_multiple_files=False,
        )

        if uploaded_file:
            # File information
            col1, col2, col3 = st.columns(3)
            with col1:
                st.write(f"**Tên tệp:** {uploaded_file.name}")
            with col2:
                st.write(f"**Kích thước:** {uploaded_file.size:,} bytes")
            with col3:
                st.write(f"**Loại tệp:** {uploaded_file.type}")

            if st.button("Bắt đầu phân tích", type="primary"):
                with st.spinner("Đang tải tệp và bắt đầu phân tích."):
                    success, result = self.file_uploader.upload_file(uploaded_file)

                    if success:
                        st.success("Tải tệp thành công!")

                        # Monitor parsing progress
                        self._monitor_parsing_progress(result["id"])
                    else:
                        st.error(f"Tải lên thất bại: {result}")

    def _monitor_parsing_progress(self, doc_id: str):
        """
        Monitor parsing progress for a document.

        Args:
            doc_id: Document ID to monitor.
        """
        progress_container = st.container()

        with progress_container:
            progress_bar = st.progress(0)
            status_text = st.empty()
            stats_container = st.empty()

        for i in range(120):  # 4 minute timeout
            try:
                response = requests.get(f"{API_BASE_URL}/documents/{doc_id}")
                if response.status_code == 200:
                    doc_data = response.json()
                    status = doc_data["parsing_status"]

                    if status == "completed":
                        progress_bar.progress(100)
                        status_text.success("Phân tích hoàn tất!")

                        # Display parsing results
                        if doc_data.get("parsed_data"):
                            elements = doc_data["parsed_data"].get("elements", [])
                            pages = max([elem["page"] for elem in elements], default=0)
                            image_elements = [
                                e for e in elements if e.get("base64_encoding")
                            ]
                            text_elements = [
                                e
                                for e in elements
                                if e.get("content", {}).get("text")
                            ]

                            with stats_container:
                                col1, col2, col3, col4 = st.columns(4)
                                with col1:
                                    st.metric("Tổng phần tử", len(elements))
                                with col2:
                                    st.metric("Trang", pages)
                                with col3:
                                    st.metric("Phần tử hình ảnh", len(image_elements))
                                with col4:
                                    st.metric("Phần tử văn bản", len(text_elements))

                        if st.button("Xem tài liệu"):
                            st.session_state.selected_doc_id = doc_id
                            st.success(
                                "Tài liệu đã được chọn. Hãy chuyển sang tab Trình xem tài liệu."
                            )
                        break

                    if status == "failed":
                        progress_bar.progress(0)
                        status_text.error(
                            f"Phân tích thất bại: {doc_data.get('error_message', 'Lỗi không xác định')}"
                        )
                        break
                    if status == "processing":
                        progress_bar.progress(min(50 + i, 90))
                        status_text.info("Đang phân tích")
                    else:
                        progress_bar.progress(min(i * 2, 30))
                        status_text.info("Đã thêm vào hàng đợi phân tích")

                time.sleep(2)

            except Exception as e:
                status_text.error(f"Lỗi kiểm tra trạng thái: {str(e)}")
                break

    def _render_document_list(self):
        """
        Render the parsed document list page.
        """
        st.header("Danh sách tài liệu đã phân tích")

        col1, col2 = st.columns([1, 1])
        with col1:
            status_label = st.selectbox(
                "Lọc theo trạng thái",
                list(self.STATUS_FILTER_OPTIONS.keys()),
            )
            status_filter = self.STATUS_FILTER_OPTIONS[status_label]
        with col2:
            sort_by = st.selectbox("Sắp xếp", ["Thời gian tải lên", "Tên tệp"])

        try:
            response = requests.get(f"{API_BASE_URL}/documents")
            if response.status_code == 200:
                documents = response.json()

                if status_filter:
                    documents = [
                        d for d in documents if d["parsing_status"] == status_filter
                    ]

                if not documents:
                    st.info("Không có tài liệu phù hợp.")
                    return

                if sort_by == "Tên tệp":
                    documents.sort(key=lambda x: x["original_filename"])

                # Display document cards
                for i, doc in enumerate(documents):
                    self._render_document_card(doc, i)

            else:
                st.error("Không thể tải danh sách tài liệu.")

        except Exception as e:
            st.error(f"Đã xảy ra lỗi: {str(e)}")

    def _render_document_card(self, doc: dict, index: int):
        """
        Render a single document card.

        Args:
            doc: Document record data.
            index: Document index for unique keys.
        """
        status_colors = {
            "completed": "success",
            "processing": "info",
            "failed": "error",
            "pending": "warning",
        }

        status_color = status_colors.get(doc["parsing_status"], "info")

        with st.expander(f"{doc['original_filename']}", expanded=False):
            col1, col2, col3 = st.columns([2, 1, 1])

            with col1:
                st.markdown(
                    f"**Trạng thái:** :{status_color}[{self._get_status_badge(doc['parsing_status'])}]"
                )
                st.write(f"**Thời gian tải lên:** {doc['upload_time'][:19]}")
                st.write(f"**Kích thước tệp:** {doc['file_size']:,} bytes")

                if doc["parsing_status"] == "completed" and doc.get("parsed_data"):
                    elements = doc["parsed_data"].get("elements", [])
                    pages = max([elem["page"] for elem in elements], default=0)
                    image_elements = [
                        e for e in elements if e.get("base64_encoding")
                    ]

                    # Statistics
                    stats_col1, stats_col2, stats_col3 = st.columns(3)
                    with stats_col1:
                        st.metric("Phần tử", len(elements))
                    with stats_col2:
                        st.metric("Trang", pages)
                    with stats_col3:
                        st.metric("Hình ảnh", len(image_elements))

            with col2:
                if doc["parsing_status"] == "completed":
                    if st.button(
                        "Xem tài liệu", key=f"view_{doc['id']}_{index}"
                    ):
                        st.session_state.selected_doc_id = doc["id"]
                        st.success(
                            "Tài liệu đã được chọn. Hãy chuyển sang tab Trình xem tài liệu."
                        )
                else:
                    st.button(
                        "Đang xử lý...",
                        key=f"waiting_{doc['id']}_{index}",
                        disabled=True,
                    )

            with col3:
                if st.button(
                    "Xóa",
                    key=f"delete_{doc['id']}_{index}",
                    type="secondary",
                ):
                    if self._delete_document(doc["id"]):
                        st.success("Đã xóa tài liệu.")
                        time.sleep(1)
                        st.rerun()
                    else:
                        st.error("Xóa tài liệu thất bại.")

    def _render_document_viewer(self):
        """
        Render the document viewer page.
        """
        st.header("Trình xem tài liệu")
        st.markdown("Hiển thị bố cục gốc + kết quả trích xuất văn bản từ ảnh")

        # Document selection
        try:
            response = requests.get(f"{API_BASE_URL}/documents")
            if response.status_code == 200:
                documents = response.json()
                completed_docs = [
                    doc for doc in documents if doc["parsing_status"] == "completed"
                ]

                if not completed_docs:
                    st.warning("Chưa có tài liệu hoàn tất.")
                    return

                doc_options = {
                    doc["original_filename"]: doc["id"] for doc in completed_docs
                }

                # Check for pre-selected document
                selected_filename = None
                if st.session_state.selected_doc_id:
                    for filename, doc_id in doc_options.items():
                        if doc_id == st.session_state.selected_doc_id:
                            selected_filename = filename
                            break

                if not selected_filename and doc_options:
                    selected_filename = list(doc_options.keys())[0]

                selected_filename = st.selectbox(
                    "Chọn tài liệu",
                    list(doc_options.keys()),
                    index=list(doc_options.keys()).index(selected_filename)
                    if selected_filename
                    else 0,
                )

                if selected_filename:
                    doc_id = doc_options[selected_filename]
                    # Render document viewer
                    self.document_viewer.render_document(doc_id)
            else:
                st.error("Không thể tải danh sách tài liệu.")

        except Exception as e:
            st.error(f"Đã xảy ra lỗi: {str(e)}")

    def _get_status_badge(self, status):
        """
        Return a localized status label for display.

        Args:
            status: Parsing status string.

        Returns:
            str: Display label for the status.
        """
        return self.STATUS_LABELS.get(status, status)

    def _delete_document(self, doc_id):
        """
        Delete a document by ID.

        Args:
            doc_id: Document ID to delete.

        Returns:
            bool: True on success, otherwise False.
        """
        try:
            response = requests.delete(f"{API_BASE_URL}/documents/{doc_id}")
            return response.status_code == 200
        except Exception:
            return False


def main():
    """
    Application entry point.
    """
    app = StreamlitApp()
    app.run()


if __name__ == "__main__":
    main()
