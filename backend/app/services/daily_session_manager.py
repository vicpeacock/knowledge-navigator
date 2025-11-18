"""
Daily Session Manager - Manages day-based sessions for users

Each user has one active session per day. When a new day starts (in user's timezone),
the previous day's session is archived and summarized, and a new session is created.
"""
import logging
from datetime import datetime, timedelta
from typing import Optional, Tuple
from uuid import UUID
from zoneinfo import ZoneInfo

from sqlalchemy import select, and_
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.database import Session as SessionModel, User, Message as MessageModel
from app.core.memory_manager import MemoryManager
from app.core.ollama_client import OllamaClient

logger = logging.getLogger(__name__)


class DailySessionManager:
    """Manages day-based sessions for users"""
    
    def __init__(
        self,
        db: AsyncSession,
        memory_manager: Optional[MemoryManager] = None,
        ollama_client: Optional[OllamaClient] = None,
    ):
        self.db = db
        self.memory_manager = memory_manager
        self.ollama_client = ollama_client
    
    def _get_user_timezone(self, user: User) -> ZoneInfo:
        """Get user's timezone or default to UTC"""
        timezone_str = user.timezone or "UTC"
        try:
            return ZoneInfo(timezone_str)
        except Exception as e:
            logger.warning(f"Invalid timezone '{timezone_str}' for user {user.id}, using UTC: {e}")
            return ZoneInfo("UTC")
    
    def _get_today_date_str(self, user: User) -> str:
        """Get today's date string in user's timezone (format: YYYY-MM-DD)"""
        user_tz = self._get_user_timezone(user)
        now = datetime.now(user_tz)
        return now.strftime("%Y-%m-%d")
    
    def _get_yesterday_date_str(self, user: User) -> str:
        """Get yesterday's date string in user's timezone (format: YYYY-MM-DD)"""
        user_tz = self._get_user_timezone(user)
        yesterday = datetime.now(user_tz) - timedelta(days=1)
        return yesterday.strftime("%Y-%m-%d")
    
    async def get_or_create_today_session(
        self,
        user_id: UUID,
        tenant_id: UUID,
    ) -> Tuple[SessionModel, bool]:
        """
        Get or create today's session for the user.
        
        Returns:
            Tuple[SessionModel, bool]: (session, is_new) - is_new indicates if session was just created
        """
        # Get user to access timezone
        user_result = await self.db.execute(
            select(User).where(User.id == user_id, User.tenant_id == tenant_id)
        )
        user = user_result.scalar_one_or_none()
        if not user:
            raise ValueError(f"User {user_id} not found")
        
        today_date = self._get_today_date_str(user)
        
        # Check if today's session already exists
        existing_session_result = await self.db.execute(
            select(SessionModel).where(
                SessionModel.tenant_id == tenant_id,
                SessionModel.user_id == user_id,
                SessionModel.status == "active",
                SessionModel.session_metadata["day"].astext == today_date,
            )
        )
        existing_session = existing_session_result.scalar_one_or_none()
        
        if existing_session:
            logger.debug(f"Found existing session {existing_session.id} for user {user_id} on {today_date}")
            return existing_session, False
        
        # Check if we need to archive yesterday's session
        await self._check_and_archive_yesterday_session(user, tenant_id, user_id)
        
        # Create new session for today
        session_name = f"Sessione {today_date}"
        new_session = SessionModel(
            tenant_id=tenant_id,
            user_id=user_id,
            name=session_name,
            title=f"Sessione {today_date}",
            description=f"Sessione giornaliera del {today_date}",
            status="active",
            session_metadata={
                "day": today_date,
                "is_daily_session": True,
                "timezone": user.timezone or "UTC",
            },
        )
        self.db.add(new_session)
        await self.db.commit()
        await self.db.refresh(new_session)
        
        logger.info(f"Created new daily session {new_session.id} for user {user_id} on {today_date}")
        return new_session, True
    
    async def _check_and_archive_yesterday_session(
        self,
        user: User,
        tenant_id: UUID,
        user_id: UUID,
    ) -> Optional[SessionModel]:
        """
        Check if yesterday's session exists and needs to be archived.
        If it exists and is still active, archive it and generate summary.
        
        Returns:
            Optional[SessionModel]: Yesterday's session if it was archived, None otherwise
        """
        yesterday_date = self._get_yesterday_date_str(user)
        
        # Find yesterday's session
        yesterday_session_result = await self.db.execute(
            select(SessionModel).where(
                SessionModel.tenant_id == tenant_id,
                SessionModel.user_id == user_id,
                SessionModel.status == "active",
                SessionModel.session_metadata["day"].astext == yesterday_date,
            )
        )
        yesterday_session = yesterday_session_result.scalar_one_or_none()
        
        if not yesterday_session:
            logger.debug(f"No active session found for user {user_id} on {yesterday_date}")
            return None
        
        logger.info(f"Found active session {yesterday_session.id} for user {user_id} on {yesterday_date}, archiving...")
        
        # Generate summary before archiving
        if self.memory_manager and self.ollama_client:
            try:
                await self._generate_daily_summary(yesterday_session, user)
            except Exception as e:
                logger.error(f"Error generating daily summary for session {yesterday_session.id}: {e}", exc_info=True)
        
        # Archive the session
        yesterday_session.status = "archived"
        yesterday_session.archived_at = datetime.now()
        await self.db.commit()
        await self.db.refresh(yesterday_session)
        
        logger.info(f"Archived session {yesterday_session.id} for user {user_id}")
        return yesterday_session
    
    async def _generate_daily_summary(
        self,
        session: SessionModel,
        user: User,
    ) -> Optional[str]:
        """
        Generate a summary of the day's session and update long-term memory.
        
        Returns:
            Optional[str]: Generated summary text, or None if generation failed
        """
        if not self.memory_manager or not self.ollama_client:
            logger.warning("Memory manager or Ollama client not available, skipping summary generation")
            return None
        
        # Get all messages from the session
        messages_result = await self.db.execute(
            select(MessageModel).where(
                MessageModel.session_id == session.id,
                MessageModel.tenant_id == session.tenant_id,
            ).order_by(MessageModel.timestamp)
        )
        messages = messages_result.scalars().all()
        
        if not messages:
            logger.debug(f"No messages found in session {session.id}, skipping summary")
            return None
        
        # Build conversation context
        conversation_text = "\n".join([
            f"{msg.role}: {msg.content}"
            for msg in messages
        ])
        
        # Generate summary using LLM
        summary_prompt = f"""Analizza la seguente conversazione della giornata {session.session_metadata.get('day', 'unknown')} e crea un riassunto conciso dei punti chiave, decisioni prese, azioni compiute, e informazioni importanti da ricordare per il futuro.

Conversazione:
{conversation_text[:8000]}  # Limit to avoid token limits

Crea un riassunto strutturato in italiano che includa:
1. Argomenti principali discussi
2. Decisioni prese o azioni compiute
3. Informazioni importanti da ricordare
4. Eventi o notifiche significative

Riassunto:"""
        
        try:
            summary_response = await self.ollama_client.generate_with_context(
                prompt=summary_prompt,
                session_context=[],
                retrieved_memory=None,
                tools=None,
                tools_description=None,
                return_raw=False,
            )
            
            summary_text = summary_response if isinstance(summary_response, str) else str(summary_response)
            
            # Update long-term memory with summary
            if summary_text:
                await self.memory_manager.add_long_term_memory(
                    content=summary_text,
                    tenant_id=session.tenant_id,
                    session_ids=[str(session.id)],
                    importance_score=0.7,  # Daily summaries are moderately important
                )
                logger.info(f"Generated and stored daily summary for session {session.id}")
            
            # Store summary in session metadata
            if not session.session_metadata:
                session.session_metadata = {}
            session.session_metadata["daily_summary"] = summary_text
            await self.db.commit()
            
            return summary_text
            
        except Exception as e:
            logger.error(f"Error generating daily summary: {e}", exc_info=True)
            return None
    
    async def check_day_transition(
        self,
        user_id: UUID,
        tenant_id: UUID,
        current_session_id: Optional[UUID] = None,
    ) -> Tuple[bool, Optional[SessionModel]]:
        """
        Check if a day transition has occurred for the user.
        
        Returns:
            Tuple[bool, Optional[SessionModel]]: 
                - (True, new_session) if day transition occurred and new session was created
                - (False, None) if no transition occurred
        """
        # Get user
        user_result = await self.db.execute(
            select(User).where(User.id == user_id, User.tenant_id == tenant_id)
        )
        user = user_result.scalar_one_or_none()
        if not user:
            return False, None
        
        # Get today's session
        today_session, is_new = await self.get_or_create_today_session(user_id, tenant_id)
        
        # If current_session_id is provided, check if it's different from today's session
        if current_session_id and current_session_id != today_session.id:
            # Day transition occurred
            logger.info(f"Day transition detected for user {user_id}: {current_session_id} -> {today_session.id}")
            return True, today_session
        
        return False, None

