"""
Web Content Indexer Service - Indexes web content into long-term memory
"""
from typing import List, Dict, Any, Optional
from sqlalchemy.ext.asyncio import AsyncSession
from uuid import UUID
from datetime import datetime, timezone
import logging
import re

from app.core.memory_manager import MemoryManager

logger = logging.getLogger(__name__)


class WebIndexer:
    """Service for indexing web content into long-term memory"""
    
    def __init__(self, memory_manager: MemoryManager):
        self.memory_manager = memory_manager
    
    def extract_text_from_snapshot(self, snapshot: str) -> str:
        """
        Extract readable text from browser snapshot (accessibility snapshot format).
        Returns cleaned text content.
        """
        try:
            # Browser snapshots are typically in YAML-like format with accessibility tree
            # Extract text nodes and links
            text_content = []
            
            # Look for text patterns in snapshot
            # Common patterns: "text: ...", "value: ...", "aria-label: ..."
            text_patterns = [
                r'text:\s*"([^"]+)"',
                r'value:\s*"([^"]+)"',
                r'aria-label:\s*"([^"]+)"',
                r'name:\s*"([^"]+)"',
            ]
            
            for pattern in text_patterns:
                matches = re.findall(pattern, snapshot, re.IGNORECASE)
                text_content.extend(matches)
            
            # Also try to extract from plain text lines (not in quotes)
            lines = snapshot.split('\n')
            for line in lines:
                line = line.strip()
                # Skip YAML structure lines
                if line and not line.startswith('-') and not line.startswith('  ') and ':' not in line[:10]:
                    if len(line) > 10:  # Ignore very short lines
                        text_content.append(line)
            
            # Remove duplicates and join
            unique_text = []
            seen = set()
            for text in text_content:
                text = text.strip()
                if text and text not in seen and len(text) > 3:
                    seen.add(text)
                    unique_text.append(text)
            
            return "\n".join(unique_text[:100])  # Limit to first 100 items
            
        except Exception as e:
            logger.warning(f"Error extracting text from snapshot: {e}")
            # Fallback: return first 2000 chars of snapshot
            return snapshot[:2000]
    
    async def index_web_search_results(
        self,
        db: AsyncSession,
        search_query: str,
        results: List[Dict[str, Any]],
        session_id: UUID,
        importance_score: float = 0.6,
        tenant_id: Optional[UUID] = None,
    ) -> Dict[str, Any]:
        """
        Index web search results into long-term memory.
        """
        indexed_count = 0
        errors = []
        
        for result in results[:5]:  # Limit to top 5 results
            try:
                title = result.get('title', 'N/A')
                url = result.get('url', 'N/A')
                content = result.get('content', '')
                
                # Build content for indexing
                content_text = f"Web Search Result: {title}\nURL: {url}\n"
                if content:
                    # Truncate content to avoid overwhelming memory
                    content_preview = content[:2000] if len(content) > 2000 else content
                    content_text += f"Content: {content_preview}\n"
                
                content_text += f"Search Query: {search_query}"
                
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
                    content=content_text,
                    learned_from_sessions=[session_id],
                    importance_score=importance_score,
                    tenant_id=tenant_id,
                )
                
                indexed_count += 1
                logger.info(f"Indexed web search result: {title}")
                
            except Exception as e:
                errors.append(f"Result {result.get('url', 'unknown')}: {str(e)}")
                logger.error(f"Error indexing web search result: {e}")
        
        return {
            "indexed": indexed_count,
            "errors": errors,
            "total": len(results),
        }
    
    async def index_web_fetch_result(
        self,
        db: AsyncSession,
        url: str,
        result: Dict[str, Any],
        session_id: UUID,
        importance_score: float = 0.7,
        tenant_id: Optional[UUID] = None,
    ) -> bool:
        """
        Index a single web fetch result into long-term memory.
        Returns True if indexed, False otherwise.
        """
        try:
            title = result.get('title', 'N/A')
            content = result.get('content', '')
            
            if not content:
                logger.debug(f"No content to index for URL: {url}")
                return False
            
            # Build content for indexing
            content_text = f"Web Page: {title}\nURL: {url}\n\nContent:\n{content[:5000]}"  # Limit to 5000 chars
            
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
                content=content_text,
                learned_from_sessions=[session_id],
                importance_score=importance_score,
                tenant_id=tenant_id,
            )
            
            logger.info(f"Indexed web page: {title} ({url})")
            return True
            
        except Exception as e:
            logger.error(f"Error indexing web fetch result for {url}: {e}", exc_info=True)
            return False
    
    async def index_browser_snapshot(
        self,
        db: AsyncSession,
        url: str,
        snapshot: str,
        session_id: UUID,
        importance_score: float = 0.65,
    ) -> bool:
        """
        Index a browser snapshot into long-term memory.
        Returns True if indexed, False otherwise.
        """
        try:
            # Extract text from snapshot
            text_content = self.extract_text_from_snapshot(snapshot)
            
            if not text_content or len(text_content.strip()) < 50:
                logger.debug(f"Insufficient content extracted from snapshot for URL: {url}")
                return False
            
            # Build content for indexing
            content_text = f"Web Page Snapshot\nURL: {url}\n\nContent:\n{text_content[:5000]}"  # Limit to 5000 chars
            
            # Index in long-term memory
            await self.memory_manager.add_long_term_memory(
                db=db,
                content=content_text,
                learned_from_sessions=[session_id],
                importance_score=importance_score,
            )
            
            logger.info(f"Indexed browser snapshot for URL: {url}")
            return True
            
        except Exception as e:
            logger.error(f"Error indexing browser snapshot for {url}: {e}", exc_info=True)
            return False

