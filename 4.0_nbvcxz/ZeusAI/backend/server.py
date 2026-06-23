"""
Antigravity Faz 7+8 — FastAPI WebSocket Orchestrator
======================================================
Sınırsız bağlam motoru, döngü tespiti, tenacity retry,
DeepSeek bulut + otomatik yedek zinciri, token/maliyet sayacı.

Sunucuyu başlatmak:
    uvicorn backend.server:app --host 0.0.0.0 --port 8000 --reload
"""
import os
import json
import asyncio
import uuid
import time
import traceback
from typing import Optional

from fastapi import FastAPI, WebSocket, WebSocketDisconnect, HTTPException
from fastapi.responses import JSONResponse
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
import litellm
from tenacity import retry, wait_exponential, stop_after_attempt, retry_if_exception_type

from backend.config import (
    get_key, save_key, resolve_model_id, MODEL_CHOICES,
    WORKSPACE_DIR, MAX_AGENT_STEPS, test_api_key,
    route_model_by_complexity,
)
from backend.tools import (
    TOOLS, TOOL_EXECUTORS, get_system_capabilities,
    set_approval_event, grant_approval,
    reset_browser,
)
from backend.memory import (
    add_to_memory, search_memory, log_episode,
    get_recent_episodes, load_project_context,
    compress_if_needed, count_tokens, dynamic_limit,
    is_stuck, UsageTracker, archive_full, load_full_transcript,
    save_checkpoint, load_checkpoint, delete_checkpoint, get_pending_checkpoints,
    MEMORY_AVAILABLE, EPISODES_DB_AVAILABLE,
)

# ==========================================
# FASTAPI UYGULAMASI
# ==========================================
app = FastAPI(title="Antigravity Agent API", version="5.1.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ==========================================
# RETRYABLE EXCEPTIONS (FAZ 7: Tenacity)
# ==========================================
try:
    from litellm.exceptions import (
        APIConnectionError, RateLimitError, Timeout, ServiceUnavailableError, InternalServerError
    )
    RETRYABLE_EXC = (APIConnectionError, RateLimitError, Timeout, ServiceUnavailableError, InternalServerError)
except Exception:
    RETRYABLE_EXC = (Exception,)

# ==========================================
# AKTİF BAĞLANTI DURUMU
# ==========================================
class AgentSession:
    def __init__(self):
        self.model_id: str = "deepseek/deepseek-chat"
        self.messages: list = []
        self.workspace_path: str = ""
        self.project_context: str = ""
        self.task_queue: list = []
        self.approval_event: Optional[asyncio.Event] = None
        self.cancel_event: Optional[asyncio.Event] = None
        self.current_agent: str = "planner"
        self.tool_history: list[dict] = []  # Döngü tespiti için araç geçmişi
        self.usage = UsageTracker()         # Token/maliyet sayacı
        self.session_id: str = ""           # JSONL arşiv için

sessions: dict[str, AgentSession] = {}  # ws_id -> session

# ==========================================
# SYSTEM PROMPT
# ==========================================
SYSTEM_PROMPT = """Sen ZeusAI / Antigravity adında, otonom ve ileri düzey bir yazılım mühendisi ajanısın.

ADIM ADIM DÜŞÜNCE SÜRECİN (ReAct):
1. ANALİZ: Görevi anla. Risk var mı? Hangi araç(lar) gerekli?
2. PLAN: Maksimum 5 adımlık kısa bir yol haritası çiz.
3. AKSİYON: Plandaki ilk aracı çağır.
4. GÖZLEM: Aracın sonucunu değerlendir.
5. YANSIMA: Hata varsa kökünü bul (read_file ile kaynağı oku), aynı kodu KÖRÜ KÖRÜNE tekrar çalıştırma.

KRİTİK KURALLAR:
1. Asla ilk hatada pes etme. Hata aldıysan analiz et ve düzelt (Self-Correction).
2. Güvenlik: Yıkıcı komutlardan kaçın.
3. Python: ASLA `input()` kullanma. Sadece `print()` ile test et.
4. Ağ: Docker sandbox'ta (run_python_code/run_command) internet YOKTUR. browser_* araçları ise GERÇEK internete bağlıdır.
5. Araç Sadakati: Sadece verilen araç listesindekileri kullan. Uydurma araç ismi üretme.
6. İNSAN ONAYI: Eğer bir araçtan `[ONAY GEREKLİ]` yanıtı alırsan, DERHAL araç çağırmayı bırak.

ARAÇ KATEGORİLERİ:
- Dosya: create_file, read_file, edit_file, list_files, diff_files, search_in_files
- Kod/Komut (izole Docker): run_python_code, run_command
- Tarayıcı (gerçek internet): browser_navigate, browser_click, browser_type, browser_screenshot
- Masaüstü: computer_click, computer_type, computer_find_on_screen
- Versiyon: git_status, git_diff, git_commit, git_log
- Ağ/Sistem: http_request, list_processes, web_search, analyze_screen
- Ses: voice_listen, voice_speak
- İzleme: start_screen_monitor, stop_screen_monitor, check_screen_monitor"""


# ==========================================
# WEBSOCKET OLAY GÖNDERİM YARDIMCISI
# ==========================================
async def ws_send(ws: WebSocket, event_type: str, **kwargs):
    payload = {"type": event_type, **kwargs}
    try:
        await ws.send_json(payload)
    except Exception:
        pass


# ==========================================
# LLM ÇAĞRISI (ASYNC STREAMING + TENACITY RETRY + FALLBACK)
# ==========================================
async def call_llm_stream(
    model_id: str,
    messages: list,
    tools: list,
    ws: WebSocket,
    session: AgentSession,
) -> tuple[str, Optional[list]]:
    """Token'ları WebSocket üzerinden akıtır. Hatada fallback zincirine düşer."""
    full_text = ""
    tool_acc: dict[int, dict] = {}
    current_model = model_id
    final_response = None

    fallback_chain = [model_id]
    # Fallback zincirini oluştur
    try:
        if get_key("deepseek") and "deepseek" in model_id:
            try: gemini_key = get_key("gemini")
            except: gemini_key = ""
            try: groq_key = get_key("groq")
            except: groq_key = ""
            if gemini_key: fallback_chain.append("gemini/gemini-2.5-flash")
            if groq_key: fallback_chain.append("groq/llama-3.1-8b-instant")
    except Exception:
        pass

    for attempt_model in fallback_chain:
        if session.cancel_event and session.cancel_event.is_set():
            break
        if attempt_model != model_id:
            await ws_send(ws, "thinking", content=f"Yedek modele geçiliyor: {attempt_model}")

        try:
            stream = await asyncio.to_thread(
                _stream_call_with_retry,
                attempt_model, messages, tools, session
            )

            for chunk in stream:
                if session.cancel_event and session.cancel_event.is_set():
                    break
                try:
                    delta = chunk.choices[0].delta
                except (IndexError, AttributeError):
                    continue

                content_piece = getattr(delta, "content", None)
                if content_piece:
                    full_text += content_piece
                    await ws_send(ws, "text_chunk", content=content_piece)

                deltas_tc = getattr(delta, "tool_calls", None)
                if deltas_tc:
                    for tc in deltas_tc:
                        idx = getattr(tc, "index", 0)
                        if idx not in tool_acc:
                            tool_acc[idx] = {"id": "", "name": "", "arguments": ""}
                        if getattr(tc, "id", None):
                            tool_acc[idx]["id"] = tc.id
                        fn = getattr(tc, "function", None)
                        if fn is not None:
                            if getattr(fn, "name", None):
                                tool_acc[idx]["name"] += fn.name
                            if getattr(fn, "arguments", None):
                                tool_acc[idx]["arguments"] += fn.arguments

            # Başarıyla tamamlandı
            current_model = attempt_model
            break

        except Exception as e:
            print(f"[LLM] {attempt_model} hatası: {e}")
            full_text = ""  # Reset, önceki modelin çıktısı geçersiz
            tool_acc = {}
            if attempt_model == fallback_chain[-1]:
                await ws_send(ws, "error", content=f"Tüm modeller başarısız: {str(e)}")
                return None, None
            continue

    # Finalize streaming
    if full_text:
        await ws_send(ws, "final", content=full_text)

    # Usage track
    session.usage.total_tokens += len(full_text) // 4

    # Build tool_calls
    tool_calls = None
    if tool_acc:
        tool_calls = []
        for idx in sorted(tool_acc.keys()):
            t = tool_acc[idx]
            tool_calls.append({
                "id": t["id"] or f"call_{idx}_{int(time.time()*1000)}",
                "type": "function",
                "function": {"name": t["name"], "arguments": t["arguments"] or "{}"},
            })

    return full_text, tool_calls


@retry(
    retry=retry_if_exception_type(RETRYABLE_EXC),
    wait=wait_exponential(multiplier=1, min=1, max=30),
    stop=stop_after_attempt(4),
    reraise=True,
)
def _stream_call_with_retry(model_id: str, messages: list, tools: list, session):
    """Tenacity ile 4 deneme exponential backoff. Thread-safe sync wrapper."""
    return litellm.completion(
        model=model_id,
        messages=messages,
        tools=tools,
        tool_choice="auto",
        temperature=0.2,
        stream=True,
        timeout=120,
    )


# ==========================================
# ARAÇ ÇALIŞTIRMA MOTORU
# ==========================================
async def execute_tool(
    func_name: str,
    func_args: dict,
    ws: WebSocket,
    session: AgentSession,
) -> dict:
    await ws_send(ws, "tool_call", tool=func_name, args=func_args, status="executing")

    if func_name not in TOOL_EXECUTORS:
        result = {
            "ok": False,
            "text": f"KRİTİK HATA: '{func_name}' kayıtlı değil.",
        }
        await ws_send(ws, "tool_result", tool=func_name, content=result["text"], success=False)
        return result

    try:
        executor = TOOL_EXECUTORS[func_name]
        if asyncio.iscoroutinefunction(executor):
            result = await executor(**func_args)
        else:
            result = await asyncio.to_thread(executor, **func_args)
    except Exception as e:
        result = {"ok": False, "text": f"Araç Hatası: {str(e)}"}

    # Döngü tespiti için kaydet
    session.tool_history.append({"tool": func_name, "args": func_args})

    # Onay kontrolü
    if isinstance(result, dict) and result.get("approval_needed"):
        await ws_send(
            ws, "approval_needed",
            content=result.get("text", ""),
            command=result.get("command", ""),
            action=result.get("action", func_name),
            params=result.get("params", {}),
        )
        session.approval_event = asyncio.Event()
        set_approval_event(session.approval_event)
        try:
            await asyncio.wait_for(session.approval_event.wait(), timeout=120)
            from backend.tools import get_approval_result as _gar
            from backend.tools import (
                execute_computer_click_approved,
                execute_computer_type_approved,
            )
            if _gar():
                action = result.get("action", func_name)
                params = result.get("params", {})
                if action == "computer_click":
                    result = await execute_computer_click_approved(**params)
                elif action == "computer_type":
                    result = await execute_computer_type_approved(**params)
                else:
                    result = await executor(**func_args) if asyncio.iscoroutinefunction(executor) else await asyncio.to_thread(executor, **func_args)
            else:
                result = {"ok": False, "text": "Kullanıcı işlemi reddetti."}
        except asyncio.TimeoutError:
            result = {"ok": False, "text": "Onay zaman aşımı (120sn)."}
        finally:
            session.approval_event = None

    is_ok = result.get("ok", True) if isinstance(result, dict) else True
    result_text = result.get("text", str(result)) if isinstance(result, dict) else str(result)

    await ws_send(
        ws, "tool_result",
        tool=func_name,
        content=result_text,
        success=is_ok,
        images=result.get("images") if isinstance(result, dict) else None,
    )

    if isinstance(result, dict) and result.get("images"):
        for img_b64 in result["images"]:
            await ws_send(ws, "image", content=img_b64, format="png")

    return result if isinstance(result, dict) else {"ok": True, "text": str(result)}


# ==========================================
# ANA AJAN DÖNGÜSÜ (FAZ 7: Döngü tespitli)
# ==========================================
async def run_agent_loop(
    ws: WebSocket,
    session: AgentSession,
    user_prompt: str,
):
    session.cancel_event = asyncio.Event()
    session.tool_history = []
    tools_used: list[str] = []
    step = 0
    session.session_id = str(uuid.uuid4())[:8]

    # Model ID'yi çözümle
    try:
        model_id = resolve_model_id(session.model_id)
    except ValueError as e:
        await ws_send(ws, "error", content=str(e))
        return

    # Mesajları hazırla
    messages = [{"role": "system", "content": SYSTEM_PROMPT}]
    if session.project_context:
        messages[0]["content"] += "\n\n" + session.project_context

    memories = search_memory(user_prompt)
    if memories:
        memory_ctx = "\n--- GEÇMİŞ BAĞLAM ---\n" + "\n".join(memories) + "\n---------------------\n"
        messages[0]["content"] += memory_ctx

    messages.append({"role": "user", "content": user_prompt})
    session.messages = messages.copy()

    # İlk mesajı JSONL arşivine yaz
    archive_full({"role": "user", "content": user_prompt}, session.session_id)

    # Context sıkıştırma
    messages = await compress_if_needed(model_id, messages, session.session_id)

    while step < MAX_AGENT_STEPS:
        if session.cancel_event.is_set():
            await ws_send(ws, "error", content="Görev iptal edildi.")
            break

        step += 1
        limit = dynamic_limit(model_id)
        current_tokens = count_tokens(messages)
        await ws_send(ws, "thinking", content=f"Adım {step}: Analiz ediliyor... ({current_tokens:,}/{limit:,} token)")

        # LLM çağrısı
        full_text, tool_calls = await call_llm_stream(model_id, messages, TOOLS, ws, session)

        if session.cancel_event.is_set():
            break

        # Usage gönder
        await ws_send(ws, "usage", usage=session.usage.summary())

        assistant_msg = {"role": "assistant", "content": full_text or ""}
        if tool_calls:
            assistant_msg["tool_calls"] = tool_calls
        messages.append(assistant_msg)
        archive_full(assistant_msg, session.session_id)

        if not tool_calls:
            if MEMORY_AVAILABLE:
                add_to_memory(f"User: {user_prompt[:100]} | AI: {(full_text or '')[:200]}")
            if EPISODES_DB_AVAILABLE:
                log_episode(goal=user_prompt, tools_used=tools_used,
                            outcome=(full_text or "")[:300], step_count=step, model=model_id)
                delete_checkpoint(session.session_id)
            return

        # Araçları çalıştır
        for tool_call in tool_calls:
            func_name = tool_call["function"]["name"]
            try:
                func_args = json.loads(tool_call["function"]["arguments"] or "{}")
            except json.JSONDecodeError:
                func_args = {}

            if "timeout" in func_args:
                try: func_args["timeout"] = int(float(str(func_args["timeout"])))
                except (ValueError, TypeError): func_args["timeout"] = 10

            tools_used.append(func_name)
            result = await execute_tool(func_name, func_args, ws, session)

            if session.cancel_event.is_set():
                break

            result_text = result.get("text", str(result)) if isinstance(result, dict) else str(result)

            messages.append({"role": "tool", "tool_call_id": tool_call["id"], "content": result_text})
            archive_full({"role": "tool", "content": result_text[:500]}, session.session_id)

            # Onay gerekiyorsa dur
            if "[ONAY GEREKLİ]" in result_text:
                try:
                    approval_resp = await asyncio.to_thread(
                        litellm.completion, model=model_id, messages=messages,
                        temperature=0.2, max_tokens=200,
                    )
                    approval_msg = approval_resp.choices[0].message.content
                    await ws_send(ws, "final", content=approval_msg)
                    messages.append({"role": "assistant", "content": approval_msg})
                except Exception:
                    pass
                await ws_send(ws, "thinking", content="Kullanıcı onayı bekleniyor...")
                save_checkpoint(session.session_id, {"goal": user_prompt, "step": step, "tools_used": tools_used, "model": model_id})
                return

        # Döngü tespiti (FAZ 7)
        if is_stuck(session.tool_history):
            await ws_send(ws, "error", content="🔄 Döngü tespit edildi: aynı araç aynı argümanla 3 kez tekrarlandı. Görev duraklatıldı.")
            break

        # Periyodik checkpoint
        if step % 5 == 0:
            save_checkpoint(session.session_id, {"goal": user_prompt, "step": step, "tools_used": tools_used, "model": model_id})

        messages = await compress_if_needed(model_id, messages, session.session_id)

    # Max adım veya döngü kırılması
    await ws_send(ws, "error", content=f"⚠️ Görev {step} adımda sonlandı.")
    if EPISODES_DB_AVAILABLE:
        log_episode(goal=user_prompt, tools_used=tools_used,
                    outcome="Sınır/döngü", step_count=step, model=model_id)


# ==========================================
# WEBSOCKET ENDPOINT
# ==========================================
@app.websocket("/ws/agent")
async def agent_websocket(ws: WebSocket):
    await ws.accept()
    ws_id = str(uuid.uuid4())
    session = AgentSession()
    sessions[ws_id] = session

    # Bekleyen checkpoint var mı?
    pending = get_pending_checkpoints()
    if pending:
        await ws_send(ws, "thinking",
                      content=f"🚀 ZeusAI v5.1 hazır. {len(pending)} tamamlanmamış görev bulundu. 'Devam et' yazarsanız kaldığınız yerden sürer.")
    else:
        await ws_send(ws, "thinking", content="🚀 ZeusAI v5.1 hazır. Komutunuzu bekliyorum.")

    try:
        while True:
            raw = await ws.receive_text()
            try:
                data = json.loads(raw)
            except json.JSONDecodeError:
                await ws_send(ws, "error", content="Geçersiz JSON.")
                continue

            msg_type = data.get("type", "")

            if msg_type == "user_message":
                content = data.get("content", data.get("message", ""))
                if content.strip():
                    await run_agent_loop(ws, session, content.strip())

            elif msg_type == "approve":
                approved = data.get("approved", False)
                if approved:
                    grant_approval()
                elif session.approval_event:
                    session.approval_event.set()
                await ws_send(ws, "thinking", content="Onay alındı.")
                last_user_msg = ""
                for m in reversed(session.messages):
                    if m.get("role") == "user":
                        last_user_msg = m.get("content", "")
                        break
                if last_user_msg and data.get("continue", True):
                    await run_agent_loop(ws, session, last_user_msg)

            elif msg_type == "set_model":
                session.model_id = data.get("model", session.model_id)
                await ws_send(ws, "thinking", content=f"Model: {session.model_id}")

            elif msg_type == "set_api_key":
                service = data.get("service", "")
                key = data.get("key", "")
                if service and key:
                    save_key(service, key)
                    await ws_send(ws, "thinking", content=f"API Key kaydedildi: {service}")

            elif msg_type == "test_api_key":
                provider = data.get("provider", "")
                test_key = data.get("key", "")
                ok = test_api_key(provider, test_key)
                await ws_send(ws, "key_test_result", provider=provider, ok=ok)

            elif msg_type == "load_workspace":
                path = data.get("path", "")
                if path and os.path.isdir(path):
                    session.workspace_path = path
                    session.project_context = load_project_context(path)
                    await ws_send(ws, "thinking", content=f"Proje yüklendi: {path}")

            elif msg_type == "load_full_transcript":
                transcript = load_full_transcript(session.session_id) if session.session_id else []
                await ws_send(ws, "full_transcript", messages=transcript)

            elif msg_type == "clear_session":
                session.messages = []
                session.project_context = ""
                session.workspace_path = ""
                session.tool_history = []
                session.usage = UsageTracker()
                if session.cancel_event:
                    session.cancel_event.set()
                await ws_send(ws, "thinking", content="Oturum temizlendi.")

            elif msg_type == "cancel":
                if session.cancel_event:
                    session.cancel_event.set()
                await ws_send(ws, "thinking", content="Görev iptal ediliyor...")

            else:
                await ws_send(ws, "error", content=f"Bilinmeyen tip: {msg_type}")

    except WebSocketDisconnect:
        print(f"[WS] Bağlantı koptu: {ws_id}")
    except Exception as e:
        print(f"[WS] Hata: {e}\n{traceback.format_exc()}")
    finally:
        if ws_id in sessions:
            sessions.pop(ws_id, None)
        try:
            await reset_browser()
        except Exception:
            pass


# ==========================================
# REST API ENDPOINTS
# ==========================================

@app.get("/api/status")
async def api_status():
    capabilities = get_system_capabilities()
    return JSONResponse({
        "status": "running",
        "version": "5.1.0",
        "services": {
            "docker": capabilities["docker"],
            "chromadb": capabilities["chromadb"],
            "playwright": capabilities["playwright"],
            "ollama": True,
            "backend": True,
        },
        "tools_count": capabilities["tools_count"],
        "plugins_count": capabilities["plugins_count"],
        "workspace": capabilities["workspace"],
    })


@app.get("/api/episodes")
async def api_episodes():
    episodes = get_recent_episodes(20)
    return JSONResponse({"episodes": episodes})


class FileRequest(BaseModel):
    filename: str
    content: str = ""


@app.get("/api/files/{filename:path}")
async def api_get_file(filename: str):
    filepath = os.path.join(WORKSPACE_DIR, os.path.basename(filename))
    if not os.path.exists(filepath):
        raise HTTPException(status_code=404, detail="Dosya bulunamadı")
    try:
        content = open(filepath, "r", encoding="utf-8").read()
        return JSONResponse({"filename": filename, "content": content})
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/api/files")
async def api_save_file(req: FileRequest):
    filepath = os.path.join(WORKSPACE_DIR, os.path.basename(req.filename))
    try:
        os.makedirs(os.path.dirname(filepath), exist_ok=True)
        with open(filepath, "w", encoding="utf-8") as f:
            f.write(req.content)
        return JSONResponse({"ok": True, "filename": req.filename})
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/models")
async def api_models():
    return JSONResponse({"models": MODEL_CHOICES})


class KeyTestRequest(BaseModel):
    provider: str
    key: str = ""


@app.post("/api/test-key")
async def api_test_key(req: KeyTestRequest):
    ok = test_api_key(req.provider, req.key)
    return JSONResponse({"provider": req.provider, "ok": ok})


@app.get("/api/checkpoints")
async def api_checkpoints():
    return JSONResponse({"checkpoints": get_pending_checkpoints()})


@app.get("/health")
async def health():
    return {"status": "ok", "service": "antigravity-agent"}


if __name__ == "__main__":
    import uvicorn
    print("🚀 ZeusAI v5.1 — FastAPI Agent Orchestrator")
    print(f"   WebSocket: ws://localhost:8000/ws/agent")
    print(f"   API:       http://localhost:8000/api/status")
    print(f"   Workspace: {WORKSPACE_DIR}")
    print(f"   Araç Sayısı: {len(TOOLS)}")
    uvicorn.run(app, host="0.0.0.0", port=8000, log_level="info")