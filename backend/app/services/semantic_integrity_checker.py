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
        Extract entities and semantic concepts from text.
        Uses regex patterns and keyword matching for common entity types.
        
        Returns:
            Dict with extracted entities: {
                "dates": [...], 
                "numbers": [...], 
                "keywords": [...],
                "concepts": [...]  # Semantic concepts (work, location, preferences, etc.)
            }
        """
        entities = {
            "dates": [],
            "numbers": [],
            "keywords": [],
            "concepts": [],  # Semantic concepts for contradiction detection
        }
        
        # Extract dates (various formats) - use full match to get complete dates
        date_patterns = [
            (r'\d{1,2}[/-]\d{1,2}[/-]\d{2,4}', lambda m: m.group(0)),  # DD/MM/YYYY or DD-MM-YYYY
            (r'\d{1,2}\s+(gennaio|febbraio|marzo|aprile|maggio|giugno|luglio|agosto|settembre|ottobre|novembre|dicembre)\s+\d{2,4}', lambda m: m.group(0)),  # "12 luglio 1966"
            (r'(gennaio|febbraio|marzo|aprile|maggio|giugno|luglio|agosto|settembre|ottobre|novembre|dicembre)\s+\d{1,2},?\s+\d{2,4}', lambda m: m.group(0)),  # "luglio 12, 1966"
            (r'\d{1,2}\s+(gen|feb|mar|apr|mag|giu|lug|ago|set|ott|nov|dic)\s+\d{2,4}', lambda m: m.group(0)),  # "12 lug 1966"
        ]
        
        for pattern, extractor in date_patterns:
            matches = re.finditer(pattern, text, re.IGNORECASE)
            for match in matches:
                entities["dates"].append(extractor(match))
        
        # Extract numbers (integers and decimals)
        number_pattern = r'\b\d+(?:\.\d+)?\b'
        numbers = re.findall(number_pattern, text)
        entities["numbers"] = [float(n) if '.' in n else int(n) for n in numbers]
        
        # Extract keywords and semantic concepts
        text_lower = text.lower()
        
        # Personal info keywords
        personal_keywords = [
            'nato', 'compleanno', 'nascita', 'data di nascita', 'born',
            'altezza', 'peso', 'età', 'age', 'height', 'weight',
            'indirizzo', 'città', 'paese', 'address', 'city', 'country',
            'residenza', 'residence', 'domicilio',
        ]
        
        # Work/professional keywords
        work_keywords = [
            'lavoro', 'azienda', 'posizione', 'ruolo', 'job', 'work', 'company', 'position', 'role',
            'impiego', 'occupazione', 'professione', 'employment', 'occupation', 'profession',
            'dipendente', 'freelance', 'autonomo', 'employee', 'self-employed',
        ]
        
        # Preferences keywords
        preference_keywords = [
            'preferisco', 'preferisce', 'preferenza', 'preferisci', 'preferiamo', 'preferiscono',
            'prefers', 'preference', 'prefer',
            'ama', 'non ama', 'piace', 'non piace', 'loves', 'hates', 'likes', 'dislikes',
            'favorisce', 'favors', 'evita', 'avoids',
        ]
        
        # Relationship keywords
        relationship_keywords = [
            'sposo', 'sposa', 'moglie', 'marito', 'spouse', 'wife', 'husband',
            'figlio', 'figlia', 'son', 'daughter', 'child',
            'genitore', 'parent', 'madre', 'padre', 'mother', 'father',
        ]
        
        # Status keywords (for contradictions like "single" vs "married")
        status_keywords = [
            'single', 'celibe', 'nubile', 'sposato', 'married', 'divorziato', 'divorced',
            'fidanzato', 'engaged', 'convivente', 'cohabiting',
        ]
        
        # Collect all keywords - use word boundaries to avoid partial matches
        all_keywords = personal_keywords + work_keywords + preference_keywords + relationship_keywords + status_keywords
        for keyword in all_keywords:
            # Use word boundaries to avoid matching "son" in "sono" or "son" in "person"
            pattern = r'\b' + re.escape(keyword) + r'\b'
            if re.search(pattern, text_lower):
                entities["keywords"].append(keyword)
        
        # Extract semantic concepts (categorize the type of information)
        concepts = []
        if any(kw in text_lower for kw in personal_keywords):
            concepts.append("personal_info")
        if any(kw in text_lower for kw in work_keywords):
            concepts.append("work_info")
        if any(kw in text_lower for kw in preference_keywords):
            concepts.append("preference")
        if any(kw in text_lower for kw in relationship_keywords):
            concepts.append("relationship")
        if any(kw in text_lower for kw in status_keywords):
            concepts.append("status")
        
        entities["concepts"] = list(set(concepts))  # Remove duplicates
        
        return entities
    
    def _entities_conflict(self, new_entities: Dict[str, Any], existing_entities: Dict[str, Any]) -> bool:
        """
        Check if extracted entities conflict.
        This is a fast pre-filter - the LLM will do the deep semantic analysis.
        Returns True if there's a potential conflict worth checking with LLM.
        """
        # Check if they share semantic concepts (same type of information)
        new_concepts = set(new_entities.get("concepts", []))
        existing_concepts = set(existing_entities.get("concepts", []))
        
        if not new_concepts.intersection(existing_concepts):
            # Different types of information - unlikely to conflict
            return False
        
        # They share concepts - check for potential conflicts
        
        # Check dates conflict (for same concept type)
        if new_entities.get("dates") and existing_entities.get("dates"):
            new_dates = set(new_entities["dates"])
            existing_dates = set(existing_entities["dates"])
            if new_dates and existing_dates and not new_dates.intersection(existing_dates):
                # Different dates for same concept type - potential conflict
                return True
        
        # Check numbers conflict (for same keyword context)
        if new_entities.get("numbers") and existing_entities.get("numbers"):
            new_keywords = set(new_entities.get("keywords", []))
            existing_keywords = set(existing_entities.get("keywords", []))
            
            if new_keywords.intersection(existing_keywords):
                # Same keywords but different numbers - potential conflict
                new_nums = set(new_entities["numbers"])
                existing_nums = set(existing_entities["numbers"])
                if new_nums and existing_nums and not new_nums.intersection(existing_nums):
                    return True
        
        # Check for mutually exclusive keywords (e.g., "single" vs "married")
        mutually_exclusive_pairs = [
            (["single", "celibe", "nubile"], ["married", "sposato", "sposa", "moglie", "marito"]),
            (["divorced", "divorziato"], ["married", "sposato"]),
            (["loves", "ama", "piace"], ["hates", "non ama", "non piace", "dislikes"]),
        ]
        
        new_keywords = set(new_entities.get("keywords", []))
        existing_keywords = set(existing_entities.get("keywords", []))
        
        for group1, group2 in mutually_exclusive_pairs:
            has_group1_new = any(kw in new_keywords for kw in group1)
            has_group2_existing = any(kw in existing_keywords for kw in group2)
            has_group2_new = any(kw in new_keywords for kw in group2)
            has_group1_existing = any(kw in existing_keywords for kw in group1)
            
            if (has_group1_new and has_group2_existing) or (has_group2_new and has_group1_existing):
                # Mutually exclusive keywords found - definite conflict
                return True
        
        # If they share concepts and keywords, worth checking with LLM
        # (even if no obvious conflict, semantic analysis might find one)
        if new_concepts.intersection(existing_concepts) and new_keywords.intersection(existing_keywords):
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

            # Use a comprehensive prompt that guides LLM to detect logical contradictions
            prompt = f"""Analizza se queste due informazioni si contraddicono logicamente.

INFORMAZIONE ESISTENTE: "{existing_memory}"
INFORMAZIONE NUOVA: "{new_memory}"

Verifica se ci sono CONTRADDIZIONI LOGICHE tra le due informazioni. Considera:

1. **Contraddizioni dirette**: Affermazioni opposte (es: "single" vs "sposato", "ama X" vs "non ama X")
2. **Contraddizioni temporali**: Date/eventi incompatibili (es: "nato il 12 luglio" vs "compleanno 15 agosto")
3. **Contraddizioni numeriche**: Valori incompatibili per la stessa proprietà (es: "età 30" vs "età 35" nella stessa data)
4. **Contraddizioni di stato**: Stati mutuamente esclusivi (es: "lavora in A" vs "lavora in B" contemporaneamente)
5. **Contraddizioni di preferenza**: Preferenze opposte (es: "preferisce X" vs "preferisce Y" per la stessa cosa)
6. **Contraddizioni di relazione**: Relazioni incompatibili (es: "single" vs "ha moglie")

IMPORTANTE:
- NON sono contraddizioni: informazioni complementari, dettagli aggiuntivi, informazioni su periodi diversi
- SONO contraddizioni: affermazioni che si escludono a vicenda logicamente
- Considera il CONTESTO: "lavora in A nel 2020" e "lavora in B nel 2024" NON sono contraddizioni

Rispondi SOLO con JSON (nessun altro testo):
{{
    "is_contradiction": true/false,
    "confidence": 0.0-1.0,
    "explanation": "breve spiegazione del tipo di contraddizione o perché non c'è contraddizione",
    "contradiction_type": "direct|temporal|numerical|status|preference|relationship|none"
}}"""

            response = await self.ollama_client.generate_with_context(
                prompt=prompt,
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

