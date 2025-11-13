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
        self.ollama_client = ollama_client
        self.embedding_service = EmbeddingService()
        self.enabled = self.ollama_client is not None
    
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
        if not self.enabled:
            logger.info("Semantic integrity checker disabled (no background LLM available)")
            return {
                "has_contradiction": False,
                "contradictions": [],
                "confidence": 0.0,
                "disabled": True,
            }

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
            
            # 1. Find similar memories using semantic search (filter by importance)
            min_importance = settings.integrity_min_importance
            similar_memories = await self._find_similar_memories(
                clean_content,
                n_results=max_similar,
                min_importance=min_importance
            )
            
            if not similar_memories:
                return {
                    "has_contradiction": False,
                    "contradictions": [],
                    "confidence": 0.0,
                }
            
            logger.info(f"Found {len(similar_memories)} similar memories to check for contradictions")
            
            # 2. Analyze all similar memories with LLM (fully LLM-based, no hard-coded heuristics)
            # Since llama.cpp is fast, we can afford to use LLM for all cases
            contradictions = []
            
            for memory_content in similar_memories:
                # Clean memory content (remove type prefix)
                clean_memory = re.sub(r'^\[.*?\]\s*', '', memory_content).strip()
                
                logger.info(f"Analyzing potential contradiction with LLM (fully LLM-based)...")
                logger.info(f"  New: '{clean_content[:100]}...'")
                logger.info(f"  Existing: '{clean_memory[:100]}...'")
                
                # Use LLM for complete semantic analysis (no pre-filtering)
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
    
    async def _find_similar_memories(self, content: str, n_results: int = 10, min_importance: float = None) -> List[str]:
        """Find similar memories using semantic search, optionally filtered by importance"""
        try:
            logger.info(f"Searching for similar memories to: '{content[:100]}...' (min_importance={min_importance})")
            # Use long-term memory retrieval with optional importance filter
            similar = await self.memory_manager.retrieve_long_term_memory(
                content,
                n_results=n_results,
                min_importance=min_importance,
            )
            logger.info(f"Found {len(similar)} similar memories: {[s[:50] + '...' if len(s) > 50 else s for s in similar[:3]]}")
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
        if not self.ollama_client:
            logger.info("Skipping LLM contradiction analysis: background client unavailable")
            return {
                "is_contradiction": False,
                "confidence": 0.0,
                "explanation": "Background LLM unavailable",
                "which_correct": "unknown",
            }

        try:
            # Comprehensive LLM-based prompt for logical contradiction detection
            # Works in any language, detects all types of contradictions
            prompt = f"""Analyze if these two statements logically contradict each other.

EXISTING STATEMENT: "{existing_memory}"
NEW STATEMENT: "{new_memory}"

Determine if there is a LOGICAL CONTRADICTION between these statements. You must reason carefully about:

1. **Direct Contradictions**: Opposite claims about the same thing
2. **Temporal Contradictions**: Incompatible dates/events for the same entity
3. **Numerical Contradictions**: Incompatible values for the same property at the same time
4. **Status Contradictions**: Mutually exclusive states
5. **Preference Contradictions**: Opposite preferences (likes vs dislikes, loves vs hates)
6. **Relationship Contradictions**: Incompatible relationships
7. **Factual Contradictions**: Incompatible facts about the same entity

**CRITICAL: TAXONOMIC RELATIONSHIPS**
Contradictions can occur at different levels of a taxonomy (hierarchy):
- If one statement is about a CATEGORY and the other about an INSTANCE or SUBCATEGORY of that category, and they express opposite preferences/claims → CONTRADICTION
- You must reason about whether the entities mentioned are taxonomically related (category-instance, category-subcategory, or semantically equivalent)
- Consider: if someone likes a category but hates an instance of that category, that is a contradiction
- Consider: if someone likes a general concept but hates a specific manifestation of that concept, that is a contradiction

**EXAMPLES OF TAXONOMIC CONTRADICTIONS:**
- "Likes pasta" vs "Hates spaghetti" → CONTRADICTION (spaghetti is a type of pasta)
- "Loves Italian food" vs "Hates ravioli" → CONTRADICTION (ravioli is Italian food)
- "Enjoys music" vs "Hates jazz" → CONTRADICTION (jazz is a type of music)
- "Likes animals" vs "Hates dogs" → CONTRADICTION (dogs are animals)

**IMPORTANT:** When analyzing preferences, you MUST check if the entities are taxonomically related. If one is a category and the other is an instance/subcategory of that category, and the preferences are opposite, it IS a contradiction.

**Reasoning Process:**
1. Identify what each statement is about (entity, category, instance, property)
2. Determine if they refer to the same or taxonomically related things
3. Check if the claims/preferences are opposite
4. Consider if they logically exclude each other

**NOT contradictions:**
- Complementary information
- Additional details that don't conflict
- Information about different time periods
- Different but compatible aspects

**ARE contradictions:**
- Statements that logically exclude each other
- Opposite preferences for the same or taxonomically related things
- Incompatible facts about the same entity

Think step by step, then respond ONLY with valid JSON (no other text):
{{
    "is_contradiction": true/false,
    "confidence": 0.0-1.0,
    "explanation": "brief explanation of your reasoning and the contradiction type or why there is no contradiction",
    "contradiction_type": "direct|temporal|numerical|status|preference|relationship|factual|none"
}}"""

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
                
                # Handle typo in LLM response: "is_contriction" -> "is_contradiction"
                is_contradiction = parsed.get("is_contradiction", parsed.get("is_contriction", False))
                
                return {
                    "is_contradiction": is_contradiction,
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

