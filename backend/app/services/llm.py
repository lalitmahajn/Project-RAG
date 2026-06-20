import json
import httpx
from abc import ABC, abstractmethod
from typing import List, Dict, Any, Optional
from google import genai
from google.genai import types
from ..config import settings
from ..db.session import SessionLocal
from .search import search_vachans

# Define Tools that LLM can call
def db_search_vachans(query: str) -> str:
    """Search for vachans using keywords or phrases."""
    db = SessionLocal()
    try:
        results = search_vachans(db, query, include_drafts=False)
        return json.dumps(results[:15], ensure_ascii=False)  # Limit context size
    finally:
        db.close()

def db_get_vachan_by_number(book_name: str, chapter_number: int, vachan_number: int) -> str:
    """Retrieve a specific vachan by book name, chapter number, and vachan number."""
    db = SessionLocal()
    try:
        # Resolve book and chapter first
        from ..db.models import Book, Chapter, Vachan
        v = db.query(Vachan).join(Book).join(Chapter).filter(
            Book.name == book_name,
            Chapter.chapter_number == chapter_number,
            Vachan.vachan_number == vachan_number,
            Vachan.status == "approved"
        ).first()
        if v:
            return json.dumps({
                "book_name": v.book.name,
                "chapter_number": v.chapter.chapter_number,
                "page_number": v.page_number,
                "vachan_number": v.vachan_number,
                "original_text": v.original_text,
                "hindi_meaning": v.hindi_meaning
            }, ensure_ascii=False)
        return "Vachan not found."
    finally:
        db.close()

class LLMProvider(ABC):
    @abstractmethod
    async def generate_response(self, question: str, mode: str, history: List[Dict[str, Any]]) -> Dict[str, Any]:
        pass

class GeminiProvider(LLMProvider):
    def __init__(self):
        # Initialize Google GenAI client
        api_key = settings.GEMINI_API_KEY
        self.client = genai.Client(api_key=api_key) if api_key else None
        self.model = "gemini-2.5-flash"

    async def generate_response(self, question: str, mode: str, history: List[Dict[str, Any]]) -> Dict[str, Any]:
        if not self.client:
            return {
                "answer": "Gemini API key is not configured in .env file. Please configure GEMINI_API_KEY.",
                "citations": []
            }

        # System instructions based on mode
        strict_instruction = (
            "You are a strict scripture research assistant. Answer the user's question ONLY using the "
            "retrieved scripture texts provided by your tools. Do not assume or extrapolate anything. "
            "If relevant scripture references are not found in the search tools, you MUST return exactly: "
            "'Relevant scripture references were not found.' and nothing else.\n"
            "Every answer must cite sources matching the schema: Book Name, Chapter Number, Page Number, Vachan Number."
        )

        commentary_instruction = (
            "You are a scripture commentary assistant. You may synthesize teachings, compare concepts, "
            "and explain meanings, but all commentary must remain strictly grounded in the retrieved "
            "scriptures provided by your tools. Do not speculate or make unsupported religious interpretations.\n"
            "Every answer must cite sources matching the schema: Book Name, Chapter Number, Page Number, Vachan Number."
        )

        sys_instruction = strict_instruction if mode == "strict" else commentary_instruction

        # Prepare tools mapping
        # Let client bind local functions as tool definitions
        config = types.GenerateContentConfig(
            system_instruction=sys_instruction,
            tools=[db_search_vachans, db_get_vachan_by_number],
            temperature=0.1
        )

        # Build message history for Gemini SDK
        # We need to map standard chat messages
        contents = []
        if history:
            for m in history:
                role = "user" if m.get("role") == "user" else "model"
                parts = m.get("parts", [])
                contents.append(types.Content(role=role, parts=[types.Part.from_text(text=p) for p in parts]))
        
        contents.append(types.Content(role="user", parts=[types.Part.from_text(text=question)]))

        try:
            # Generate content (client handles function call loop automatically)
            response = self.client.models.generate_content(
                model=self.model,
                contents=contents,
                config=config
            )
            
            answer = response.text
            
            # Simple heuristic/regex to extract citations from answer text
            # e.g. "सुखरामजी महाराज की जीवनी - Ch 1, p.2, v.1"
            citations = []
            # We can also parse from the function calls context, or run a final extraction pass
            # Let's extract citations by searching for book references in the database
            db = SessionLocal()
            try:
                # Query database for all vachans to match against keywords in the answer
                from ..db.models import Vachan
                vachans = db.query(Vachan).filter(Vachan.status == "approved").all()
                for v in vachans:
                    # Check if vachan original or meaning parts appear in the answer
                    if len(v.original_text) > 15 and v.original_text[:15] in answer:
                        citations.append({
                            "book_name": v.book.name,
                            "chapter_number": v.chapter.chapter_number,
                            "page_number": v.page_number,
                            "vachan_number": v.vachan_number
                        })
            finally:
                db.close()

            # Remove duplicates from citations
            unique_citations = []
            seen = set()
            for c in citations:
                key = (c["book_name"], c["chapter_number"], c["vachan_number"])
                if key not in seen:
                    seen.add(key)
                    unique_citations.append(c)

            return {
                "answer": answer,
                "citations": unique_citations
            }
        except Exception as e:
            return {
                "answer": f"Error running Gemini assistant: {str(e)}",
                "citations": []
            }

class OllamaProvider(LLMProvider):
    def __init__(self):
        self.base_url = settings.OLLAMA_BASE_URL
        self.model = "llama3"

    async def generate_response(self, question: str, mode: str, history: List[Dict[str, Any]]) -> Dict[str, Any]:
        # Local model doesn't support automatic tool use reliably, so we run direct FTS search
        db = SessionLocal()
        try:
            # 1. Retrieve context
            results = search_vachans(db, question, include_drafts=False)
            
            if not results:
                if mode == "strict":
                    return {
                        "answer": "Relevant scripture references were not found.",
                        "citations": []
                    }
                context_str = "No scripture records matched the query directly."
            else:
                context_parts = []
                for r in results[:10]:  # Take top 10 matches
                    context_parts.append(
                        f"Source: {r['book_name']}, Chapter {r['chapter_number']}, Page {r['page_number']}, Vachan {r['vachan_number']}\n"
                        f"Original: {r['original_text']}\n"
                        f"Hindi Meaning: {r['hindi_meaning']}\n"
                    )
                context_str = "\n---\n".join(context_parts)

            # 2. Build prompt
            system_prompt = (
                "You are an AI research assistant for religious scriptures. You are provided with retrieved scripture sections "
                "from our database. You must answer the user's question based on the retrieved context.\n"
            )
            if mode == "strict":
                system_prompt += (
                    "STRICT RULES:\n"
                    "1. Answer ONLY using the provided scripture contexts.\n"
                    "2. If the context does not contain relevant references to answer, return exactly: 'Relevant scripture references were not found.' and nothing else.\n"
                    "3. Do not formulate answers outside the context.\n"
                )
            else:
                system_prompt += (
                    "COMMENTARY RULES:\n"
                    "1. Synthesize, compare, and explain concepts, but keep all commentary strictly grounded in the provided scriptures.\n"
                    "2. Do not speculate or make unsupported religious interpretations.\n"
                )
            
            system_prompt += "\nFormat every answer with inline citations or list source references (Book, Chapter, Page, Vachan)."

            prompt = f"Context:\n{context_str}\n\nQuestion: {question}\n\nAnswer:"

            # Send HTTP post to Ollama
            async with httpx.AsyncClient() as client:
                res = await client.post(
                    f"{self.base_url}/api/generate",
                    json={
                        "model": self.model,
                        "prompt": f"{system_prompt}\n\n{prompt}",
                        "stream": False,
                        "options": {"temperature": 0.1}
                    },
                    timeout=60.0
                )
                if res.status_code == 200:
                    answer = res.json().get("response", "")
                    
                    # Format citations list from matched search results
                    citations = []
                    for r in results[:10]:
                        citations.append({
                            "book_name": r["book_name"],
                            "chapter_number": r["chapter_number"],
                            "page_number": r["page_number"],
                            "vachan_number": r["vachan_number"]
                        })
                    return {
                        "answer": answer,
                        "citations": citations
                    }
                else:
                    return {
                        "answer": f"Ollama returned error: {res.text}",
                        "citations": []
                    }
        except Exception as e:
            return {
                "answer": f"Failed to connect to Ollama: {str(e)}",
                "citations": []
            }
        finally:
            db.close()

def get_llm_provider() -> LLMProvider:
    if settings.LLM_PROVIDER == "ollama":
        return OllamaProvider()
    return GeminiProvider()
