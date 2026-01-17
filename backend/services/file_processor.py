# project_path/backend/services/file_processor.py

import asyncio
import html2text
from pathlib import Path
from typing import Optional, Dict, Any, List
from backend.models.document import DocumentRecord, DocumentElement, ElementContent
from backend.services.upstage_client import UpstageClient
from backend.services.storage import StorageService
from backend.config import config
from backend.utils.helpers import get_image_mime_type_from_base64, parse_api_error


class FileProcessor:
    def __init__(self, api_key: Optional[str] = None):
        """
        Initialize FileProcessor.
        - Create Upstage API client
        - Initialize storage service
        - Configure Markdown converter

        Note: This class is used as a singleton and initialized once per app run.
        """
        # Ensure storage directories exist
        config.ensure_directories_exist()

        self.upstage_client = UpstageClient(api_key=api_key)
        self.storage_service = StorageService()
        self.markdown_converter = html2text.HTML2Text()
        self.markdown_converter.ignore_links = True
        self.markdown_converter.body_width = 0

        print("[FileProcessor] Initialized with hybrid parsing capabilities")
        print(f"[FileProcessor] Storage directory: {config.STORAGE_DIR}")

    def set_api_key(self, api_key: str):
        if not api_key:
            return
        if self.upstage_client:
            self.upstage_client.api_key = api_key
        else:
            self.upstage_client = UpstageClient(api_key=api_key)

    async def process_file(
        self,
        file_content: bytes,
        filename: str,
        content_type: str,
        enhanced_options: Optional[Dict[str, Any]] = None,
        background: bool = True,
    ) -> DocumentRecord:
        """Process an uploaded file and start parsing."""
        record = await self.storage_service.save_uploaded_file(
            file_content, filename, content_type
        )

        default_options = {
            "extract_images": False,
            "hybrid_parsing": True,
        }

        if enhanced_options:
            default_options.update(enhanced_options)

        if background:
            asyncio.create_task(self._parse_document_hybrid_async(record, default_options))
            return record

        await self._parse_document_hybrid_async(record, default_options)
        updated = await self.storage_service.get_document_record(record.id)
        return updated or record

    def _convert_elements_to_markdown(self, elements: list[DocumentElement]) -> str:
        """Convert document elements to a single Markdown string in reading order."""
        if not elements:
            return ""

        sorted_elements = sorted(
            elements, key=lambda e: (e.page, e.coordinates[0].y if e.coordinates else 0)
        )

        markdown_parts = []
        for elem in sorted_elements:
            if (hasattr(elem, "_ocr_enhanced") and elem._ocr_enhanced) or elem.category == "composite_table":
                if elem.content and elem.content.markdown:
                    markdown_parts.append(elem.content.markdown)
                elif elem.content and elem.content.text:
                    markdown_parts.append(elem.content.text)
            else:
                html_content = elem.content.html
                if html_content:
                    markdown_content = self.markdown_converter.handle(html_content).strip()
                    elem.content.markdown = markdown_content
                    markdown_parts.append(markdown_content)

        return "\n\n".join(part for part in markdown_parts if part)

    async def _parse_document_hybrid_async(
        self, record: DocumentRecord, options: Dict[str, Any]
    ):
        """Parse a document asynchronously using hybrid extraction."""
        try:
            if not self.upstage_client or not self.upstage_client.api_key:
                raise ValueError("Upstage API key is required for parsing.")

            await self._update_parsing_status(record.id, "processing")

            file_path = Path(record.file_path)

            # Always use the hybrid parsing method
            print(
                f"[FileProcessor] Starting hybrid parsing for {record.original_filename}"
            )
            parsed_data = await self.upstage_client.parse_document_with_hybrid_extraction(
                file_path=file_path, extract_images=options.get("extract_images", False)
            )

            if parsed_data and parsed_data.elements:
                # Add MIME type to all image elements
                for elem in parsed_data.elements:
                    if elem.base64_encoding:
                        elem.image_mime_type = get_image_mime_type_from_base64(
                            elem.base64_encoding
                        )

                # Analyze for composite structures using OCR-enhanced data
                if self._is_complex_content_pattern(parsed_data.elements):
                    enhanced_elements = self._analyze_and_enhance_elements(
                        parsed_data.elements
                    )
                    parsed_data.elements = enhanced_elements

                # Generate a complete markdown document from final elements
                full_markdown = self._convert_elements_to_markdown(parsed_data.elements)
                parsed_data.content.markdown = full_markdown

                stats = self._generate_parsing_statistics(parsed_data.elements)
                print(f"[FileProcessor] Parsing completed. {stats}")

            await self.storage_service.save_parsed_data(record.id, parsed_data)

        except Exception as e:
            error_message = str(e)
            status_code, vietnamese_message = parse_api_error(error_message)
            
            # Format error message with Vietnamese message
            if status_code:
                formatted_error = f"[{status_code}] {vietnamese_message}"
            else:
                formatted_error = vietnamese_message
            
            await self._update_parsing_status(record.id, "failed", formatted_error)
            print(f"Parsing failed (ID: {record.id}): {error_message}")

    def _generate_parsing_statistics(self, elements: List[DocumentElement]) -> str:
        """Generate parsing statistics including OCR info."""
        total_elements = len(elements)
        image_elements = len([e for e in elements if e.base64_encoding])
        ocr_enhanced = len(
            [e for e in elements if hasattr(e, "_ocr_enhanced") and e._ocr_enhanced]
        )
        return (
            f"Total Elements: {total_elements}, "
            f"Image Elements: {image_elements}, "
            f"OCR Enhanced: {ocr_enhanced}"
        )

    async def _update_parsing_status(
        self, doc_id: str, status: str, error_message: Optional[str] = None
    ):
        """Update parsing status."""
        record = await self.storage_service.get_document_record(doc_id)
        if record:
            record.parsing_status = status
            if error_message:
                record.error_message = error_message
            await self.storage_service._save_metadata(record)

    async def get_document(self, doc_id: str) -> Optional[DocumentRecord]:
        """Get a document record."""
        return await self.storage_service.get_document_record(doc_id)

    async def get_all_documents(self) -> list[DocumentRecord]:
        """Get all document records."""
        return await self.storage_service.get_all_documents()

    async def delete_document(self, doc_id: str) -> bool:
        """Delete a document."""
        return await self.storage_service.delete_document(doc_id)

    def validate_file(self, filename: str, file_size: int) -> tuple[bool, str]:
        """
        Validate file.

        Args:
            filename: File name.
            file_size: File size in bytes.

        Returns:
            tuple[bool, str]: (validity, error_message)
        """
        # Check file extension
        file_path = Path(filename)
        allowed_extensions = [
            ".pdf",
            ".docx",
            ".pptx",
            ".xlsx",
            ".jpg",
            ".jpeg",
            ".png",
            ".bmp",
            ".tiff",
            ".heic",
            ".webp",
        ]
        if file_path.suffix.lower() not in allowed_extensions:
            return (
                False,
                f"Unsupported file format. Supported formats: {', '.join(allowed_extensions)}",
            )

        # Check file size
        if file_size > config.MAX_FILE_SIZE:
            max_size_mb = config.MAX_FILE_SIZE // (1024 * 1024)
            return False, f"File too large. Maximum size: {max_size_mb}MB"

        # Check minimum size
        if file_size < 100:  # Less than 100 bytes
            return False, "File too small. Please check if it's a valid document."

        return True, ""

    def _analyze_and_enhance_elements(
        self, elements: List[DocumentElement]
    ) -> List[DocumentElement]:
        """
        Analyze parsed elements and convert composite structures into enhanced elements.
        """
        if not elements:
            return elements

        enhanced_elements = []
        processed_element_ids = set()

        # Group elements by page
        pages = {}
        for elem in elements:
            page = elem.page
            if page not in pages:
                pages[page] = []
            pages[page].append(elem)

        for page_num, page_elements in pages.items():
            page_enhanced = self._process_page_elements(
                page_elements, processed_element_ids
            )
            enhanced_elements.extend(page_enhanced)

        return enhanced_elements

    def _process_page_elements(
        self, page_elements: List[DocumentElement], processed_ids: set
    ) -> List[DocumentElement]:
        """Analyze page elements for composite structures."""
        enhanced_elements = []

        # Use image elements as anchors for composite detection (including OCR-enhanced)
        image_elements = [
            elem
            for elem in page_elements
            if elem.base64_encoding and elem.id not in processed_ids
        ]

        for img_elem in image_elements:
            # Find nearby text elements around the image
            related_text_elements = self._find_spatially_related_elements(
                img_elem, page_elements
            )

            if related_text_elements:
                # Convert to a composite table element
                composite_element = self._create_enhanced_table_element(
                    img_elem, related_text_elements
                )
                enhanced_elements.append(composite_element)

                # Mark processed elements
                processed_ids.add(img_elem.id)
                for text_elem in related_text_elements:
                    processed_ids.add(text_elem.id)
            else:
                # Keep original image element when no related text
                enhanced_elements.append(img_elem)
                processed_ids.add(img_elem.id)

        # Add any remaining elements
        for elem in page_elements:
            if elem.id not in processed_ids:
                enhanced_elements.append(elem)

        return enhanced_elements

    def _find_spatially_related_elements(
        self, image_element: DocumentElement, all_elements: List[DocumentElement]
    ) -> List[DocumentElement]:
        """Find text elements related to an image based on spatial proximity."""
        if not image_element.coordinates:
            return []

        related_elements = []
        img_bbox = image_element.bounding_box

        # Find text elements in the same row or nearby region
        for elem in all_elements:
            if (
                elem.id != image_element.id
                and elem.coordinates
                and elem.category in ["paragraph", "text", "caption"]
                and elem.content
                and elem.content.text.strip()
            ):
                elem_bbox = elem.bounding_box

                # Vertical proximity check (same row or close row)
                vertical_distance = abs(
                    elem_bbox.top_left.y - img_bbox.top_left.y
                )
                max_vertical_threshold = max(img_bbox.height, 50)  # Image height or 50px

                # Horizontal relation check (right of image)
                is_right_of_image = elem_bbox.top_left.x > img_bbox.top_left.x

                if vertical_distance <= max_vertical_threshold and is_right_of_image:
                    related_elements.append(elem)

        # Sort by Y coordinate to preserve reading order
        related_elements.sort(
            key=lambda e: e.coordinates[0].y if e.coordinates else 0
        )

        return related_elements

    def _create_enhanced_table_element(
        self, image_element: DocumentElement, text_elements: List[DocumentElement]
    ) -> DocumentElement:
        """Create a composite element by merging image and nearby text."""
        # Combine text from adjacent elements
        combined_text_parts = []
        for text_elem in text_elements:
            if text_elem.content and text_elem.content.text.strip():
                combined_text_parts.append(text_elem.content.text.strip())

        # Use the image OCR text as the primary source
        image_text = ""
        if (
            hasattr(image_element, "_ocr_enhanced")
            and image_element._ocr_enhanced
            and image_element.content.text
        ):
            image_text = image_element.content.text.strip()

        # Merge texts: image text first, then adjacent text
        final_text = image_text
        if combined_text_parts:
            final_text += "\n" + "\n".join(combined_text_parts)

        final_html = f"""
        <div class="composite-element hybrid-enhanced">
            <div class="image-cell">
                <img src="data:{image_element.image_mime_type or "image/png"};base64,{image_element.base64_encoding}" alt="Ảnh tổng hợp"/>
            </div>
            <div class="text-cell">
                <h4>Nội dung trích xuất (OCR nâng cao)</h4>
                <pre>{final_text}</pre>
            </div>
        </div>
        """
        final_markdown = (
            "![Ảnh tổng hợp]\n\n"
            "**Nội dung trích xuất:**\n"
            f"```\n{final_text}\n```"
        )

        # Create a new composite element
        composite_element = DocumentElement(
            id=image_element.id,
            category="composite_table",  # New category for these special elements
            content=ElementContent(
                html=final_html, markdown=final_markdown, text=final_text
            ),
            coordinates=image_element.coordinates,  # Use original image coordinates
            page=image_element.page,
            base64_encoding=image_element.base64_encoding,
            image_mime_type=image_element.image_mime_type,
        )

        # Preserve the OCR flag
        if hasattr(image_element, "_ocr_enhanced"):
            setattr(composite_element, "_ocr_enhanced", image_element._ocr_enhanced)

        return composite_element

    def _is_complex_content_pattern(self, elements: List[DocumentElement]) -> bool:
        """Detect whether elements contain potential composite structures."""
        has_images = any(elem.base64_encoding for elem in elements)
        has_text = any(elem.content and elem.content.text for elem in elements)
        # If there are images and text on the same page, analyze composite structures.
        return has_images and has_text
