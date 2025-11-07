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
            # Comprehensive LLM-based prompt for logical contradiction detection
            # Works in any language, detects all types of contradictions
            prompt = f"""Analyze if these two statements logically contradict each other.

EXISTING STATEMENT: "{existing_memory}"
NEW STATEMENT: "{new_memory}"

Determine if there is a LOGICAL CONTRADICTION between these statements. Consider:

1. **Direct Contradictions**: Opposite claims (e.g., "single" vs "married", "likes X" vs "dislikes X")
2. **Temporal Contradictions**: Incompatible dates/events (e.g., "born July 12" vs "born August 15" for same person)
3. **Numerical Contradictions**: Incompatible values for same property (e.g., "age 30" vs "age 35" at same time)
4. **Status Contradictions**: Mutually exclusive states (e.g., "works at A" vs "works at B" simultaneously)
5. **Preference Contradictions**: Opposite preferences for the SAME or SEMANTICALLY RELATED things:
   - "likes pasta" vs "hates spaghetti" → CONTRADICTION (spaghetti is a type of pasta)
   - "likes pastasciutta" vs "hates spaghetti" → CONTRADICTION (both refer to pasta dishes)
   - "likes Italian food" vs "hates pasta" → CONTRADICTION (pasta is core to Italian food)
   - "likes pizza" vs "hates margherita" → CONTRADICTION (margherita is a type of pizza)
   - "likes red wine" vs "hates Chianti" → CONTRADICTION (Chianti is a type of red wine)
6. **Relationship Contradictions**: Incompatible relationships (e.g., "single" vs "has wife")
7. **Factual Contradictions**: Incompatible facts about the same entity

IMPORTANT:
- NOT contradictions: Complementary information, additional details, information about different time periods
- ARE contradictions: Statements that logically exclude each other
- Consider CONTEXT: "works at A in 2020" and "works at B in 2024" are NOT contradictions
- Consider SEMANTIC RELATIONSHIPS: 
  * If one statement is about a category and the other about a specific item in that category, and they have opposite preferences → CONTRADICTION
  * If both refer to the same semantic concept (e.g., "pastasciutta" = "spaghetti" = pasta dishes) with opposite preferences → CONTRADICTION
  * Examples of semantic relationships: pasta/spaghetti/pastasciutta, wine/Chianti, food/pizza, car/Ferrari, etc.

Respond ONLY with valid JSON (no other text):
{{
    "is_contradiction": true/false,
    "confidence": 0.0-1.0,
    "explanation": "brief explanation of the contradiction type or why there is no contradiction",
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

