from fastapi import APIRouter, Depends, HTTPException, status
from ..schemas.chat import ChatRequest, ChatResponse
from ..services.llm import get_llm_provider
from ..services.search import search_vachans
from ..db.session import SessionLocal

router = APIRouter(prefix="/api", tags=["Chat"])

@router.post("/chat", response_model=ChatResponse)
async def chat_assistant(payload: ChatRequest):
    # Search mode: bypass LLM entirely, return FTS results directly
    if payload.mode == "search":
        db = SessionLocal()
        try:
            results = search_vachans(db, payload.question, include_drafts=False, search_type=payload.search_type)
            if not results:
                return {
                    "answer": "No matching scripture references found for your search terms.",
                    "citations": []
                }
            
            # Format results as readable text
            lines = []
            citations = []
            for i, r in enumerate(results[:15], 1):
                lines.append(
                    f"**{i}. {r['book_name']}** — Chapter {r['chapter_number']}, "
                    f"Page {r['page_number']}, Vachan {r['vachan_number']}\n"
                    f"   Verse: {r['original_text']}\n"
                    f"   Meaning: {r['hindi_meaning']}"
                )
                citations.append({
                    "book_name": r["book_name"],
                    "chapter_number": r["chapter_number"],
                    "page_number": r["page_number"],
                    "vachan_number": r["vachan_number"]
                })
            
            answer = f"Found {len(results)} result(s) for \"{payload.question}\":\n\n" + "\n\n".join(lines)
            return {"answer": answer, "citations": citations}
        finally:
            db.close()
 
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
        history=history_dicts,
        search_type=payload.search_type
    )
    
    return result
