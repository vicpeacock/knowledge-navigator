"""
Memory Consolidator Service - Consolidates and summarizes long-term memory
"""
from typing import List, Dict, Any, Optional
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, delete
from uuid import UUID
from datetime import datetime, timezone, timedelta
import logging
import numpy as np

from app.core.memory_manager import MemoryManager
from app.core.ollama_client import OllamaClient
from app.core.dependencies import get_ollama_client
from app.models.database import MemoryLong
from app.services.embedding_service import EmbeddingService

logger = logging.getLogger(__name__)


class MemoryConsolidator:
    """Service for consolidating and summarizing long-term memory"""
    
    def __init__(
        self,
        memory_manager: MemoryManager,
        ollama_client: Optional[OllamaClient] = None,
    ):
        self.memory_manager = memory_manager
        # Use get_ollama_client() which returns OllamaClient or GeminiClient based on LLM_PROVIDER
        self.ollama_client = ollama_client or get_ollama_client()
        self.embedding_service = EmbeddingService()
    
    async def consolidate_duplicates(
        self,
        db: AsyncSession,
        similarity_threshold: float = 0.85,
    ) -> Dict[str, Any]:
        """
        Find and merge duplicate or very similar memories.
        Returns statistics about consolidation.
        """
        try:
            # Get all long-term memories from database
            result = await db.execute(select(MemoryLong))
            all_memories = result.scalars().all()
            
            if len(all_memories) < 2:
                return {"merged": 0, "kept": len(all_memories), "removed": 0}
            
            # Group similar memories
            to_merge = []
            processed = set()
            
            for i, mem1 in enumerate(all_memories):
                if i in processed:
                    continue
                
                similar_group = [mem1]
                
                for j, mem2 in enumerate(all_memories[i+1:], start=i+1):
                    if j in processed:
                        continue
                    
                    # Calculate similarity
                    similarity = self._calculate_similarity(mem1.content, mem2.content)
                    
                    if similarity >= similarity_threshold:
                        similar_group.append(mem2)
                        processed.add(j)
                
                if len(similar_group) > 1:
                    to_merge.append(similar_group)
                    processed.add(i)
            
            # Merge groups
            merged_count = 0
            removed_count = 0
            
            for group in to_merge:
                # Keep the one with highest importance score
                group.sort(key=lambda m: m.importance_score, reverse=True)
                kept = group[0]
                to_remove = group[1:]
                
                # Merge learned_from_sessions
                all_sessions = set(kept.learned_from_sessions or [])
                for mem in to_remove:
                    all_sessions.update(mem.learned_from_sessions or [])
                
                kept.learned_from_sessions = list(all_sessions)
                
                # Update content if needed (can be enhanced with LLM summarization)
                # For now, just keep the most important one
                
                # Remove duplicates from ChromaDB and database
                for mem in to_remove:
                    try:
                        # Remove from ChromaDB
                        self.memory_manager.long_term_memory_collection.delete(
                            ids=[mem.embedding_id]
                        )
                        
                        # Remove from database
                        await db.delete(mem)
                        
                        removed_count += 1
                    except Exception as e:
                        logger.warning(f"Error removing duplicate memory {mem.id}: {e}")
                
                merged_count += 1
            
            await db.commit()
            
            logger.info(f"Consolidated {merged_count} groups, removed {removed_count} duplicates")
            
            return {
                "merged": merged_count,
                "kept": len(all_memories) - removed_count,
                "removed": removed_count,
            }
            
        except Exception as e:
            logger.error(f"Error consolidating duplicates: {e}", exc_info=True)
            await db.rollback()
            return {"merged": 0, "kept": 0, "removed": 0, "error": str(e)}
    
    def _calculate_similarity(self, content1: str, content2: str) -> float:
        """Calculate cosine similarity between two content strings"""
        try:
            emb1 = self.embedding_service.generate_embedding(content1)
            emb2 = self.embedding_service.generate_embedding(content2)
            
            # Cosine similarity
            similarity = np.dot(emb1, emb2) / (
                np.linalg.norm(emb1) * np.linalg.norm(emb2)
            )
            
            return float(similarity)
            
        except Exception as e:
            logger.warning(f"Error calculating similarity: {e}")
            return 0.0
    
    async def summarize_old_memories(
        self,
        db: AsyncSession,
        days_old: int = 90,
        max_memories: int = 50,
    ) -> Dict[str, Any]:
        """
        Summarize old memories to reduce storage while preserving knowledge.
        Returns statistics about summarization.
        """
        try:
            # Get old memories
            cutoff_date = datetime.now(timezone.utc) - timedelta(days=days_old)
            
            result = await db.execute(
                select(MemoryLong)
                .where(MemoryLong.created_at < cutoff_date)
                .order_by(MemoryLong.importance_score.desc())
                .limit(max_memories)
            )
            old_memories = result.scalars().all()
            
            if not old_memories:
                return {"summarized": 0, "kept": 0}
            
            # Group by content type or topic (simple grouping by first word)
            groups = {}
            for mem in old_memories:
                # Extract type/topic from content
                content_type = self._extract_content_type(mem.content)
                if content_type not in groups:
                    groups[content_type] = []
                groups[content_type].append(mem)
            
            summarized_count = 0
            
            # Summarize each group
            for content_type, memories in groups.items():
                if len(memories) < 3:  # Don't summarize small groups
                    continue
                
                # Create summary using LLM
                summary = await self._create_summary(memories, content_type)
                
                if summary:
                    # Create new consolidated memory
                    all_sessions = set()
                    max_importance = 0.0
                    for mem in memories:
                        all_sessions.update(mem.learned_from_sessions or [])
                        max_importance = max(max_importance, mem.importance_score)
                    
                    # Add consolidated memory
                    await self.memory_manager.add_long_term_memory(
                        db=db,
                        content=f"[CONSOLIDATED {content_type.upper()}] {summary}",
                        learned_from_sessions=list(all_sessions),
                        importance_score=max_importance * 0.9,  # Slightly reduce importance
                    )
                    
                    # Remove old memories
                    for mem in memories:
                        try:
                            self.memory_manager.long_term_memory_collection.delete(
                                ids=[mem.embedding_id]
                            )
                            await db.delete(mem)
                        except Exception as e:
                            logger.warning(f"Error removing old memory {mem.id}: {e}")
                    
                    summarized_count += len(memories)
            
            await db.commit()
            
            logger.info(f"Summarized {summarized_count} old memories")
            
            return {
                "summarized": summarized_count,
                "kept": len(old_memories) - summarized_count,
            }
            
        except Exception as e:
            logger.error(f"Error summarizing old memories: {e}", exc_info=True)
            await db.rollback()
            return {"summarized": 0, "kept": 0, "error": str(e)}
    
    def _extract_content_type(self, content: str) -> str:
        """Extract content type from memory content"""
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
        elif "email from:" in content_lower:
            return "email"
        elif "web search result:" in content_lower or "url:" in content_lower:
            return "web"
        else:
            return "general"
    
    async def _create_summary(
        self,
        memories: List[MemoryLong],
        content_type: str,
    ) -> Optional[str]:
        """Create a summary of multiple memories using LLM"""
        try:
            # Combine memories
            combined_content = "\n\n".join([
                f"- {mem.content}" for mem in memories[:10]  # Limit to 10 for prompt size
            ])
            
            prompt = f"""Riassumi le seguenti informazioni di tipo {content_type} in un unico riassunto conciso che preservi le informazioni più importanti:

{combined_content}

Crea un riassunto che:
1. Mantiene tutti i fatti importanti
2. Elimina duplicati
3. È conciso ma completo
4. Preserva dettagli critici

Riassunto:"""

            response = await self.ollama_client.generate_with_context(
                prompt=prompt,
                session_context=[],
                retrieved_memory=None,
                tools=None,
                tools_description=None,
                return_raw=False,
            )
            
            return response.strip()
            
        except Exception as e:
            logger.error(f"Error creating summary: {e}", exc_info=True)
            return None
    
    async def update_importance_scores(
        self,
        db: AsyncSession,
        usage_data: Dict[str, int],  # embedding_id -> usage_count
    ) -> Dict[str, Any]:
        """
        Update importance scores based on usage frequency.
        Memories that are retrieved more often get higher importance.
        """
        try:
            updated_count = 0
            
            # Get all memories
            result = await db.execute(select(MemoryLong))
            all_memories = result.scalars().all()
            
            # Calculate max usage for normalization
            max_usage = max(usage_data.values()) if usage_data else 1
            
            for mem in all_memories:
                usage_count = usage_data.get(mem.embedding_id, 0)
                
                if usage_count > 0:
                    # Boost importance based on usage
                    # Formula: new_score = old_score + (usage_ratio * 0.2)
                    usage_ratio = usage_count / max_usage
                    boost = usage_ratio * 0.2
                    
                    new_score = min(mem.importance_score + boost, 1.0)
                    
                    if abs(new_score - mem.importance_score) > 0.05:  # Only update if significant change
                        mem.importance_score = new_score
                        updated_count += 1
            
            await db.commit()
            
            logger.info(f"Updated importance scores for {updated_count} memories")
            
            return {
                "updated": updated_count,
                "total": len(all_memories),
            }
            
        except Exception as e:
            logger.error(f"Error updating importance scores: {e}", exc_info=True)
            await db.rollback()
            return {"updated": 0, "total": 0, "error": str(e)}

