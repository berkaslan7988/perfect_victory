"""
ZeusAI Faz 7 — Sınırsız Bağlam & Hafıza Sistemi
========================================================
- ChromaDB semantik bellek (vektör arama)
- SQLite episodik log (görev geçmişi)
- Dinamik context window sıkıştırma (model bazlı limit)
- Kayıpsız kaydırmalı özetleme (JSONL arşiv + LLM digest)
- Döngü tespiti (aynı araç+argüman 3 kez tekrar)
- Token / maliyet sayacı
"""
import os
import json
import hashlib
import sqlite3
import datetime
import threading
from typing import Optional

from litellm import completion
try:
    from litellm import get_max_tokens as _litellm_get_max_tokens
    LITELLM_MAX_TOKENS_AVAILABLE = True
except ImportError:
    LITELLM_MAX_TOKENS_AVAILABLE = False

from backend.config import CHROMA_DB_PATH, EPISODES_DB, CONTEXT_TOKEN_LIMIT, WORKSPACE_DIR

# ==========================================
# 1. CHROMADB SEMANTİK BELLEK
# ==========================================
MEMORY_AVAILABLE = False
_chroma_client = None
_memory_collection = None

try:
    import chromadb
    _chroma_client = chromadb.PersistentClient(path=CHROMA_DB_PATH)
    try:
        _memory_collection = _chroma_client.get_collection(name="zeus_memory")
    except Exception:
        _memory_collection = _chroma_client.create_collection(name="zeus_memory")
    MEMORY_AVAILABLE = True
except Exception as e:
    print(f"[BELLEK] ChromaDB başlatılamadı: {e}")


def add_to_memory(text: str) -> None:
    if not MEMORY_AVAILABLE or not _memory_collection:
        return
    try:
        doc_id = hashlib.md5(text.encode()).hexdigest()
        _memory_collection.add(documents=[text], ids=[doc_id])
    except Exception:
        pass


def search_memory(query: str, n_results: int = 2) -> list[str]:
    if not MEMORY_AVAILABLE or not _memory_collection:
        return []
    try:
        results = _memory_collection.query(query_texts=[query], n_results=n_results)
        return results["documents"][0] if results["documents"] else []
    except Exception:
        return []


# ==========================================
# 2. SQLİTE EPİSODİK LOG + GÖREV CHECKPOINT
# ==========================================
EPISODES_DB_AVAILABLE = False


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
        # Faz 11: Görev checkpoint tablosu
        conn.execute("""CREATE TABLE IF NOT EXISTS task_checkpoints(
            task_id TEXT PRIMARY KEY,
            state TEXT NOT NULL,
            updated_ts TEXT NOT NULL
        )""")
        conn.commit()
        conn.close()
        return True
    except Exception as e:
        print(f"[DB HATA] {e}")
        return False


EPISODES_DB_AVAILABLE = _init_episodes_db()


def log_episode(
    goal: str,
    tools_used: list,
    outcome: str,
    step_count: int,
    model: str = "",
    files_created: Optional[list] = None,
) -> None:
    if not EPISODES_DB_AVAILABLE:
        return
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
            ),
        )
        conn.commit()
        conn.close()
    except Exception as e:
        print(f"[DB HATA] {str(e)}")


def save_checkpoint(task_id: str, state: dict) -> None:
    """Görev durumunu diske yaz (Faz 11: kesinti sonrası devam)."""
    if not EPISODES_DB_AVAILABLE:
        return
    try:
        conn = sqlite3.connect(EPISODES_DB)
        conn.execute(
            "INSERT OR REPLACE INTO task_checkpoints(task_id, state, updated_ts) VALUES(?,?,?)",
            (task_id, json.dumps(state, ensure_ascii=False), datetime.datetime.now().isoformat()),
        )
        conn.commit()
        conn.close()
    except Exception as e:
        print(f"[CHECKPOINT HATA] {e}")


def load_checkpoint(task_id: str) -> Optional[dict]:
    """Diskten görev durumunu yükle."""
    if not EPISODES_DB_AVAILABLE:
        return None
    try:
        conn = sqlite3.connect(EPISODES_DB)
        cur = conn.execute("SELECT state FROM task_checkpoints WHERE task_id = ?", (task_id,))
        row = cur.fetchone()
        conn.close()
        if row:
            return json.loads(row[0])
    except Exception:
        pass
    return None


def delete_checkpoint(task_id: str) -> None:
    """Tamamlanan görevin checkpoint'ini sil."""
    if not EPISODES_DB_AVAILABLE:
        return
    try:
        conn = sqlite3.connect(EPISODES_DB)
        conn.execute("DELETE FROM task_checkpoints WHERE task_id = ?", (task_id,))
        conn.commit()
        conn.close()
    except Exception:
        pass


def get_pending_checkpoints() -> list[dict]:
    """Tamamlanmamış görev checkpoint'lerini döndür."""
    if not EPISODES_DB_AVAILABLE:
        return []
    try:
        conn = sqlite3.connect(EPISODES_DB)
        cur = conn.execute("SELECT task_id, state, updated_ts FROM task_checkpoints ORDER BY updated_ts DESC LIMIT 10")
        cols = [c[0] for c in cur.description]
        rows = [dict(zip(cols, row)) for row in cur.fetchall()]
        conn.close()
        return rows
    except Exception:
        return []


def get_recent_episodes(n: int = 8) -> list[dict]:
    if not EPISODES_DB_AVAILABLE:
        return []
    try:
        conn = sqlite3.connect(EPISODES_DB)
        cur = conn.execute(
            "SELECT ts, goal, tools_used, outcome, step_count, model FROM episodes ORDER BY id DESC LIMIT ?",
            (n,),
        )
        cols = [c[0] for c in cur.description]
        rows = [dict(zip(cols, row)) for row in cur.fetchall()]
        conn.close()
        return rows
    except Exception:
        return []


# ==========================================
# 3. DİNAMİK CONTEXT LİMİT (FAZ 7)
# ==========================================
def dynamic_limit(model_id: str) -> int:
    """
    Her model için gerçek context penceresinin %85'ini döndürür.
    Sabit 80K sınırı YOK — model neyi destekliyorsa odur.
    """
    try:
        if LITELLM_MAX_TOKENS_AVAILABLE:
            raw = _litellm_get_max_tokens(model_id)
            if raw and raw > 10_000:
                return int(raw * 0.85)
    except Exception:
        pass

    # Fallback: modele göre bilinen değerler
    model_lower = model_id.lower()
    if "gemini-2.5-pro" in model_lower or "gemini-3" in model_lower:
        return 1_700_000  # Gemini 2M token window
    if "gemini" in model_lower:
        return 850_000
    if "claude" in model_lower:
        return 170_000  # Claude 200K
    if "deepseek" in model_lower:
        return 108_000  # DeepSeek 128K
    if "gpt-4" in model_lower:
        return 108_000
    return 50_000  # Bilinmeyen model için güvenli fallback


# ==========================================
# 4. CONTEXT WINDOW YÖNETİMİ + KAYIPSIZ ARŞİV (FAZ 7)
# ==========================================
TIKTOKEN_AVAILABLE = False
_TIKTOKEN_ENC = None

try:
    import tiktoken
    TIKTOKEN_AVAILABLE = True
    _TIKTOKEN_ENC = tiktoken.get_encoding("cl100k_base")
except Exception:
    pass

# Transcripts arşiv klasörü
TRANSCRIPTS_DIR = os.path.join(os.path.dirname(WORKSPACE_DIR), "transcripts")
os.makedirs(TRANSCRIPTS_DIR, exist_ok=True)
_archive_lock = threading.Lock()


def archive_full(msg: dict, session_id: str) -> None:
    """Tüm mesajları kayıpsız JSONL olarak diske yazar."""
    try:
        with _archive_lock:
            fpath = os.path.join(TRANSCRIPTS_DIR, f"{session_id}.jsonl")
            with open(fpath, "a", encoding="utf-8") as f:
                f.write(json.dumps(msg, ensure_ascii=False) + "\n")
    except Exception:
        pass


def load_full_transcript(session_id: str) -> list[dict]:
    """Diskteki tam konuşma transkriptini yükler."""
    fpath = os.path.join(TRANSCRIPTS_DIR, f"{session_id}.jsonl")
    if not os.path.exists(fpath):
        return []
    try:
        with open(fpath, "r", encoding="utf-8") as f:
            return [json.loads(line) for line in f if line.strip()]
    except Exception:
        return []


def count_tokens(messages: list) -> int:
    if TIKTOKEN_AVAILABLE and _TIKTOKEN_ENC:
        try:
            return sum(len(_TIKTOKEN_ENC.encode(str(m))) for m in messages)
        except Exception:
            pass
    return sum(len(str(m)) // 4 for m in messages)


async def compress_if_needed(model_id: str, messages: list, session_id: str = "") -> list:
    """
    Dinamik limit + kayıpsız arşivleme.
    Token limiti aşılırsa ortadakileri özetle, tam metni JSONL'ye arşivle.
    """
    import asyncio

    limit = dynamic_limit(model_id)
    total = count_tokens(messages)
    if total < limit:
        return messages

    print(f"[CTX] {total:,} token → limit {limit:,} — sıkıştırılıyor...")

    system_msgs = [m for m in messages if m.get("role") == "system"]
    non_system = [m for m in messages if m.get("role") != "system"]

    if len(non_system) <= 8:
        return messages

    # Kayıpsız arşiv: tüm middle mesajları JSONL'ye yaz
    if session_id:
        middle_full = non_system[:-6]
        for msg in middle_full:
            archive_full(msg, session_id)

    tail = non_system[-6:]

    try:
        summary_resp = await asyncio.to_thread(
            completion,
            model=model_id,
            messages=[
                {
                    "role": "user",
                    "content": (
                        "Aşağıdaki konuşmayı max 300 kelimede Türkçe özetle. "
                        "Sadece özeti yaz:\n\n" + str(non_system[:-6])[:8000]
                    ),
                }
            ],
            temperature=0.1,
            max_tokens=500,
        )
        summary_text = summary_resp.choices[0].message.content
        print(f"[CTX] {len(non_system[:-6])} mesaj özetlendi → {count_tokens([{'role':'system','content':summary_text}])} token")
    except Exception as e:
        print(f"[CTX] Sıkıştırma hatası: {e}")
        return messages

    return (
        system_msgs
        + [{"role": "system", "content": f"[KONUŞMA ÖZETİ]: {summary_text}"}]
        + tail
    )


# ==========================================
# 5. DÖNGÜ TESPİTİ (FAZ 7)
# ==========================================
def is_stuck(tool_history: list[dict]) -> bool:
    """
    Son 3 araç çağrısı aynı tool + aynı argüman ise True döner.
    Sonsuz döngü yerine akıllı döngü tespiti.
    """
    if len(tool_history) < 3:
        return False
    last3 = tool_history[-3:]
    sigs = [(h.get("tool", ""), str(h.get("args", {}))) for h in last3]
    return len(set(sigs)) == 1


# ==========================================
# 6. TOKEN / MALİYET SAYACI (FAZ 7)
# ==========================================
class UsageTracker:
    """Oturum başına token ve maliyet takibi."""
    def __init__(self):
        self.total_tokens: int = 0
        self.total_cost: float = 0.0
        self.call_count: int = 0
        self.model_usage: dict[str, dict] = {}  # model -> {"tokens":int, "cost":float, "calls":int}

    def track(self, model_id: str, response):
        """Litellm yanıtından usage bilgilerini kaydeder."""
        try:
            usage = getattr(response, "usage", None)
            if usage:
                tokens = getattr(usage, "total_tokens", 0) or 0
                self.total_tokens += tokens
                self.call_count += 1

                if model_id not in self.model_usage:
                    self.model_usage[model_id] = {"tokens": 0, "cost": 0.0, "calls": 0}
                self.model_usage[model_id]["tokens"] += tokens
                self.model_usage[model_id]["calls"] += 1
            else:
                tokens = 0

            # Maliyet hesaplama (litellm destekliyorsa)
            try:
                from litellm import completion_cost
                cost = completion_cost(completion_response=response)
                self.total_cost += cost
                if model_id in self.model_usage:
                    self.model_usage[model_id]["cost"] += cost
            except Exception:
                cost = self._estimate_cost(model_id, tokens)
                self.total_cost += cost
                if model_id in self.model_usage:
                    self.model_usage[model_id]["cost"] += cost

        except Exception:
            pass

    def _estimate_cost(self, model_id: str, tokens: int) -> float:
        """Model bazlı yaklaşık maliyet (USD / 1M token)."""
        rates = {
            "deepseek": (0.14, 0.28),  # input/output
            "gemini": (0.075, 0.30),
            "claude": (3.0, 15.0),
            "groq": (0.05, 0.10),
            "gpt-4": (2.5, 10.0),
        }
        model_lower = model_id.lower()
        for key, (inp, out) in rates.items():
            if key in model_lower:
                return (tokens / 1_000_000) * ((inp + out) / 2)
        return (tokens / 1_000_000) * 0.5  # Varsayılan

    def summary(self) -> dict:
        return {
            "total_tokens": self.total_tokens,
            "total_cost_usd": round(self.total_cost, 4),
            "call_count": self.call_count,
            "by_model": self.model_usage,
        }


# ==========================================
# 7. PROJE WORKSPACE BAĞLAM YÜKLEME
# ==========================================
def load_project_context(path: str) -> str:
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

    tree_lines: list[str] = []
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

    py_files: list[tuple[str, float]] = []
    for root, _, files in os.walk(path):
        for f in files:
            if f.endswith(".py"):
                fp = os.path.join(root, f)
                try:
                    py_files.append((fp, os.path.getmtime(fp)))
                except Exception:
                    pass
    py_files.sort(key=lambda x: x[1], reverse=True)

    recent: list[str] = []
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