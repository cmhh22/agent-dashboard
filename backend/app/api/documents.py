"""
Documents API endpoints.
"""
import io
from fastapi import APIRouter, HTTPException, Request, UploadFile, File
from app.models import DocumentUpload, DocumentResponse
import logging
from pypdf import PdfReader
from docx import Document as DocxDocument

logger = logging.getLogger(__name__)
router = APIRouter()

# File upload limits
_MAX_FILE_SIZE = 10 * 1024 * 1024  # 10 MB
_ALLOWED_CONTENT_TYPES = {
    "text/plain", "text/markdown", "text/csv", "text/html",
    "application/json", "application/pdf",
    "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
    "application/msword",
}
_ALLOWED_EXTENSIONS = {
    ".txt", ".md", ".csv", ".html", ".json", ".pdf", ".docx", ".doc"
}


def _get_extension(filename: str | None) -> str:
    if not filename or "." not in filename:
        return ""
    return "." + filename.rsplit(".", 1)[1].lower()


def _extract_text_from_pdf(content: bytes) -> str:
    reader = PdfReader(io.BytesIO(content))
    parts = []
    for page in reader.pages:
        page_text = page.extract_text() or ""
        if page_text.strip():
            parts.append(page_text.strip())
    return "\n\n".join(parts).strip()


def _extract_text_from_docx(content: bytes) -> str:
    document = DocxDocument(io.BytesIO(content))
    parts = [paragraph.text.strip() for paragraph in document.paragraphs if paragraph.text.strip()]
    return "\n".join(parts).strip()


def _extract_text_content(file: UploadFile, content: bytes) -> str:
    filename = (file.filename or "").lower()
    content_type = (file.content_type or "").lower()
    extension = _get_extension(filename)

    if content_type == "application/pdf" or extension == ".pdf":
        return _extract_text_from_pdf(content)

    if (
        content_type == "application/vnd.openxmlformats-officedocument.wordprocessingml.document"
        or extension == ".docx"
    ):
        return _extract_text_from_docx(content)

    if content_type == "application/msword" or extension == ".doc":
        raise HTTPException(
            status_code=400,
            detail="Legacy .doc files are not supported. Please upload .docx or .pdf."
        )

    try:
        return content.decode("utf-8")
    except UnicodeDecodeError:
        try:
            return content.decode("latin-1")
        except UnicodeDecodeError:
            raise HTTPException(status_code=400, detail="File content could not be decoded.")


@router.post("/upload", response_model=DocumentResponse)
async def upload_document(request: DocumentUpload, app_request: Request):
    """
    Upload a document to the RAG vector store.
    
    Args:
        request: Document content and metadata
        app_request: FastAPI request object
        
    Returns:
        Document upload response
    """
    try:
        rag_service = app_request.app.state.rag_service
        
        # Add document to vector store
        document_id = await rag_service.add_document(
            content=request.content,
            metadata=request.metadata
        )
        
        return DocumentResponse(
            document_id=document_id,
            status="success",
            message="Document uploaded successfully"
        )
        
    except Exception as e:
        logger.error(f"Error uploading document: {str(e)}")
        raise HTTPException(status_code=500, detail="Failed to upload document.")


@router.post("/upload-file", response_model=DocumentResponse)
async def upload_file(app_request: Request, file: UploadFile = File(...)):
    """
    Upload a file to the RAG vector store.
    
    Args:
        app_request: FastAPI request object
        file: Uploaded file
        
    Returns:
        Document upload response
    """
    try:
        extension = _get_extension(file.filename)

        # Validate content type
        if (
            file.content_type
            and file.content_type not in _ALLOWED_CONTENT_TYPES
            and extension not in _ALLOWED_EXTENSIONS
        ):
            raise HTTPException(
                status_code=400,
                detail=f"Unsupported file type: {file.content_type}. "
                       f"Allowed extensions: {', '.join(sorted(_ALLOWED_EXTENSIONS))}"
            )
        
        rag_service = app_request.app.state.rag_service
        
        # Read file content with size limit
        content = await file.read()
        if len(content) > _MAX_FILE_SIZE:
            raise HTTPException(
                status_code=400,
                detail=f"File too large. Maximum size: {_MAX_FILE_SIZE // (1024*1024)} MB"
            )

        text_content = _extract_text_content(file, content)
        if not text_content.strip():
            raise HTTPException(status_code=400, detail="No readable text found in file.")
        
        # Add document with metadata
        metadata = {
            "source": file.filename,
            "content_type": file.content_type
        }
        
        document_id = await rag_service.add_document(
            content=text_content,
            metadata=metadata
        )
        
        return DocumentResponse(
            document_id=document_id,
            status="success",
            message=f"File '{file.filename}' uploaded successfully"
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error uploading file: {str(e)}")
        raise HTTPException(status_code=500, detail="Failed to upload file.")


@router.get("/stats")
async def get_stats(app_request: Request):
    """Get statistics about the document collection."""
    try:
        rag_service = app_request.app.state.rag_service
        stats = rag_service.get_collection_stats()
        return stats
    except Exception as e:
        logger.error(f"Error getting stats: {str(e)}")
        raise HTTPException(status_code=500, detail="Failed to retrieve stats.")
