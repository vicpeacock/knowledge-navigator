"""
Email Indexer Service - Indexes important emails into long-term memory
"""
from typing import List, Dict, Any, Optional
from sqlalchemy.ext.asyncio import AsyncSession
from uuid import UUID
from datetime import datetime, timezone
import logging

from app.core.memory_manager import MemoryManager
from app.core.ollama_client import OllamaClient

logger = logging.getLogger(__name__)


class EmailIndexer:
    """Service for indexing emails into long-term memory"""
    
    def __init__(self, memory_manager: MemoryManager, ollama_client: Optional[OllamaClient] = None):
        self.memory_manager = memory_manager
        self.ollama_client = ollama_client or OllamaClient()
    
    async def should_index_email(
        self,
        email: Dict[str, Any],
        importance_threshold: float = 0.6,
    ) -> bool:
        """
        Determine if an email should be indexed based on importance.
        Can use LLM to classify or simple heuristics.
        """
        # Simple heuristic: index emails with body content (not just snippets)
        # and emails from important contacts or with important keywords
        has_body = bool(email.get("body"))
        is_unread = "unread" in email.get("snippet", "").lower()
        
        # Check for important keywords
        important_keywords = [
            "urgent", "important", "meeting", "appointment",
            "deadline", "project", "action required", "follow up"
        ]
        subject = email.get("subject", "").lower()
        body = email.get("body", "").lower()
        snippet = email.get("snippet", "").lower()
        
        has_important_keyword = any(
            keyword in subject or keyword in body or keyword in snippet
            for keyword in important_keywords
        )
        
        # Index if: has body content OR is unread with important keywords OR has body and keywords OR has important keywords (even without body)
        return has_body or (is_unread and has_important_keyword) or (has_body and has_important_keyword) or has_important_keyword
    
    async def index_email(
        self,
        db: AsyncSession,
        email: Dict[str, Any],
        session_id: UUID,
        importance_score: Optional[float] = None,
        tenant_id: Optional[UUID] = None,
    ) -> bool:
        """
        Index a single email into long-term memory.
        Returns True if indexed, False otherwise.
        """
        try:
            # Check if should index
            if not await self.should_index_email(email):
                logger.debug(f"Email {email.get('id')} not important enough to index")
                return False
            
            # Build content for indexing
            content = self._build_email_content(email)
            
            # Calculate importance score if not provided
            if importance_score is None:
                importance_score = await self._calculate_importance(email)
            
            # Get tenant_id from session if not provided
            if not tenant_id:
                from app.models.database import Session as SessionModel
                from sqlalchemy import select
                session_result = await db.execute(
                    select(SessionModel.tenant_id).where(SessionModel.id == session_id)
                )
                tenant_id = session_result.scalar_one_or_none()
            
            # Index in long-term memory
            await self.memory_manager.add_long_term_memory(
                db=db,
                content=content,
                learned_from_sessions=[session_id],
                importance_score=importance_score,
                tenant_id=tenant_id,
            )
            
            logger.info(f"Indexed email {email.get('id')} into long-term memory with importance {importance_score}")
            return True
            
        except Exception as e:
            logger.error(f"Error indexing email {email.get('id')}: {e}", exc_info=True)
            return False
    
    async def index_emails(
        self,
        db: AsyncSession,
        emails: List[Dict[str, Any]],
        session_id: UUID,
        auto_index: bool = True,
    ) -> Dict[str, Any]:
        """
        Index multiple emails into long-term memory.
        Returns statistics about indexing.
        """
        indexed_count = 0
        skipped_count = 0
        errors = []
        
        for email in emails:
            try:
                # Check if should index first
                should_index = await self.should_index_email(email)
                if not should_index:
                    skipped_count += 1
                    continue
                
                # Try to index
                indexed = await self.index_email(db, email, session_id)
                if indexed:
                    indexed_count += 1
                else:
                    # If should_index is True but index_email returns False, it's an error
                    errors.append(f"Email {email.get('id')}: Indexing failed")
                    logger.error(f"Email {email.get('id')} should be indexed but indexing returned False")
            except Exception as e:
                errors.append(f"Email {email.get('id')}: {str(e)}")
                logger.error(f"Error indexing email {email.get('id')}: {e}")
        
        return {
            "indexed": indexed_count,
            "skipped": skipped_count,
            "errors": errors,
            "total": len(emails),
        }
    
    def _build_email_content(self, email: Dict[str, Any]) -> str:
        """Build formatted content string for email indexing"""
        content_parts = []
        
        # Add metadata
        content_parts.append(f"Email from: {email.get('from', 'Unknown')}")
        content_parts.append(f"Subject: {email.get('subject', 'No Subject')}")
        content_parts.append(f"Date: {email.get('date', 'Unknown')}")
        
        if email.get('to'):
            content_parts.append(f"To: {email.get('to')}")
        
        # Add body or snippet
        if email.get('body'):
            content_parts.append(f"\nBody:\n{email.get('body')}")
        elif email.get('snippet'):
            content_parts.append(f"\nSnippet:\n{email.get('snippet')}")
        
        return "\n".join(content_parts)
    
    async def _calculate_importance(self, email: Dict[str, Any]) -> float:
        """
        Calculate importance score for an email (0.0 to 1.0).
        Uses simple heuristics, can be enhanced with LLM classification.
        """
        score = 0.5  # Base score
        
        # Has full body content
        if email.get('body'):
            score += 0.2
        
        # Important keywords
        important_keywords = [
            "urgent", "important", "meeting", "appointment",
            "deadline", "project", "action required"
        ]
        subject = email.get("subject", "").lower()
        body = email.get("body", "").lower()
        
        keyword_count = sum(1 for kw in important_keywords if kw in subject or kw in body)
        score += min(keyword_count * 0.1, 0.3)
        
        # From important contacts (can be enhanced with contact list)
        # For now, just check if it's a reply or forward
        subject_lower = subject
        if subject_lower.startswith("re:") or subject_lower.startswith("fw:"):
            score += 0.1
        
        return min(score, 1.0)  # Cap at 1.0

