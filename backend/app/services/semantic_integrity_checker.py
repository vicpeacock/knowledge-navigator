"""
Semantic Integrity Checker - Detects contradictions in long-term memory
"""
from typing import List, Dict, Any, Optional
from sqlalchemy.ext.asyncio import AsyncSession
from uuid import UUID
import logging
import re
import json

from app.core.memory_manager import MemoryManager
from app.core.ollama_client import OllamaClient
from app.services.embedding_service import EmbeddingService
from app.core.config import settings

logger = logging.getLogger(__name__)


class SemanticIntegrityChecker:
    """Service for checking semantic integrity and detecting contradictions"""
    
    def __init__(self, memory_manager: MemoryManager, ollama_client: Optional[OllamaClient] = None):
        self.memory_manager = memory_manager
        self.ollama_client = ollama_client or OllamaClient()
        self.embedding_service = EmbeddingService()
    
    async def check_contradictions(
        self,
        new_knowledge: Dict[str, Any],
        db: AsyncSession,
        max_similar_memories: int = None,
        confidence_threshold: float = None,
    ) -> Dict[str, Any]:
        """
        Check if new knowledge contradicts existing memories.
        Executed in background, can be exhaustive.
        
        Args:
            new_knowledge: New knowledge item to check (from ConversationLearner)
            db: Database session
            max_similar_memories: Max number of similar memories to check (default from config)
            confidence_threshold: Confidence threshold for contradictions (default from config)
            
        Returns:
            Dict with contradiction information
        """
        max_similar = max_similar_memories or settings.integrity_max_similar_memories
        threshold = confidence_threshold or settings.integrity_confidence_threshold
        
        try:
            # Extract content from knowledge item
            content = new_knowledge.get("content", "")
            if not content:
                return {
                    "has_contradiction": False,
                    "contradictions": [],
                    "confidence": 0.0,
                }
            
            # Remove type prefix if present (e.g., "[FACT] ...")
            clean_content = re.sub(r'^\[.*?\]\s*', '', content).strip()
            
            # 1. Find similar memories using semantic search
            similar_memories = await self._find_similar_memories(
                clean_content,
                n_results=max_similar
            )
            
            if not similar_memories:
                return {
                    "has_contradiction": False,
                    "contradictions": [],
                    "confidence": 0.0,
                }
            
            logger.info(f"Found {len(similar_memories)} similar memories to check for contradictions")
            
            # 2. Extract entities from new knowledge
            new_entities = self._extract_entities(clean_content)
            
            # 3. Compare with each similar memory
            contradictions = []
            for memory_content in similar_memories:
                # Clean memory content (remove type prefix)
                clean_memory = re.sub(r'^\[.*?\]\s*', '', memory_content).strip()
                
                # Extract entities from existing memory
                existing_entities = self._extract_entities(clean_memory)
                
                # Check if entities conflict
                if self._entities_conflict(new_entities, existing_entities):
                    logger.info(f"Potential contradiction detected, analyzing with LLM...")
                    # 4. Use LLM for deep analysis
                    contradiction = await self._analyze_with_llm(
                        clean_content,
                        clean_memory,
                        threshold
                    )
                    
                    if contradiction.get("is_contradiction") and contradiction.get("confidence", 0) >= threshold:
                        contradiction["new_memory"] = clean_content
                        contradiction["existing_memory"] = clean_memory
                        contradictions.append(contradiction)
                        logger.warning(f"Contradiction confirmed: {contradiction.get('explanation', 'No explanation')}")
            
            return {
                "has_contradiction": len(contradictions) > 0,
                "contradictions": contradictions,
                "confidence": max([c.get("confidence", 0) for c in contradictions]) if contradictions else 0.0,
            }
            
        except Exception as e:
            logger.error(f"Error checking contradictions: {e}", exc_info=True)
            return {
                "has_contradiction": False,
                "contradictions": [],
                "confidence": 0.0,
                "error": str(e),
            }
    
    async def _find_similar_memories(self, content: str, n_results: int = 10) -> List[str]:
        """Find similar memories using semantic search"""
        try:
            # Use long-term memory retrieval with high similarity threshold
            similar = await self.memory_manager.retrieve_long_term_memory(
                content,
                n_results=n_results,
            )
            return similar
        except Exception as e:
            logger.error(f"Error finding similar memories: {e}", exc_info=True)
            return []
    
    def _extract_entities(self, text: str) -> Dict[str, Any]:
        """
        Extract entities (dates, numbers, names) from text.
        Uses regex patterns for common entity types.
        
        Returns:
            Dict with extracted entities: {"dates": [...], "numbers": [...], "keywords": [...]}
        """
        entities = {
            "dates": [],
            "numbers": [],
            "keywords": [],
        }
        
        # Extract dates (various formats)
        date_patterns = [
            r'\d{1,2}[/-]\d{1,2}[/-]\d{2,4}',  # DD/MM/YYYY or DD-MM-YYYY
            r'\d{1,2}\s+(gennaio|febbraio|marzo|aprile|maggio|giugno|luglio|agosto|settembre|ottobre|novembre|dicembre)\s+\d{2,4}',
            r'(gennaio|febbraio|marzo|aprile|maggio|giugno|luglio|agosto|settembre|ottobre|novembre|dicembre)\s+\d{1,2},?\s+\d{2,4}',
            r'\d{1,2}\s+(gen|feb|mar|apr|mag|giu|lug|ago|set|ott|nov|dic)\s+\d{2,4}',
        ]
        
        for pattern in date_patterns:
            matches = re.findall(pattern, text, re.IGNORECASE)
            entities["dates"].extend(matches)
        
        # Extract numbers (integers and decimals)
        number_pattern = r'\b\d+(?:\.\d+)?\b'
        numbers = re.findall(number_pattern, text)
        entities["numbers"] = [float(n) if '.' in n else int(n) for n in numbers]
        
        # Extract keywords (important words like "nato", "compleanno", "altezza", etc.)
        important_keywords = [
            'nato', 'compleanno', 'nascita', 'data di nascita',
            'altezza', 'peso', 'età',
            'indirizzo', 'città', 'paese',
            'lavoro', 'azienda', 'posizione',
            'preferisce', 'preferenza',
        ]
        
        text_lower = text.lower()
        for keyword in important_keywords:
            if keyword in text_lower:
                entities["keywords"].append(keyword)
        
        return entities
    
    def _entities_conflict(self, new_entities: Dict[str, Any], existing_entities: Dict[str, Any]) -> bool:
        """
        Check if extracted entities conflict.
        Returns True if there's a potential conflict.
        """
        # Check dates conflict
        if new_entities.get("dates") and existing_entities.get("dates"):
            # If both have dates and they're different, potential conflict
            new_dates = set(new_entities["dates"])
            existing_dates = set(existing_entities["dates"])
            if new_dates and existing_dates and not new_dates.intersection(existing_dates):
                # Different dates found
                return True
        
        # Check numbers conflict (for same keyword context)
        if new_entities.get("numbers") and existing_entities.get("numbers"):
            # If both have numbers and keywords overlap, check if numbers are very different
            new_keywords = set(new_entities.get("keywords", []))
            existing_keywords = set(existing_entities.get("keywords", []))
            
            if new_keywords.intersection(existing_keywords):
                # Same keywords but different numbers might be a conflict
                # This is a simple heuristic - LLM will do deeper analysis
                new_nums = set(new_entities["numbers"])
                existing_nums = set(existing_entities["numbers"])
                if new_nums and existing_nums and not new_nums.intersection(existing_nums):
                    # Different numbers for same keywords
                    return True
        
        # Check keywords conflict (mutually exclusive preferences)
        new_keywords = set(new_entities.get("keywords", []))
        existing_keywords = set(existing_entities.get("keywords", []))
        
        # If both mention same type of info (e.g., both have "compleanno" or "nato")
        # but with different values, potential conflict
        if new_keywords.intersection(existing_keywords):
            # Same type of information - check if values differ
            # This is a simple check - LLM will do deeper analysis
            return True
        
        return False
    
    async def _analyze_with_llm(
        self,
        new_memory: str,
        existing_memory: str,
        confidence_threshold: float,
    ) -> Dict[str, Any]:
        """
        Use LLM to analyze if memories contradict.
        
        Returns:
            {
                "is_contradiction": bool,
                "confidence": float,
                "explanation": str
            }
        """
        try:
            prompt = f"""Analizza queste due memorie e determina se si contraddicono.

Memoria esistente: "{existing_memory}"

Memoria nuova: "{new_memory}"

Le memorie si contraddicono? (sì/no)
Se sì, quale informazione è corretta? (memoria esistente, memoria nuova, o entrambe potrebbero essere corrette)
Motivazione: [spiegazione breve]

Rispondi in formato JSON:
{{
    "is_contradiction": true/false,
    "confidence": 0.0-1.0,
    "explanation": "spiegazione",
    "which_correct": "existing" | "new" | "both" | "unknown"
}}"""

            # Use a simpler prompt for background agent (faster)
            simple_prompt = f"""Analizza se queste due informazioni si contraddicono:

1. "{existing_memory}"
2. "{new_memory}"

Rispondi SOLO con JSON:
{{"is_contradiction": true/false, "confidence": 0.0-1.0, "explanation": "breve spiegazione"}}"""

            response = await self.ollama_client.generate_with_context(
                prompt=simple_prompt,
                session_context=[],
                retrieved_memory=None,
                tools=None,
                tools_description=None,
                format="json",
                return_raw=False,
            )
            
            # Parse JSON response
            try:
                # Try to extract JSON from response
                json_match = re.search(r'\{.*\}', response, re.DOTALL)
                if json_match:
                    parsed = json.loads(json_match.group())
                else:
                    parsed = json.loads(response)
                
                return {
                    "is_contradiction": parsed.get("is_contradiction", False),
                    "confidence": float(parsed.get("confidence", 0.0)),
                    "explanation": parsed.get("explanation", ""),
                    "which_correct": parsed.get("which_correct", "unknown"),
                }
            except json.JSONDecodeError:
                # Fallback: try to parse from text
                is_contradiction = "sì" in response.lower() or "yes" in response.lower() or "true" in response.lower()
                return {
                    "is_contradiction": is_contradiction,
                    "confidence": 0.7 if is_contradiction else 0.0,  # Lower confidence if can't parse
                    "explanation": response[:200],  # First 200 chars
                    "which_correct": "unknown",
                }
                
        except Exception as e:
            logger.error(f"Error analyzing with LLM: {e}", exc_info=True)
            return {
                "is_contradiction": False,
                "confidence": 0.0,
                "explanation": f"Error: {str(e)}",
                "which_correct": "unknown",
            }

