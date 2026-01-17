# project_path/frontend/app.py

import time
import json
from pathlib import Path
import sys

import streamlit as st

# Add project root to Python path
current_dir = Path(__file__).parent
root_dir = current_dir.parent
sys.path.append(str(root_dir))

from backend.services.file_processor import FileProcessor
from frontend.components.file_uploader import FileUploader
from frontend.components.document_viewer import DocumentViewer
from frontend.utils.async_utils import run_async
from frontend.utils import key_manager


# Streamlit page configuration
st.set_page_config(
    page_title="Playground Phân tích tài liệu Upstage",
    layout="wide",
    initial_sidebar_state="expanded",
)


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
        self.processor = FileProcessor()
        self.file_uploader = FileUploader(self.processor)
        self.document_viewer = DocumentViewer(self.processor)

        # Session state initialization
        if "selected_doc_id" not in st.session_state:
            st.session_state.selected_doc_id = None
        if "active_api_key" not in st.session_state:
            st.session_state.active_api_key = None

    def run(self):
        """
        Run the Streamlit app UI and route between pages.
        """
        st.title("Playground Phân tích tài liệu Upstage")

        # Sidebar menu
        with st.sidebar:
            st.header("API Key")
            self._render_api_key_section()
            st.markdown("---")

            st.header("Danh mục")
            page = st.radio(
                "Chọn trang",
                [
                    "Tải tệp lên",
                    "Danh sách tài liệu đã phân tích",
                    "Trình xem tài liệu",
                ],
            )

            self._render_system_summary_sidebar()

        # Page routing
        if page == "Tải tệp lên":
            self._render_upload_page()
        elif page == "Danh sách tài liệu đã phân tích":
            self._render_document_list()
        elif page == "Trình xem tài liệu":
            self._render_document_viewer()

    def _render_api_key_section(self):
        data = key_manager.load_keys()
        keys = data.get("keys", [])
        active_key = data.get("active_key")

        if keys:
            options = []
            for idx, key in enumerate(keys):
                if len(key) <= 8:
                    label = f"{idx + 1}: {key}"
                else:
                    label = f"{idx + 1}: {key[:4]}...{key[-4:]}"
                options.append((label, key))

            labels = [item[0] for item in options]
            key_map = {item[0]: item[1] for item in options}
            default_index = 0
            if active_key in keys:
                default_index = keys.index(active_key)

            selected_label = st.selectbox("Chọn API key", labels, index=default_index)
            selected_key = key_map[selected_label]
            if selected_key != active_key:
                key_manager.set_active_key(selected_key)
                active_key = selected_key
        else:
            st.info("Chưa có API key nào được lưu.")

        new_key = st.text_input("Nhập API key mới", type="password")
        if st.button("Lưu API key"):
            if new_key.strip():
                data = key_manager.add_key(new_key.strip())
                active_key = data.get("active_key")
                st.success("Đã lưu API key.")
                st.rerun()
            else:
                st.warning("Vui lòng nhập API key.")

        st.session_state.active_api_key = active_key

    def _render_system_summary_sidebar(self):
        st.markdown("#### Tóm tắt hệ thống")
        try:
            documents = run_async(self.processor.get_all_documents())
            total = len(documents)
            completed = len([d for d in documents if d.parsing_status == "completed"])
            st.metric("Tổng tài liệu", total)
            st.metric("Đã hoàn tất", completed)
        except Exception:
            pass

    def _render_upload_page(self):
        """
        Render the file upload and parsing page.
        """
        st.header("Tải tệp và phân tích")

        if not st.session_state.active_api_key:
            st.warning("Vui lòng nhập API key để tải lên và phân tích tài liệu.")
            return

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
            col1, col2, col3 = st.columns(3)
            with col1:
                st.write(f"**Tên tệp:** {uploaded_file.name}")
            with col2:
                st.write(f"**Kích thước:** {uploaded_file.size:,} bytes")
            with col3:
                st.write(f"**Loại tệp:** {uploaded_file.type}")

            if st.button("Bắt đầu phân tích", type="primary"):
                with st.spinner("Đang tải tệp và bắt đầu phân tích."):
                    success, result = self.file_uploader.upload_file(
                        uploaded_file, st.session_state.active_api_key
                    )

                    if success:
                        st.success("Phân tích hoàn tất!")
                        self._render_parsing_stats(result)
                    else:
                        # Check if result contains error message format
                        if isinstance(result, str):
                            error_msg = result
                        else:
                            error_msg = str(result)
                        st.error(f"**Phân tích thất bại:** {error_msg}")

    def _render_parsing_stats(self, record):
        if not record or not record.parsed_data:
            return
        elements = record.parsed_data.elements
        pages = max((elem.page for elem in elements), default=0)
        image_elements = [e for e in elements if e.base64_encoding]
        text_elements = [e for e in elements if e.content and e.content.text]

        col1, col2, col3, col4 = st.columns(4)
        with col1:
            st.metric("Tổng phần tử", len(elements))
        with col2:
            st.metric("Trang", pages)
        with col3:
            st.metric("Phần tử hình ảnh", len(image_elements))
        with col4:
            st.metric("Phần tử văn bản", len(text_elements))

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
            documents = run_async(self.processor.get_all_documents())

            if status_filter:
                documents = [d for d in documents if d.parsing_status == status_filter]

            if not documents:
                st.info("Không có tài liệu phù hợp.")
                return

            if sort_by == "Tên tệp":
                documents.sort(key=lambda x: x.original_filename)

            for i, doc in enumerate(documents):
                self._render_document_card(doc, i)

        except Exception as e:
            st.error(f"Đã xảy ra lỗi: {str(e)}")

    def _render_document_card(self, doc, index: int):
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

        status_color = status_colors.get(doc.parsing_status, "info")

        with st.expander(f"{doc.original_filename}", expanded=False):
            col1, col2, col3 = st.columns([2, 1, 1])

            with col1:
                st.markdown(
                    f"**Trạng thái:** :{status_color}[{self._get_status_badge(doc.parsing_status)}]"
                )
                st.write(f"**Thời gian tải lên:** {self._format_time(doc.upload_time)}")
                st.write(f"**Kích thước tệp:** {doc.file_size:,} bytes")

                # Display error message if failed
                if doc.parsing_status == "failed" and hasattr(doc, "error_message") and doc.error_message:
                    st.error(f"**Lỗi:** {doc.error_message}")

                if doc.parsing_status == "completed" and doc.parsed_data:
                    elements = doc.parsed_data.elements
                    pages = max((elem.page for elem in elements), default=0)
                    image_elements = [e for e in elements if e.base64_encoding]

                    stats_col1, stats_col2, stats_col3 = st.columns(3)
                    with stats_col1:
                        st.metric("Phần tử", len(elements))
                    with stats_col2:
                        st.metric("Trang", pages)
                    with stats_col3:
                        st.metric("Hình ảnh", len(image_elements))

            with col2:
                if doc.parsing_status == "completed":
                    if st.button(
                        "Xem tài liệu", key=f"view_{doc.id}_{index}"
                    ):
                        st.session_state.selected_doc_id = doc.id
                        st.success(
                            "Tài liệu đã được chọn. Hãy chuyển sang tab Trình xem tài liệu."
                        )
                    if st.button(
                        "📋 Sao chép", key=f"copy_html_{doc.id}_{index}", help="Sao chép nội dung tài liệu đã được trích xuất"
                    ):
                            if doc.parsed_data and doc.parsed_data.content:
                                html_content = doc.parsed_data.content.html
                                if html_content:
                                    st.code(html_content, language="html")
                                    st.success("Nội dung đã được hiển thị ở trên. Bạn có thể copy từ code block.")
                                else:
                                    # Combine HTML from all elements if content.html is empty
                                    html_parts = []
                                    if doc.parsed_data.elements:
                                        for elem in doc.parsed_data.elements:
                                            if elem.content and elem.content.html:
                                                html_parts.append(elem.content.html)
                                    combined_html = "\n".join(html_parts)
                                    if combined_html:
                                        st.code(combined_html, language="html")
                                        st.success("Nội dung đã được hiển thị ở trên. Bạn có thể copy từ code block.")
                                    else:
                                        st.warning("Không có nội dung để sao chép.")
                            else:
                                st.warning("Không có dữ liệu phân tích.")
                else:
                    st.button(
                        "Đang xử lý...",
                        key=f"waiting_{doc.id}_{index}",
                        disabled=True,
                    )

            with col3:
                if st.button(
                    "Xóa",
                    key=f"delete_{doc.id}_{index}",
                    type="secondary",
                ):
                    if self._delete_document(doc.id):
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

        try:
            documents = run_async(self.processor.get_all_documents())
            completed_docs = [doc for doc in documents if doc.parsing_status == "completed"]

            if not completed_docs:
                st.warning("Chưa có tài liệu hoàn tất.")
                return

            doc_options = {doc.original_filename: doc.id for doc in completed_docs}

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
                self.document_viewer.render_document(doc_id)

        except Exception as e:
            st.error(f"Đã xảy ra lỗi: {str(e)}")

    def _get_status_badge(self, status):
        return self.STATUS_LABELS.get(status, status)

    def _delete_document(self, doc_id):
        try:
            return run_async(self.processor.delete_document(doc_id))
        except Exception:
            return False

    def _format_time(self, value) -> str:
        if isinstance(value, str):
            return value[:19]
        try:
            return value.strftime("%Y-%m-%d %H:%M:%S")
        except Exception:
            return str(value)


def main():
    app = StreamlitApp()
    app.run()


if __name__ == "__main__":
    main()
