"""
Metrics API endpoints for RAG evaluation.
"""
from fastapi import APIRouter, HTTPException, Request
from app.models import MetricsResponse, RAGMetrics
from datetime import datetime, timezone
import logging

logger = logging.getLogger(__name__)
router = APIRouter()

# Mock metrics storage (in production, use a database)
_metrics_store = {
    "queries_processed": 0,
    "total_response_time": 0.0,
    "last_metrics": None
}


@router.get("/", response_model=MetricsResponse)
async def get_metrics(app_request: Request):
    """
    Get current RAG evaluation metrics.
    
    Returns:
        Current metrics and statistics
    """
    try:
        # Calculate average response time
        avg_response_time = (
            _metrics_store["total_response_time"] / _metrics_store["queries_processed"]
            if _metrics_store["queries_processed"] > 0
            else 0.0
        )
        
        # Get or create default metrics
        metrics = _metrics_store.get("last_metrics") or RAGMetrics(
            faithfulness=0.85,
            answer_relevancy=0.82,
            context_precision=0.88,
            context_recall=0.79,
            timestamp=datetime.now(timezone.utc)
        )
        
        return MetricsResponse(
            metrics=metrics,
            queries_processed=_metrics_store["queries_processed"],
            average_response_time=avg_response_time
        )
        
    except Exception as e:
        logger.error(f"Error getting metrics: {str(e)}")
        raise HTTPException(status_code=500, detail="Failed to retrieve metrics.")


@router.post("/evaluate")
async def evaluate_rag(app_request: Request):
    """
    Trigger RAG evaluation with RAGAS.
    
    This endpoint would typically be called periodically or on-demand
    to evaluate the RAG system's performance.
    """
    try:
        rag_service = app_request.app.state.rag_service
        
        # In a real system, you would collect actual queries, answers, and contexts
        # For demonstration, we'll use mock data
        questions = ["What is the capital of France?"]
        answers = ["The capital of France is Paris."]
        contexts = [["Paris is the capital and largest city of France."]]
        
        # Mock result for demonstration
        result = {
            "faithfulness": 0.85,
            "answer_relevancy": 0.82,
            "context_precision": 0.88,
            "context_recall": 0.79
        }
        
        # Store metrics and increment counter
        _metrics_store["queries_processed"] += 1
        _metrics_store["last_metrics"] = RAGMetrics(
            **result,
            timestamp=datetime.now(timezone.utc)
        )
        
        return {
            "status": "success",
            "message": "RAG evaluation completed",
            "metrics": result
        }
        
    except Exception as e:
        logger.error(f"Error evaluating RAG: {str(e)}")
        raise HTTPException(status_code=500, detail="Failed to evaluate RAG.")
