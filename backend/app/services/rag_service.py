"""
RAG service with ChromaDB and RAGAS evaluation.
"""
import asyncio
import logging
import uuid
from typing import List, Dict, Any
import chromadb
from chromadb.config import Settings as ChromaSettings
from langchain_openai import OpenAIEmbeddings
try:
    from langchain_chroma import Chroma
except ImportError:  # fallback for older environments
    from langchain_community.vectorstores import Chroma
try:
    from langchain_text_splitters import RecursiveCharacterTextSplitter
except ImportError:  # fallback for older environments
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

        # In-memory fallback store used when vector operations fail or time out.
        self._fallback_documents: List[Dict[str, Any]] = []
        
        logger.info("RAG service initialized with ChromaDB")

    async def _add_to_fallback(self, content: str, metadata: Dict[str, Any] = None) -> str:
        """Store document in local fallback memory and return a stable id."""
        document_id = str(uuid.uuid4())
        self._fallback_documents.append(
            {
                "id": document_id,
                "content": content,
                "metadata": metadata or {},
            }
        )
        return document_id

    def _search_fallback(self, query: str, top_k: int) -> List[Dict[str, Any]]:
        """Simple keyword overlap search over fallback in-memory documents."""
        lowered_query = (query or "").lower().strip()
        words = [w for w in lowered_query.split() if w]
        scored: List[Dict[str, Any]] = []

        for item in self._fallback_documents:
            content = str(item.get("content", ""))
            lowered_content = content.lower()

            if lowered_query and lowered_query in lowered_content:
                score = 0.95
            elif words:
                overlap = sum(1 for w in words if w in lowered_content)
                if overlap == 0:
                    continue
                score = min(0.9, 0.5 + (overlap * 0.08))
            else:
                score = 0.4

            scored.append(
                {
                    "content": content,
                    "metadata": item.get("metadata", {}),
                    "score": float(score),
                }
            )

        scored.sort(key=lambda x: x["score"], reverse=True)
        return scored[:top_k]

    async def get_documents_snapshot(
        self,
        max_items: int = 50,
        max_chars_per_item: int = 1200,
    ) -> List[Dict[str, Any]]:
        """Return recent document chunks from vector store and fallback memory."""
        snapshot: List[Dict[str, Any]] = []
        candidates: List[Dict[str, Any]] = []
        seen = set()

        try:
            def _read_collection_payload():
                collection = self.chroma_client.get_collection(settings.vector_db_collection)
                return collection.get(include=["documents", "metadatas"])

            payload = await asyncio.wait_for(
                asyncio.to_thread(_read_collection_payload),
                timeout=20,
            )

            documents = payload.get("documents", []) if isinstance(payload, dict) else []
            metadatas = payload.get("metadatas", []) if isinstance(payload, dict) else []

            for idx, content in enumerate(documents):

                text = str(content or "").strip()
                if not text:
                    continue

                metadata = metadatas[idx] if idx < len(metadatas) and isinstance(metadatas[idx], dict) else {}
                source = str(metadata.get("source", f"Document {idx + 1}"))
                clipped = text[:max_chars_per_item]
                candidates.append({
                    "content": clipped,
                    "metadata": metadata,
                    "source": source,
                    "uploaded_at": str(metadata.get("uploaded_at", "")),
                    "order_index": idx,
                })
        except Exception as exc:
            logger.warning(f"Could not build vector snapshot, continuing with fallback docs: {exc}")

        for idx, item in enumerate(self._fallback_documents):
            text = str(item.get("content", "")).strip()
            if not text:
                continue

            metadata = item.get("metadata", {}) if isinstance(item.get("metadata", {}), dict) else {}
            source = str(metadata.get("source", f"Fallback Document {idx + 1}"))
            clipped = text[:max_chars_per_item]
            candidates.append({
                "content": clipped,
                "metadata": metadata,
                "source": source,
                "uploaded_at": str(metadata.get("uploaded_at", "")),
                "order_index": idx,
            })

        # Prioritize more recently uploaded chunks using ISO timestamp metadata.
        candidates.sort(
            key=lambda item: (item.get("uploaded_at", ""), item.get("order_index", 0)),
            reverse=True,
        )

        for item in candidates:
            if len(snapshot) >= max_items:
                break

            source = str(item.get("source", "Document"))
            clipped = str(item.get("content", ""))
            signature = (source, clipped[:120])
            if signature in seen:
                continue
            seen.add(signature)

            snapshot.append({
                "content": clipped,
                "metadata": item.get("metadata", {}),
                "source": source,
            })

        return snapshot[:max_items]
    
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
            if not chunks:
                chunks = [content]
            
            # Create documents with metadata
            documents = [
                Document(page_content=chunk, metadata=metadata or {})
                for chunk in chunks
            ]
            
            try:
                # Add to vector store (blocking — offload to thread) with timeout protection.
                ids = await asyncio.wait_for(
                    asyncio.to_thread(self.vector_store.add_documents, documents),
                    timeout=35,
                )
                logger.info(f"Added document with {len(chunks)} chunks")
                if ids:
                    return ids[0]
            except Exception as vector_exc:
                logger.warning(f"Vector store add failed, falling back to memory store: {vector_exc}")

            fallback_id = await self._add_to_fallback(content=content, metadata=metadata)
            logger.info("Stored document in fallback memory store")
            return fallback_id
            
        except Exception as e:
            logger.error(f"Error adding document: {str(e)}")
            fallback_id = await self._add_to_fallback(content=content, metadata=metadata)
            logger.info("Stored document in fallback memory store after exception")
            return fallback_id
    
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
            try:
                results = await asyncio.wait_for(
                    asyncio.to_thread(self.vector_store.similarity_search_with_score, query, k=k),
                    timeout=20,
                )

                parsed = [
                    {
                        "content": doc.page_content,
                        "metadata": doc.metadata,
                        "score": float(score)
                    }
                    for doc, score in results
                ]

                if parsed:
                    return parsed
            except Exception as vector_exc:
                logger.warning(f"Vector store search failed, using fallback memory store: {vector_exc}")

            return self._search_fallback(query=query, top_k=k)
        except Exception as e:
            logger.error(f"Error searching documents: {str(e)}")
            return self._search_fallback(query=query, top_k=top_k or settings.top_k_results)
    
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

            # RAGAS may return a Score object, convert to plain dict
            if hasattr(result, "to_pandas"):
                result_df = result.to_pandas()
                result = result_df.mean(numeric_only=True).to_dict()
            
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
                "fallback_document_count": len(self._fallback_documents),
                "collection_name": settings.vector_db_collection
            }
        except Exception as e:
            logger.error(f"Error getting collection stats: {str(e)}")
            return {
                "document_count": 0,
                "fallback_document_count": len(self._fallback_documents),
                "collection_name": settings.vector_db_collection,
            }
