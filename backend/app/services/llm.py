import json
import httpx
import contextvars
from abc import ABC, abstractmethod
from typing import List, Dict, Any, Optional

# Context variable to propagate search type configuration to Gemini function calls
current_search_type = contextvars.ContextVar("current_search_type", default="keyword")
from google import genai
from google.genai import types
from ..config import settings
from ..db.session import SessionLocal
from .search import search_vachans

def generate_embedding(text: str) -> Optional[List[float]]:
    """Generate vector embedding using Gemini API (text-embedding-004)."""
    api_key = settings.GEMINI_API_KEY
    if not api_key:
        return None
    try:
        client = genai.Client(api_key=api_key)
        response = client.models.embed_content(
            model=settings.GEMINI_EMBEDDING_MODEL,
            contents=text
        )
        if response.embeddings:
            return response.embeddings[0].values
        return None
    except Exception as e:
        print(f"Error generating embedding: {str(e)}")
        return None

# Define Tools that LLM can call
def db_search_vachans(query: str) -> str:
    """Search for vachans using keywords or phrases."""
    db = SessionLocal()
    try:
        search_type = current_search_type.get()
        results = search_vachans(db, query, include_drafts=False, search_type=search_type)
        cleaned_results = [
            {
                "book_name": r["book_name"],
                "chapter_number": r["chapter_number"],
                "page_number": r["page_number"],
                "vachan_number": r["vachan_number"],
                "original_text": r["original_text"],
                "hindi_meaning": r["hindi_meaning"]
            }
            for r in results[:15]
        ]
        return json.dumps(cleaned_results, ensure_ascii=False)
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

def db_list_books() -> str:
    """Retrieve the list of all books available in the scripture library."""
    db = SessionLocal()
    try:
        from ..db.models import Book
        books = db.query(Book).all()
        return json.dumps([b.name for b in books], ensure_ascii=False)
    finally:
        db.close()

def db_list_chapters(book_name: str) -> str:
    """Retrieve the list of all chapters for a specific book."""
    db = SessionLocal()
    try:
        from ..db.models import Book, Chapter
        book = db.query(Book).filter(Book.name == book_name).first()
        if not book:
            return f"Book '{book_name}' not found."
        chapters = db.query(Chapter).filter(Chapter.book_id == book.id).all()
        return json.dumps([{"chapter_number": c.chapter_number, "name": c.name} for c in chapters], ensure_ascii=False)
    finally:
        db.close()

def _build_system_prompt(mode: str) -> str:
    """Build the system prompt based on the response mode (strict or commentary)."""
    system_prompt = (
        "You are an AI research assistant for religious scriptures. The original texts are in a regional "
        "dialect written in the Devanagari script, followed by their Hindi meanings/explanations.\n"
        "You are provided with retrieved scripture sections from our database. You must answer the user's question "
        "based on the retrieved context.\n"
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
    return system_prompt

def _build_citations(results: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """Build a citations list from search results."""
    return [
        {
            "book_name": r["book_name"],
            "chapter_number": r["chapter_number"],
            "page_number": r["page_number"],
            "vachan_number": r["vachan_number"]
        }
        for r in results[:10]
    ]

class LLMProvider(ABC):
    @abstractmethod
    async def generate_response(
        self, question: str, mode: str, history: List[Dict[str, Any]], search_type: str = "keyword"
    ) -> Dict[str, Any]:
        pass

class GeminiProvider(LLMProvider):
    def __init__(self):
        # Initialize Google GenAI client
        api_key = settings.GEMINI_API_KEY
        self.client = genai.Client(api_key=api_key) if api_key else None
        self.model = settings.GEMINI_MODEL

    async def generate_response(
        self, question: str, mode: str, history: List[Dict[str, Any]], search_type: str = "keyword"
    ) -> Dict[str, Any]:
        if not self.client:
            return {
                "answer": "Gemini API key is not configured in .env file. Please configure GEMINI_API_KEY.",
                "citations": []
            }

        # System instructions based on mode
        strict_instruction = (
            "You are a strict scripture research assistant. The original verses are in a regional dialect "
            "(Devanagari script) accompanied by Hindi explanations. "
            "Answer the user's question ONLY using the retrieved scripture texts provided by your tools. Do not assume or extrapolate anything. "
            "If relevant scripture references are not found in the search tools, you MUST return exactly: "
            "'Relevant scripture references were not found.' and nothing else.\n"
            "Every answer must cite sources matching the schema: Book Name, Chapter Number, Page Number, Vachan Number."
        )

        commentary_instruction = (
            "You are a scripture commentary assistant. The original verses are in a regional dialect "
            "(Devanagari script) accompanied by Hindi explanations. "
            "You may synthesize teachings, compare concepts, and explain meanings, but all commentary must remain strictly grounded in the retrieved "
            "scriptures provided by your tools. Do not speculate or make unsupported religious interpretations.\n"
            "Every answer must cite sources matching the schema: Book Name, Chapter Number, Page Number, Vachan Number."
        )

        sys_instruction = strict_instruction if mode == "strict" else commentary_instruction

        # Prepare tools mapping
        # Let client bind local functions as tool definitions
        config = types.GenerateContentConfig(
            system_instruction=sys_instruction,
            tools=[db_search_vachans, db_get_vachan_by_number, db_list_books, db_list_chapters],
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

        # Set the active search type ContextVar so tool calls respect it
        token = current_search_type.set(search_type)
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
            err_msg = str(e)
            if "429" in err_msg or "RESOURCE_EXHAUSTED" in err_msg:
                friendly_error = (
                    "⚠️ **Gemini API Rate Limit Exceeded (429)**\n\n"
                    "The Gemini Free Tier limit (15 requests per minute or daily quota) has been reached.\n\n"
                    "**To continue immediately:**\n"
                    "- Switch the **Search Strategy** to **Keyword (FTS5)** (top right of this panel) to run local searches without using Gemini tokens.\n"
                    "- Or toggle the mode to **Search** (bypasses LLM entirely to fetch direct database matches).\n\n"
                    "Please wait a few seconds before retrying semantic questions."
                )
                return {
                    "answer": friendly_error,
                    "citations": []
                }
            return {
                "answer": f"Error running Gemini assistant: {err_msg}",
                "citations": []
            }
        finally:
            current_search_type.reset(token)

class OllamaProvider(LLMProvider):
    def __init__(self):
        self.base_url = settings.OLLAMA_BASE_URL
        self.model = settings.OLLAMA_MODEL

    async def generate_response(self, question: str, mode: str, history: List[Dict[str, Any]], search_type: str = "keyword") -> Dict[str, Any]:
        # Local model doesn't support automatic tool use reliably, so we run direct FTS search
        db = SessionLocal()
        try:
            # 1. Retrieve context
            results = search_vachans(db, question, include_drafts=False, search_type=search_type)
            
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

class OpenAIProvider(LLMProvider):
    """LLM provider for OpenAI API."""

    def __init__(self):
        self.api_key = settings.OPENAI_API_KEY
        self.model = settings.OPENAI_MODEL

    async def generate_response(self, question: str, mode: str, history: List[Dict[str, Any]], search_type: str = "keyword") -> Dict[str, Any]:
        if not self.api_key:
            return {
                "answer": "OpenAI API key is not configured. Please set OPENAI_API_KEY in your .env file.",
                "citations": []
            }

        db = SessionLocal()
        try:
            results = search_vachans(db, question, include_drafts=False, search_type=search_type)

            if not results:
                if mode == "strict":
                    return {
                        "answer": "Relevant scripture references were not found.",
                        "citations": []
                    }
                context_str = "No scripture records matched the query directly."
            else:
                context_parts = []
                for r in results[:10]:
                    context_parts.append(
                        f"Source: {r['book_name']}, Chapter {r['chapter_number']}, Page {r['page_number']}, Vachan {r['vachan_number']}\n"
                        f"Original: {r['original_text']}\n"
                        f"Hindi Meaning: {r['hindi_meaning']}\n"
                    )
                context_str = "\n---\n".join(context_parts)

            system_prompt = _build_system_prompt(mode)

            messages = [{"role": "system", "content": system_prompt}]
            if history:
                for m in history:
                    role = m.get("role", "user")
                    content = " ".join(m.get("parts", []))
                    messages.append({"role": role, "content": content})
            messages.append({"role": "user", "content": f"Context:\n{context_str}\n\nQuestion: {question}\n\nAnswer:"})

            async with httpx.AsyncClient() as client:
                res = await client.post(
                    "https://api.openai.com/v1/chat/completions",
                    headers={
                        "Authorization": f"Bearer {self.api_key}",
                        "Content-Type": "application/json"
                    },
                    json={
                        "model": self.model,
                        "messages": messages,
                        "temperature": 0.1
                    },
                    timeout=90.0
                )
                if res.status_code == 200:
                    data = res.json()
                    answer = data.get("choices", [{}])[0].get("message", {}).get("content", "")
                    citations = _build_citations(results)
                    return {"answer": answer, "citations": citations}
                else:
                    return {
                        "answer": f"OpenAI returned error ({res.status_code}): {res.text}",
                        "citations": []
                    }
        except Exception as e:
            return {
                "answer": f"Failed to connect to OpenAI: {str(e)}",
                "citations": []
            }
        finally:
            db.close()


class AnthropicProvider(LLMProvider):
    """LLM provider for Anthropic Messages API."""

    def __init__(self):
        self.api_key = settings.ANTHROPIC_API_KEY
        self.model = settings.ANTHROPIC_MODEL

    async def generate_response(self, question: str, mode: str, history: List[Dict[str, Any]], search_type: str = "keyword") -> Dict[str, Any]:
        if not self.api_key:
            return {
                "answer": "Anthropic API key is not configured. Please set ANTHROPIC_API_KEY in your .env file.",
                "citations": []
            }

        db = SessionLocal()
        try:
            results = search_vachans(db, question, include_drafts=False, search_type=search_type)

            if not results:
                if mode == "strict":
                    return {
                        "answer": "Relevant scripture references were not found.",
                        "citations": []
                    }
                context_str = "No scripture records matched the query directly."
            else:
                context_parts = []
                for r in results[:10]:
                    context_parts.append(
                        f"Source: {r['book_name']}, Chapter {r['chapter_number']}, Page {r['page_number']}, Vachan {r['vachan_number']}\n"
                        f"Original: {r['original_text']}\n"
                        f"Hindi Meaning: {r['hindi_meaning']}\n"
                    )
                context_str = "\n---\n".join(context_parts)

            system_prompt = _build_system_prompt(mode)

            # Anthropic Messages API uses a separate system parameter (not a system message)
            messages = []
            if history:
                for m in history:
                    role = m.get("role", "user")
                    # Anthropic only accepts "user" and "assistant" roles
                    if role == "model":
                        role = "assistant"
                    content = " ".join(m.get("parts", []))
                    messages.append({"role": role, "content": content})
            messages.append({"role": "user", "content": f"Context:\n{context_str}\n\nQuestion: {question}\n\nAnswer:"})

            async with httpx.AsyncClient() as client:
                res = await client.post(
                    "https://api.anthropic.com/v1/messages",
                    headers={
                        "x-api-key": self.api_key,
                        "anthropic-version": "2023-06-01",
                        "Content-Type": "application/json"
                    },
                    json={
                        "model": self.model,
                        "system": system_prompt,
                        "messages": messages,
                        "max_tokens": 4096,
                        "temperature": 0.1
                    },
                    timeout=90.0
                )
                if res.status_code == 200:
                    data = res.json()
                    # Anthropic response: {"content": [{"type": "text", "text": "..."}]}
                    content_blocks = data.get("content", [])
                    answer = "".join(
                        block.get("text", "") for block in content_blocks if block.get("type") == "text"
                    )
                    citations = _build_citations(results)
                    return {"answer": answer, "citations": citations}
                else:
                    return {
                        "answer": f"Anthropic returned error ({res.status_code}): {res.text}",
                        "citations": []
                    }
        except Exception as e:
            return {
                "answer": f"Failed to connect to Anthropic: {str(e)}",
                "citations": []
            }
        finally:
            db.close()


class DeepSeekProvider(LLMProvider):
    """LLM provider for DeepSeek (OpenAI-compatible API)."""

    def __init__(self):
        self.api_key = settings.DEEPSEEK_API_KEY
        self.model = settings.DEEPSEEK_MODEL

    async def generate_response(self, question: str, mode: str, history: List[Dict[str, Any]], search_type: str = "keyword") -> Dict[str, Any]:
        if not self.api_key:
            return {
                "answer": "DeepSeek API key is not configured. Please set DEEPSEEK_API_KEY in your .env file.",
                "citations": []
            }

        db = SessionLocal()
        try:
            results = search_vachans(db, question, include_drafts=False, search_type=search_type)

            if not results:
                if mode == "strict":
                    return {
                        "answer": "Relevant scripture references were not found.",
                        "citations": []
                    }
                context_str = "No scripture records matched the query directly."
            else:
                context_parts = []
                for r in results[:10]:
                    context_parts.append(
                        f"Source: {r['book_name']}, Chapter {r['chapter_number']}, Page {r['page_number']}, Vachan {r['vachan_number']}\n"
                        f"Original: {r['original_text']}\n"
                        f"Hindi Meaning: {r['hindi_meaning']}\n"
                    )
                context_str = "\n---\n".join(context_parts)

            system_prompt = _build_system_prompt(mode)

            messages = [{"role": "system", "content": system_prompt}]
            if history:
                for m in history:
                    role = m.get("role", "user")
                    content = " ".join(m.get("parts", []))
                    messages.append({"role": role, "content": content})
            messages.append({"role": "user", "content": f"Context:\n{context_str}\n\nQuestion: {question}\n\nAnswer:"})

            async with httpx.AsyncClient() as client:
                res = await client.post(
                    "https://api.deepseek.com/chat/completions",
                    headers={
                        "Authorization": f"Bearer {self.api_key}",
                        "Content-Type": "application/json"
                    },
                    json={
                        "model": self.model,
                        "messages": messages,
                        "temperature": 0.1
                    },
                    timeout=90.0
                )
                if res.status_code == 200:
                    data = res.json()
                    answer = data.get("choices", [{}])[0].get("message", {}).get("content", "")
                    citations = _build_citations(results)
                    return {"answer": answer, "citations": citations}
                else:
                    return {
                        "answer": f"DeepSeek returned error ({res.status_code}): {res.text}",
                        "citations": []
                    }
        except Exception as e:
            return {
                "answer": f"Failed to connect to DeepSeek: {str(e)}",
                "citations": []
            }
        finally:
            db.close()


class OpenRouterProvider(LLMProvider):
    """LLM provider for OpenRouter (OpenAI-compatible API)."""

    def __init__(self):
        self.api_key = settings.OPENROUTER_API_KEY
        self.model = settings.OPENROUTER_MODEL
        self.base_url = settings.OPENROUTER_BASE_URL.rstrip("/")

    async def generate_response(self, question: str, mode: str, history: List[Dict[str, Any]], search_type: str = "keyword") -> Dict[str, Any]:
        if not self.api_key:
            return {
                "answer": "OpenRouter API key is not configured. Please set OPENROUTER_API_KEY in your .env file.",
                "citations": []
            }

        db = SessionLocal()
        try:
            results = search_vachans(db, question, include_drafts=False, search_type=search_type)

            if not results:
                if mode == "strict":
                    return {
                        "answer": "Relevant scripture references were not found.",
                        "citations": []
                    }
                context_str = "No scripture records matched the query directly."
            else:
                context_parts = []
                for r in results[:10]:
                    context_parts.append(
                        f"Source: {r['book_name']}, Chapter {r['chapter_number']}, Page {r['page_number']}, Vachan {r['vachan_number']}\n"
                        f"Original: {r['original_text']}\n"
                        f"Hindi Meaning: {r['hindi_meaning']}\n"
                    )
                context_str = "\n---\n".join(context_parts)

            system_prompt = _build_system_prompt(mode)

            messages = [{"role": "system", "content": system_prompt}]
            if history:
                for m in history:
                    role = m.get("role", "user")
                    content = " ".join(m.get("parts", []))
                    messages.append({"role": role, "content": content})
            messages.append({"role": "user", "content": f"Context:\n{context_str}\n\nQuestion: {question}\n\nAnswer:"})

            async with httpx.AsyncClient() as client:
                res = await client.post(
                    f"{self.base_url}/chat/completions",
                    headers={
                        "Authorization": f"Bearer {self.api_key}",
                        "Content-Type": "application/json",
                        "HTTP-Referer": "https://project-rag.local",
                        "X-Title": "Project-RAG"
                    },
                    json={
                        "model": self.model,
                        "messages": messages,
                        "temperature": 0.1
                    },
                    timeout=90.0
                )
                if res.status_code == 200:
                    data = res.json()
                    answer = data.get("choices", [{}])[0].get("message", {}).get("content", "")
                    citations = _build_citations(results)
                    return {"answer": answer, "citations": citations}
                else:
                    return {
                        "answer": f"OpenRouter returned error ({res.status_code}): {res.text}",
                        "citations": []
                    }
        except Exception as e:
            return {
                "answer": f"Failed to connect to OpenRouter: {str(e)}",
                "citations": []
            }
        finally:
            db.close()


class NvidiaNimProvider(LLMProvider):
    """LLM provider for NVIDIA NIM (OpenAI-compatible API)."""

    def __init__(self):
        self.api_key = settings.NVIDIA_NIM_API_KEY
        self.model = settings.NVIDIA_NIM_MODEL
        self.base_url = settings.NVIDIA_NIM_BASE_URL.rstrip("/")

    async def generate_response(self, question: str, mode: str, history: List[Dict[str, Any]], search_type: str = "keyword") -> Dict[str, Any]:
        if not self.api_key:
            return {
                "answer": "NVIDIA NIM API key is not configured. Please set NVIDIA_NIM_API_KEY in your .env file.",
                "citations": []
            }

        db = SessionLocal()
        try:
            results = search_vachans(db, question, include_drafts=False, search_type=search_type)

            if not results:
                if mode == "strict":
                    return {
                        "answer": "Relevant scripture references were not found.",
                        "citations": []
                    }
                context_str = "No scripture records matched the query directly."
            else:
                context_parts = []
                for r in results[:10]:
                    context_parts.append(
                        f"Source: {r['book_name']}, Chapter {r['chapter_number']}, Page {r['page_number']}, Vachan {r['vachan_number']}\n"
                        f"Original: {r['original_text']}\n"
                        f"Hindi Meaning: {r['hindi_meaning']}\n"
                    )
                context_str = "\n---\n".join(context_parts)

            system_prompt = _build_system_prompt(mode)

            messages = [{"role": "system", "content": system_prompt}]
            if history:
                for m in history:
                    role = m.get("role", "user")
                    content = " ".join(m.get("parts", []))
                    messages.append({"role": role, "content": content})
            messages.append({"role": "user", "content": f"Context:\n{context_str}\n\nQuestion: {question}\n\nAnswer:"})

            async with httpx.AsyncClient() as client:
                res = await client.post(
                    f"{self.base_url}/chat/completions",
                    headers={
                        "Authorization": f"Bearer {self.api_key}",
                        "Content-Type": "application/json"
                    },
                    json={
                        "model": self.model,
                        "messages": messages,
                        "temperature": 0.1,
                        "max_tokens": 4096
                    },
                    timeout=90.0
                )
                if res.status_code == 200:
                    data = res.json()
                    answer = data.get("choices", [{}])[0].get("message", {}).get("content", "")
                    citations = _build_citations(results)
                    return {"answer": answer, "citations": citations}
                else:
                    return {
                        "answer": f"NVIDIA NIM returned error ({res.status_code}): {res.text}",
                        "citations": []
                    }
        except Exception as e:
            return {
                "answer": f"Failed to connect to NVIDIA NIM: {str(e)}",
                "citations": []
            }
        finally:
            db.close()


def get_llm_provider() -> LLMProvider:
    provider = settings.LLM_PROVIDER.lower()
    if provider == "ollama":
        return OllamaProvider()
    elif provider == "openai":
        return OpenAIProvider()
    elif provider == "anthropic":
        return AnthropicProvider()
    elif provider == "deepseek":
        return DeepSeekProvider()
    elif provider == "openrouter":
        return OpenRouterProvider()
    elif provider == "nvidia_nim":
        return NvidiaNimProvider()
    return GeminiProvider()


def backfill_embeddings_task():
    """Background task to backfill embeddings for approved vachans that lack them using batching."""
    db = SessionLocal()
    try:
        from ..db.models import Vachan
        vachans_to_backfill = db.query(Vachan).filter(
            Vachan.status == "approved",
            Vachan.embedding.is_(None)
        ).all()
        
        if not vachans_to_backfill:
            print("No vachans lack embeddings. Skipping backfill.")
            return
            
        print(f"Backfilling embeddings for {len(vachans_to_backfill)} vachans in batches...")
        
        BATCH_SIZE = 20
        api_key = settings.GEMINI_API_KEY
        if not api_key:
            print("No Gemini API key. Cannot backfill.")
            return
            
        client = genai.Client(api_key=api_key)
        count = 0
        
        for i in range(0, len(vachans_to_backfill), BATCH_SIZE):
            batch = vachans_to_backfill[i:i+BATCH_SIZE]
            texts = [f"Original: {v.original_text}\nMeaning: {v.hindi_meaning}" for v in batch]
            
            try:
                response = client.models.embed_content(
                    model=settings.GEMINI_EMBEDDING_MODEL,
                    contents=texts
                )
                if response.embeddings:
                    for v, emb in zip(batch, response.embeddings):
                        v.embedding = json.dumps(emb.values)
                        count += 1
                    db.commit()
                    print(f"Embedded batch of {len(batch)} vachans.")
                    import time
                    time.sleep(10)
            except Exception as e:
                print(f"Failed to embed batch: {e}")
                
        print(f"Backfill completed. Processed {count} vachans.")
    except Exception as e:
        print(f"Failed to backfill embeddings: {e}")
    finally:
        db.close()

