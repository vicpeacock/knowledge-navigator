from sentence_transformers import SentenceTransformer
from typing import List, Optional
import numpy as np
import logging

logger = logging.getLogger(__name__)


class EmbeddingService:
    """Service for generating text embeddings with lazy model loading"""
    
    def __init__(self, model_name: str = "all-MiniLM-L6-v2"):
        # Use a lightweight model by default
        self.model_name = model_name
        self._model: Optional[SentenceTransformer] = None
        self._initialization_error: Optional[Exception] = None
    
    def _ensure_model_loaded(self):
        """Lazy load the model only when needed"""
        if self._model is None:
            if self._initialization_error:
                # If we already tried and failed, raise the cached error
                raise self._initialization_error
            
            try:
                logger.info(f"Loading embedding model: {self.model_name}")
                self._model = SentenceTransformer(self.model_name)
                logger.info(f"✅ Embedding model loaded successfully")
            except Exception as e:
                self._initialization_error = e
                logger.error(f"❌ Failed to load embedding model: {e}", exc_info=True)
                raise RuntimeError(
                    f"Failed to load embedding model '{self.model_name}'. "
                    f"Please check your internet connection and try again. "
                    f"Original error: {str(e)}"
                ) from e
    
    def generate_embedding(self, text: str) -> List[float]:
        """Generate embedding for a single text"""
        self._ensure_model_loaded()
        embedding = self._model.encode(text, convert_to_numpy=True)
        return embedding.tolist()
    
    def generate_embeddings(self, texts: List[str]) -> List[List[float]]:
        """Generate embeddings for multiple texts"""
        self._ensure_model_loaded()
        embeddings = self._model.encode(texts, convert_to_numpy=True)
        return embeddings.tolist()

