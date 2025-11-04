from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from typing import List, Dict, Any, Optional
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from uuid import UUID

from app.db.database import get_db
from app.models.database import Integration
from app.services.whatsapp_service import WhatsAppService
from app.core.config import settings

router = APIRouter()

# Global WhatsApp service instance
_whatsapp_service = WhatsAppService()


def get_whatsapp_service() -> WhatsAppService:
    """Dependency to get WhatsApp service"""
    return _whatsapp_service


class WhatsAppSetupRequest(BaseModel):
    headless: bool = False
    profile_path: Optional[str] = None


@router.post("/setup")
async def setup_whatsapp(
    request: WhatsAppSetupRequest,
    whatsapp_service: WhatsAppService = Depends(get_whatsapp_service),
):
    """Setup WhatsApp integration"""
    try:
        await whatsapp_service.setup_whatsapp_web(
            headless=request.headless,
            profile_path=request.profile_path,
        )
        return {
            "success": True,
            "message": "WhatsApp Web setup completed. Please scan QR code if needed.",
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error setting up WhatsApp: {str(e)}")


@router.get("/messages")
async def get_messages(
    contact_name: Optional[str] = None,
    max_results: int = 10,
    whatsapp_service: WhatsAppService = Depends(get_whatsapp_service),
):
    """Get WhatsApp messages"""
    try:
        if not whatsapp_service.is_authenticated:
            raise HTTPException(status_code=401, detail="WhatsApp not authenticated. Please setup first.")
        
        messages = await whatsapp_service.get_recent_messages(
            contact_name=contact_name,
            max_results=max_results,
        )
        
        return {
            "success": True,
            "messages": messages,
            "count": len(messages),
        }
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error retrieving messages: {str(e)}")


@router.post("/send")
async def send_message(
    phone_number: str,
    message: str,
    whatsapp_service: WhatsAppService = Depends(get_whatsapp_service),
):
    """Send WhatsApp message"""
    try:
        await whatsapp_service.send_message_pywhatkit(
            phone_number=phone_number,
            message=message,
        )
        return {
            "success": True,
            "message": f"Message scheduled to be sent to {phone_number}",
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error sending message: {str(e)}")


@router.post("/close")
async def close_whatsapp(
    whatsapp_service: WhatsAppService = Depends(get_whatsapp_service),
):
    """Close WhatsApp Web session"""
    try:
        await whatsapp_service.close()
        return {
            "success": True,
            "message": "WhatsApp session closed",
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error closing WhatsApp: {str(e)}")

