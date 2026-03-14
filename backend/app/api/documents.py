"""
Documents API endpoints.
"""
from fastapi import APIRouter, HTTPException, Request, UploadFile, File
from app.models import DocumentUpload, DocumentResponse
import logging

logger = logging.getLogger(__name__)
router = APIRouter()

# File upload limits
_MAX_FILE_SIZE = 10 * 1024 * 1024  # 10 MB
_ALLOWED_CONTENT_TYPES = {
    "text/plain", "text/markdown", "text/csv", "text/html",
    "application/json", "application/pdf",
}


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
        # Validate content type
        if file.content_type and file.content_type not in _ALLOWED_CONTENT_TYPES:
            raise HTTPException(
                status_code=400,
                detail=f"Unsupported file type: {file.content_type}. "
                       f"Allowed: {', '.join(sorted(_ALLOWED_CONTENT_TYPES))}"
            )
        
        rag_service = app_request.app.state.rag_service
        
        # Read file content with size limit
        content = await file.read()
        if len(content) > _MAX_FILE_SIZE:
            raise HTTPException(
                status_code=400,
                detail=f"File too large. Maximum size: {_MAX_FILE_SIZE // (1024*1024)} MB"
            )
        
        try:
            text_content = content.decode('utf-8')
        except UnicodeDecodeError:
            raise HTTPException(status_code=400, detail="File must be UTF-8 encoded text.")
        
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
