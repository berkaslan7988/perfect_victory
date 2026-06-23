import streamlit as st
import time
import os
import json
import subprocess
import hashlib
import base64
import io
import difflib
import threading
import sqlite3
import importlib.util
import datetime

from litellm import completion
import litellm
from tenacity import retry, wait_exponential, stop_after_attempt, retry_if_exception_type

import mss
import google.generativeai as genai
from PIL import Image
from tavily import TavilyClient
import docker
from docker.errors import DockerException, ImageNotFound
import chromadb

import keyring
from dotenv import load_dotenv

# ==========================================
# OPSİYONEL BAĞIMLILIKLAR (FAZ 2 ARAÇLARI)
# Kurulu değilse veya ortam desteklemiyorsa (headless sunucu vb.)
# uygulama çökmesin, ilgili araçlar sadece "kullanılamıyor" der.
# ==========================================
try:
    import pyautogui
    pyautogui.FAILSAFE = True
    PYAUTOGUI_AVAILABLE = True
except Exception:
    PYAUTOGUI_AVAILABLE = False

try:
    from playwright.sync_api import sync_playwright
    PLAYWRIGHT_AVAILABLE = True
except Exception:
    PLAYWRIGHT_AVAILABLE = False

try:
    from git import Repo, InvalidGitRepositoryError
    GIT_AVAILABLE = True
except Exception:
    GIT_AVAILABLE = False

try:
    import httpx
    HTTPX_AVAILABLE = True
except Exception:
    HTTPX_AVAILABLE = False

try:
    import psutil
    PSUTIL_AVAILABLE = True
except Exception:
    PSUTIL_AVAILABLE = False

load_dotenv()
litellm.suppress_debug_info = True

# Tenacity ile yeniden deneme için retry edilebilir hata tipleri (FAZ 1)
try:
    from litellm.exceptions import (
        APIConnectionError, RateLimitError, Timeout, ServiceUnavailableError, InternalServerError
    )
    RETRYABLE_EXC = (APIConnectionError, RateLimitError, Timeout, ServiceUnavailableError, InternalServerError)
except Exception:
    RETRYABLE_EXC = (Exception,)

# ==========================================
# 1. DOCKER SANDBOX BAŞLATMA (FAZ 2/3)
# ==========================================
try:
    docker_client = docker.from_env()
    docker_client.ping()
    DOCKER_AVAILABLE = True
    SANDBOX_IMAGE = "python:3.11-slim"
    try:
        docker_client.images.get(SANDBOX_IMAGE)
    except ImageNotFound:
        print(f"📦 {SANDBOX_IMAGE} imajı indiriliyor...")
        docker_client.images.pull(SANDBOX_IMAGE)
except DockerException:
    DOCKER_AVAILABLE = False
    print("⚠️ Docker bulunamadı. Subprocess modu.")

# ==========================================
# 2. CHROMADB HAFIZA SİSTEMİ (FAZ 3/4)
# ==========================================
CHROMA_DB_PATH = "./chroma_db"
os.makedirs(CHROMA_DB_PATH, exist_ok=True)
try:
    chroma_client = chromadb.PersistentClient(path=CHROMA_DB_PATH)
    try:
        memory_collection = chroma_client.get_collection(name="antigravity_memory")
    except Exception:
        memory_collection = chroma_client.create_collection(name="antigravity_memory")
    MEMORY_AVAILABLE = True
except Exception:
    MEMORY_AVAILABLE = False

def add_to_memory(text: str):
    if not MEMORY_AVAILABLE: return
    try:
        doc_id = hashlib.md5(text.encode()).hexdigest()
        memory_collection.add(documents=[text], ids=[doc_id])
    except: pass

def search_memory(query: str, n_results: int = 2) -> list:
    if not MEMORY_AVAILABLE: return []
    try:
        results = memory_collection.query(query_texts=[query], n_results=n_results)
        return results['documents'][0] if results['documents'] else []
    except: return []

# ==========================================
# 2b. SQLİTE EPİSODİK LOG (FAZ 4)
# ==========================================
EPISODES_DB = "./antigravity_episodes.db"

def _init_episodes_db() -> bool:
    try:
        conn = sqlite3.connect(EPISODES_DB)
        conn.execute("""CREATE TABLE IF NOT EXISTS episodes(
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            ts TEXT NOT NULL,
            goal TEXT,
            tools_used TEXT,
            outcome TEXT,
            step_count INTEGER,
            model TEXT,
            files_created TEXT
        )""")
        conn.commit()
        conn.close()
        return True
    except Exception as e:
        print(f"[DB HATA] {e}")
        return False

def log_episode(goal: str, tools_used: list, outcome: str, step_count: int, model: str = "", files_created: list = None):
    try:
        conn = sqlite3.connect(EPISODES_DB)
        conn.execute(
            "INSERT INTO episodes(ts,goal,tools_used,outcome,step_count,model,files_created) VALUES(?,?,?,?,?,?,?)",
            (
                datetime.datetime.now().isoformat(),
                goal[:300],
                json.dumps(list(set(tools_used)), ensure_ascii=False),
                outcome[:500],
                step_count,
                model,
                json.dumps(files_created or [], ensure_ascii=False),
            )
        )
        conn.commit()
        conn.close()
    except Exception as e:
        print(f"[DB HATA] {str(e)}")

def get_recent_episodes(n: int = 8) -> list:
    try:
        conn = sqlite3.connect(EPISODES_DB)
        cur = conn.execute(
            "SELECT ts, goal, tools_used, outcome, step_count, model FROM episodes ORDER BY id DESC LIMIT ?", (n,)
        )
        cols = [c[0] for c in cur.description]
        rows = [dict(zip(cols, row)) for row in cur.fetchall()]
        conn.close()
        return rows
    except Exception:
        return []

EPISODES_DB_AVAILABLE = _init_episodes_db()

# ==========================================
# 2c. CONTEXT WINDOW YÖNETİMİ (FAZ 4)
# ==========================================
try:
    import tiktoken
    TIKTOKEN_AVAILABLE = True
    _TIKTOKEN_ENC = tiktoken.get_encoding("cl100k_base")
except Exception:
    TIKTOKEN_AVAILABLE = False
    _TIKTOKEN_ENC = None

def _count_tokens(messages: list) -> int:
    if TIKTOKEN_AVAILABLE and _TIKTOKEN_ENC:
        try:
            return sum(len(_TIKTOKEN_ENC.encode(str(m))) for m in messages)
        except Exception:
            pass
    return sum(len(str(m)) // 4 for m in messages)

def compress_if_needed(model_id: str, messages: list) -> list:
    """Token sayısı 80 000'i aşarsa ortadaki mesajları özetle, baş+son koru."""
    total = _count_tokens(messages)
    if total < 80_000:
        return messages
    add_log("sys", f"[CTX] {total:,} token — sıkıştırılıyor...")
    system_msgs  = [m for m in messages if m.get("role") == "system"]
    non_system   = [m for m in messages if m.get("role") != "system"]
    if len(non_system) <= 8:
        return messages
    middle = non_system[:-6]
    tail   = non_system[-6:]
    try:
        summary_resp = completion(
            model=model_id,
            messages=[{"role": "user", "content":
                f"Aşağıdaki konuşmayı max 300 kelimede Türkçe özetle. Sadece özeti yaz:\n\n{str(middle)[:8000]}"}],
            temperature=0.1, max_tokens=500
        )
        summary_text = summary_resp.choices[0].message.content
        add_log("ok", f"[CTX] {len(middle)} mesaj özetlendi.")
    except Exception as e:
        add_log("sys", f"[CTX] Sıkıştırma hatası: {e}")
        return messages
    return system_msgs + [{"role": "system", "content": f"[KONUŞMA ÖZETİ]: {summary_text}"}] + tail

# ==========================================
# 2d. PROJE WORKSPACE KONSEPTİ (FAZ 4)
# ==========================================
def load_project_context(path: str) -> str:
    """Verilen klasördeki README, dosya ağacı ve son .py dosyalarını özetle."""
    if not path or not os.path.isdir(path):
        return ""
    parts = ["=== PROJE BAĞLAMI ==="]
    for rname in ("README.md", "README.txt", "readme.md"):
        rpath = os.path.join(path, rname)
        if os.path.exists(rpath):
            try:
                parts.append("README:\n" + open(rpath, encoding="utf-8").read()[:1500])
                break
            except Exception:
                pass
    tree_lines = []
    SKIP_DIRS = {"__pycache__", "node_modules", ".git", "venv", "env", ".venv", "dist", "build"}
    for root, dirs, files in os.walk(path):
        dirs[:] = [d for d in dirs if not d.startswith(".") and d not in SKIP_DIRS]
        level = root.replace(path, "").count(os.sep)
        if level > 2:
            continue
        indent = "  " * level
        rel = os.path.relpath(root, path)
        if rel != ".":
            tree_lines.append(f"{indent}{os.path.basename(root)}/")
        sub_indent = "  " * (level + 1)
        for f in files[:12]:
            tree_lines.append(f"{sub_indent}{f}")
    if tree_lines:
        parts.append("DOSYA YAPISI:\n" + "\n".join(tree_lines[:60]))
    py_files = []
    for root, _, files in os.walk(path):
        for f in files:
            if f.endswith(".py"):
                fp = os.path.join(root, f)
                try:
                    py_files.append((fp, os.path.getmtime(fp)))
                except Exception:
                    pass
    py_files.sort(key=lambda x: x[1], reverse=True)
    recent = []
    for fp, _ in py_files[:5]:
        try:
            content = open(fp, encoding="utf-8").read()
            rel = os.path.relpath(fp, path)
            recent.append(f"{rel}:\n{content[:600]}\n...")
        except Exception:
            pass
    if recent:
        parts.append("SON DEĞİŞTİRİLEN DOSYALAR:\n" + "\n\n".join(recent))
    parts.append("=== PROJE BAĞLAMI SONU ===")
    return "\n\n".join(parts)

# ==========================================
# 2e. PLUGIN SİSTEMİ (FAZ 2)
# ==========================================
PLUGINS_DIR = "./plugins"
os.makedirs(PLUGINS_DIR, exist_ok=True)

def load_plugins() -> list:
    """plugins/ klasöründeki .py dosyalarından (TOOL_DEF + execute) çiftlerini yükler."""
    loaded = []
    if not os.path.isdir(PLUGINS_DIR):
        return loaded
    for fname in sorted(os.listdir(PLUGINS_DIR)):
        if not fname.endswith(".py") or fname.startswith("_"):
            continue
        fpath = os.path.join(PLUGINS_DIR, fname)
        try:
            spec   = importlib.util.spec_from_file_location(fname[:-3], fpath)
            module = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(module)
            tool_def = getattr(module, "TOOL_DEF", None)
            executor = getattr(module, "execute", None)
            if tool_def and callable(executor):
                loaded.append((tool_def, executor))
                print(f"[PLUGIN] Yüklendi: {fname} → {tool_def['function']['name']}")
        except Exception as e:
            print(f"[PLUGIN HATA] {fname}: {e}")
    return loaded

_PLUGIN_ENTRIES     = load_plugins()
_PLUGIN_TOOL_DEFS   = [td for td, _ in _PLUGIN_ENTRIES]
_PLUGIN_EXECUTORS   = {td["function"]["name"]: ex for td, ex in _PLUGIN_ENTRIES}

# ==========================================
# 3. GÜVENLİ API KEY YÖNETİMİ (FAZ 1)
# Öncelik: .env / ortam değişkeni > OS Keychain > sidebar manuel giriş
# ==========================================
KEYRING_SERVICE = "antigravity"

def get_key(service: str) -> str:
    env_val = os.getenv(f"{service.upper()}_API_KEY")
    if env_val:
        return env_val
    try:
        kr_val = keyring.get_password(KEYRING_SERVICE, service)
        if kr_val:
            return kr_val
    except Exception:
        pass
    return st.session_state.get(f"{service}_key", "")

def save_key(service: str, key: str):
    if not key:
        return
    st.session_state[f"{service}_key"] = key
    try:
        keyring.set_password(KEYRING_SERVICE, service, key)
    except Exception:
        pass

# ==========================================
# SAYFA AYARLARI & CSS
# ==========================================
st.set_page_config(page_title="Project Antigravity", page_icon="🚀", layout="wide", initial_sidebar_state="expanded")
st.markdown("""
<style>
    .stApp { background: linear-gradient(135deg, #0F172A 0%, #1E1B4B 50%, #000000 100%); background-attachment: fixed; }
    [data-testid="stSidebar"] { background: rgba(255, 255, 255, 0.03) !important; backdrop-filter: blur(20px); border-right: 1px solid rgba(255, 255, 255, 0.1); }
    .stChatInput textarea { background: rgba(255, 255, 255, 0.05) !important; border: 1px solid rgba(255, 255, 255, 0.1) !important; border-radius: 15px !important; color: white !important; }
    h1, h2, h3, h4, p, span, label { color: #E0E7FF !important; }
    .terminal { background: rgba(0, 0, 0, 0.7); border: 1px solid rgba(255, 255, 255, 0.1); border-radius: 10px; padding: 15px; font-family: 'Consolas', monospace; font-size: 12px; color: #94A3B8; max-height: 400px; overflow-y: auto; }
    .log-sys { color: #60A5FA; } .log-tool { color: #FBBF24; } .log-ok { color: #4ADE80; } .log-vis { color: #A78BFA; } .log-wait { color: #F87171; }
</style>
""", unsafe_allow_html=True)
st.markdown('<link href="https://fonts.googleapis.com/icon?family=Material+Icons" rel="stylesheet">', unsafe_allow_html=True)
def icon(name, color="#67E8F9", size="20px"):
    return f'<span class="material-icons" style="color:{color};font-size:{size};vertical-align:middle;">{name}</span>'

# ==========================================
# SESSION STATE & WORKSPACE
# ==========================================
if "messages" not in st.session_state: st.session_state.messages = []
if "logs" not in st.session_state: st.session_state.logs = [("[SYS]", "Antigravity Core initialized.")]
if "active_tool" not in st.session_state: st.session_state.active_tool = "None (Idle)"
if "fail_count" not in st.session_state: st.session_state.fail_count = 0
if "project_path" not in st.session_state: st.session_state.project_path = ""
if "project_context" not in st.session_state: st.session_state.project_context = ""

WORKSPACE_DIR = os.path.abspath("./antigravity_workspace")
os.makedirs(WORKSPACE_DIR, exist_ok=True)

def add_log(level, msg):
    st.session_state.logs.append((level, msg))
    if len(st.session_state.logs) > 100: st.session_state.logs.pop(0)

# Çalışan araca canlı stdout basmak için ortak "kutu" referansı (FAZ 3)
_CURRENT_STREAM_PLACEHOLDER = {"box": None}
def set_stream_placeholder(box):
    _CURRENT_STREAM_PLACEHOLDER["box"] = box

# ==========================================
# İNSAN ONAY MEKANİZMASI (HUMAN-IN-THE-LOOP)
# ==========================================
def check_user_approval() -> bool:
    """Kullanıcının son mesajında onay ifadesi var mı diye kontrol eder."""
    last_user_msg = ""
    for m in reversed(st.session_state.messages):
        if m["role"] == "user":
            last_user_msg = m["content"].lower()
            break
    approval_keywords = ["onaylıyorum", "evet", "yap", "devam et", "onay", "ok", "sil", "kaldır", "yes"]
    return any(w in last_user_msg for w in approval_keywords)

# ==========================================
# STREAMING LLM ÇAĞRISI + OTOMATİK RETRY (FAZ 1)
# ==========================================
@retry(retry=retry_if_exception_type(RETRYABLE_EXC),
       wait=wait_exponential(multiplier=1, min=1, max=20),
       stop=stop_after_attempt(4), reraise=True)
def stream_llm_response(model_id: str, messages: list, tools: list, placeholder):
    """LLM yanıtını token-token akıtır. Tool-call delta'larını biriktirip
    OpenAI uyumlu tool_calls listesi olarak döner. Ağ hatalarında tenacity
    ile otomatik exponential backoff yapar."""
    full_text = ""
    tool_acc = {}

    stream = completion(model=model_id, messages=messages, tools=tools,
                         tool_choice="auto", temperature=0.2, stream=True, timeout=60)

    for chunk in stream:
        try:
            delta = chunk.choices[0].delta
        except (IndexError, AttributeError):
            continue

        content_piece = getattr(delta, "content", None)
        if content_piece:
            full_text += content_piece
            placeholder.markdown(full_text + "▋")

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

    if full_text:
        placeholder.markdown(full_text)
    else:
        placeholder.empty()

    tool_calls = None
    if tool_acc:
        tool_calls = []
        for idx in sorted(tool_acc.keys()):
            t = tool_acc[idx]
            tool_calls.append({
                "id": t["id"] or f"call_{idx}_{int(time.time()*1000)}",
                "type": "function",
                "function": {"name": t["name"], "arguments": t["arguments"] or "{}"}
            })
    return full_text, tool_calls

# ==========================================
# ARAÇLAR (TOOLS)
# ==========================================
TOOLS = [
    {"type": "function", "function": {"name": "create_file", "description": "Workspace içinde dosya oluşturur.", "parameters": {"type": "object", "properties": {"filename": {"type": "string"}, "content": {"type": "string"}}, "required": ["filename", "content"]}}},
    {"type": "function", "function": {"name": "list_files", "description": "Workspace dosyalarını listeler.", "parameters": {"type": "object", "properties": {}}}},
    {"type": "function", "function": {"name": "analyze_screen", "description": "Ekran görüntüsü alıp analiz eder.", "parameters": {"type": "object", "properties": {"query": {"type": "string"}}, "required": ["query"]}}},
    {"type": "function", "function": {"name": "web_search", "description": "İnternette arama yapar.", "parameters": {"type": "object", "properties": {"query": {"type": "string"}}, "required": ["query"]}}},
    {"type": "function", "function": {"name": "run_python_code", "description": "Docker sandbox içinde Python kodu çalıştırır. Matplotlib grafikleri otomatik yakalanıp gösterilir.", "parameters": {"type": "object", "properties": {"code": {"type": "string"}, "timeout": {"type": "integer"}}, "required": ["code"]}}},
    {"type": "function", "function": {"name": "run_command", "description": "Docker sandbox içinde shell komutu çalıştırır. KRİTİK KOMUTLAR İÇİN ONAY GEREKTİRİR.", "parameters": {"type": "object", "properties": {"command": {"type": "string"}}, "required": ["command"]}}},
    {"type": "function", "function": {"name": "read_file", "description": "Workspace'den dosya okur.", "parameters": {"type": "object", "properties": {"path": {"type": "string"}}, "required": ["path"]}}},
    {"type": "function", "function": {"name": "edit_file", "description": "Workspace'deki dosyayı günceller.", "parameters": {"type": "object", "properties": {"path": {"type": "string"}, "content": {"type": "string"}}, "required": ["path", "content"]}}},

    {"type": "function", "function": {"name": "browser_navigate", "description": "Gerçek bir tarayıcıda (Playwright/Chromium) verilen URL'ye gider. Gerçek internet erişimi vardır.", "parameters": {"type": "object", "properties": {"url": {"type": "string"}}, "required": ["url"]}}},
    {"type": "function", "function": {"name": "browser_click", "description": "Açık tarayıcı sayfasında CSS selector ile belirtilen elemente tıklar.", "parameters": {"type": "object", "properties": {"selector": {"type": "string"}}, "required": ["selector"]}}},
    {"type": "function", "function": {"name": "browser_type", "description": "Açık tarayıcı sayfasında CSS selector ile belirtilen input alanına metin yazar.", "parameters": {"type": "object", "properties": {"selector": {"type": "string"}, "text": {"type": "string"}}, "required": ["selector", "text"]}}},
    {"type": "function", "function": {"name": "browser_screenshot", "description": "Açık tarayıcı sayfasının ekran görüntüsünü alır ve Gemini Vision ile analiz eder.", "parameters": {"type": "object", "properties": {"query": {"type": "string"}}, "required": ["query"]}}},

    {"type": "function", "function": {"name": "computer_click", "description": "Kullanıcının gerçek masaüstünde belirtilen koordinata tıklar. ONAY GEREKTİRİR.", "parameters": {"type": "object", "properties": {"x": {"type": "integer"}, "y": {"type": "integer"}, "button": {"type": "string"}}, "required": ["x", "y"]}}},
    {"type": "function", "function": {"name": "computer_type", "description": "Aktif pencereye klavye ile metin yazar. ONAY GEREKTİRİR.", "parameters": {"type": "object", "properties": {"text": {"type": "string"}}, "required": ["text"]}}},
    {"type": "function", "function": {"name": "computer_find_on_screen", "description": "Workspace'deki bir görsel dosyasını ekranda arar, bulursa merkez koordinatını döner.", "parameters": {"type": "object", "properties": {"image_path": {"type": "string"}}, "required": ["image_path"]}}},

    {"type": "function", "function": {"name": "git_status", "description": "Workspace git deposunun durumunu gösterir.", "parameters": {"type": "object", "properties": {}}}},
    {"type": "function", "function": {"name": "git_diff", "description": "Workspace'deki commit edilmemiş değişikliklerin diff'ini gösterir.", "parameters": {"type": "object", "properties": {"file": {"type": "string"}}, "required": []}}},
    {"type": "function", "function": {"name": "git_commit", "description": "Workspace'deki tüm değişiklikleri commit eder.", "parameters": {"type": "object", "properties": {"message": {"type": "string"}}, "required": ["message"]}}},
    {"type": "function", "function": {"name": "git_log", "description": "Son commit geçmişini gösterir.", "parameters": {"type": "object", "properties": {"n": {"type": "integer"}}, "required": []}}},

    {"type": "function", "function": {"name": "diff_files", "description": "Workspace içindeki iki dosyayı karşılaştırır (unified diff).", "parameters": {"type": "object", "properties": {"path1": {"type": "string"}, "path2": {"type": "string"}}, "required": ["path1", "path2"]}}},
    {"type": "function", "function": {"name": "search_in_files", "description": "Workspace içinde belirtilen uzantılı dosyalarda metin arar (grep benzeri).", "parameters": {"type": "object", "properties": {"pattern": {"type": "string"}, "extension": {"type": "string"}}, "required": ["pattern"]}}},
    {"type": "function", "function": {"name": "http_request", "description": "Herhangi bir REST API'ye HTTP isteği gönderir.", "parameters": {"type": "object", "properties": {"method": {"type": "string"}, "url": {"type": "string"}, "body": {"type": "object"}}, "required": ["method", "url"]}}},
    {"type": "function", "function": {"name": "list_processes", "description": "Sistemde çalışan süreçleri CPU kullanımına göre listeler.", "parameters": {"type": "object", "properties": {}}}},
] + _PLUGIN_TOOL_DEFS  # Plugin araçları dinamik olarak eklenir

# ==========================================
# EXECUTORS — TEMEL (FAZ 0)
# ==========================================
def execute_create_file(filename: str, content: str) -> str:
    try:
        safe_path = os.path.join(WORKSPACE_DIR, os.path.basename(filename))
        with open(safe_path, "w", encoding="utf-8") as f: f.write(content)
        add_log("ok", f"[OK] Dosya oluşturuldu: {filename}")
        return f"Başarılı: '{filename}' oluşturuldu."
    except Exception as e: return f"Hata: {str(e)}"

def execute_list_files() -> str:
    files = os.listdir(WORKSPACE_DIR)
    add_log("ok", f"[OK] {len(files)} öğe listelendi")
    return json.dumps(files)

def execute_analyze_screen(query: str) -> str:
    gemini_key = get_key("gemini")
    if not gemini_key: return "Hata: Gemini API Key eksik."
    try:
        with mss.mss() as sct:
            img = Image.frombytes("RGB", sct.grab(sct.monitors[1]).size, sct.grab(sct.monitors[1]).bgra, "raw", "BGRX")
            img.thumbnail((1024, 1024))
            genai.configure(api_key=gemini_key)
            response = genai.GenerativeModel("gemini-2.5-flash").generate_content([query, img])
            return response.text
    except Exception as e: return f"Vision Hatası: {str(e)}"

def execute_web_search(query: str) -> str:
    tavily_key = get_key("tavily")
    if not tavily_key: return "Hata: Tavily Key eksik."
    try:
        response = TavilyClient(api_key=tavily_key).search(query, max_results=3)
        return "\n---\n".join([f"[{i+1}] {r['title']}\n{r['content']}" for i, r in enumerate(response.get("results", []))])
    except Exception as e: return f"Web Hatası: {str(e)}"

def execute_read_file(path: str) -> str:
    try:
        with open(os.path.join(WORKSPACE_DIR, os.path.basename(path)), "r", encoding="utf-8") as f: return f.read()
    except Exception as e: return f"Hata: {str(e)}"

def execute_edit_file(path: str, content: str) -> str:
    try:
        with open(os.path.join(WORKSPACE_DIR, os.path.basename(path)), "w", encoding="utf-8") as f: f.write(content)
        return f"Başarılı: '{path}' güncellendi."
    except Exception as e: return f"Hata: {str(e)}"

# ==========================================
# EXECUTORS — SANDBOX STREAMING + MATPLOTLIB (FAZ 3)
# ==========================================
def _kill_container_after(container, timeout):
    time.sleep(timeout)
    try:
        container.reload()
        if container.status == "running":
            container.kill()
    except Exception:
        pass

def _docker_run_streaming(command_list, timeout: int) -> str:
    box = _CURRENT_STREAM_PLACEHOLDER.get("box")
    lines = []
    container = None
    exit_code = -1
    try:
        container = docker_client.containers.run(
            SANDBOX_IMAGE, command=command_list,
            volumes={WORKSPACE_DIR: {"bind": "/workspace", "mode": "rw"}},
            working_dir="/workspace", mem_limit="512m",
            network_mode="none", detach=True
        )
        killer = threading.Thread(target=_kill_container_after, args=(container, timeout), daemon=True)
        killer.start()
        for chunk in container.logs(stream=True, follow=True):
            for line in chunk.decode("utf-8", errors="replace").splitlines():
                lines.append(line)
                if box is not None:
                    box.code("\n".join(lines[-40:]), language="bash")
        try:
            result = container.wait(timeout=5)
            exit_code = result.get("StatusCode", -1)
        except Exception:
            exit_code = -1
    except Exception as e:
        lines.append(f"[DOCKER HATASI]: {str(e)}")
    finally:
        if container is not None:
            try: container.remove(force=True)
            except Exception: pass
    return "STDOUT/STDERR (canlı akış):\n" + "\n".join(lines) + f"\nReturn Code: {exit_code}"

def _subprocess_run_streaming(cmd, timeout: int, shell: bool = False) -> str:
    box = _CURRENT_STREAM_PLACEHOLDER.get("box")
    lines = []
    try:
        proc = subprocess.Popen(cmd, shell=shell, cwd=WORKSPACE_DIR,
                                 stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                                 text=True, bufsize=1)
        start = time.time()
        for line in proc.stdout:
            lines.append(line.rstrip())
            if box is not None:
                box.code("\n".join(lines[-40:]), language="bash")
            if time.time() - start > timeout:
                proc.kill()
                lines.append("[TIMEOUT] Süre sınırı aşıldı.")
                break
        try:
            proc.wait(timeout=5)
        except Exception:
            proc.kill()
        return "STDOUT/STDERR (canlı akış):\n" + "\n".join(lines) + f"\nReturn Code: {proc.returncode}"
    except Exception as e:
        return f"Hata: {str(e)}"

MPL_WRAP_HEADER = (
    "try:\n"
    "    import matplotlib\n"
    "    matplotlib.use('Agg')\n"
    "    import matplotlib.pyplot as plt, io as _io, base64 as _b64, json as _json\n"
    "    _MPL_OK = True\n"
    "except ImportError:\n"
    "    _MPL_OK = False\n\n"
)

MPL_WRAP_FOOTER = (
    "\n\nif _MPL_OK:\n"
    "    _figs = []\n"
    "    for _n in plt.get_fignums():\n"
    "        _buf = _io.BytesIO()\n"
    "        plt.figure(_n).savefig(_buf, format='png', dpi=130, bbox_inches='tight')\n"
    "        _figs.append(_b64.b64encode(_buf.getvalue()).decode())\n"
    "    if _figs:\n"
    "        print('__FIGS__:' + _json.dumps(_figs))\n"
)

def _extract_and_render_figures(output: str) -> str:
    clean_lines = []
    fig_count = 0
    for line in output.splitlines():
        if line.startswith("__FIGS__:"):
            try:
                figs = json.loads(line[len("__FIGS__:"):])
                for b64 in figs:
                    st.image(base64.b64decode(b64))
                fig_count += len(figs)
                add_log("vis", f"[VIS] {len(figs)} grafik gösterildi")
            except Exception:
                pass
        else:
            clean_lines.append(line)
    cleaned = "\n".join(clean_lines)
    if fig_count:
        cleaned += f"\n[SİSTEM]: {fig_count} grafik üretildi ve kullanıcı arayüzünde gösterildi."
    return cleaned

def execute_run_python_code(code: str, timeout: int = 10) -> str:
    wrapped = MPL_WRAP_HEADER + code + MPL_WRAP_FOOTER
    if not DOCKER_AVAILABLE:
        raw = _subprocess_run_streaming(["python", "-c", wrapped], timeout)
    else:
        raw = _docker_run_streaming(["python", "-c", wrapped], timeout)
    return _extract_and_render_figures(raw)

def execute_run_command(command: str, timeout: int = 30) -> str:
    if any(p in command.lower() for p in ["rm -rf /", "mkfs", "format c:", ":(){:|:&};:"]):
        return "HATA: Yıkıcı sistem komutu engellendi."

    critical_patterns = ["rm ", "rm -", "del ", "pip uninstall", "rmdir", "sudo ", "drop table", "git reset --hard"]
    is_critical = any(p in command.lower() for p in critical_patterns)
    if is_critical and not check_user_approval():
        add_log("wait", f"[WAIT] ⏳ İnsan onayı bekleniyor: {command}")
        return f"[ONAY GEREKLİ] Bu komut kritik/yıkıcı bir işlem içeriyor: `{command}`. Lütfen araç çağırmayı BIRAK ve kullanıcıdan bu komutu çalıştırmak için onay iste. Kullanıcı 'onaylıyorum' veya 'evet' dedikten sonra bu aracı TEKRAR çağır."

    if not DOCKER_AVAILABLE:
        return _subprocess_run_streaming(command, timeout, shell=True)
    return _docker_run_streaming(["/bin/bash", "-c", command], timeout)

# ==========================================
# EXECUTORS — TARAYICI OTOMASYONU (PLAYWRIGHT) (FAZ 2)
# ==========================================
@st.cache_resource(show_spinner=False)
def _get_browser_page():
    pw = sync_playwright().start()
    browser = pw.chromium.launch(headless=True)
    page = browser.new_page()
    return pw, browser, page

def execute_browser_navigate(url: str) -> str:
    if not PLAYWRIGHT_AVAILABLE:
        return "Hata: Playwright kurulu değil. `pip install playwright && playwright install chromium` çalıştırın."
    try:
        _, _, page = _get_browser_page()
        page.goto(url, wait_until="networkidle", timeout=15000)
        add_log("ok", f"[OK] Tarayıcı: {url}")
        return f"Navigated: {page.title()}"
    except Exception as e:
        return f"Tarayıcı Hatası: {str(e)}"

def execute_browser_click(selector: str) -> str:
    if not PLAYWRIGHT_AVAILABLE:
        return "Hata: Playwright kurulu değil."
    try:
        _, _, page = _get_browser_page()
        page.click(selector, timeout=5000)
        add_log("ok", f"[OK] Tıklandı: {selector}")
        return f"Clicked: {selector}"
    except Exception as e:
        return f"Tarayıcı Hatası: {str(e)}"

def execute_browser_type(selector: str, text: str) -> str:
    if not PLAYWRIGHT_AVAILABLE:
        return "Hata: Playwright kurulu değil."
    try:
        _, _, page = _get_browser_page()
        page.fill(selector, text, timeout=5000)
        return f"Yazıldı: {selector} <- {text[:40]}"
    except Exception as e:
        return f"Tarayıcı Hatası: {str(e)}"

def execute_browser_screenshot(query: str = "Bu sayfada ne var?") -> str:
    if not PLAYWRIGHT_AVAILABLE:
        return "Hata: Playwright kurulu değil."
    gemini_key = get_key("gemini")
    if not gemini_key:
        return "Hata: Gemini API Key eksik (görsel analiz için gerekli)."
    try:
        _, _, page = _get_browser_page()
        img_bytes = page.screenshot(full_page=True)
        img = Image.open(io.BytesIO(img_bytes))
        img.thumbnail((1280, 1280))
        genai.configure(api_key=gemini_key)
        response = genai.GenerativeModel("gemini-2.5-flash").generate_content([query, img])
        return response.text
    except Exception as e:
        return f"Tarayıcı/Vision Hatası: {str(e)}"

# ==========================================
# EXECUTORS — COMPUTER USE (PYAUTOGUI) (FAZ 2)
# ==========================================
def execute_computer_click(x: int, y: int, button: str = "left") -> str:
    if not PYAUTOGUI_AVAILABLE:
        return "Hata: pyautogui kullanılamıyor (headless ortam veya kurulu değil)."
    if not check_user_approval():
        add_log("wait", f"[WAIT] ⏳ Onay bekleniyor: click({x},{y})")
        return f"[ONAY GEREKLİ] Masaüstünde ({x},{y}) konumuna tıklanacak. Lütfen kullanıcıdan onay iste."
    try:
        pyautogui.click(x, y, button=button)
        add_log("ok", f"[OK] Tıklandı: ({x},{y})")
        return f"Tıklandı: ({x},{y})"
    except Exception as e:
        return f"Hata: {str(e)}"

def execute_computer_type(text: str) -> str:
    if not PYAUTOGUI_AVAILABLE:
        return "Hata: pyautogui kullanılamıyor."
    if not check_user_approval():
        add_log("wait", f"[WAIT] ⏳ Onay bekleniyor: type('{text[:30]}...')")
        return f"[ONAY GEREKLİ] Aktif pencereye '{text[:40]}...' yazılacak. Lütfen kullanıcıdan onay iste."
    try:
        pyautogui.typewrite(text, interval=0.02)
        return f"Yazıldı: {text[:60]}"
    except Exception as e:
        return f"Hata: {str(e)}"

def execute_computer_find_on_screen(image_path: str) -> str:
    if not PYAUTOGUI_AVAILABLE:
        return "Hata: pyautogui kullanılamıyor."
    try:
        full_path = os.path.join(WORKSPACE_DIR, os.path.basename(image_path))
        loc = pyautogui.locateOnScreen(full_path, confidence=0.8)
        if loc:
            center = pyautogui.center(loc)
            return f"Bulundu: merkez=({center.x},{center.y})"
        return "Ekranda bulunamadı."
    except Exception as e:
        return f"Hata: {str(e)}"

# ==========================================
# EXECUTORS — GIT ENTEGRASYONU (FAZ 2)
# ==========================================
def _get_repo():
    try:
        return Repo(WORKSPACE_DIR)
    except InvalidGitRepositoryError:
        return Repo.init(WORKSPACE_DIR)

def execute_git_status() -> str:
    if not GIT_AVAILABLE: return "Hata: gitpython kurulu değil."
    try:
        repo = _get_repo()
        return repo.git.status() or "Temiz çalışma dizini."
    except Exception as e:
        return f"Hata: {str(e)}"

def execute_git_diff(file: str = None) -> str:
    if not GIT_AVAILABLE: return "Hata: gitpython kurulu değil."
    try:
        repo = _get_repo()
        diff = repo.git.diff(file) if file else repo.git.diff()
        return diff or "Değişiklik yok."
    except Exception as e:
        return f"Hata: {str(e)}"

def execute_git_commit(message: str) -> str:
    if not GIT_AVAILABLE: return "Hata: gitpython kurulu değil."
    try:
        repo = _get_repo()
        repo.git.add(A=True)
        if not repo.is_dirty(untracked_files=True):
            return "Commit edilecek değişiklik yok."
        commit = repo.index.commit(message)
        add_log("ok", f"[OK] Git commit: {commit.hexsha[:8]}")
        return f"Commit: {commit.hexsha[:8]} — {message}"
    except Exception as e:
        return f"Hata: {str(e)}"

def execute_git_log(n: int = 5) -> str:
    if not GIT_AVAILABLE: return "Hata: gitpython kurulu değil."
    try:
        repo = _get_repo()
        if not repo.head.is_valid():
            return "Henüz commit yok."
        return "\n".join(f"{c.hexsha[:8]} {c.message.strip()[:60]}" for c in repo.iter_commits(max_count=n))
    except Exception as e:
        return f"Hata: {str(e)}"

# ==========================================
# EXECUTORS — GELİŞMİŞ DOSYA OPS + HTTP + SÜREÇ (FAZ 2)
# ==========================================
def execute_diff_files(path1: str, path2: str) -> str:
    try:
        p1 = os.path.join(WORKSPACE_DIR, os.path.basename(path1))
        p2 = os.path.join(WORKSPACE_DIR, os.path.basename(path2))
        with open(p1, "r", encoding="utf-8") as f1, open(p2, "r", encoding="utf-8") as f2:
            diff = difflib.unified_diff(f1.readlines(), f2.readlines(), fromfile=path1, tofile=path2)
        result = "".join(diff)
        return result or "Fark yok."
    except Exception as e:
        return f"Hata: {str(e)}"

def execute_search_in_files(pattern: str, extension: str = ".py") -> str:
    try:
        matches = []
        for root, _, files in os.walk(WORKSPACE_DIR):
            for fn in files:
                if fn.endswith(extension):
                    fpath = os.path.join(root, fn)
                    try:
                        with open(fpath, "r", encoding="utf-8", errors="ignore") as f:
                            for i, line in enumerate(f, 1):
                                if pattern in line:
                                    rel = os.path.relpath(fpath, WORKSPACE_DIR)
                                    matches.append(f"{rel}:{i}: {line.strip()}")
                    except Exception:
                        continue
        return "\n".join(matches[:200]) if matches else "Eşleşme bulunamadı."
    except Exception as e:
        return f"Hata: {str(e)}"

def execute_http_request(method: str, url: str, body: dict = None) -> str:
    if not HTTPX_AVAILABLE:
        return "Hata: httpx kurulu değil."
    try:
        with httpx.Client(timeout=30) as client:
            r = client.request(method.upper(), url, json=body)
        return json.dumps({"status": r.status_code, "body": r.text[:2000]}, indent=2, ensure_ascii=False)
    except Exception as e:
        return f"HTTP Hatası: {str(e)}"

def execute_list_processes() -> str:
    if not PSUTIL_AVAILABLE:
        return "Hata: psutil kurulu değil."
    try:
        procs = [p.info for p in psutil.process_iter(["pid", "name", "cpu_percent"])]
        procs = sorted(procs, key=lambda x: x.get("cpu_percent") or 0, reverse=True)[:20]
        return json.dumps(procs, indent=2, ensure_ascii=False)
    except Exception as e:
        return f"Hata: {str(e)}"

# ==========================================
# TOOL EXECUTOR HARİTASI
# ==========================================
TOOL_EXECUTORS = {
    "create_file": execute_create_file, "list_files": execute_list_files,
    "analyze_screen": execute_analyze_screen, "web_search": execute_web_search,
    "run_python_code": execute_run_python_code, "run_command": execute_run_command,
    "read_file": execute_read_file, "edit_file": execute_edit_file,

    "browser_navigate": execute_browser_navigate, "browser_click": execute_browser_click,
    "browser_type": execute_browser_type, "browser_screenshot": execute_browser_screenshot,

    "computer_click": execute_computer_click, "computer_type": execute_computer_type,
    "computer_find_on_screen": execute_computer_find_on_screen,

    "git_status": execute_git_status, "git_diff": execute_git_diff,
    "git_commit": execute_git_commit, "git_log": execute_git_log,

    "diff_files": execute_diff_files, "search_in_files": execute_search_in_files,
    "http_request": execute_http_request, "list_processes": execute_list_processes,
    **_PLUGIN_EXECUTORS,  # Plugin executor'ları dinamik olarak eklenir
}

# ==========================================
# 1. SOL PANEL (Sidebar)
# ==========================================
with st.sidebar:
    st.markdown(f'<h1>{icon("auto_awesome", "#67E8F9", "28px")} Antigravity</h1>', unsafe_allow_html=True)
    st.markdown("---")
    st.markdown("### 🔑 API Keys")
    st.caption("Anahtarlar önce .env, sonra OS Keychain'den okunur. Buraya girersen otomatik Keychain'e kaydedilir.")
    
    # OpenRouter ve HuggingFace eklendi, Anthropic vb. çıkarıldı
    for svc, label in [("openrouter", "OpenRouter"), ("huggingface", "HuggingFace"), ("groq", "Groq"), ("gemini", "Gemini")]:
        val = st.text_input(f"{label} API Key", type="password", value=get_key(svc), key=f"input_{svc}")
        if val:
            save_key(svc, val)

    st.markdown("### 🧠 Model Seçici (Router)")
    model_choice = st.selectbox("Aktif Beyin:", [
        "Local: DeepSeek Coder 💻",
        "Local: Llama 3.1 (8B) 💻",
        "Local: Dolphin Llama 3 💻",
        "Local: Dolphin Mistral 💻",
        "Gemini (3.5 Flash)",
        "Gemini (3.1 Pro)",
        "OpenRouter: Llama 3.1 8B (Ücretsiz) 🌐",
        "OpenRouter: Llama 3.3 70B (Ücretsiz) 🌐",
        "HuggingFace: Qwen 2.5 Coder 🤗",
        "Groq: Llama 3.1 8B (Hızlı Yedek) ☁️"
    ], index=4)
    st.session_state.selected_model = model_choice

    st.markdown("---")
    with st.expander("⚙️ Sistem Durumu", expanded=False):
        st.write(f"{'✅' if DOCKER_AVAILABLE else '❌'} Docker Sandbox")
        st.write(f"{'✅' if MEMORY_AVAILABLE else '❌'} ChromaDB Bellek")
        st.write(f"{'✅' if EPISODES_DB_AVAILABLE else '❌'} SQLite Episodik Log")
        st.write(f"{'✅' if TIKTOKEN_AVAILABLE else '❌'} Context Sıkıştırma (tiktoken)")
        st.write(f"{'✅' if PLAYWRIGHT_AVAILABLE else '❌'} Playwright Tarayıcı")
        st.write(f"{'✅' if PYAUTOGUI_AVAILABLE else '❌'} Computer Use (pyautogui)")
        st.write(f"{'✅' if GIT_AVAILABLE else '❌'} Git Entegrasyonu")
        st.write(f"{'✅' if HTTPX_AVAILABLE else '❌'} HTTP Request Aracı")
        st.write(f"{'✅' if PSUTIL_AVAILABLE else '❌'} Süreç Yöneticisi")
        plugin_count = len(_PLUGIN_ENTRIES)
        st.write(f"{'✅' if plugin_count > 0 else '➕'} Plugins: {plugin_count} araç yüklü")

    st.markdown("---")
    st.markdown("### 📁 Proje Workspace (FAZ 4)")
    st.caption("Klasör yolu gir → README, dosya ağacı ve son değişiklikler otomatik context'e eklenir.")
    proj_path_input = st.text_input("Proje Klasörü:", value=st.session_state.project_path, placeholder="/home/user/myproject", key="proj_path_input")
    col_a, col_b = st.columns(2)
    with col_a:
        if st.button("📂 Yükle", use_container_width=True):
            if proj_path_input and os.path.isdir(proj_path_input):
                ctx = load_project_context(proj_path_input)
                st.session_state.project_path = proj_path_input
                st.session_state.project_context = ctx
                add_log("ok", f"[OK] Proje yüklendi: {proj_path_input}")
                st.success(f"Proje yüklendi! ({len(ctx)} karakter)")
            else:
                st.error("Geçersiz klasör yolu.")
    with col_b:
        if st.button("🗑️ Temizle", use_container_width=True):
            st.session_state.project_path = ""
            st.session_state.project_context = ""
            st.rerun()
    if st.session_state.project_path:
        st.caption(f"Aktif: `{st.session_state.project_path}`")

    st.markdown("---")
    with st.expander("📜 Oturum Geçmişi (SQLite)", expanded=False):
        episodes = get_recent_episodes(8)
        if not episodes:
            st.caption("Henüz kayıt yok.")
        else:
            for ep in episodes:
                ts_short = ep.get("ts", "")[:16]
                goal_short = (ep.get("goal") or "")[:50]
                tools = json.loads(ep.get("tools_used") or "[]")
                steps = ep.get("step_count", 0)
                model_short = (ep.get("model") or "").replace("groq/","").replace("anthropic/","").replace("gemini/","")[:20]
                st.markdown(
                    f'<div style="font-size:11px;padding:5px 0;border-bottom:1px solid rgba(255,255,255,0.05);">'
                    f'<b>{ts_short}</b> — {goal_short}<br>'
                    f'<span style="color:#94A3B8">{steps} adım · {len(tools)} araç · {model_short}</span>'
                    f'</div>', unsafe_allow_html=True
                )

    if PLAYWRIGHT_AVAILABLE and st.button("🌐 Tarayıcıyı Sıfırla", use_container_width=True):
        _get_browser_page.clear()
        st.success("Tarayıcı oturumu sıfırlandı.")

    if st.button("🗑️ Sohbeti Temizle", use_container_width=True):
        st.session_state.messages = []
        st.rerun()

# ==========================================
# 2. ORTA PANEL: OTONOM AJAN DÖNGÜSÜ
# ==========================================
col_chat, col_context = st.columns([2.5, 1])

with col_chat:
    for msg in st.session_state.messages:
        with st.chat_message(msg["role"], avatar="🤖" if msg["role"]=="assistant" else "👤"):
            st.markdown(msg["content"])

    if prompt := st.chat_input("Otonom komut ver..."):
        st.session_state.messages.append({"role": "user", "content": prompt})
        with st.chat_message("user", avatar="👤"): st.markdown(prompt)

        with st.chat_message("assistant", avatar="🤖"):
            status_placeholder = st.empty()
            add_log("sys", f"[USER] {prompt[:50]}...")

            try:
                system_prompt = """Sen Antigravity adında, otonom ve ileri düzey bir yazılım mühendisi ajanısın.

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
5. Araç Sadakati: Sadece TOOLS listesindeki araçları kullan. Uydurma araç ismi üretme.
6. İNSAN ONAYI: Eğer bir araçtan `[ONAY GEREKLİ]` yanıtı alırsan, DERHAL araç çağırmayı bırak. Kullanıcıya ne yapacağını açıkça söyle ve onay iste. Kullanıcı onaylayana kadar (örn: 'evet', 'onaylıyorum') o aracı tekrar çağırma.

ARAÇ KATEGORİLERİ:
- Dosya: create_file, read_file, edit_file, list_files, diff_files, search_in_files
- Kod/Komut (izole Docker sandbox): run_python_code, run_command
- Tarayıcı (gerçek internet): browser_navigate, browser_click, browser_type, browser_screenshot
- Masaüstü Kontrolü (onay gerektirir): computer_click, computer_type, computer_find_on_screen
- Versiyon Kontrolü: git_status, git_diff, git_commit, git_log
- Ağ/Sistem: http_request, list_processes, web_search, analyze_screen"""

                # Proje workspace context (FAZ 4)
                project_ctx = ""
                if st.session_state.project_context:
                    project_ctx = "\n\n" + st.session_state.project_context

                # Plugin araç isimleri varsa sisteme bildir
                if _PLUGIN_ENTRIES:
                    plugin_names = ", ".join(_PLUGIN_EXECUTORS.keys())
                    project_ctx += f"\n\nEKSTRA ARAÇLAR (Plugin): {plugin_names}"

                memories = search_memory(prompt)
                memory_ctx = "\n--- GEÇMİŞ BAĞLAM ---\n" + "\n".join(memories) + "\n---------------------\n" if memories else ""

                messages_for_groq = [{"role": "system", "content": system_prompt + project_ctx + memory_ctx}]
                for m in st.session_state.messages: messages_for_groq.append({"role": m["role"], "content": m["content"]})

                MAX_STEPS = 10
                step = 0
                final_text = ""
                tools_used_this_run = []  # SQLite log için araç takibi

                while step < MAX_STEPS:
                    step += 1
                    status_placeholder.info(f"🧠 Adım {step}/{MAX_STEPS}: Düşünülüyor...")

                    model_choice = st.session_state.get("selected_model", "Local: DeepSeek Coder")
                    
                    # --- YEREL MODELLER (Senin Klasöründekiler) ---
                    if "DeepSeek" in model_choice:
                        model_id = "ollama/deepseek-coder"
                    elif "Local: Llama 3.1" in model_choice:
                        model_id = "ollama/llama3.1"
                    elif "Dolphin Llama 3" in model_choice:
                        model_id = "ollama/dolphin-llama3"
                    elif "Dolphin Mistral" in model_choice:
                        model_id = "ollama/dolphin-mistral"
                        
                # --- GERÇEK GEMINI AİLESİ (2026) ---
                    elif "Gemini" in model_choice:
                        gemini_key = get_key("gemini")
                        if not gemini_key: st.error("Gemini API Key eksik!"); st.stop()
                        os.environ["GEMINI_API_KEY"] = gemini_key
                        
                        if "3.1 Pro" in model_choice:
                            # ARC-AGI-2 rekortmeni, en zeki model
                            model_id = "gemini/gemini-3.1-pro"
                        else:
                            # Ajan sistemleri ve otonom döngüler için 3.5 Flash
                            model_id = "gemini/gemini-3.5-flash"
                        
                    # --- OPENROUTER (Ücretsiz Kodlama Canavarları) ---
                    elif "OpenRouter" in model_choice:
                        or_key = get_key("openrouter")
                        if not or_key: st.error("OpenRouter API Key eksik!"); st.stop()
                        os.environ["OPENROUTER_API_KEY"] = or_key
                        
                        if "Qwen" in model_choice:
                            # Qwen sunucuları dolduğunda hata vermemesi için kararlı ücretsiz Llama'ya yönlendirdik
                            model_id = "openrouter/meta-llama/llama-3.1-8b-instruct:free"
                        else:
                            # 70B için şansımızı deniyoruz
                            model_id = "openrouter/meta-llama/llama-3.3-70b-instruct:free"
                            
                    # --- HUGGINGFACE ---
                    elif "HuggingFace" in model_choice:
                        hf_key = get_key("huggingface")
                        if not hf_key: st.error("HuggingFace API Key eksik!"); st.stop()
                        os.environ["HUGGINGFACE_API_KEY"] = hf_key
                        # HF Inference API üzerinden doğrudan modele bağlanıyoruz
                        model_id = "huggingface/Qwen/Qwen2.5-Coder-32B-Instruct"
                        
                    # --- GROQ (Yedek) ---
                    else:
                        groq_key = get_key("groq")
                        if not groq_key: st.error("Groq API Key eksik!"); st.stop()
                        os.environ["GROQ_API_KEY"] = groq_key
                        model_id = "groq/llama-3.1-8b-instant"

                    # Context window sıkıştırması (FAZ 4)
                    messages_for_groq = compress_if_needed(model_id, messages_for_groq)

                    answer_box = st.empty()
                    full_text, tool_calls = stream_llm_response(model_id, messages_for_groq, TOOLS, answer_box)

                    assistant_msg = {"role": "assistant", "content": full_text or ""}
                    if tool_calls:
                        assistant_msg["tool_calls"] = tool_calls
                    messages_for_groq.append(assistant_msg)

                    if tool_calls:
                        answer_box.empty()
                        for tool_call in tool_calls:
                            func_name = tool_call["function"]["name"]
                            try: func_args = json.loads(tool_call["function"]["arguments"]) if tool_call["function"]["arguments"] else {}
                            except Exception: func_args = {}

                            if "timeout" in func_args:
                                try: func_args["timeout"] = int(float(str(func_args["timeout"])))
                                except Exception: func_args["timeout"] = 10

                            st.session_state.active_tool = func_name
                            add_log("tool", f"[TOOL] {func_name}")
                            status_placeholder.warning(f"🛠️ Adım {step}: **{func_name}** çalıştırılıyor...")

                            set_stream_placeholder(st.empty() if func_name in ("run_python_code", "run_command") else None)

                            if func_name not in TOOL_EXECUTORS:
                                result = f"KRİTİK HATA: '{func_name}' kayıtlı değil. Sadece şunları kullanabilirsin: {list(TOOL_EXECUTORS.keys())}."
                                add_log("sys", f"[WARN] 🚫 Halüsinasyon: {func_name}")
                            else:
                                tools_used_this_run.append(func_name)  # SQLite log için takip
                                result = TOOL_EXECUTORS[func_name](**func_args)

                                if func_name in ["run_python_code", "run_command"] and "Return Code: 1" in result:
                                    st.session_state.fail_count += 1
                                    if st.session_state.fail_count >= 2:
                                        result += "\n\n[SİSTEM UYARISI]: 2 kez hata aldın. Lütfen denemeyi bırak ve kullanıcıya hatayı açıkla."
                                        add_log("sys", "[BREAK] 🛑 Hata döngüsü kırıldı.")
                                else:
                                    st.session_state.fail_count = 0

                                if "[ONAY GEREKLİ]" in result:
                                    messages_for_groq.append({"role": "tool", "tool_call_id": tool_call["id"], "content": result})
                                    status_placeholder.empty()
                                    approval_response = completion(model=model_id, messages=messages_for_groq, temperature=0.2)
                                    final_text = approval_response.choices[0].message.content
                                    st.session_state.messages.append({"role": "assistant", "content": final_text})
                                    with st.chat_message("assistant", avatar="🤖"):
                                        st.markdown(final_text)
                                    st.session_state.active_tool = "None (Idle)"
                                    st.stop()

                            messages_for_groq.append({"role": "tool", "tool_call_id": tool_call["id"], "content": result})
                        continue
                    else:
                        final_text = full_text
                        break

                status_placeholder.empty()
                if final_text:
                    st.session_state.messages.append({"role": "assistant", "content": final_text})
                    if MEMORY_AVAILABLE: add_to_memory(f"User: {prompt[:100]} | AI: {final_text[:200]}")
                    # SQLite episodik log (FAZ 4)
                    if EPISODES_DB_AVAILABLE:
                        files_created = [a.get("filename","") for t in tools_used_this_run if t=="create_file"
                                         for a in [{}]]  # basit placeholder
                        log_episode(
                            goal=prompt,
                            tools_used=tools_used_this_run,
                            outcome=final_text[:300],
                            step_count=step,
                            model=model_id,
                        )
                else:
                    st.warning(f"⚠️ Ajan {MAX_STEPS} adım sınırına ulaştı.")
                    if EPISODES_DB_AVAILABLE:
                        log_episode(goal=prompt, tools_used=tools_used_this_run,
                                    outcome="MAX_STEPS aşıldı", step_count=step, model=model_id)

                st.session_state.active_tool = "None (Idle)"
            except Exception as e:
                status_placeholder.error(f"❌ Hata: {str(e)}")
                add_log("sys", f"[ERR] {str(e)}")

# ==========================================
# 3. SAĞ PANEL: CONTEXT & LOGS
# ==========================================
with col_context:
    st.markdown("### 🎯 ACTIVE TOOL")
    tool_color = "#FBBF24" if st.session_state.active_tool != "None (Idle)" else "#94A3B8"
    st.markdown(f'<div style="background:rgba(255,255,255,0.04);padding:15px;border-radius:12px;border:1px solid rgba(255,255,255,0.1);"><div style="font-size:20px;font-weight:bold;color:{tool_color};">⚡ {st.session_state.active_tool}</div></div>', unsafe_allow_html=True)

    st.markdown("### 📟 SYSTEM LOGS")
    logs_html = '<div class="terminal">'
    for level, msg in st.session_state.logs[-30:]:
        css_class = "log-sys"
        if "[TOOL]" in msg: css_class = "log-tool"
        elif "[OK]" in msg: css_class = "log-ok"
        elif "[VIS]" in msg: css_class = "log-vis"
        elif "[WAIT]" in msg: css_class = "log-wait"
        logs_html += f'<div class="{css_class}">{msg}</div>'
    logs_html += '</div>'
    st.markdown(logs_html, unsafe_allow_html=True)