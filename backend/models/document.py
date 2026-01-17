# project_path/backend/config.py

from pydantic import BaseModel
from typing import List, Optional, Dict, Any
from datetime import datetime


class Coordinate(BaseModel):
    """
    2D coordinate within a document using normalized values.

    Attributes:
        x: X-axis coordinate (0.0-1.0 normalized).
        y: Y-axis coordinate (0.0-1.0 normalized).
    """

    x: float
    y: float


class BoundingBox(BaseModel):
    """
    Bounding box defined by four corner coordinates.

    Attributes:
        coordinates: Coordinate list (top-left, top-right, bottom-right, bottom-left).
    """

    coordinates: List[Coordinate]

    @property
    def top_left(self) -> Coordinate:
        return self.coordinates[0]

    @property
    def bottom_right(self) -> Coordinate:
        return self.coordinates[2]

    @property
    def width(self) -> float:
        return abs(self.bottom_right.x - self.top_left.x)

    @property
    def height(self) -> float:
        return abs(self.bottom_right.y - self.top_left.y)


class ElementContent(BaseModel):
    """
    Content of a document element in multiple formats.

    Attributes:
        html: HTML content.
        markdown: Markdown content.
        text: Plain text content.
    """

    html: str = ""
    markdown: str = ""
    text: str = ""


class DocumentElement(BaseModel):
    """
    Single element in a document (paragraph, table, image, etc.).

    Attributes:
        id: Unique element ID.
        category: Element type (heading1, paragraph, table, figure, chart, etc.).
        content: Element content (HTML, Markdown, Text).
        coordinates: Element coordinates (4 points).
        page: Page number (1-based).
        base64_encoding: Base64-encoded image data (if image element).
        image_mime_type: MIME type for the image (e.g., image/png, image/jpeg).
    """

    id: int
    category: str  # heading1, paragraph, table, figure, chart, etc.
    content: ElementContent
    coordinates: List[Coordinate]
    page: int
    base64_encoding: Optional[str] = None
    image_mime_type: Optional[str] = None

    @property
    def bounding_box(self) -> BoundingBox:
        return BoundingBox(coordinates=self.coordinates)


class DocumentContent(BaseModel):
    """
    Full document content in multiple formats.

    Attributes:
        html: Full document HTML.
        markdown: Full document Markdown.
        text: Full document plain text.
    """

    html: str = ""
    markdown: str = ""
    text: str = ""


class ParsedDocument(BaseModel):
    """
    Parsed document returned by the Upstage API.

    Attributes:
        api: API name (e.g., upstage-document-parse).
        model: Model name (e.g., document-parse).
        content: Full document content.
        elements: List of document elements.
        usage: API usage info (tokens, pages, etc.).
    """

    api: str
    model: str
    content: DocumentContent
    elements: List[DocumentElement]
    usage: Dict[str, Any]


class DocumentRecord(BaseModel):
    """
    Metadata and parsing status for an uploaded document.

    Attributes:
        id: Document ID (UUID).
        filename: Stored filename (UUID + extension).
        original_filename: Original filename.
        file_path: Full file path.
        file_size: File size in bytes.
        content_type: MIME type.
        upload_time: Upload timestamp.
        parsing_status: Status (pending, processing, completed, failed).
        parsed_data: Parsed document data (when completed).
        error_message: Error message (when failed).
    """

    id: str
    filename: str
    original_filename: str
    file_path: str
    file_size: int
    content_type: str
    upload_time: datetime
    parsing_status: str = "pending"  # pending, processing, completed, failed
    parsed_data: Optional[ParsedDocument] = None
    error_message: Optional[str] = None

    @property
    def is_parsed(self) -> bool:
        return self.parsing_status == "completed" and self.parsed_data is not None
