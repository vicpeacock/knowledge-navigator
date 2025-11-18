"""
Email Analyzer Service - Analyzes emails using LLM to detect actions and categorize
"""
import logging
import json
from typing import Dict, Any, Optional
from app.core.ollama_client import OllamaClient

logger = logging.getLogger(__name__)


class EmailAnalyzer:
    """Analyzes emails to detect required actions and categorize them"""
    
    def __init__(self, ollama_client: Optional[OllamaClient] = None):
        self.ollama_client = ollama_client or OllamaClient()
    
    async def analyze_email(
        self,
        email: Dict[str, Any],
    ) -> Dict[str, Any]:
        """
        Analyze email and return:
        - category: "direct" | "mailing_list" | "promotional" | "update" | "social" | "unknown"
        - requires_action: bool
        - action_type: "reply" | "calendar_event" | "task" | "info" | None
        - action_summary: str (description of required action)
        - urgency: "high" | "medium" | "low"
        
        Args:
            email: Email dict with keys: id, subject, from, to, snippet, body (optional), category (optional)
            
        Returns:
            Analysis dict with category, requires_action, action_type, action_summary, urgency
        """
        # First, use Gmail category if available
        gmail_category = email.get("category", "unknown")
        
        # If category is already determined by Gmail, use it
        # Otherwise, analyze with LLM
        if gmail_category != "unknown":
            # Use Gmail category, but still analyze for actions
            category = gmail_category
        else:
            # Fallback to LLM analysis if Gmail category not available
            category = await self._analyze_category_with_llm(email)
        
        # Always analyze for actions using LLM
        action_analysis = await self._analyze_actions_with_llm(email, category)
        
        return {
            "category": category,
            "requires_action": action_analysis.get("requires_action", False),
            "action_type": action_analysis.get("action_type"),
            "action_summary": action_analysis.get("action_summary", ""),
            "urgency": action_analysis.get("urgency", "medium"),
            "reasoning": action_analysis.get("reasoning", ""),
        }
    
    async def _analyze_category_with_llm(self, email: Dict[str, Any]) -> str:
        """Use LLM to determine email category if Gmail labels not available"""
        prompt = f"""Analizza questa email e determina il tipo:

Mittente: {email.get('from', 'Unknown')}
Oggetto: {email.get('subject', 'No Subject')}
Contenuto: {email.get('snippet', email.get('body', ''))[:500]}

Determina se è:
- "direct": Email diretta all'utente (richiede attenzione)
- "mailing_list": Email da mailing list o gruppo
- "promotional": Email promozionale/commerciale
- "update": Notifica/aggiornamento automatico
- "social": Email da social network
- "unknown": Non determinabile

Rispondi solo con una delle parole chiave sopra."""
        
        try:
            response = await self.ollama_client.generate_with_context(
                prompt=prompt,
                session_context=[],
                retrieved_memory=None,
                tools=None,
                tools_description=None,
                return_raw=False,
            )
            
            # Extract category from response
            response_lower = response.lower().strip()
            valid_categories = ["direct", "mailing_list", "promotional", "update", "social", "unknown"]
            for cat in valid_categories:
                if cat in response_lower:
                    return cat
            
            return "unknown"
        except Exception as e:
            logger.warning(f"Error analyzing email category with LLM: {e}")
            return "unknown"
    
    async def _analyze_actions_with_llm(
        self,
        email: Dict[str, Any],
        category: str,
    ) -> Dict[str, Any]:
        """Use LLM to detect required actions in email"""
        
        # Build email content for analysis
        email_content = f"""
Mittente: {email.get('from', 'Unknown')}
Oggetto: {email.get('subject', 'No Subject')}
Tipo email: {category}
Contenuto: {email.get('snippet', email.get('body', ''))[:1000]}
"""
        
        prompt = f"""Analizza questa email e determina se richiede un'azione da parte del ricevente.

{email_content}

Determina:

1. **Azione richiesta**:
   - "reply": L'utente deve rispondere (es. domande dirette, richieste di conferma)
   - "calendar_event": C'è un evento/riunione da aggiungere al calendario
   - "task": C'è un task/azione da completare (es. compilare form, inviare documento)
   - "info": Solo informativa, nessuna azione richiesta
   - null: Nessuna azione richiesta

2. **Urgenza**: "high" | "medium" | "low"
   - high: Richiesta urgente, scadenze imminenti, richieste esplicite
   - medium: Richiesta normale, scadenze future
   - low: Informazioni, aggiornamenti, niente di urgente

3. **Riassunto azione**: Breve descrizione dell'azione richiesta (se presente)

Rispondi SOLO in formato JSON valido:
{{
  "requires_action": true/false,
  "action_type": "reply" | "calendar_event" | "task" | "info" | null,
  "action_summary": "descrizione breve",
  "urgency": "high" | "medium" | "low",
  "reasoning": "breve spiegazione del perché"
}}

Se non c'è azione richiesta, usa:
{{
  "requires_action": false,
  "action_type": null,
  "action_summary": "",
  "urgency": "low",
  "reasoning": "Email informativa, nessuna azione richiesta"
}}"""
        
        try:
            response = await self.ollama_client.generate_with_context(
                prompt=prompt,
                session_context=[],
                retrieved_memory=None,
                tools=None,
                tools_description=None,
                return_raw=False,
            )
            
            # Try to parse JSON from response
            analysis = self._parse_llm_response(response)
            
            # Validate and normalize
            if not isinstance(analysis, dict):
                logger.warning(f"LLM returned non-dict response: {analysis}")
                return {
                    "requires_action": False,
                    "action_type": None,
                    "action_summary": "",
                    "urgency": "low",
                    "reasoning": "Error parsing LLM response",
                }
            
            # Normalize action_type
            action_type = analysis.get("action_type")
            if action_type == "null" or action_type is None:
                action_type = None
            
            # Normalize urgency
            urgency = analysis.get("urgency", "medium").lower()
            if urgency not in ["high", "medium", "low"]:
                urgency = "medium"
            
            return {
                "requires_action": analysis.get("requires_action", False),
                "action_type": action_type,
                "action_summary": analysis.get("action_summary", ""),
                "urgency": urgency,
                "reasoning": analysis.get("reasoning", ""),
            }
        except Exception as e:
            logger.error(f"Error analyzing email actions with LLM: {e}", exc_info=True)
            return {
                "requires_action": False,
                "action_type": None,
                "action_summary": "",
                "urgency": "low",
                "reasoning": f"Error during analysis: {str(e)}",
            }
    
    def _parse_llm_response(self, response: str) -> Dict[str, Any]:
        """Parse JSON from LLM response, handling various formats"""
        # Try to extract JSON from response
        response = response.strip()
        
        # Try to find JSON object in response
        start_idx = response.find("{")
        end_idx = response.rfind("}")
        
        if start_idx != -1 and end_idx != -1 and end_idx > start_idx:
            json_str = response[start_idx:end_idx + 1]
            try:
                return json.loads(json_str)
            except json.JSONDecodeError:
                pass
        
        # Try parsing entire response
        try:
            return json.loads(response)
        except json.JSONDecodeError:
            pass
        
        # Fallback: try to extract key-value pairs
        result = {}
        if "requires_action" in response.lower():
            result["requires_action"] = "true" in response.lower() or "yes" in response.lower()
        if "action_type" in response.lower():
            for action in ["reply", "calendar_event", "task", "info"]:
                if action in response.lower():
                    result["action_type"] = action
                    break
        if "urgency" in response.lower():
            for urgency in ["high", "medium", "low"]:
                if urgency in response.lower():
                    result["urgency"] = urgency
                    break
        
        return result if result else {
            "requires_action": False,
            "action_type": None,
            "action_summary": "",
            "urgency": "low",
            "reasoning": "Could not parse LLM response",
        }

