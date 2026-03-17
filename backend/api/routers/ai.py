"""
AI API router for FastAPI.
Handles AI-powered content generation and processing.
"""

from typing import Optional
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
import httpx
from shared.database import get_db
from shared.schemas import AIRequest, AIResponse
from api.dependencies import get_current_active_user, rate_limiter
from api.config import api_settings


router = APIRouter(prefix="/ai", tags=["ai"])


@router.post("/generate", response_model=AIResponse)
async def generate_content(
    request: AIRequest,
    db: AsyncSession = Depends(get_db),
    current_user = Depends(get_current_active_user)
):
    """Generate AI content based on the prompt."""
    # Check rate limit
    client_id = str(current_user.id)
    if not await rate_limiter.check_rate_limit(client_id):
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail="Rate limit exceeded. Please try again later."
        )
    
    # Build the AI prompt
    prompt = _build_ai_prompt(request)
    
    # Call AI API (OpenAI compatible)
    if not api_settings.OPENAI_API_KEY:
        # Return mock response for development
        return AIResponse(
            generated_content=f"Mock AI generated content for: {request.prompt[:100]}...",
            model_used="mock",
            tokens_used=50
        )
    
    try:
        async with httpx.AsyncClient() as client:
            response = await client.post(
                api_settings.OPENAI_BASE_URL,
                headers={
                    "Authorization": f"Bearer {api_settings.OPENAI_API_KEY}",
                    "Content-Type": "application/json"
                },
                json={
                    "model": "gpt-3.5-turbo",
                    "messages": [
                        {
                            "role": "system",
                            "content": _get_system_prompt(request.content_type, request.platform, request.tone)
                        },
                        {
                            "role": "user",
                            "content": prompt
                        }
                    ],
                    "max_tokens": request.max_tokens,
                    "temperature": 0.7,
                },
                timeout=30.0
            )
            
            response.raise_for_status()
            data = response.json()
            
            return AIResponse(
                generated_content=data["choices"][0]["message"]["content"],
                model_used=data.get("model", "gpt-3.5-turbo"),
                tokens_used=data.get("usage", {}).get("total_tokens", 0)
            )
            
    except httpx.HTTPError as e:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=f"AI service error: {str(e)}"
        )


@router.post("/optimize-post", response_model=AIResponse)
async def optimize_post(
    content: str,
    platform: str = "linkedin",
    tone: str = "professional",
    db: AsyncSession = Depends(get_db),
    current_user = Depends(get_current_active_user)
):
    """Optimize existing post content for a specific platform."""
    # Check rate limit
    client_id = str(current_user.id)
    if not await rate_limiter.check_rate_limit(client_id):
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail="Rate limit exceeded. Please try again later."
        )
    
    request = AIRequest(
        prompt=f"Optimize this content for {platform} with a {tone} tone:\n\n{content}",
        content_type="optimization",
        platform=platform,
        tone=tone,
        max_tokens=1000
    )
    
    return await generate_content(request, db, current_user)


@router.post("/generate-variations", response_model=list[AIResponse])
async def generate_variations(
    content: str,
    count: int = 3,
    db: AsyncSession = Depends(get_db),
    current_user = Depends(get_current_active_user)
):
    """Generate multiple variations of existing content."""
    # Check rate limit
    client_id = str(current_user.id)
    if not await rate_limiter.check_rate_limit(client_id):
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail="Rate limit exceeded. Please try again later."
        )
    
    if count > 5:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Maximum 5 variations per request"
        )
    
    variations = []
    tones = ["professional", "casual", "engaging", "informative", "persuasive"][:count]
    
    for tone in tones:
        request = AIRequest(
            prompt=f"Rewrite this content with a {tone} tone:\n\n{content}",
            content_type="variation",
            platform="linkedin",
            tone=tone,
            max_tokens=500
        )
        variation = await generate_content(request, db, current_user)
        variations.append(variation)
    
    return variations


def _build_ai_prompt(request: AIRequest) -> str:
    """Build the AI prompt based on request parameters."""
    base_prompt = request.prompt
    
    if request.content_type == "post":
        base_prompt = f"Generate a social media post:\n\n{base_prompt}"
        if request.platform:
            base_prompt += f"\n\nPlatform: {request.platform.title()}"
        if request.tone:
            base_prompt += f"\nTone: {request.tone}"
    
    return base_prompt


def _get_system_prompt(content_type: str, platform: Optional[str], tone: Optional[str]) -> str:
    """Get the system prompt for AI generation."""
    base_prompt = "You are an expert social media content creator."
    
    if content_type == "post":
        base_prompt = """You are an expert social media content creator specializing in LinkedIn posts.
Your content is engaging, professional, and drives meaningful engagement.
You use storytelling techniques, ask questions, and provide value to readers.
Keep posts between 500-1500 characters for optimal engagement."""
    
    if platform:
        platform_prompts = {
            "linkedin": " You specialize in professional LinkedIn content that builds thought leadership.",
            "twitter": " You specialize in concise, impactful Twitter content (280 chars or less).",
            "facebook": " You specialize in engaging Facebook content that sparks conversations.",
            "instagram": " You specialize in visually descriptive Instagram captions with effective hashtags."
        }
        base_prompt += platform_prompts.get(platform.lower(), "")
    
    if tone:
        tone_prompts = {
            "professional": " Maintain a highly professional and authoritative tone.",
            "casual": " Use a friendly, conversational tone that feels approachable.",
            "engaging": " Use an engaging, interactive tone that encourages responses.",
            "humorous": " Include tasteful humor to make content memorable.",
            "inspirational": " Use an inspirational, motivational tone."
        }
        base_prompt += tone_prompts.get(tone.lower(), "")
    
    return base_prompt
