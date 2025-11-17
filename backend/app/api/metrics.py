"""
Metrics API endpoint for Prometheus scraping
"""
from fastapi import APIRouter
from fastapi.responses import Response
from app.core.metrics import get_metrics_export

router = APIRouter()


@router.get("/metrics")
async def get_metrics():
    """
    Prometheus metrics endpoint
    Returns metrics in Prometheus format for scraping
    """
    metrics_bytes, content_type = get_metrics_export()
    return Response(content=metrics_bytes, media_type=content_type)

