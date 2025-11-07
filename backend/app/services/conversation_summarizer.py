"""
Conversation Summarizer Service - Summarizes conversations when context becomes too large
"""
from typing import List, Dict, Any, Optional
from sqlalchemy.ext.asyncio import AsyncSession
from uuid import UUID
from datetime import datetime, timezone
import logging

from app.core.memory_manager import MemoryManager
from app.core.ollama_client import OllamaClient

logger = logging.getLogger(__name__)


class ConversationSummarizer:
    """Service for summarizing conversations to reduce context size"""
    
    def __init__(
        self,
        memory_manager: MemoryManager,
        ollama_client: Optional[OllamaClient] = None,
    ):
        self.memory_manager = memory_manager
        self.ollama_client = ollama_client or OllamaClient()
    
    def estimate_tokens(self, text: str) -> int:
        """
        Estimate token count from text.
        Rough approximation: ~4 characters per token for English/Italian.
        """
        return len(text) // 4
    
    def estimate_context_size(
        self,
        session_context: List[Dict[str, str]],
        system_prompt: str = "",
        retrieved_memory: List[str] = None,
    ) -> int:
        """Estimate total context size in tokens"""
        total = 0
        
        # System prompt
        if system_prompt:
            total += self.estimate_tokens(system_prompt)
        
        # Session context
        for msg in session_context:
            total += self.estimate_tokens(msg.get("content", ""))
        
        # Retrieved memory
        if retrieved_memory:
            for mem in retrieved_memory:
                total += self.estimate_tokens(mem)
        
        return total
    
    async def summarize_conversation_segment(
        self,
        messages: List[Dict[str, str]],
        session_id: UUID,
    ) -> Optional[str]:
        """
        Summarize a segment of conversation using LLM.
        Returns the summary or None if summarization fails.
        """
        try:
            if not messages or len(messages) < 2:
                return None
            
            # Format conversation
            conversation_text = self._format_conversation(messages)
            
            # Create summarization prompt
            summary_prompt = f"""Riassumi questa conversazione in modo conciso ma completo, preservando:
1. I punti chiave discussi
2. Le decisioni prese
3. Le informazioni importanti menzionate
4. Il contesto necessario per continuare la conversazione

Conversazione:
{conversation_text}

Riassunto (massimo 500 parole, mantieni tutti i dettagli importanti):"""

            response = await self.ollama_client.generate_with_context(
                prompt=summary_prompt,
                session_context=[],
                retrieved_memory=None,
                tools=None,
                tools_description=None,
                return_raw=False,
            )
            
            return response.strip()
            
        except Exception as e:
            logger.error(f"Error summarizing conversation segment: {e}", exc_info=True)
            return None
    
    def _format_conversation(self, messages: List[Dict[str, str]]) -> str:
        """Format messages into a readable conversation text"""
        formatted = []
        for msg in messages:
            role = msg.get("role", "unknown")
            content = msg.get("content", "")
            formatted.append(f"{role.upper()}: {content}")
        return "\n\n".join(formatted)
    
    async def should_summarize(
        self,
        session_context: List[Dict[str, str]],
        system_prompt: str = "",
        retrieved_memory: List[str] = None,
        max_tokens: int = 8000,  # Default threshold
    ) -> bool:
        """
        Check if conversation should be summarized based on context size.
        Returns True if context exceeds max_tokens.
        """
        estimated_tokens = self.estimate_context_size(
            session_context, system_prompt, retrieved_memory
        )
        return estimated_tokens > max_tokens
    
    async def create_summary_and_store(
        self,
        db: AsyncSession,
        session_id: UUID,
        messages_to_summarize: List[Dict[str, str]],
    ) -> Optional[str]:
        """
        Create a summary of messages and store it in medium-term memory.
        Returns the summary text if successful, None otherwise.
        """
        try:
            # Summarize
            summary = await self.summarize_conversation_segment(
                messages_to_summarize,
                session_id,
            )
            
            if not summary:
                logger.warning("Failed to generate summary")
                return None
            
            # Store in medium-term memory
            await self.memory_manager.add_medium_term_memory(
                db=db,
                session_id=session_id,
                content=f"[RIASSUNTO CONVERSAZIONE] {summary}",
            )
            
            logger.info(f"Created and stored conversation summary in medium-term memory for session {session_id}")
            return summary
            
        except Exception as e:
            logger.error(f"Error creating and storing summary: {e}", exc_info=True)
            return None
    
    async def get_optimized_context(
        self,
        db: AsyncSession,
        session_id: UUID,
        all_messages: List[Dict[str, str]],
        system_prompt: str = "",
        retrieved_memory: List[str] = None,
        max_tokens: int = 8000,
        keep_recent: int = 10,  # Keep last N messages
    ) -> List[Dict[str, str]]:
        """
        Get optimized context by summarizing old messages if needed.
        Returns optimized session_context.
        
        Strategy:
        1. Keep last N messages (keep_recent)
        2. If context is still too large, summarize older messages
        3. Store summaries in medium-term memory
        4. Use summaries + recent messages
        """
        # Start with recent messages
        recent_messages = all_messages[-keep_recent:] if len(all_messages) > keep_recent else all_messages
        older_messages = all_messages[:-keep_recent] if len(all_messages) > keep_recent else []
        
        # Check total context size (recent + older + system + retrieved_memory)
        total_tokens = self.estimate_context_size(
            all_messages, system_prompt, retrieved_memory
        )
        
        # Also check if just recent messages exceed threshold
        recent_tokens = self.estimate_context_size(
            recent_messages, system_prompt, retrieved_memory
        )
        
        # If total doesn't exceed threshold, no need to summarize
        if total_tokens <= max_tokens or not older_messages:
            # Context is fine, return recent messages (or all if small enough)
            return recent_messages if len(all_messages) > keep_recent else all_messages
        
        # If we get here, total exceeds threshold, so we need to summarize older messages
        # But if recent alone exceeds threshold, we still need to summarize older to make room
        
        # Need to summarize older messages
        logger.info(f"Context too large ({current_tokens} tokens), summarizing {len(older_messages)} older messages")
        
        # Get existing summaries from medium-term memory (search for summaries)
        existing_summaries = await self.memory_manager.retrieve_medium_term_memory(
            session_id, "riassunto conversazione precedente", n_results=10
        )
        
        # Filter to only get actual summaries (those starting with [RIASSUNTO CONVERSAZIONE])
        summary_texts = []
        for summary in existing_summaries:
            if "[RIASSUNTO CONVERSAZIONE]" in summary or "[Riassunto conversazione precedente]" in summary:
                # Extract just the summary text (remove the prefix)
                summary_text = summary.replace("[RIASSUNTO CONVERSAZIONE]", "").replace("[Riassunto conversazione precedente]", "").strip()
                if summary_text:
                    summary_texts.append(summary_text)
        
        existing_summaries = summary_texts
        
        # If we have summaries, use them
        if existing_summaries:
            # Build context with summaries + recent messages
            optimized_context = []
            
            # Add summaries as system-like messages
            for summary in existing_summaries:
                optimized_context.append({
                    "role": "system",
                    "content": f"[Riassunto conversazione precedente] {summary}",
                })
            
            # Add recent messages
            optimized_context.extend(recent_messages)
            
            # Check if still too large
            new_tokens = self.estimate_context_size(
                optimized_context, system_prompt, retrieved_memory
            )
            
            if new_tokens <= max_tokens:
                return optimized_context
        
        # Create new summary from older messages
        # Split older messages into chunks if too many
        chunk_size = 20  # Summarize 20 messages at a time
        summaries_created = []
        
        for i in range(0, len(older_messages), chunk_size):
            chunk = older_messages[i:i + chunk_size]
            summary = await self.create_summary_and_store(
                db, session_id, chunk
            )
            if summary:
                summaries_created.append(summary)
        
        # Build optimized context
        optimized_context = []
        
        # Add newly created summaries
        for summary in summaries_created:
            optimized_context.append({
                "role": "system",
                "content": f"[Riassunto conversazione precedente] {summary}",
            })
        
        # Add existing summaries (if any)
        for summary in existing_summaries:
            if summary not in summaries_created:  # Avoid duplicates
                optimized_context.append({
                    "role": "system",
                    "content": f"[Riassunto conversazione precedente] {summary}",
                })
        
        # Add recent messages
        optimized_context.extend(recent_messages)
        
        logger.info(f"Optimized context: {len(summaries_created)} new summaries + {len(recent_messages)} recent messages")
        
        return optimized_context

