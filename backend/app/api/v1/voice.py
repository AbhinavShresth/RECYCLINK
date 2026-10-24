import logging

import httpx
from fastapi import APIRouter, Depends, HTTPException

from app.api.dependencies import get_current_user, require_csrf
from app.core.config import get_settings
from app.core.rate_limit import rate_limit
from app.models.identity import User

router = APIRouter(prefix="/voice", tags=["voice assistant"])
logger = logging.getLogger("recyclink.voice")


@router.get("/status")
def voice_status(_: User = Depends(get_current_user)) -> dict:
    settings = get_settings()
    configured = bool(settings.elevenlabs_api_key and settings.elevenlabs_agent_id)
    return {"configured": configured, "provider": "ElevenLabs Conversational AI", "mode": "signed_url" if configured else "unconfigured", "message": "Voice provider is ready to start a session." if configured else "Voice is unavailable until ELEVENLABS_API_KEY and ELEVENLABS_AGENT_ID are configured. Typed workflows remain available."}


@router.post("/session", dependencies=[Depends(require_csrf), Depends(rate_limit("voice-session", 5, 60))])
async def create_voice_session(user: User = Depends(get_current_user)) -> dict:
    settings = get_settings()
    if not settings.elevenlabs_api_key or not settings.elevenlabs_agent_id:
        raise HTTPException(503, "ElevenLabs voice is not configured; typed workflows remain available")
    url = f"{settings.elevenlabs_api_base_url.rstrip('/')}/convai/conversation/get-signed-url"
    try:
        async with httpx.AsyncClient(timeout=8.0) as client:
            response = await client.get(url, params={"agent_id": settings.elevenlabs_agent_id}, headers={"xi-api-key": settings.elevenlabs_api_key})
        if response.status_code != 200:
            logger.warning("ElevenLabs signed session request returned status %s", response.status_code)
            raise HTTPException(502, "ElevenLabs could not issue a voice session. Try again or use typed actions.")
        body = response.json()
        signed_url = body.get("signed_url")
        if not isinstance(signed_url, str) or not signed_url.startswith("wss://"):
            logger.error("ElevenLabs signed session response had an invalid shape")
            raise HTTPException(502, "ElevenLabs returned an invalid session response")
        return {"signed_url": signed_url, "user_id": str(user.id), "expires_in_minutes": 15}
    except httpx.HTTPError:
        logger.exception("ElevenLabs session provider unavailable")
        raise HTTPException(503, "ElevenLabs is temporarily unavailable. Use the typed workflows instead.") from None
