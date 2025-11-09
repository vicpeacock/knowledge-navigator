"""
Health check service for verifying all dependencies are available at startup
"""
import httpx
import logging
from typing import Dict, Any, Optional
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine
from app.core.config import settings

logger = logging.getLogger(__name__)


class HealthCheckService:
    """Service for checking health of all dependencies"""
    
    def __init__(self):
        self.health_status: Dict[str, Dict[str, Any]] = {}
        # Mandatory services required for the application to operate correctly.
        # Background LLM can be disabled (fire-and-forget tasks), so we treat it as optional by default.
        self.mandatory_services = {
            "postgres",
            "chromadb",
            "ollama_main",
        }
        # Allow forcing background model as mandatory if needed via env flag.
        if settings.use_llama_cpp_background and getattr(settings, "require_background_llm", False):
            self.mandatory_services.add("ollama_background")
    
    async def check_all_services(self) -> Dict[str, Dict[str, Any]]:
        """
        Check health of all services:
        - PostgreSQL
        - ChromaDB
        - Ollama Main
        - Ollama Background
        """
        logger.info("🔍 Starting health check for all services...")
        
        # Check PostgreSQL
        postgres_status = await self._check_postgres()
        postgres_status["mandatory"] = "postgres" in self.mandatory_services
        self.health_status["postgres"] = postgres_status
        
        # Check ChromaDB
        chromadb_status = await self._check_chromadb()
        chromadb_status["mandatory"] = "chromadb" in self.mandatory_services
        self.health_status["chromadb"] = chromadb_status
        
        # Check Ollama Main
        ollama_main_status = await self._check_ollama_main()
        ollama_main_status["mandatory"] = "ollama_main" in self.mandatory_services
        self.health_status["ollama_main"] = ollama_main_status
        
        # Check Ollama Background
        ollama_background_status = await self._check_ollama_background()
        ollama_background_status["mandatory"] = "ollama_background" in self.mandatory_services
        self.health_status["ollama_background"] = ollama_background_status
        
        # Summary
        all_services_healthy = all(status.get("healthy", False) for status in self.health_status.values())
        all_mandatory_healthy = all(
            status.get("healthy", False)
            for name, status in self.health_status.items()
            if status.get("mandatory", False)
        )
        unhealthy_services = [
            {"service": name, **status}
            for name, status in self.health_status.items()
            if not status.get("healthy", False)
        ]
        unhealthy_mandatory = [
            service for service in unhealthy_services if service.get("mandatory", False)
        ]
        
        logger.info(
            "✅ Health check completed. Mandatory services healthy: %s (all services healthy: %s)",
            all_mandatory_healthy,
            all_services_healthy,
        )
        if not all_mandatory_healthy:
            logger.warning("⚠️  Some services are not healthy:")
            for service in unhealthy_services:
                logger.warning(
                    "  - %s%s: %s",
                    service["service"],
                    " (mandatory)" if service.get("mandatory") else "",
                    service.get("error", "Unknown error"),
                )
        
        return {
            "all_healthy": all_services_healthy,
            "all_mandatory_healthy": all_mandatory_healthy,
            "services": self.health_status,
            "unhealthy_services": unhealthy_services,
            "unhealthy_mandatory_services": unhealthy_mandatory,
        }
    
    async def _check_postgres(self) -> Dict[str, Any]:
        """Check PostgreSQL connection"""
        try:
            from sqlalchemy import text
            engine = create_async_engine(settings.database_url)
            async with engine.connect() as conn:
                await conn.execute(text("SELECT 1"))
            await engine.dispose()
            return {"healthy": True, "message": "PostgreSQL connection successful"}
        except Exception as e:
            logger.error(f"❌ PostgreSQL health check failed: {e}")
            return {"healthy": False, "error": str(e)}
    
    async def _check_chromadb(self) -> Dict[str, Any]:
        """Check ChromaDB connection"""
        try:
            async with httpx.AsyncClient(timeout=5.0) as client:
                heartbeat_url = f"http://{settings.chromadb_host}:{settings.chromadb_port}/api/v2/heartbeat"
                response = await client.get(heartbeat_url)

                if response.status_code == 404:
                    # Older Chroma versions only expose v1 heartbeat
                    fallback_url = f"http://{settings.chromadb_host}:{settings.chromadb_port}/api/v1/heartbeat"
                    response = await client.get(fallback_url)
                    heartbeat_url = fallback_url

                if response.status_code == 200:
                    return {
                        "healthy": True,
                        "message": f"ChromaDB connection successful ({heartbeat_url})",
                        "heartbeat_url": heartbeat_url,
                    }
                return {"healthy": False, "error": f"ChromaDB returned status {response.status_code}"}
        except Exception as e:
            logger.error("❌ ChromaDB health check failed: %s", e)
            return {"healthy": False, "error": str(e)}
    
    async def _check_ollama_main(self) -> Dict[str, Any]:
        """Check Ollama Main connection and model availability"""
        try:
            async with httpx.AsyncClient(timeout=10.0) as client:
                # Check if Ollama is running
                response = await client.get(f"{settings.ollama_base_url}/api/tags")
                if response.status_code != 200:
                    return {"healthy": False, "error": f"Ollama main returned status {response.status_code}"}
                
                # Check if model is available
                models = response.json().get("models", [])
                model_names = [m.get("name", "") for m in models]
                
                if settings.ollama_model not in model_names:
                    return {
                        "healthy": False,
                        "error": f"Model '{settings.ollama_model}' not found. Available: {model_names}"
                    }
                
                return {
                    "healthy": True,
                    "message": f"Ollama main connection successful, model '{settings.ollama_model}' available"
                }
        except httpx.ConnectError:
            logger.error(f"❌ Ollama main health check failed: Connection refused")
            return {"healthy": False, "error": "Cannot connect to Ollama main (connection refused)"}
        except Exception as e:
            logger.error(f"❌ Ollama main health check failed: {e}")
            return {"healthy": False, "error": str(e)}
    
    async def _check_ollama_background(self) -> Dict[str, Any]:
        """Check Background LLM connection (Ollama or llama.cpp) and model availability"""
        try:
            async with httpx.AsyncClient(timeout=10.0) as client:
                if settings.use_llama_cpp_background:
                    # llama.cpp uses OpenAI-compatible API
                    base_url = settings.ollama_background_base_url
                    if not base_url.endswith('/v1'):
                        base_url = base_url.rstrip('/') + '/v1'
                    
                    response = await client.get(f"{base_url}/models")
                    if response.status_code != 200:
                        return {
                            "healthy": False,
                            "error": f"llama.cpp background returned status {response.status_code}"
                        }
                    
                    # Check if model is available (llama.cpp format)
                    models_data = response.json().get("data", [])
                    model_names = [m.get("id", "") or m.get("name", "") or m.get("model", "") for m in models_data]
                    
                    # llama.cpp might return model name with .gguf extension
                    expected_model = settings.ollama_background_model
                    # Check if model name matches (with or without .gguf extension)
                    # llama.cpp returns model name as "Phi-3-mini-4k-instruct-q4.gguf" but we configure without .gguf
                    model_found = (
                        expected_model in model_names or 
                        f"{expected_model}.gguf" in model_names or
                        any(expected_model in name or name.replace(".gguf", "") == expected_model for name in model_names)
                    )
                    
                    if not model_found:
                        return {
                            "healthy": False,
                            "error": f"Model '{expected_model}' not found. Available: {model_names}. "
                                    f"Make sure llama-server is running with the correct model."
                        }
                    
                    return {
                        "healthy": True,
                        "message": f"llama.cpp background connection successful, model '{expected_model}' available"
                    }
                else:
                    # Ollama Docker container
                    response = await client.get(f"{settings.ollama_background_base_url}/api/tags")
                    if response.status_code != 200:
                        return {
                            "healthy": False,
                            "error": f"Ollama background returned status {response.status_code}"
                        }
                    
                    # Check if model is available
                    models = response.json().get("models", [])
                    model_names = [m.get("name", "") for m in models]
                    
                    if settings.ollama_background_model not in model_names:
                        return {
                            "healthy": False,
                            "error": f"Model '{settings.ollama_background_model}' not found. Available: {model_names}. "
                                    f"Run: docker exec knowledge-navigator-ollama-background ollama pull {settings.ollama_background_model}"
                        }
                    
                    return {
                        "healthy": True,
                        "message": f"Ollama background connection successful, model '{settings.ollama_background_model}' available"
                    }
        except httpx.ConnectError:
            logger.error(f"❌ Background LLM health check failed: Connection refused")
            service_name = "llama.cpp" if settings.use_llama_cpp_background else "Ollama background"
            return {
                "healthy": False,
                "error": f"Cannot connect to {service_name} (connection refused). "
                        f"Make sure the service is running on {settings.ollama_background_base_url}"
            }
        except Exception as e:
            logger.error(f"❌ Background LLM health check failed: {e}")
            return {"healthy": False, "error": str(e)}
    
    def get_status_summary(self) -> Dict[str, Any]:
        """Get summary of health status"""
        all_services_healthy = all(status.get("healthy", False) for status in self.health_status.values())
        all_mandatory_healthy = all(
            status.get("healthy", False)
            for status in self.health_status.values()
            if status.get("mandatory", False)
        )
        unhealthy_services = [
            {"service": name, **status}
            for name, status in self.health_status.items()
            if not status.get("healthy", False)
        ]
        unhealthy_mandatory = [
            service for service in unhealthy_services if service.get("mandatory", False)
        ]
        
        return {
            "all_healthy": all_services_healthy,
            "all_mandatory_healthy": all_mandatory_healthy,
            "services": self.health_status,
            "unhealthy_services": unhealthy_services,
            "unhealthy_mandatory_services": unhealthy_mandatory,
        }


# Global health check service instance
_health_check_service: Optional[HealthCheckService] = None


def get_health_check_service() -> HealthCheckService:
    """Get global health check service instance"""
    global _health_check_service
    if _health_check_service is None:
        _health_check_service = HealthCheckService()
    return _health_check_service

