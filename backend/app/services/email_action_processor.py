"""
Email Action Processor Service - Processes email actions and creates automatic sessions
"""
import logging
import asyncio
from typing import Dict, Any, Optional
from uuid import UUID
from sqlalchemy.ext.asyncio import AsyncSession
from datetime import datetime, timezone

from app.models.database import Session as SessionModel, Message as MessageModel
from app.core.ollama_client import OllamaClient
from app.core.memory_manager import MemoryManager
from app.core.dependencies import get_ollama_client
from app.services.daily_session_manager import DailySessionManager

logger = logging.getLogger(__name__)


class EmailActionProcessor:
    """Processes email actions and adds them to daily sessions"""
    
    def __init__(
        self,
        db: AsyncSession,
        ollama_client: Optional[OllamaClient] = None,
        memory_manager: Optional[MemoryManager] = None,
    ):
        self.db = db
        # Use get_ollama_client() which returns OllamaClient or GeminiClient based on LLM_PROVIDER
        self.ollama_client = ollama_client or get_ollama_client()
        self.memory_manager = memory_manager
        self.daily_session_manager = DailySessionManager(
            db=db,
            memory_manager=memory_manager,
            ollama_client=ollama_client,
        )
    
    async def process_email_action(
        self,
        email: Dict[str, Any],
        analysis: Dict[str, Any],
        tenant_id: UUID,
        user_id: UUID,
    ) -> Optional[UUID]:
        """
        Add email to today's daily session if action is required.
        Returns session_id if email was added to session, None otherwise.
        """
        if not analysis.get("requires_action"):
            return None
        
        action_type = analysis.get("action_type")
        urgency = analysis.get("urgency", "medium")
        
        # Check if we should process this email based on urgency
        from app.core.config import settings
        urgency_levels = {"high": 3, "medium": 2, "low": 1}
        min_urgency_str = settings.email_analysis_min_urgency_for_session
        min_urgency_level = urgency_levels.get(min_urgency_str, 2)  # Default to medium if invalid
        if urgency_levels.get(urgency, 0) < min_urgency_level:
            logger.debug(f"Skipping email processing for low urgency: {email.get('subject')} (urgency: {urgency}, min required: {min_urgency_str})")
            return None
        
        # Check if this email was already processed (deduplication)
        email_id = email.get("id")
        if email_id:
            from sqlalchemy import select
            # Check if there's already a message about this email in any session
            existing_message = await self.db.execute(
                select(MessageModel).where(
                    MessageModel.tenant_id == tenant_id,
                    MessageModel.session_metadata["email_id"].astext == str(email_id),
                ).limit(1)
            )
            if existing_message.scalar_one_or_none():
                logger.debug(f"Email {email_id} already processed, skipping")
                return None
        
        try:
            # Get or create today's daily session
            session, is_new = await self.daily_session_manager.get_or_create_today_session(
                user_id=user_id,
                tenant_id=tenant_id,
            )
            
            # Track processed emails in session metadata
            if not session.session_metadata:
                session.session_metadata = {}
            if "processed_emails" not in session.session_metadata:
                session.session_metadata["processed_emails"] = []
            
            # Add email info to processed emails list
            email_info = {
                "email_id": email_id,
                "subject": email.get("subject"),
                "from": email.get("from"),
                "date": email.get("date"),
                "action_type": action_type,
                "urgency": urgency,
            }
            # Check if email_id already exists (more reliable than checking entire dict)
            existing_ids = [e.get("email_id") for e in session.session_metadata["processed_emails"]]
            if email_id not in existing_ids:
                session.session_metadata["processed_emails"].append(email_info)
                await self.db.commit()  # Commit metadata update
            
            # Create initial message with email summary and action request
            # IMPORTANT: This message should be from the ASSISTANT, not the user
            initial_message = self._create_initial_message(email, analysis)
            
            # Save initial message as ASSISTANT message
            message = MessageModel(
                session_id=session.id,
                tenant_id=tenant_id,
                role="assistant",
                content=initial_message,
                session_metadata={
                    "email_id": email_id,
                    "source": "email_analysis",
                    "action_type": action_type,
                    "urgency": urgency,
                },
            )
            self.db.add(message)
            await self.db.commit()
            
            logger.info(f"Added email {email_id} to daily session {session.id}")
            
            return session.id
        except Exception as e:
            logger.error(f"Error processing email action: {e}", exc_info=True)
            await self.db.rollback()
            return None
    
    def _create_initial_message(
        self,
        email: Dict[str, Any],
        analysis: Dict[str, Any],
    ) -> str:
        """Create initial chat message summarizing email and action"""
        action_summary = analysis.get("action_summary", "")
        action_type = analysis.get("action_type")
        email_preview = email.get("snippet", "")[:300]
        subject = email.get("subject", "No Subject")
        sender = email.get("from", "Unknown Sender")
        
        # Build action suggestions based on action_type
        action_suggestions = []
        if action_type == "reply":
            action_suggestions.append("- Rispondere all'email")
        if action_type == "calendar_event":
            action_suggestions.append("- Creare un evento nel calendario")
        if action_type == "task":
            action_suggestions.append("- Creare un task/ricordo")
        if not action_suggestions:
            action_suggestions.append("- Valutare l'email e decidere come procedere")
        
        suggestions_text = "\n".join(action_suggestions)
        
        message = f"""Ho ricevuto una nuova email che richiede attenzione:

**Da**: {sender}
**Oggetto**: {subject}

**Contenuto**: {email_preview}

**Azione richiesta**: {action_summary if action_summary else 'Richiede attenzione'}

Come vuoi procedere? Posso aiutarti a:
{suggestions_text}
- Solo archiviare l'email se non è importante

Dimmi come vuoi procedere e ti aiuterò!"""
        
        return message
    
    async def _trigger_chat_response(
        self,
        session_id: UUID,
        initial_message: str,
        tenant_id: UUID,
    ):
        """Trigger automatic chat response for the session"""
        try:
            # Import here to avoid circular dependencies
            from app.agents import run_langgraph_chat
            from app.models.schemas import ChatRequest
            from app.core.dependencies import get_planner_client, get_agent_activity_stream
            
            # Get fresh database session for background task
            from app.db.database import AsyncSessionLocal
            async with AsyncSessionLocal() as db_session:
                planner_client = get_planner_client()
                agent_activity_stream = get_agent_activity_stream()
                
                # Get session to verify it exists and get user_id
                from sqlalchemy import select
                from app.models.database import User
                result = await db_session.execute(
                    select(SessionModel).where(SessionModel.id == session_id)
                )
                session = result.scalar_one_or_none()
                
                if not session:
                    logger.warning(f"Session {session_id} not found for chat response")
                    return
                
                # Get user for current_user parameter
                current_user = None
                if session.user_id:
                    user_result = await db_session.execute(
                        select(User).where(User.id == session.user_id)
                    )
                    current_user = user_result.scalar_one_or_none()
                
                # Generate automatic response
                request = ChatRequest(
                    message=initial_message,
                    session_id=session_id,
                    use_memory=True,
                    force_web_search=False,
                )
                
                # Get session context (should be empty for new session)
                session_context = []
                retrieved_memory = []
                memory_used = {}
                
                # Run chat to generate response
                langgraph_result = await run_langgraph_chat(
                    db=db_session,
                    session_id=session_id,
                    request=request,
                    ollama=self.ollama_client,
                    planner_client=planner_client,
                    agent_activity_stream=agent_activity_stream,
                    memory_manager=self.memory_manager,
                    session_context=session_context,
                    retrieved_memory=retrieved_memory,
                    memory_used=memory_used,
                    previous_messages=[],
                    pending_plan=None,
                    current_user=current_user,
                )
                
                logger.info(f"Generated automatic response for session {session_id}")
        except Exception as e:
            logger.error(f"Error triggering chat response for session {session_id}: {e}", exc_info=True)

