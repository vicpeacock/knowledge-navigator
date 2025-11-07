"""
Background Agent - Autonomous thinking agent for proactive checks
"""
from typing import Dict, Any, Optional
from sqlalchemy.ext.asyncio import AsyncSession
from uuid import UUID
import logging

from app.core.memory_manager import MemoryManager
from app.core.ollama_client import OllamaClient
from app.core.dependencies import get_ollama_background_client
from app.services.semantic_integrity_checker import SemanticIntegrityChecker
from app.services.notification_service import NotificationService
from app.core.config import settings

logger = logging.getLogger(__name__)


class BackgroundAgent:
    """
    Background agent for autonomous thinking.
    Handles: semantic integrity, external events, todo list, etc.
    """
    
    def __init__(
        self,
        memory_manager: MemoryManager,
        db: AsyncSession,
        ollama_client: Optional[OllamaClient] = None,
    ):
        self.memory_manager = memory_manager
        self.db = db
        
        # Use background Ollama client (phi3:mini) for background tasks
        self.ollama_client = ollama_client or get_ollama_background_client()
        
        # Initialize services
        self.integrity_checker = SemanticIntegrityChecker(
            memory_manager=memory_manager,
            ollama_client=self.ollama_client,  # Use background client
        )
        self.notification_service = NotificationService(db=db)
    
    async def process_new_knowledge(
        self,
        knowledge_item: Dict[str, Any],
        session_id: Optional[UUID] = None,
    ):
        """
        Process new knowledge in background:
        - Check semantic integrity
        - Generate notifications if necessary
        
        Args:
            knowledge_item: Knowledge item from ConversationLearner
            session_id: Session ID where knowledge was extracted
        """
        try:
            logger.info(f"Processing new knowledge in background: {knowledge_item.get('content', '')[:50]}...")
            
            # Check integrity (exhaustive or limited based on config)
            contradiction_info = await self.integrity_checker.check_contradictions(
                knowledge_item,
                db=self.db,
                max_similar_memories=settings.integrity_max_similar_memories,
                confidence_threshold=settings.integrity_confidence_threshold,
            )
            
            logger.debug(f"Integrity check result: has_contradiction={contradiction_info.get('has_contradiction')}, confidence={contradiction_info.get('confidence', 0):.2f}, contradictions_count={len(contradiction_info.get('contradictions', []))}")
            
            if contradiction_info.get("has_contradiction"):
                logger.warning(f"⚠️ Contradiction detected for knowledge: {knowledge_item.get('content', '')[:50]}...")
                logger.warning(f"   Confidence: {contradiction_info.get('confidence', 0):.2f}, Count: {len(contradiction_info.get('contradictions', []))}")
                
                # Create notification (always HIGH urgency for contradictions)
                notification = await self.notification_service.create_notification(
                    type="contradiction",
                    urgency="high",
                    content={
                        "new_knowledge": knowledge_item,
                        "contradictions": contradiction_info.get("contradictions", []),
                        "confidence": contradiction_info.get("confidence", 0.0),
                    },
                    session_id=session_id,
                )
                
                logger.info(f"✅ Created contradiction notification {notification.id} for session {session_id}")
            else:
                logger.debug(f"No contradictions found for knowledge: {knowledge_item.get('content', '')[:50]}... (confidence: {contradiction_info.get('confidence', 0):.2f})")
                
        except Exception as e:
            logger.error(f"Error processing new knowledge in background: {e}", exc_info=True)
            # Don't raise - background tasks should not fail the main flow
    
    async def check_external_events(self):
        """Check external events (email, calendar, etc.) - to be implemented"""
        # TODO: Implement event checking
        pass
    
    async def check_todo_list(self):
        """Check todo list - to be implemented"""
        # TODO: Implement todo list checking
        pass

