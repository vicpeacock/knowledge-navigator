import pytest

from app.core.health_check import HealthCheckService


pytestmark = pytest.mark.asyncio


async def test_health_check_marks_mandatory_services(monkeypatch):
    service = HealthCheckService()

    async def fake_postgres():
        return {"healthy": True}

    async def fake_chroma():
        return {"healthy": False, "error": "not reachable"}

    async def fake_ollama_main():
        return {"healthy": True}

    async def fake_ollama_background():
        return {"healthy": False, "error": "connection refused"}

    monkeypatch.setattr(service, "_check_postgres", fake_postgres)
    monkeypatch.setattr(service, "_check_chromadb", fake_chroma)
    monkeypatch.setattr(service, "_check_ollama_main", fake_ollama_main)
    monkeypatch.setattr(service, "_check_ollama_background", fake_ollama_background)

    result = await service.check_all_services()

    assert result["all_healthy"] is False
    assert result["all_mandatory_healthy"] is False

    chroma_status = result["services"]["chromadb"]
    assert chroma_status["mandatory"] is True
    assert chroma_status["healthy"] is False

    background_status = result["services"]["ollama_background"]
    assert background_status["mandatory"] is False

    unhealthy_mandatory = result["unhealthy_mandatory_services"]
    assert any(item["service"] == "chromadb" for item in unhealthy_mandatory)


async def test_get_status_summary_uses_cached_status(monkeypatch):
    service = HealthCheckService()

    service.health_status = {
        "postgres": {"healthy": True, "mandatory": True},
        "chromadb": {"healthy": True, "mandatory": True},
        "ollama_main": {"healthy": True, "mandatory": True},
    }

    summary = service.get_status_summary()

    assert summary["all_healthy"] is True
    assert summary["all_mandatory_healthy"] is True
    assert summary["unhealthy_services"] == []
    assert summary["unhealthy_mandatory_services"] == []

