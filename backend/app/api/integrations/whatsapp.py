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
    wait_for_auth: bool = False  # Don't wait by default to avoid blocking
    timeout: int = 30  # Shorter timeout by default


@router.post("/setup")
async def setup_whatsapp(
    request: WhatsAppSetupRequest,
    whatsapp_service: WhatsAppService = Depends(get_whatsapp_service),
):
    """Setup WhatsApp integration - non-blocking by default"""
    try:
        result = await whatsapp_service.setup_whatsapp_web(
            headless=request.headless,
            profile_path=request.profile_path,
            wait_for_auth=request.wait_for_auth,
            timeout=request.timeout,
        )
        return result
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error setting up WhatsApp: {str(e)}")


@router.get("/status")
async def get_status(
    whatsapp_service: WhatsAppService = Depends(get_whatsapp_service),
):
    """Get WhatsApp connection status"""
    try:
        if not whatsapp_service.driver:
            # Cannot reconnect to manually opened Chrome - Selenium needs to control Chrome
            # User needs to click "Connetti WhatsApp" which will use the same profile
            # and should be already authenticated if Chrome was opened before
            return {
                "success": True,
                "authenticated": False,
                "status": "not_initialized",
                "message": "WhatsApp Web not initialized. Click 'Connetti WhatsApp' to connect. If Chrome is already open with WhatsApp, it will use the same profile and should be authenticated.",
            }
        
        status = whatsapp_service._check_authentication_status()
        return {
            "success": True,
            "authenticated": status.get("authenticated", False),
            "status": status.get("status", "unknown"),
            "message": status.get("message", ""),
        }
    except Exception as e:
        return {
            "success": False,
            "authenticated": False,
            "status": "error",
            "message": str(e),
        }


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


@router.post("/reset")
async def reset_whatsapp(
    clear_profile: bool = False,
    whatsapp_service: WhatsAppService = Depends(get_whatsapp_service),
):
    """Force reset WhatsApp service - closes any hanging sessions
    
    Args:
        clear_profile: If True, clears the WhatsApp profile directory (requires re-authentication)
    """
    try:
        # Force close driver if exists
        if whatsapp_service.driver:
            try:
                whatsapp_service.driver.quit()
            except:
                pass
        whatsapp_service.driver = None
        whatsapp_service.is_authenticated = False
        
        # Clear profile if requested
        if clear_profile:
            whatsapp_service._profile_reset = True
            return {
                "success": True,
                "message": "WhatsApp service reset and profile cleared. You will need to reconnect.",
            }
        else:
            return {
                "success": True,
                "message": "WhatsApp service reset",
            }
    except Exception as e:
        return {
            "success": True,
            "message": f"Reset completed (with errors: {str(e)})",
        }

