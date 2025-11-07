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
            
            # 2. Fast pre-filtering: check for obvious contradictions before LLM
            # This reduces LLM calls significantly
            contradictions = []
            new_entities = self._extract_entities(clean_content)
            
            for memory_content in similar_memories:
                # Clean memory content (remove type prefix)
                clean_memory = re.sub(r'^\[.*?\]\s*', '', memory_content).strip()
                
                # Extract entities from existing memory
                existing_entities = self._extract_entities(clean_memory)
                
                # Fast pre-filter: check for obvious contradictions (dates, numbers, direct opposites)
                fast_check = self._fast_contradiction_check(clean_content, clean_memory, new_entities, existing_entities)
                
                if fast_check.get("is_contradiction"):
                    # Fast check found contradiction - use it directly (high confidence)
                    fast_check["new_memory"] = clean_content
                    fast_check["existing_memory"] = clean_memory
                    contradictions.append(fast_check)
                    logger.info(f"✅ Fast check found contradiction: {fast_check.get('explanation', '')[:100]}...")
                    continue  # Skip LLM call for this memory
                
                # If fast check didn't find contradiction, use LLM for deeper analysis
                # But only if entities suggest potential conflict
                should_check_llm = False
                if new_entities.get("dates") or existing_entities.get("dates") or \
                   new_entities.get("numbers") or existing_entities.get("numbers"):
                    should_check_llm = self._entities_conflict(new_entities, existing_entities)
                else:
                    # No dates/numbers, but semantic similarity is high - check with LLM
                    # But limit to top 3 most similar to avoid too many LLM calls
                    memory_index = similar_memories.index(memory_content) if memory_content in similar_memories else len(similar_memories)
                    if len(contradictions) == 0 and memory_index < 3:
                        should_check_llm = True
                
                if should_check_llm:
                    logger.info(f"Analyzing potential contradiction with LLM (language-agnostic)...")
                    logger.info(f"  New: '{clean_content[:100]}...'")
                    logger.info(f"  Existing: '{clean_memory[:100]}...'")
                    # Use LLM for semantic analysis (works in any language)
                    contradiction = await self._analyze_with_llm(
                        clean_content,
                        clean_memory,
                        threshold
                    )
                    
                    logger.info(f"LLM analysis result: is_contradiction={contradiction.get('is_contradiction')}, confidence={contradiction.get('confidence', 0):.2f}, threshold={threshold:.2f}")
                    
                    if contradiction.get("is_contradiction") and contradiction.get("confidence", 0) >= threshold:
                        contradiction["new_memory"] = clean_content
                        contradiction["existing_memory"] = clean_memory
                        contradictions.append(contradiction)
                        logger.warning(f"✅ Contradiction confirmed: {contradiction.get('explanation', 'No explanation')[:100]}...")
                    else:
                        logger.info(f"❌ No contradiction (is_contradiction={contradiction.get('is_contradiction')}, confidence={contradiction.get('confidence', 0):.2f} < threshold={threshold:.2f})")
            
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
        Extract basic entities from text (language-agnostic).
        Only extracts dates and numbers - semantic analysis is done by LLM.
        
        Returns:
            Dict with extracted entities: {
                "dates": [...],  # Extracted dates (various formats)
                "numbers": [...],  # Extracted numbers
            }
        """
        entities = {
            "dates": [],
            "numbers": [],
        }
        
        # Extract dates (various formats) - language-agnostic patterns
        # These patterns work for many languages (Italian, English, etc.)
        date_patterns = [
            (r'\d{1,2}[/-]\d{1,2}[/-]\d{2,4}', lambda m: m.group(0)),  # DD/MM/YYYY or DD-MM-YYYY
            # Italian month names
            (r'\d{1,2}\s+(gennaio|febbraio|marzo|aprile|maggio|giugno|luglio|agosto|settembre|ottobre|novembre|dicembre)\s+\d{2,4}', lambda m: m.group(0)),
            (r'(gennaio|febbraio|marzo|aprile|maggio|giugno|luglio|agosto|settembre|ottobre|novembre|dicembre)\s+\d{1,2},?\s+\d{2,4}', lambda m: m.group(0)),
            (r'\d{1,2}\s+(gen|feb|mar|apr|mag|giu|lug|ago|set|ott|nov|dic)\s+\d{2,4}', lambda m: m.group(0)),
            # English month names
            (r'\d{1,2}\s+(january|february|march|april|may|june|july|august|september|october|november|december)\s+\d{2,4}', lambda m: m.group(0)),
            (r'(january|february|march|april|may|june|july|august|september|october|november|december)\s+\d{1,2},?\s+\d{2,4}', lambda m: m.group(0)),
            (r'\d{1,2}\s+(jan|feb|mar|apr|may|jun|jul|aug|sep|oct|nov|dec)\s+\d{2,4}', lambda m: m.group(0)),
        ]
        
        for pattern, extractor in date_patterns:
            matches = re.finditer(pattern, text, re.IGNORECASE)
            for match in matches:
                entities["dates"].append(extractor(match))
        
        # Extract numbers (integers and decimals) - universal
        number_pattern = r'\b\d+(?:\.\d+)?\b'
        numbers = re.findall(number_pattern, text)
        entities["numbers"] = [float(n) if '.' in n else int(n) for n in numbers]
        
        return entities
    
    def _fast_contradiction_check(
        self,
        new_text: str,
        existing_text: str,
        new_entities: Dict[str, Any],
        existing_entities: Dict[str, Any],
    ) -> Dict[str, Any]:
        """
        Fast pre-filtering for obvious contradictions without LLM.
        Returns dict with is_contradiction, confidence, explanation if found, else empty.
        """
        # Check for different dates (high confidence contradiction)
        if new_entities.get("dates") and existing_entities.get("dates"):
            new_dates = set(new_entities["dates"])
            existing_dates = set(existing_entities["dates"])
            if new_dates and existing_dates and not new_dates.intersection(existing_dates):
                # Different dates - likely contradiction
                return {
                    "is_contradiction": True,
                    "confidence": 0.9,  # High confidence for different dates
                    "explanation": f"Different dates found: {list(new_dates)[0]} vs {list(existing_dates)[0]}",
                    "contradiction_type": "temporal",
                }
        
        # Check for direct opposites (common patterns)
        opposites = [
            ("single", "sposato", "married", "moglie", "wife"),
            ("single", "fidanzato", "engaged"),
            ("lavora", "non lavora", "disoccupato", "unemployed"),
            ("ama", "non ama", "odia", "hates"),
            ("preferisce", "non preferisce", "evita", "avoids"),
        ]
        
        new_lower = new_text.lower()
        existing_lower = existing_text.lower()
        
        for group in opposites:
            new_has = any(word in new_lower for word in group)
            existing_has = any(word in existing_lower for word in group)
            if new_has and existing_has:
                # Check if they're opposite (one has first word, other has different word from group)
                new_first = any(new_lower.count(group[0]) > 0 for word in group[:2])
                existing_other = any(existing_lower.count(word) > 0 for word in group[2:])
                if new_first and existing_other:
                    return {
                        "is_contradiction": True,
                        "confidence": 0.85,
                        "explanation": f"Direct opposite found in status/preference",
                        "contradiction_type": "direct",
                    }
        
        # No fast contradiction found
        return {
            "is_contradiction": False,
            "confidence": 0.0,
            "explanation": "",
            "contradiction_type": "none",
        }
    
    def _entities_conflict(self, new_entities: Dict[str, Any], existing_entities: Dict[str, Any]) -> bool:
        """
        Check if extracted entities suggest a potential conflict.
        This is a lightweight pre-filter - the LLM will do the deep semantic analysis.
        Returns True if there's a potential conflict worth checking with LLM.
        
        Since we removed language-specific keywords, we only check:
        - Different dates (might indicate contradiction)
        - Different numbers (might indicate contradiction)
        - If both have dates/numbers, it's worth checking with LLM
        """
        # If both have dates and they're different, potential conflict
        if new_entities.get("dates") and existing_entities.get("dates"):
            new_dates = set(new_entities["dates"])
            existing_dates = set(existing_entities["dates"])
            if new_dates and existing_dates and not new_dates.intersection(existing_dates):
                # Different dates - potential conflict (LLM will determine if it's a real contradiction)
                return True
        
        # If both have numbers and they're different, potential conflict
        # (but this is less reliable without context, so we're more conservative)
        if new_entities.get("numbers") and existing_entities.get("numbers"):
            new_nums = set(new_entities["numbers"])
            existing_nums = set(existing_entities["numbers"])
            if new_nums and existing_nums and not new_nums.intersection(existing_nums):
                # Different numbers - might be a conflict (LLM will analyze context)
                # But we're more conservative here since numbers alone don't mean much
                # Only flag if there are also dates (suggests same type of info)
                if new_entities.get("dates") or existing_entities.get("dates"):
                    return True
        
        # If both have dates or both have numbers, it's worth checking with LLM
        # (semantic similarity search already filtered similar memories)
        if (new_entities.get("dates") and existing_entities.get("dates")) or \
           (new_entities.get("numbers") and existing_entities.get("numbers")):
            return True
        
        # Default: let LLM decide based on semantic similarity
        # If memories are semantically similar (found by search), check them
        return True
    
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

            # Ultra-simplified prompt for phi3:mini (very small model, needs minimal prompts)
            prompt = f"""Do these contradict? Answer JSON only.

EXISTING: "{existing_memory}"
NEW: "{new_memory}"

JSON: {{"is_contradiction": true/false, "confidence": 0.0-1.0, "explanation": "why", "contradiction_type": "temporal|direct|none"}}"""

            logger.info(f"Calling LLM for contradiction analysis (model: {self.ollama_client.model}, base_url: {self.ollama_client.base_url})")
            # Don't use format="json" for phi3:mini - it's too slow, parse JSON from text response instead
            response = await self.ollama_client.generate_with_context(
                prompt=prompt,
                session_context=[],
                retrieved_memory=None,
                tools=None,
                tools_description=None,
                format=None,  # No strict JSON mode for faster response
                return_raw=False,
            )
            
            logger.info(f"LLM raw response (first 500 chars): {response[:500]}")
            
            # Parse JSON response
            try:
                # Try to extract JSON from response
                json_match = re.search(r'\{.*\}', response, re.DOTALL)
                if json_match:
                    parsed = json.loads(json_match.group())
                    logger.info(f"Parsed JSON: {parsed}")
                else:
                    parsed = json.loads(response)
                    logger.info(f"Parsed JSON (direct): {parsed}")
                
                return {
                    "is_contradiction": parsed.get("is_contradiction", False),
                    "confidence": float(parsed.get("confidence", 0.0)),
                    "explanation": parsed.get("explanation", ""),
                    "which_correct": parsed.get("which_correct", "unknown"),
                    "contradiction_type": parsed.get("contradiction_type", "none"),
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

