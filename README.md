# Scripture Knowledge Base & Research Assistant

A web-based platform to manage, search, and analyze religious scriptures (specifically Marwadi/Rajasthani verses with Hindi meanings) using a RAG (Retrieval-Augmented Generation) system.

## Features

- **Scripture Browser**: Browse by books and chapters.
- **Full-Text Search**: Fast keyword search utilizing SQLite's `FTS5` engine.
- **AI Research Assistant**: RAG-powered chatbot with Strict and Commentary modes for scripture analysis.
- **Admin Dashboard**:
  - Upload PDF scriptures.
  - Track background ingestion tasks.
  - Side-by-side editor to review, edit, and approve parsed verses against the original PDF.

---

## Tech Stack

- **Backend**: FastAPI, SQLAlchemy (SQLite), PyMuPDF (PDF extraction), Google GenAI SDK (Gemini)
- **Frontend**: React 19, TypeScript, Vite, Vanilla CSS

---

## Getting Started

### Prerequisites

- Python 3.10+
- Node.js 18+

### Backend Setup

1. Navigate to the backend directory:
   ```bash
   cd backend
   ```
2. Create and activate a virtual environment:
   ```bash
   python -m venv .venv
   # Windows:
   .\.venv\Scripts\activate
   # macOS/Linux:
   source .venv/bin/activate
   ```
3. Install dependencies:
   ```bash
   pip install -r requirements.txt
   ```
4. Set up environment variables:
   ```bash
   cp .env.example .env
   ```
   Edit the `.env` file to configure your LLM provider:
   ```env
   # Choose your provider
   LLM_PROVIDER=gemini   # Options: gemini, ollama, openai, anthropic, deepseek, openrouter, nvidia_nim

   # Then set the API key for your chosen provider
   GEMINI_API_KEY=your_key_here
   ```

   #### Supported LLM Providers

   | Provider | `LLM_PROVIDER` value | Required Env Vars |
   |---|---|---|
   | Google Gemini | `gemini` | `GEMINI_API_KEY` |
   | Ollama (local) | `ollama` | `OLLAMA_BASE_URL` (default: `http://localhost:11434`) |
   | OpenAI | `openai` | `OPENAI_API_KEY`, `OPENAI_MODEL` |
   | Anthropic | `anthropic` | `ANTHROPIC_API_KEY`, `ANTHROPIC_MODEL` |
   | DeepSeek | `deepseek` | `DEEPSEEK_API_KEY`, `DEEPSEEK_MODEL` |
   | OpenRouter | `openrouter` | `OPENROUTER_API_KEY`, `OPENROUTER_MODEL` |
   | NVIDIA NIM | `nvidia_nim` | `NVIDIA_NIM_API_KEY`, `NVIDIA_NIM_MODEL` |

   > See [`.env.example`](backend/.env.example) for all available settings and their defaults.

5. Run the FastAPI development server:
   ```bash
   uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload
   ```

The backend API will run at `http://localhost:8000`.

### Frontend Setup

1. Navigate to the frontend directory:
   ```bash
   cd frontend
   ```
2. Install npm packages:
   ```bash
   npm install
   ```
3. Run the Vite development server:
   ```bash
   npm run dev
   ```

The frontend will run at `http://localhost:5173`.
