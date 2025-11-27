from sentence_transformers import SentenceTransformer
from typing import List, Optional
import numpy as np
import logging
import time
import os
from app.core.config import settings

logger = logging.getLogger(__name__)


class EmbeddingService:
    """Service for generating text embeddings with lazy model loading"""
    
    def __init__(self, model_name: str = "all-MiniLM-L6-v2"):
        # Use a lightweight model by default
        self.model_name = model_name
        self._model: Optional[SentenceTransformer] = None
        self._initialization_error: Optional[Exception] = None
    
    def _ensure_model_loaded(self):
        """Lazy load the model only when needed with retry logic for rate limits"""
        if self._model is None:
            if self._initialization_error:
                # If we already tried and failed, raise the cached error
                raise self._initialization_error
            
            # Retry logic for HuggingFace rate limits (429 errors)
            # Increased retries and delays for Cloud Run environments
            max_retries = 5
            retry_delay = 10  # Start with 10 seconds (longer for rate limits)
            
            for attempt in range(max_retries):
                try:
                    logger.info(f"Loading embedding model: {self.model_name} (attempt {attempt + 1}/{max_retries})")
                    
                    # Set HuggingFace token if available (helps avoid rate limits)
                    hf_token = os.getenv("HUGGINGFACE_TOKEN") or getattr(settings, "huggingface_token", None)
                    if hf_token:
                        os.environ["HF_TOKEN"] = hf_token
                        logger.info("Using HuggingFace token for authentication")
                    
                    self._model = SentenceTransformer(self.model_name)
                    logger.info(f"✅ Embedding model loaded successfully")
                    return
                    
                except Exception as e:
                    error_str = str(e)
                    is_rate_limit = "429" in error_str or "Too Many Requests" in error_str
                    
                    if is_rate_limit and attempt < max_retries - 1:
                        # Exponential backoff for rate limits with jitter
                        import random
                        base_wait = retry_delay * (2 ** attempt)
                        jitter = random.uniform(0, base_wait * 0.3)  # Add up to 30% jitter
                        wait_time = base_wait + jitter
                        logger.warning(
                            f"⚠️  Rate limit error (429) when loading model. "
                            f"Retrying in {wait_time:.1f} seconds... (attempt {attempt + 1}/{max_retries})"
                        )
                        time.sleep(wait_time)
                        continue
                    else:
                        # For non-rate-limit errors or final attempt, cache and raise
                        self._initialization_error = e
                        logger.error(f"❌ Failed to load embedding model: {e}", exc_info=True)
                        
                        if is_rate_limit:
                            raise RuntimeError(
                                f"Failed to load embedding model '{self.model_name}' due to HuggingFace rate limits. "
                                f"Please wait a few minutes and try again, or set HUGGINGFACE_TOKEN environment variable. "
                                f"Original error: {str(e)}"
                            ) from e
                        else:
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

