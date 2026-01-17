# project_path/backend/services/storage.py

import json
import uuid
from pathlib import Path
from datetime import datetime
from typing import List, Optional, Dict, Any
import aiofiles
from backend.config import config
from backend.models.document import DocumentRecord, ParsedDocument


class StorageService:
    """File storage and document record management service."""

    def __init__(self):
        # Use shared config
        self.uploads_dir = config.UPLOADS_DIR
        self.parsed_dir = config.PARSED_DIR
        self.metadata_file = config.STORAGE_DIR / "metadata.json"

        # Ensure directories exist on initialization
        self._ensure_directories()

    def _ensure_directories(self):
        """Ensure required directories exist, creating them if needed."""
        try:
            # Create directories synchronously
            self.uploads_dir.mkdir(parents=True, exist_ok=True)
            self.parsed_dir.mkdir(parents=True, exist_ok=True)
            config.STORAGE_DIR.mkdir(parents=True, exist_ok=True)

            print("[StorageService] Directories verified/created:")
            print(f"  - uploads: {self.uploads_dir}")
            print(f"  - parsed: {self.parsed_dir}")
            print(f"  - storage: {config.STORAGE_DIR}")
        except Exception as e:
            print(f"[StorageService] Directory creation failed: {e}")

    async def save_uploaded_file(
        self, file_content: bytes, filename: str, content_type: str
    ) -> DocumentRecord:
        """
        Save the uploaded file and create a DocumentRecord.

        Args:
            file_content: File bytes.
            filename: Original filename.
            content_type: MIME type.

        Returns:
            DocumentRecord: Created document record.
        """
        # Re-check directories before writing
        self._ensure_directories()

        # Generate unique ID
        doc_id = str(uuid.uuid4())
        file_extension = Path(filename).suffix
        stored_filename = f"{doc_id}{file_extension}"
        file_path = self.uploads_dir / stored_filename

        try:
            # Save file
            async with aiofiles.open(file_path, "wb") as f:
                await f.write(file_content)

            print(f"[StorageService] File saved: {file_path}")

        except Exception as e:
            print(f"[StorageService] File save failed: {e}")
            # Retry after re-ensuring directories
            self._ensure_directories()
            async with aiofiles.open(file_path, "wb") as f:
                await f.write(file_content)

        # Create DocumentRecord
        record = DocumentRecord(
            id=doc_id,
            filename=stored_filename,
            original_filename=filename,
            file_path=str(file_path),
            file_size=len(file_content),
            content_type=content_type,
            upload_time=datetime.now(),
            parsing_status="pending",
        )

        # Save metadata
        await self._save_metadata(record)

        return record

    async def save_parsed_data(self, doc_id: str, parsed_data: ParsedDocument) -> bool:
        """
        Save parsed document data.

        Args:
            doc_id: Document ID.
            parsed_data: Parsed document data.

        Returns:
            bool: True if saved successfully.
        """
        try:
            # Ensure directories exist
            self._ensure_directories()

            # Save parsed result as JSON
            parsed_file_path = self.parsed_dir / f"{doc_id}.json"
            async with aiofiles.open(parsed_file_path, "w", encoding="utf-8") as f:
                await f.write(parsed_data.model_dump_json(indent=2))

            print(f"[StorageService] Parsed data saved: {parsed_file_path}")

            # Update metadata
            record = await self.get_document_record(doc_id)
            if record:
                record.parsed_data = parsed_data
                record.parsing_status = "completed"
                await self._save_metadata(record)
                return True

            return False

        except Exception as e:
            print(f"[StorageService] Parsed data save failed: {e}")
            # Update error status
            record = await self.get_document_record(doc_id)
            if record:
                record.parsing_status = "failed"
                record.error_message = str(e)
                await self._save_metadata(record)
            raise e

    async def get_document_record(self, doc_id: str) -> Optional[DocumentRecord]:
        """
        Retrieve a document record.

        Args:
            doc_id: Document ID.

        Returns:
            Optional[DocumentRecord]: Document record if found.
        """
        metadata = await self._load_metadata()
        record_data = metadata.get(doc_id)

        if not record_data:
            return None

        record = DocumentRecord(**record_data)

        # Load parsed data when completed
        if record.parsing_status == "completed":
            parsed_data = await self._load_parsed_data(doc_id)
            if parsed_data:
                record.parsed_data = parsed_data

        return record

    async def get_all_documents(self) -> List[DocumentRecord]:
        """
        Retrieve all document records.

        Returns:
            List[DocumentRecord]: Document record list.
        """
        metadata = await self._load_metadata()
        records = []

        for doc_id in metadata.keys():
            record = await self.get_document_record(doc_id)
            if record:
                records.append(record)

        # Sort by upload time (descending)
        return sorted(records, key=lambda x: x.upload_time, reverse=True)

    async def delete_document(self, doc_id: str) -> bool:
        """
        Delete a document and related files.

        Args:
            doc_id: Document ID.

        Returns:
            bool: True if deleted successfully.
        """
        try:
            record = await self.get_document_record(doc_id)
            if not record:
                return False

            # Delete uploaded file
            file_path = Path(record.file_path)
            if file_path.exists():
                file_path.unlink()

            # Delete parsed file
            parsed_file_path = self.parsed_dir / f"{doc_id}.json"
            if parsed_file_path.exists():
                parsed_file_path.unlink()

            # Remove metadata
            metadata = await self._load_metadata()
            if doc_id in metadata:
                del metadata[doc_id]
                await self._save_metadata_dict(metadata)

            return True

        except Exception:
            return False

    async def _load_metadata(self) -> Dict[str, Any]:
        """Load metadata file."""
        # Ensure metadata directory exists
        self.metadata_file.parent.mkdir(parents=True, exist_ok=True)

        if not self.metadata_file.exists():
            return {}

        try:
            async with aiofiles.open(self.metadata_file, "r", encoding="utf-8") as f:
                content = await f.read()
                return json.loads(content)
        except Exception:
            return {}

    async def _save_metadata(self, record: DocumentRecord):
        """Save metadata for a single document record."""
        metadata = await self._load_metadata()
        # parsed_data is stored separately, so exclude it from metadata
        record_dict = record.model_dump()
        record_dict.pop("parsed_data", None)
        metadata[record.id] = record_dict
        await self._save_metadata_dict(metadata)

    async def _save_metadata_dict(self, metadata: Dict[str, Any]):
        """Save metadata dictionary to file."""
        # Ensure metadata directory exists
        self.metadata_file.parent.mkdir(parents=True, exist_ok=True)

        async with aiofiles.open(self.metadata_file, "w", encoding="utf-8") as f:
            await f.write(json.dumps(metadata, indent=2, default=str))

    async def _load_parsed_data(self, doc_id: str) -> Optional[ParsedDocument]:
        """Load parsed document data."""
        parsed_file_path = self.parsed_dir / f"{doc_id}.json"

        if not parsed_file_path.exists():
            return None

        try:
            async with aiofiles.open(parsed_file_path, "r", encoding="utf-8") as f:
                content = await f.read()
                data = json.loads(content)
                return ParsedDocument(**data)
        except Exception:
            return None
