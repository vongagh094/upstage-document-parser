# project_path/backend/services/upstage_client.py

import httpx
import aiofiles
from typing import Dict, Any
from pathlib import Path
from backend.config import config
from backend.models.document import (
    ParsedDocument,
    DocumentElement,
    ElementContent,
    Coordinate,
    DocumentContent,
)


class UpstageClient:
    def __init__(self, api_key: str = None):
        self.api_key = api_key or config.UPSTAGE_API_KEY
        self.base_url = config.UPSTAGE_API_URL

        if not self.api_key:
            raise ValueError(
                "Upstage API key is required. Please set UPSTAGE_API_KEY in environment variables."
            )

    async def parse_document_with_hybrid_extraction(
        self, file_path: Path, extract_images: bool = True
    ) -> ParsedDocument:
        """
        Parse a document using the Upstage API.

        Single API call to process the entire document:
        - Parse all pages in one request
        - Force OCR
        - Extract images (table, figure, chart, equation)

        Args:
            file_path: Path to the file to parse.
            extract_images: Whether to extract base64 image data.

        Returns:
            ParsedDocument: Parsed document data (all pages included).
        """
        print(f"[UpstageClient] Starting document parsing: {file_path.name}")
        print("[UpstageClient] Calling Upstage API (single request for entire document)...")

        headers = {"Authorization": f"Bearer {self.api_key}"}

        try:
            async with aiofiles.open(file_path, "rb") as file:
                file_content = await file.read()

            files = {
                "document": (
                    file_path.name,
                    file_content,
                    self._get_content_type(file_path),
                )
            }

            data = {"model": "document-parse", "ocr": "force"}

            if extract_images:
                data["base64_encoding"] = "['table', 'figure', 'chart', 'equation']"

            timeout = httpx.Timeout(600.0)

            async with httpx.AsyncClient(timeout=timeout) as client:
                response = await client.post(
                    self.base_url, headers=headers, files=files, data=data
                )
                response.raise_for_status()
                result = response.json()

                parsed_data = self._parse_response(result)

                # Mark OCR-enhanced image elements
                ocr_enhanced_count = 0
                if parsed_data and parsed_data.elements:
                    for elem in parsed_data.elements:
                        if elem.base64_encoding and elem.content and elem.content.text:
                            setattr(elem, "_ocr_enhanced", True)
                            ocr_enhanced_count += 1

                print("[UpstageClient] Parsing completed successfully!")
                print(
                    f"[UpstageClient] Total elements: {len(parsed_data.elements) if parsed_data else 0}"
                )
                print(f"[UpstageClient] OCR enhanced elements: {ocr_enhanced_count}")
                return parsed_data

        except Exception as e:
            print(f"[ERROR] Document parsing failed: {str(e)}")
            raise

    def _get_content_type(self, file_path: Path) -> str:
        """
        Determine MIME type from file extension.

        Args:
            file_path: File path.

        Returns:
            str: MIME type (e.g., 'application/pdf', 'image/jpeg').
        """
        extension = file_path.suffix.lower()
        content_types = {
            ".pdf": "application/pdf",
            ".docx": "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
            ".pptx": "application/vnd.openxmlformats-officedocument.presentationml.presentation",
            ".xlsx": "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            ".jpg": "image/jpeg",
            ".jpeg": "image/jpeg",
            ".png": "image/png",
            ".bmp": "image/bmp",
            ".tiff": "image/tiff",
            ".tif": "image/tiff",
            ".heic": "image/heic",
            ".webp": "image/webp",
        }
        return content_types.get(extension, "application/octet-stream")

    def _parse_response(self, response_data: Dict[str, Any]) -> ParsedDocument:
        """
        Convert Upstage API response into a ParsedDocument.

        Args:
            response_data: JSON response from Upstage API.

        Returns:
            ParsedDocument: Parsed document data.

        Raises:
            Exception: When response parsing fails.
        """
        try:
            elements = []

            if "elements" in response_data and isinstance(response_data["elements"], list):
                for elem_data in response_data["elements"]:
                    elements.append(self._parse_element(elem_data))
            elif "content" in response_data:
                content_data = response_data.get("content", {})
                element = DocumentElement(
                    id=1,
                    category="document",
                    content=ElementContent(
                        html=content_data.get("html", ""),
                        markdown=content_data.get("markdown", ""),
                        text=content_data.get("text", str(content_data)),
                    ),
                    coordinates=[],
                    page=1,
                    base64_encoding=None,
                )
                elements = [element]

            content_data = response_data.get("content", {})
            if isinstance(content_data, str):
                document_content = DocumentContent(
                    html="", markdown="", text=content_data
                )
            else:
                document_content = DocumentContent(
                    html=content_data.get("html", ""),
                    markdown=content_data.get("markdown", ""),
                    text=content_data.get("text", ""),
                )

            return ParsedDocument(
                api=response_data.get("api", "upstage-document-parse"),
                model=response_data.get("model", "document-parse"),
                content=document_content,
                elements=elements,
                usage=response_data.get("usage", {}),
            )

        except Exception as e:
            raise Exception(
                f"Response parsing failed: {str(e)}. Response: {response_data}"
            )

    def _parse_element(self, elem_data: Dict[str, Any]) -> DocumentElement:
        """
        Convert a single API element into a DocumentElement.

        Args:
            elem_data: Element data dict.

        Returns:
            DocumentElement: Parsed element.
        """
        # Parse coordinates (4 points)
        coordinates = []
        coord_data = elem_data.get("coordinates", [])

        if coord_data:
            for coord in coord_data:
                # Dict format {'x': ..., 'y': ...}
                if isinstance(coord, dict) and "x" in coord and "y" in coord:
                    coordinates.append(
                        Coordinate(x=float(coord["x"]), y=float(coord["y"]))
                    )
                # List format [x, y]
                elif isinstance(coord, list) and len(coord) >= 2:
                    coordinates.append(
                        Coordinate(x=float(coord[0]), y=float(coord[1]))
                    )

        # Parse content (html, markdown, text)
        content_data = elem_data.get("content", {})
        if isinstance(content_data, str):
            content = ElementContent(text=content_data, html="", markdown="")
        else:
            content = ElementContent(
                html=content_data.get("html", ""),
                markdown=content_data.get("markdown", ""),
                text=content_data.get("text", ""),
            )

        # Parse base64 image data (handles multiple response formats)
        base64_encoding = elem_data.get("base64_encoding")
        if isinstance(base64_encoding, dict):
            # Dict format: {'data': 'base64string...'}
            base64_encoding = base64_encoding.get("data", "")
        elif not isinstance(base64_encoding, str):
            # Non-string values treated as None
            base64_encoding = None

        # Empty string becomes None
        if base64_encoding == "":
            base64_encoding = None

        return DocumentElement(
            id=elem_data.get("id", 0),
            category=elem_data.get("category", "unknown"),
            content=content,
            coordinates=coordinates,
            page=elem_data.get("page", 1),
            base64_encoding=base64_encoding,
        )
