"""
RAG service with ChromaDB and RAGAS evaluation.
"""
import asyncio
import logging
from typing import List, Dict, Any
import chromadb
from chromadb.config import Settings as ChromaSettings
from langchain_openai import OpenAIEmbeddings
from langchain_community.vectorstores import Chroma
from langchain.text_splitter import RecursiveCharacterTextSplitter
from langchain_core.documents import Document

from app.config import settings

logger = logging.getLogger(__name__)

try:
    from ragas import evaluate
    from ragas.metrics import (
        faithfulness,
        answer_relevancy,
        context_precision,
        context_recall
    )
    RAGAS_AVAILABLE = True
except ImportError:
    RAGAS_AVAILABLE = False
    logger.warning("RAGAS not installed. RAG evaluation will use mock metrics.")


class RAGService:
    """Service for managing RAG operations with ChromaDB."""
    
    def __init__(self):
        """Initialize the RAG service."""
        self.embeddings = OpenAIEmbeddings(
            model=settings.embedding_model,
            api_key=settings.openai_api_key,
            base_url=settings.embedding_base_url
        )
        
        # Initialize ChromaDB
        self.chroma_client = chromadb.PersistentClient(
            path=settings.vector_db_path,
            settings=ChromaSettings(anonymized_telemetry=False)
        )
        
        # Initialize vector store
        self.vector_store = Chroma(
            client=self.chroma_client,
            collection_name=settings.vector_db_collection,
            embedding_function=self.embeddings
        )
        
        # Text splitter for chunking
        self.text_splitter = RecursiveCharacterTextSplitter(
            chunk_size=settings.chunk_size,
            chunk_overlap=settings.chunk_overlap,
            separators=["\n\n", "\n", " ", ""]
        )
        
        logger.info("RAG service initialized with ChromaDB")
    
    async def add_document(self, content: str, metadata: Dict[str, Any] = None) -> str:
        """
        Add a document to the vector store.
        
        Args:
            content: Document content
            metadata: Optional document metadata
            
        Returns:
            Document ID
        """
        try:
            # Split text into chunks
            chunks = self.text_splitter.split_text(content)
            
            # Create documents with metadata
            documents = [
                Document(page_content=chunk, metadata=metadata or {})
                for chunk in chunks
            ]
            
            # Add to vector store (blocking — offload to thread)
            ids = await asyncio.to_thread(self.vector_store.add_documents, documents)
            
            logger.info(f"Added document with {len(chunks)} chunks")
            return ids[0] if ids else None
            
        except Exception as e:
            logger.error(f"Error adding document: {str(e)}")
            raise
    
    async def search(self, query: str, top_k: int = None) -> List[Dict[str, Any]]:
        """
        Search for relevant documents.
        
        Args:
            query: Search query
            top_k: Number of results to return
            
        Returns:
            List of relevant documents with scores
        """
        try:
            k = top_k or settings.top_k_results
            results = await asyncio.to_thread(
                self.vector_store.similarity_search_with_score, query, k=k
            )
            
            return [
                {
                    "content": doc.page_content,
                    "metadata": doc.metadata,
                    "score": float(score)
                }
                for doc, score in results
            ]
        except Exception as e:
            logger.error(f"Error searching documents: {str(e)}")
            raise
    
    async def retrieve_context(self, query: str, top_k: int = None) -> str:
        """
        Retrieve context for a query.
        
        Args:
            query: Search query
            top_k: Number of results to return
            
        Returns:
            Combined context from retrieved documents
        """
        results = await self.search(query, top_k)
        context = "\n\n".join([result["content"] for result in results])
        return context
    
    async def evaluate_rag(
        self,
        questions: List[str],
        answers: List[str],
        contexts: List[List[str]],
        ground_truths: List[str] = None
    ) -> Dict[str, float]:
        """
        Evaluate RAG performance using RAGAS metrics.
        
        Args:
            questions: List of questions
            answers: List of generated answers
            contexts: List of retrieved contexts for each question
            ground_truths: Optional list of ground truth answers
            
        Returns:
            Dictionary of metric scores
        """
        try:
            if not RAGAS_AVAILABLE:
                logger.warning("RAGAS not available, returning mock metrics")
                return {
                    "faithfulness": 0.85,
                    "answer_relevancy": 0.82,
                    "context_precision": 0.88,
                    "context_recall": 0.79
                }
            
            # Prepare dataset for RAGAS
            dataset = {
                "question": questions,
                "answer": answers,
                "contexts": contexts,
            }
            
            if ground_truths:
                dataset["ground_truths"] = ground_truths
            
            # Select metrics based on available data
            metrics = [faithfulness, answer_relevancy, context_precision]
            if ground_truths:
                metrics.append(context_recall)
            
            # Evaluate
            result = evaluate(dataset, metrics=metrics)
            
            logger.info(f"RAG evaluation completed: {result}")
            return result
            
        except Exception as e:
            logger.error(f"Error evaluating RAG: {str(e)}")
            raise
    
    def get_collection_stats(self) -> Dict[str, Any]:
        """Get statistics about the vector store collection."""
        try:
            collection = self.chroma_client.get_collection(
                settings.vector_db_collection
            )
            return {
                "document_count": collection.count(),
                "collection_name": settings.vector_db_collection
            }
        except Exception as e:
            logger.error(f"Error getting collection stats: {str(e)}")
            return {"document_count": 0, "collection_name": settings.vector_db_collection}
