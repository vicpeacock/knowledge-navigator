"""
Advanced Semantic Search Service - Enhanced search with re-ranking and hybrid search
"""
from typing import List, Dict, Any, Optional, Tuple
from sqlalchemy.ext.asyncio import AsyncSession
from uuid import UUID
from datetime import datetime, timezone, timedelta
import logging
import re

from app.core.memory_manager import MemoryManager
from app.services.embedding_service import EmbeddingService

logger = logging.getLogger(__name__)


class AdvancedSearch:
    """Service for advanced semantic search with re-ranking and hybrid search"""
    
    def __init__(self, memory_manager: MemoryManager):
        self.memory_manager = memory_manager
        self.embedding_service = EmbeddingService()
    
    async def hybrid_search(
        self,
        query: str,
        n_results: int = 5,
        semantic_weight: float = 0.7,
        keyword_weight: float = 0.3,
        min_importance: Optional[float] = None,
        content_type: Optional[str] = None,
        date_from: Optional[datetime] = None,
        date_to: Optional[datetime] = None,
    ) -> List[Dict[str, Any]]:
        """
        Perform hybrid search combining semantic and keyword matching.
        
        Args:
            query: Search query
            n_results: Number of results to return
            semantic_weight: Weight for semantic similarity (0.0-1.0)
            keyword_weight: Weight for keyword matching (0.0-1.0)
            min_importance: Minimum importance score filter
            content_type: Filter by content type (e.g., "fact", "preference", "email", "web")
            date_from: Filter by date (from)
            date_to: Filter by date (to)
        
        Returns:
            List of search results with scores and metadata
        """
        try:
            # Semantic search
            semantic_results = await self.memory_manager.retrieve_long_term_memory(
                query=query,
                n_results=n_results * 2,  # Get more for re-ranking
                min_importance=min_importance,
            )
            
            # Keyword search
            keyword_results = self._keyword_search(query, semantic_results)
            
            # Combine and re-rank
            combined_results = self._combine_and_rerank(
                semantic_results,
                keyword_results,
                query,
                semantic_weight,
                keyword_weight,
            )
            
            # Apply filters
            filtered_results = self._apply_filters(
                combined_results,
                content_type=content_type,
                date_from=date_from,
                date_to=date_to,
            )
            
            # Return top n_results
            return filtered_results[:n_results]
            
        except Exception as e:
            logger.error(f"Error in hybrid search: {e}", exc_info=True)
            return []
    
    def _keyword_search(
        self,
        query: str,
        candidate_docs: List[str],
    ) -> List[Tuple[str, float]]:
        """
        Perform keyword matching on candidate documents.
        Returns list of (document, score) tuples.
        """
        query_keywords = set(re.findall(r'\w+', query.lower()))
        keyword_scores = []
        
        for doc in candidate_docs:
            doc_keywords = set(re.findall(r'\w+', doc.lower()))
            
            # Calculate Jaccard similarity
            intersection = query_keywords.intersection(doc_keywords)
            union = query_keywords.union(doc_keywords)
            
            if len(union) > 0:
                score = len(intersection) / len(union)
            else:
                score = 0.0
            
            keyword_scores.append((doc, score))
        
        # Sort by score descending
        keyword_scores.sort(key=lambda x: x[1], reverse=True)
        return keyword_scores
    
    def _combine_and_rerank(
        self,
        semantic_results: List[str],
        keyword_results: List[Tuple[str, float]],
        query: str,
        semantic_weight: float,
        keyword_weight: float,
    ) -> List[Dict[str, Any]]:
        """
        Combine semantic and keyword results and re-rank.
        """
        # Create a map of document -> keyword score
        keyword_scores_map = {doc: score for doc, score in keyword_results}
        
        # Calculate semantic scores (normalized position-based)
        semantic_scores_map = {}
        for i, doc in enumerate(semantic_results):
            # Higher position = higher score (inverse rank)
            semantic_scores_map[doc] = 1.0 / (i + 1)
        
        # Combine all unique documents
        all_docs = set(semantic_results) | set([doc for doc, _ in keyword_results])
        
        combined = []
        for doc in all_docs:
            semantic_score = semantic_scores_map.get(doc, 0.0)
            keyword_score = keyword_scores_map.get(doc, 0.0)
            
            # Combined score
            combined_score = (semantic_score * semantic_weight) + (keyword_score * keyword_weight)
            
            # Extract metadata from document
            content_type = self._extract_content_type(doc)
            
            combined.append({
                "content": doc,
                "semantic_score": semantic_score,
                "keyword_score": keyword_score,
                "combined_score": combined_score,
                "content_type": content_type,
            })
        
        # Sort by combined score
        combined.sort(key=lambda x: x["combined_score"], reverse=True)
        return combined
    
    def _extract_content_type(self, content: str) -> str:
        """Extract content type from document content"""
        content_lower = content.lower()
        
        if content.startswith("[FACT]"):
            return "fact"
        elif content.startswith("[PREFERENCE]"):
            return "preference"
        elif content.startswith("[PERSONAL_INFO]"):
            return "personal_info"
        elif content.startswith("[CONTACT]"):
            return "contact"
        elif content.startswith("[PROJECT]"):
            return "project"
        elif "email from:" in content_lower or "subject:" in content_lower:
            return "email"
        elif "web search result:" in content_lower or "url:" in content_lower:
            return "web"
        else:
            return "general"
    
    def _apply_filters(
        self,
        results: List[Dict[str, Any]],
        content_type: Optional[str] = None,
        date_from: Optional[datetime] = None,
        date_to: Optional[datetime] = None,
    ) -> List[Dict[str, Any]]:
        """Apply filters to search results"""
        filtered = results
        
        if content_type:
            filtered = [r for r in filtered if r.get("content_type") == content_type]
        
        # Date filtering would require metadata from database
        # For now, we'll skip date filtering as it requires additional queries
        # This can be enhanced later by storing dates in ChromaDB metadata
        
        return filtered
    
    async def cross_session_search(
        self,
        query: str,
        session_ids: Optional[List[UUID]] = None,
        n_results: int = 5,
    ) -> List[Dict[str, Any]]:
        """
        Search across multiple sessions.
        If session_ids is None, searches all sessions.
        """
        try:
            # Get results from long-term memory (already cross-session)
            results = await self.memory_manager.retrieve_long_term_memory(
                query=query,
                n_results=n_results,
            )
            
            # Format results
            formatted_results = []
            for content in results:
                formatted_results.append({
                    "content": content,
                    "content_type": self._extract_content_type(content),
                })
            
            return formatted_results
            
        except Exception as e:
            logger.error(f"Error in cross-session search: {e}", exc_info=True)
            return []
    
    async def suggest_related(
        self,
        query: str,
        n_suggestions: int = 3,
    ) -> List[str]:
        """
        Suggest related queries based on search results.
        """
        try:
            # Get search results
            results = await self.hybrid_search(query, n_results=5)
            
            if not results:
                return []
            
            # Extract keywords from results
            all_keywords = set()
            for result in results:
                content = result.get("content", "")
                keywords = re.findall(r'\b\w{4,}\b', content.lower())  # Words with 4+ chars
                all_keywords.update(keywords)
            
            # Remove common stop words
            stop_words = {
                "the", "and", "or", "but", "in", "on", "at", "to", "for",
                "of", "with", "by", "from", "this", "that", "these", "those",
                "is", "are", "was", "were", "be", "been", "being", "have",
                "has", "had", "do", "does", "did", "will", "would", "could",
                "should", "may", "might", "must", "can", "cannot",
            }
            all_keywords = all_keywords - stop_words
            
            # Return top keywords as suggestions
            suggestions = list(all_keywords)[:n_suggestions]
            return suggestions
            
        except Exception as e:
            logger.error(f"Error generating suggestions: {e}", exc_info=True)
            return []

