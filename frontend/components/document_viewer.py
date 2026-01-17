# project_path/frontend/components/document_viewer.py
import streamlit as st
import requests
from typing import Dict, Any, List
import base64
from io import BytesIO
from PIL import Image, ImageDraw
from pathlib import Path
import sys

# Add project root to Python path
current_dir = Path(__file__).parent
root_dir = current_dir.parent.parent
sys.path.append(str(root_dir))


class DocumentViewer:
    def __init__(self, api_base_url: str):
        self.api_base_url = api_base_url

    def render_document(self, doc_id: str):
        """
        Render the document viewer page.
        - Shows document info and parsing stats
        - Supports per-page view
        - Provides layout, bounding boxes, and element details tabs

        Args:
            doc_id: Document ID to render.
        """
        try:
            # Fetch base document data first
            doc_response = requests.get(f"{self.api_base_url}/documents/{doc_id}")
            doc_response.raise_for_status()
            doc_data = doc_response.json()

            if doc_data["parsing_status"] != "completed":
                st.warning("Phân tích tài liệu chưa hoàn tất.")
                return

            # Calculate total pages
            total_pages = 0
            if doc_data.get("parsed_data") and doc_data["parsed_data"].get("elements"):
                pages = [elem["page"] for elem in doc_data["parsed_data"]["elements"]]
                if pages:
                    total_pages = max(pages)

            if total_pages == 0:
                st.warning("Không tìm thấy trang trong tài liệu.")
                return

            selected_page = st.selectbox(
                "Chọn trang",
                list(range(1, total_pages + 1)),
                format_func=lambda x: f"Trang {x}",
            )

            self._render_enhanced_main_view_with_hybrid(doc_data, selected_page)

        except requests.exceptions.RequestException as e:
            st.error(f"Không thể tải tài liệu từ API: {e}")
        except Exception as e:
            st.error(f"Lỗi khi hiển thị tài liệu: {str(e)}")

    def _render_enhanced_main_view_with_hybrid(
        self, doc_data: Dict[str, Any], page_num: int
    ):
        """
        Render the main view including hybrid parsing results.
        - Tab 1: original layout reconstruction (image-first) + text-only flow
        - Tab 2: bounding box visualization (OCR-enhanced highlighted)
        - Tab 3: element details (filterable)

        Args:
            doc_data: Document data.
            page_num: Current page number.
        """
        page_elements = []
        if doc_data.get("parsed_data"):
            page_elements = [
                elem
                for elem in doc_data["parsed_data"]["elements"]
                if elem["page"] == page_num
            ]

        if not page_elements:
            st.warning(f"Không tìm thấy phần tử trên trang {page_num}.")
            return

        st.header(f"Phân tích chi tiết trang {page_num}")

        tab_titles = [
            "Bố cục tài liệu",
            "Hiển thị bounding box",
            "Thông tin phần tử",
        ]
        tab1, tab2, tab3 = st.tabs(tab_titles)

        with tab1:
            st.markdown("#### Khôi phục bố cục gốc (ưu tiên hình ảnh)")
            st.info(
                "Tái tạo bố cục dựa trên tọa độ. "
                "Các phần tử có dữ liệu hình ảnh sẽ hiển thị bằng ảnh."
            )
            self._render_coordinate_preserved_content_with_hybrid(page_elements)

            st.markdown("---")
            st.markdown("#### Hiển thị văn bản theo thứ tự đọc (không gồm ảnh)")
            st.info(
                "Hiển thị HTML của tất cả phần tử theo thứ tự đọc. "
                "Ảnh sẽ được loại bỏ để dễ sao chép và tìm kiếm."
            )

            page_html_content = self._generate_page_html(page_elements)
            st.components.v1.html(page_html_content, height=600, scrolling=True)

        with tab2:
            self._render_visual_with_bounding_boxes_hybrid(page_elements, page_num)

        with tab3:
            self._render_element_details_with_hybrid(page_elements)

    def _render_coordinate_preserved_content_with_hybrid(
        self, elements: List[Dict[str, Any]]
    ):
        """
        Render layout-preserved content as HTML.

        Args:
            elements: Page element list.
        """
        try:
            coordinate_html = self._generate_coordinate_preserved_html_with_hybrid(
                elements
            )
            st.components.v1.html(coordinate_html, height=850, scrolling=True)
        except Exception as e:
            st.error(f"Lỗi hiển thị nội dung theo tọa độ: {str(e)}")

    def _generate_coordinate_preserved_html_with_hybrid(
        self, elements: List[Dict[str, Any]]
    ) -> str:
        """
        Generate HTML that preserves original layout using absolute positioning.
        - Elements are positioned using normalized coordinates.
        - Image elements are rendered first.
        - Non-image elements are rendered as HTML text.

        Args:
            elements: Document element list.

        Returns:
            str: Renderable HTML string (image-first).
        """
        html_elements = []
        for elem in elements:
            coordinates = elem.get("coordinates", [])
            if not (
                coordinates and isinstance(coordinates, list) and len(coordinates) >= 4
            ):
                continue

            try:
                top_left, _, bottom_right, _ = coordinates
                left, top = top_left.get("x", 0) * 100, top_left.get("y", 0) * 100
                width = (bottom_right.get("x", 0) - top_left.get("x", 0)) * 100
                height = (bottom_right.get("y", 0) - top_left.get("y", 0)) * 100

                if width <= 0 or height <= 0:
                    continue

                content = elem.get("content", {})
                base64_data = elem.get("base64_encoding")
                ocr_enhanced = elem.get("ocr_enhanced", False)

                border_style = (
                    "2px solid #28a745"
                    if ocr_enhanced
                    else "1px solid rgba(0,0,0,0.1)"
                )

                inner_html = ""
                if base64_data:
                    mime_type = elem.get("image_mime_type", "image/png")
                    ocr_badge = (
                        '<div class="ocr-badge">OCR nâng cao</div>'
                        if ocr_enhanced
                        else ""
                    )

                    # Append OCR text when available
                    ocr_text_html = ""
                    if ocr_enhanced and content.get("text"):
                        ocr_text_html = f"""
                        <div class="ocr-text-wrapper">
                            <div class="ocr-text-header">Văn bản trích xuất</div>
                            <pre class="ocr-text-content">{content['text']}</pre>
                        </div>
                        """

                    inner_html = f"""
                    <div class="image-wrapper">
                        <img src="data:{mime_type};base64,{base64_data}" style="width:100%; height:auto; object-fit: contain;"/>
                        {ocr_badge}
                    </div>
                    {ocr_text_html}
                    """
                elif content.get("html"):
                    inner_html = (
                        f'<div class="content-wrapper">{content["html"]}</div>'
                    )
                else:
                    inner_html = (
                        f'<div class="content-wrapper"><p>{content.get("text", "")}</p></div>'
                    )

                style = (
                    f"position: absolute; left: {left:.4f}%; top: {top:.4f}%; "
                    f"width: {width:.4f}%; height: {height:.4f}%; border: {border_style}; "
                    f"display: flex; flex-direction: column; overflow: hidden;"
                )

                html_elements.append(f'<div style="{style}">{inner_html}</div>')
            except (KeyError, IndexError, TypeError):
                continue

        return f"""
        <!DOCTYPE html><html><head><title>Xem trước tài liệu</title><meta charset="UTF-8">
        <style>
            body {{ margin: 0; font-family: sans-serif; background-color: #f0f2f6; }}
            .page-container {{
                position: relative; width: 100%; max-width: 800px; margin: 20px auto;
                border: 1px solid #ccc; background-color: white; aspect-ratio: 1 / 1.414;
                box-shadow: 0 4px 8px rgba(0,0,0,0.1);
            }}
            .page-container * {{ box-sizing: border-box; }}
            .content-wrapper {{ width: 100%; height: 100%; padding: 1% 2%; overflow: auto; font-size: 1.5vw; line-height: 1.2; }}
            .image-wrapper {{ position: relative; flex-shrink: 0; }}
            .ocr-badge {{
                position: absolute; top: 2px; right: 2px; background: #28a745; color: white;
                font-size: 10px; padding: 2px 4px; border-radius: 3px; z-index: 10;
            }}
            .ocr-text-wrapper {{
                flex-grow: 1; overflow-y: auto; background-color: #f8f9fa; border-top: 1px solid #dee2e6;
            }}
            .ocr-text-header {{
                font-size: 11px; font-weight: bold; color: #495057; background-color: #e9ecef;
                padding: 2px 5px;
            }}
            pre.ocr-text-content {{
                white-space: pre-wrap; word-wrap: break-word; font-size: 10px; margin: 0; padding: 5px;
            }}
        </style></head><body>
        <div class="page-container">{''.join(html_elements)}</div>
        </body></html>"""

    def _render_visual_with_bounding_boxes_hybrid(
        self, elements: List[Dict[str, Any]], page_num: int
    ):
        """
        Visualize bounding boxes for elements on a page.
        - Different colors per category
        - OCR-enhanced elements get thicker borders and labels
        - Legend shows category colors

        Args:
            elements: Page element list.
            page_num: Current page number.
        """
        try:
            canvas_width, canvas_height = 800, int(800 * 1.414)
            img = Image.new("RGB", (canvas_width, canvas_height), "white")
            draw = ImageDraw.Draw(img)

            # Enhanced category colors with OCR indication
            category_colors = {
                "heading1": "#e74c3c",
                "heading2": "#c0392b",
                "paragraph": "#3498db",
                "table": "#e67e22",
                "figure": "#27ae60",
                "chart": "#f39c12",
                "list": "#9b59b6",
                "footer": "#95a5a6",
                "header": "#34495e",
                "unknown": "#bdc3c7",
                "composite_table": "#8e44ad",
            }

            for elem in elements:
                coordinates = elem.get("coordinates", [])
                if not (
                    coordinates and isinstance(coordinates, list) and len(coordinates) >= 4
                ):
                    continue

                category = elem.get("category", "unknown")
                elem_id = elem.get("id", "")
                has_image = bool(elem.get("base64_encoding"))
                ocr_enhanced = elem.get("ocr_enhanced", False)

                top_left, _, bottom_right, _ = coordinates
                left = top_left.get("x", 0) * canvas_width
                top = top_left.get("y", 0) * canvas_height
                right = bottom_right.get("x", 0) * canvas_width
                bottom = bottom_right.get("y", 0) * canvas_height

                if right <= left or bottom <= top:
                    continue

                color = category_colors.get(category, "#95a5a6")

                # Different line styles for OCR enhanced elements
                line_width = 4 if ocr_enhanced else (3 if has_image else 2)

                draw.rectangle([left, top, right, bottom], outline=color, width=line_width)

                # Add OCR indicator
                label = f"{category} ({elem_id})"
                if ocr_enhanced:
                    label += " [OCR]"

                try:
                    bbox = draw.textbbox((left, top - 12), label)
                    bg_color = "#28a745" if ocr_enhanced else color
                    draw.rectangle(bbox, fill=bg_color)
                    draw.text((left, top - 12), label, fill="white")
                except AttributeError:
                    text_color = "#28a745" if ocr_enhanced else color
                    draw.text((left, top - 12), label, fill=text_color)

            st.image(
                img,
                caption=f"Trang {page_num} - hiển thị bounding box",
                use_container_width=True,
            )

            legend_items = []
            for cat, color in category_colors.items():
                legend_items.append(
                    f"<span style='background-color:{color};color:white;padding:2px 5px;border-radius:3px;'>{cat}</span>"
                )

            legend_html = " | ".join(legend_items)
            st.markdown(f"**Chú giải:** {legend_html}", unsafe_allow_html=True)

        except Exception as e:
            st.error(f"Lỗi hiển thị bounding box: {str(e)}")

    def _generate_page_html(self, elements: List[Dict[str, Any]]) -> str:
        """
        Combine all element HTML content in reading order into a single HTML string.

        Note: base64 images are excluded, only content.html is used.

        Args:
            elements: Page element list.

        Returns:
            str: Combined HTML string (text-only).
        """
        # Sort by y coordinate to approximate reading order
        sorted_elements = sorted(
            elements, key=lambda e: e.get("coordinates", [{}])[0].get("y", 0)
        )

        # Collect HTML parts
        html_parts = [elem.get("content", {}).get("html", "") for elem in sorted_elements]

        # Wrap with basic styling
        full_html = f"""
        <body style="margin: 0; padding: 0;">
            <div style="font-family: sans-serif; border: 1px solid #ddd; padding: 20px; background-color: #fff; margin: 10px;">
                {'<br>'.join(html_parts)}
            </div>
        </body>
        """
        return full_html

    def _render_element_details_with_hybrid(self, elements: List[Dict[str, Any]]):
        """
        Render detailed info for all elements on the page.
        - Optional filter for OCR-enhanced elements
        - Optional filter for image elements
        - Show text, HTML, image, and coordinate data

        Args:
            elements: Page element list.
        """
        st.info("Kiểm tra chi tiết dữ liệu đã trích xuất.")

        # Filter options
        col1, col2 = st.columns(2)
        with col1:
            show_only_ocr = st.checkbox(
                "Chỉ hiển thị phần tử OCR nâng cao", value=False
            )
        with col2:
            show_only_images = st.checkbox(
                "Chỉ hiển thị phần tử hình ảnh", value=False
            )

        filtered_elements = elements
        if show_only_ocr:
            filtered_elements = [
                elem for elem in filtered_elements if elem.get("ocr_enhanced", False)
            ]
        if show_only_images:
            filtered_elements = [
                elem for elem in filtered_elements if elem.get("base64_encoding")
            ]

        if not filtered_elements:
            st.warning("Không có phần tử phù hợp với bộ lọc.")
            return

        for i, elem in enumerate(sorted(filtered_elements, key=lambda x: x.get("id", 0))):
            self._render_single_element_card_with_hybrid(elem, i)

    def _render_single_element_card_with_hybrid(
        self, element: Dict[str, Any], index: int
    ):
        """
        Render a single element detail card.
        - Left: page, OCR status, bounding box, image
        - Right: text, HTML, stats

        Args:
            element: Element data.
            index: Element index for unique keys.
        """
        category = element.get("category", "unknown")
        elem_id = element.get("id", "N/A")
        ocr_enhanced = element.get("ocr_enhanced", False)

        title_suffix = " [OCR nâng cao]" if ocr_enhanced else ""
        title = f"**{category.upper()}** (ID: {elem_id}){title_suffix}"

        with st.expander(title, expanded=False):
            col1, col2 = st.columns([1, 1])

            with col1:
                st.write(f"**Trang:** {element.get('page', 'N/A')}")
                st.write(
                    f"**OCR:** {'Đã áp dụng' if ocr_enhanced else 'Chưa áp dụng'}"
                )

                if element.get("coordinates"):
                    bbox = self._calculate_bounding_box(element["coordinates"])
                    st.write("**Bounding box:**")
                    st.json({k: f"{v:.4f}" for k, v in bbox.items()}, expanded=False)

                if element.get("base64_encoding"):
                    try:
                        image_data = base64.b64decode(element["base64_encoding"])
                        image = Image.open(BytesIO(image_data))
                        caption = f"Hình ảnh (ID: {elem_id})"
                        if ocr_enhanced:
                            caption += " - OCR nâng cao"
                        st.image(image, caption=caption, use_container_width=True)
                    except Exception:
                        st.error("Không thể tải hình ảnh.")

            with col2:
                content = element.get("content", {})
                st.write("**Nội dung văn bản**")
                text_content = content.get("text", "N/A")

                if ocr_enhanced and text_content != "N/A":
                    st.success("Văn bản trích xuất từ OCR:")

                st.text_area(
                    "Văn bản",
                    value=text_content,
                    height=120,
                    disabled=True,
                    key=f"text_{elem_id}_{index}",
                )

                if text_content != "N/A":
                    st.write(f"**Độ dài văn bản:** {len(text_content)} ký tự")
                    st.write(f"**Số từ:** {len(text_content.split())} từ")

                st.write("**Nội dung HTML**")
                html_content = content.get("html", "N/A")
                if html_content != "N/A":
                    st.code(html_content, language="html")
                else:
                    st.text("Không có nội dung HTML")

    def _calculate_bounding_box(
        self, coordinates: List[Dict[str, float]]
    ) -> Dict[str, float]:
        """
        Calculate bounding box from coordinates.

        Args:
            coordinates: Coordinate list [{'x': ..., 'y': ...}, ...]

        Returns:
            Dict: left, top, right, bottom, width, height.
        """
        if not (coordinates and isinstance(coordinates, list)):
            return {}
        x = [c.get("x", 0) for c in coordinates]
        y = [c.get("y", 0) for c in coordinates]
        left, right, top, bottom = min(x), max(x), min(y), max(y)
        return {
            "left": left,
            "top": top,
            "right": right,
            "bottom": bottom,
            "width": abs(right - left),
            "height": abs(bottom - top),
        }
