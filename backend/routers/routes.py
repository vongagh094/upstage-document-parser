# project_path/backend/routers/routes.py

from fastapi import APIRouter, UploadFile, File, HTTPException, Depends, Query
from typing import List, Optional
from collections import defaultdict
from backend.services.file_processor import FileProcessor
from backend.models.document import DocumentRecord


router = APIRouter()

# FileProcessor singleton instance
# Reused across requests to avoid repeated initialization.
_file_processor_instance = None


def get_file_processor():
    """
    Return a singleton FileProcessor instance.

    Returns:
        FileProcessor: File processing service instance.
    """
    global _file_processor_instance
    if _file_processor_instance is None:
        _file_processor_instance = FileProcessor()
    return _file_processor_instance


@router.post("/upload", response_model=DocumentRecord)
async def upload_file(
    file: UploadFile = File(...),
    processor: FileProcessor = Depends(get_file_processor),
):
    """
    Upload a file and start parsing.
    - Uses Upstage API to perform OCR and text extraction
    - Extracts image text automatically
    - Parsing runs asynchronously in the background

    Args:
        file: File to upload (PDF, DOCX, PPTX, image, etc.)

    Returns:
        DocumentRecord: Created document record (parsing runs in background)
    """
    try:
        file_content = await file.read()

        is_valid, error_message = processor.validate_file(
            file.filename, len(file_content)
        )
        if not is_valid:
            raise HTTPException(status_code=400, detail=error_message)

        # Simplified options: only image extraction is meaningful here
        options = {"extract_images": True}

        record = await processor.process_file(
            file_content=file_content,
            filename=file.filename,
            content_type=file.content_type or "application/octet-stream",
            enhanced_options=options,
        )

        return record
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to process document: {str(e)}")


@router.delete("/documents/{doc_id}")
async def delete_document(
    doc_id: str,
    processor: FileProcessor = Depends(get_file_processor),
):
    """
    Delete a document.
    - Removes uploaded file
    - Removes parsed results
    - Removes metadata entry

    Args:
        doc_id: Document ID to delete.

    Returns:
        message: Deletion result message.
    """
    try:
        success = await processor.delete_document(doc_id)
        if not success:
            raise HTTPException(status_code=404, detail="Document not found.")
        return {"message": "Document deleted successfully."}
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to delete document: {str(e)}")


@router.get("/analytics/summary")
async def get_analytics_summary(
    processor: FileProcessor = Depends(get_file_processor),
):
    """Get system analytics summary."""
    try:
        all_docs = await processor.get_all_documents()

        summary = defaultdict(int)
        category_stats = defaultdict(int)
        status_counts = defaultdict(int)

        for doc in all_docs:
            summary["total_documents"] += 1
            status_counts[doc.parsing_status] += 1

            if doc.is_parsed:
                summary["completed_documents"] += 1
                elements = doc.parsed_data.elements
                summary["total_elements"] += len(elements)

                for element in elements:
                    category_stats[element.category] += 1
                    if element.base64_encoding:
                        summary["total_images"] += 1
                    if hasattr(element, "_ocr_enhanced") and element._ocr_enhanced:
                        summary["ocr_enhanced_elements"] += 1

        return {
            "summary": {
                **summary,
                "success_rate": (
                    summary["completed_documents"] / summary["total_documents"] * 100
                )
                if summary["total_documents"] > 0
                else 0,
            },
            "category_distribution": category_stats,
            "processing_status": status_counts,
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to retrieve analytics: {str(e)}")


@router.get("/documents", response_model=List[DocumentRecord])
async def get_documents(
    status: Optional[str] = Query(None, description="Status filter"),
    has_ocr_enhancement: Optional[bool] = Query(
        None, description="Filter documents with OCR"
    ),
    limit: int = Query(50, ge=1, le=100, description="Result limit"),
    processor: FileProcessor = Depends(get_file_processor),
):
    """Get all documents with filtering support."""
    try:
        documents = await processor.get_all_documents()

        if status:
            documents = [doc for doc in documents if doc.parsing_status == status]

        if has_ocr_enhancement is not None:
            filtered_docs = []
            for doc in documents:
                if doc.parsing_status == "completed" and doc.parsed_data:
                    has_ocr = any(
                        hasattr(elem, "_ocr_enhanced") and elem._ocr_enhanced
                        for elem in doc.parsed_data.elements
                    )
                    if has_ocr_enhancement == has_ocr:
                        filtered_docs.append(doc)
                elif not has_ocr_enhancement:
                    filtered_docs.append(doc)
            documents = filtered_docs

        documents = documents[:limit]

        return documents
    except Exception as e:
        raise HTTPException(
            status_code=500, detail=f"Failed to retrieve document list: {str(e)}"
        )


@router.get("/documents/{doc_id}", response_model=DocumentRecord)
async def get_document(
    doc_id: str,
    processor: FileProcessor = Depends(get_file_processor),
):
    """Get a specific document."""
    try:
        record = await processor.get_document(doc_id)
        if not record:
            raise HTTPException(status_code=404, detail="Document not found.")
        return record
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to get document: {str(e)}")
