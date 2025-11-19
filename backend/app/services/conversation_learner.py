"""
Conversation Learner Service - Extracts knowledge from conversations
"""
from typing import List, Dict, Any, Optional
from sqlalchemy.ext.asyncio import AsyncSession
from uuid import UUID
from datetime import datetime, timezone
import logging
import re
import numpy as np

from app.core.memory_manager import MemoryManager
from app.core.ollama_client import OllamaClient
from app.core.dependencies import get_ollama_client

logger = logging.getLogger(__name__)


class ConversationLearner:
    """Service for learning from conversations and extracting knowledge"""
    
    def __init__(self, memory_manager: MemoryManager, ollama_client: Optional[OllamaClient] = None):
        self.memory_manager = memory_manager
        # Use get_ollama_client() which returns OllamaClient or GeminiClient based on LLM_PROVIDER
        self.ollama_client = ollama_client or get_ollama_client()
    
    async def extract_knowledge_from_conversation(
        self,
        db: AsyncSession,
        session_id: UUID,
        messages: List[Dict[str, str]],
        min_importance: float = 0.6,
    ) -> List[Dict[str, Any]]:
        """
        Extract knowledge from a conversation.
        Returns list of extracted knowledge items.
        """
        extracted_knowledge = []
        
        try:
            # Combine conversation into a single text
            conversation_text = self._format_conversation(messages)
            
            # Use LLM to extract facts, preferences, and important information
            extraction_prompt = f"""Analizza questa conversazione e estrai conoscenze importanti che dovrebbero essere ricordate a lungo termine.

Conversazione:
{conversation_text}

Estrai:
1. Fatti importanti (date, eventi, decisioni)
2. Preferenze dell'utente (cibi, attività, stili, opinioni - includi sia preferenze positive che negative)
3. Informazioni personali rilevanti
4. Contatti o riferimenti importanti
5. Progetti o attività menzionate

Per le preferenze:
- Estrai sia preferenze positive ("mi piace", "amo", "preferisco") che negative ("non mi piace", "detesto", "odio")
- Per ogni preferenza, includi il contesto completo (es. "L'utente ama la pastasciutta" o "L'utente detesta gli spaghetti")
- Usa descrizioni chiare che permettano di identificare l'oggetto della preferenza

Per ogni conoscenza estratta, fornisci:
- Tipo: "fact", "preference", "personal_info", "contact", "project"
- Contenuto: descrizione chiara e concisa con contesto completo
- Importanza: stima da 0.0 a 1.0

Formato JSON:
{{
  "knowledge": [
    {{
      "type": "preference",
      "content": "L'utente ama la pastasciutta",
      "importance": 0.7
    }}
  ]
}}

Se non ci sono conoscenze importanti da estrarre, restituisci {{"knowledge": []}}."""

            response = await self.ollama_client.generate_with_context(
                prompt=extraction_prompt,
                session_context=[],
                retrieved_memory=None,
                tools=None,
                tools_description=None,
                return_raw=False,
            )
            
            # Parse response (try to extract JSON)
            knowledge_items = self._parse_extraction_response(response)
            
            # Filter by importance
            for item in knowledge_items:
                if item.get("importance", 0) >= min_importance:
                    extracted_knowledge.append(item)
            
            logger.info(f"Extracted {len(extracted_knowledge)} knowledge items from conversation")
            
        except Exception as e:
            logger.error(f"Error extracting knowledge from conversation: {e}", exc_info=True)
        
        return extracted_knowledge
    
    def _format_conversation(self, messages: List[Dict[str, str]]) -> str:
        """Format messages into a readable conversation text"""
        formatted = []
        for msg in messages:
            role = msg.get("role", "unknown")
            content = msg.get("content", "")
            formatted.append(f"{role.upper()}: {content}")
        return "\n".join(formatted)
    
    def _parse_extraction_response(self, response: str) -> List[Dict[str, Any]]:
        """Parse LLM response to extract knowledge items"""
        knowledge_items = []
        
        try:
            # Try to extract JSON from response
            # Look for JSON block
            json_match = re.search(r'\{[^{}]*"knowledge"[^{}]*\[[^\]]*\][^{}]*\}', response, re.DOTALL)
            if json_match:
                import json
                json_str = json_match.group(0)
                data = json.loads(json_str)
                knowledge_items = data.get("knowledge", [])
            else:
                # Fallback: try to extract structured information
                # Look for patterns like "type: ...", "content: ...", "importance: ..."
                items = re.findall(
                    r'(?:type|tipo)[:\s]+(\w+).*?(?:content|contenuto)[:\s]+([^\n]+).*?(?:importance|importanza)[:\s]+([\d.]+)',
                    response,
                    re.IGNORECASE | re.DOTALL
                )
                for item_type, content, importance in items:
                    try:
                        knowledge_items.append({
                            "type": item_type.strip(),
                            "content": content.strip(),
                            "importance": float(importance.strip()),
                        })
                    except ValueError:
                        continue
        except Exception as e:
            logger.warning(f"Error parsing extraction response: {e}")
        
        return knowledge_items
    
    async def index_extracted_knowledge(
        self,
        db: AsyncSession,
        knowledge_items: List[Dict[str, Any]],
        session_id: UUID,
    ) -> Dict[str, Any]:
        """
        Index extracted knowledge into long-term memory.
        Returns statistics about indexing.
        """
        indexed_count = 0
        errors = []
        
        logger.info(f"Processing {len(knowledge_items)} knowledge items for indexing")
        items_to_check_contradictions = []  # Store items for contradiction check even if duplicate
        
        for item in knowledge_items:
            try:
                content = item.get("content", "")
                if not content:
                    logger.info("⚠️ Skipping knowledge item: empty content")
                    continue
                
                # Add type information to content
                knowledge_type = item.get("type", "fact")
                formatted_content = f"[{knowledge_type.upper()}] {content}"
                
                importance = item.get("importance", 0.6)
                logger.info(f"📝 Processing knowledge item: type={knowledge_type}, importance={importance}, content={content[:50]}...")
                
                # Check if similar knowledge already exists
                existing = await self._check_duplicate_knowledge(content, importance)
                if existing:
                    logger.info(f"⚠️ Similar knowledge already exists, skipping indexing: {content[:50]}...")
                    # Still add to contradiction check list - duplicates might still be contradictions
                    items_to_check_contradictions.append(item)
                    continue
                
                # Get tenant_id from session
                from app.models.database import Session as SessionModel
                from sqlalchemy import select
                session_result = await db.execute(
                    select(SessionModel.tenant_id).where(SessionModel.id == session_id)
                )
                tenant_id = session_result.scalar_one_or_none()
                
                # Index in long-term memory (non-blocking)
                logger.info(f"📝 Attempting to index knowledge: type={knowledge_type}, importance={importance}, content={content[:50]}...")
                await self.memory_manager.add_long_term_memory(
                    db=db,
                    content=formatted_content,
                    learned_from_sessions=[session_id],
                    importance_score=importance,
                    tenant_id=tenant_id,
                )
                
                indexed_count += 1
                logger.info(f"✅ Indexed knowledge: {content[:50]}... (importance: {importance})")
                # Add to contradiction check list
                items_to_check_contradictions.append(item)
                
            except Exception as e:
                errors.append(f"Knowledge item: {str(e)}")
                logger.error(f"Error indexing knowledge item: {e}")
        
        # Build stats before integrity check
        stats = {
            "indexed": indexed_count,
            "errors": errors,
            "total": len(knowledge_items),
        }
        
        # Schedule background integrity check (fire and forget)
        # IMPORTANT: Only check contradictions if we actually indexed NEW knowledge to long-term memory
        # This prevents the integrity agent from being activated when no knowledge was extracted or indexed
        # CRITICAL: Only schedule integrity check if we actually indexed NEW knowledge (not just duplicates)
        if indexed_count == 0:
            logger.info(f"⏭️  Skipping integrity check: no new knowledge indexed (indexed_count=0, items_to_check={len(items_to_check_contradictions)})")
            return stats
        
        # Only proceed if we have items to check AND we actually indexed something
        if items_to_check_contradictions:
            
            try:
                import asyncio
                from app.db.database import AsyncSessionLocal
                from app.services.background_agent import BackgroundAgent
                from app.core.dependencies import get_task_queue
                
                async def _check_integrity_background():
                    """Background task to check integrity of knowledge (including duplicates)"""
                    # IMPORTANT: This runs silently in background - no activity events published
                    # Activity events are only published when contradictions are actually found (in process_new_knowledge)
                    async with AsyncSessionLocal() as db_session:
                        try:
                            agent = BackgroundAgent(
                                memory_manager=self.memory_manager,
                                db=db_session,
                                ollama_client=None,  # Will use background client
                                task_queue=get_task_queue(),
                            )
                            
                            # Process each knowledge item (including duplicates) for contradiction check
                            # This runs silently - no telemetry events unless contradictions are found
                            for item in items_to_check_contradictions:
                                content = item.get("content", "")
                                if content:
                                    logger.debug(f"🔍 Checking contradictions for: {content[:50]}...")
                                    await agent.process_new_knowledge(
                                        knowledge_item=item,
                                        session_id=session_id,
                                    )
                        except Exception as e:
                            logger.warning(f"Error in background integrity check: {e}", exc_info=True)
                
                # Schedule background task (don't await to avoid blocking)
                # NOTE: This runs silently in background - no telemetry events are published
                # The integrity agent will only appear active if contradictions are found (handled in process_new_knowledge)
                asyncio.create_task(_check_integrity_background())
                logger.debug(f"🔍 Scheduled background integrity check for {len(items_to_check_contradictions)} knowledge items ({indexed_count} newly indexed) - running silently")
                
            except Exception as e:
                logger.warning(f"Error scheduling background integrity check: {e}", exc_info=True)
        else:
            logger.debug("No knowledge items to check for contradictions (no items extracted or all filtered)")
        
        return stats
    
    async def _check_duplicate_knowledge(
        self,
        content: str,
        min_similarity: float = 0.85,
    ) -> bool:
        """
        Check if similar knowledge already exists in long-term memory.
        Returns True if duplicate found, False otherwise.
        """
        try:
            # Retrieve similar memories
            similar = await self.memory_manager.retrieve_long_term_memory(
                query=content,
                n_results=3,
            )
            
            if not similar:
                return False
            
            # Check similarity using embeddings
            from app.services.embedding_service import EmbeddingService
            embedding_service = EmbeddingService()
            
            content_embedding = embedding_service.generate_embedding(content)
            
            for similar_content in similar:
                similar_embedding = embedding_service.generate_embedding(similar_content)
                
                # Calculate cosine similarity
                similarity = np.dot(content_embedding, similar_embedding) / (
                    np.linalg.norm(content_embedding) * np.linalg.norm(similar_embedding)
                )
                
                if similarity >= min_similarity:
                    return True
            
            return False
            
        except Exception as e:
            logger.warning(f"Error checking duplicate knowledge: {e}")
            return False

