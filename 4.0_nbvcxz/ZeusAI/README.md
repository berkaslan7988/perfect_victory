# Zeus AI — Autonomous Multi-Agent Coding Assistant

Zeus AI is an autonomous coding agent that
plans, writes, runs, and validates software on its own. Instead of a single LLM
loop, it splits work across **four specialized agents** that coordinate through an
async orchestrator.

## Architecture

**Agents** (`backend/agents.py`) — each has its own system prompt, model, and a
restricted subset of tools:

| Agent | Role | Tool subset |
|-------|------|-------------|
| **Planner** | Breaks a goal into ordered, dependency-aware `TaskStep`s | planning only |
| **Coder** | Writes/edits code, runs it, commits | file + code + git tools |
| **Researcher** | Searches the web and reads pages | browser + web tools |
| **Validator** | Reviews and verifies the Coder's output | file/read tools |

Steps carry `depends_on` links, so the orchestrator runs independent steps in
parallel and dependent ones in sequence.

**Tooling** (`backend/tools.py`) — ~25 function-calling tools grouped into
subsets: file ops, code/command execution **inside a Docker sandbox**
(`python:3.11-slim`), git operations, a real Playwright/Chromium browser,
desktop control (click/type), screen analysis, and voice (Whisper STT + TTS).
Critical commands require explicit user approval.

**Model routing** (`backend/config.py`) — resolves API keys in priority order
(`.env` → OS keychain → runtime memory) and routes each call to a model by task
complexity, with an automatic fallback chain and a token/cost counter. Uses
`litellm` so any provider (Gemini, Groq, DeepSeek, OpenRouter, HuggingFace) works
behind one interface.

**Memory** — ChromaDB vector store plus an episodes DB for long-term recall.

**Background monitoring** (`backend/screen_monitor.py`) — continuously watches the
screen and auto-notifies the agent when errors/exceptions appear.

## Stack

- **Backend:** Python, FastAPI + WebSocket orchestrator, `litellm`, `tenacity`
  retry, ChromaDB, Docker sandbox, Playwright
- **Frontend:** Tauri (Rust) + React 18 + Vite, Monaco editor, xterm.js terminal,
  react-arborist file tree

## Run

```bash
# 1. Backend
cd ZeusAI
cp .env.example .env          # add your own API keys
pip install -r requirements.txt   # (litellm, fastapi, uvicorn, chromadb, ...)
playwright install            # tarayıcı binary'lerini indirir, tools.py içinde Playwright kullanılıyor
uvicorn backend.server:app --host 0.0.0.0 --port 8000 --reload

# 2. Frontend (separate terminal)
cd ZeusAI/frontend
npm install
npm run dev                   # or: npm run tauri dev  for the desktop app
```

Docker must be running for the code-execution sandbox.

> ⚠️ Zeus AI can execute code and control the desktop. Run it only in an
> environment you trust. Critical actions are gated behind approval prompts.
