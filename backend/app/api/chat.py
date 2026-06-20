from fastapi import APIRouter, Depends, HTTPException, status
from ..schemas.chat import ChatRequest, ChatResponse
from ..services.llm import get_llm_provider

router = APIRouter(prefix="/api", tags=["Chat"])

@router.post("/chat", response_model=ChatResponse)
async def chat_assistant(payload: ChatRequest):
    provider = get_llm_provider()
    
    # Format message history to simple dictionaries for the service
    history_dicts = []
    if payload.history:
        for m in payload.history:
            history_dicts.append({
                "role": m.role,
                "parts": m.parts
            })
            
    # Run the generator
    result = await provider.generate_response(
        question=payload.question,
        mode=payload.mode,
        history=history_dicts
    )
    
    return result
