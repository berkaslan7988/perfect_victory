"""
Antigravity Faz 5+6 — Araç (Tool) Katmanı
============================================
Tüm araç tanımları (TOOLS), async executor fonksiyonları ve
TOOL_EXECUTORS sözlüğü burada yaşar.

Sync bloklar asyncio.to_thread() ile sarılır.
Faz 6: Voice interface + Screen Monitor araçları eklendi.
"""
import os
import io
import json
import time
import base64
import difflib
import asyncio
import hashlib
import subprocess
import threading
import importlib.util
from typing import Any, Callable, Optional

from backend.config import WORKSPACE_DIR, PLUGINS_DIR, SANDBOX_IMAGE, get_key

# ==========================================
# OPSİYONEL BAĞIMLILIKLAR (Faz 6: Voice + Screen)
# ==========================================
try:
    from backend.voice import listen as _voice_listen, speak as _voice_speak, get_voice_capabilities
    VOICE_AVAILABLE = True
except Exception:
    VOICE_AVAILABLE = False
    async def _voice_listen(**kw): return {"ok": False, "text": "Voice sistemi kullanılamıyor."}
    async def _voice_speak(**kw): return {"ok": False, "text": "Voice sistemi kullanılamıyor."}

try:
    from backend.screen_monitor import (
        start_screen_monitor as _start_sm,
        stop_screen_monitor as _stop_sm,
        is_monitoring as _is_monitoring,
        get_screen_capabilities,
    )
    SCREEN_MONITOR_AVAILABLE = True
except Exception:
    SCREEN_MONITOR_AVAILABLE = False
    def _start_sm(**kw): pass
    def _stop_sm(): pass
    def _is_monitoring(): return False

# ==========================================
# DİĞER OPSİYONEL BAĞIMLILIKLAR
# ==========================================
try:
    import docker
    from docker.errors import DockerException, ImageNotFound
    _docker_client = docker.from_env()
    _docker_client.ping()
    DOCKER_AVAILABLE = True
    try:
        _docker_client.images.get(SANDBOX_IMAGE)
    except ImageNotFound:
        print(f"📦 {SANDBOX_IMAGE} imajı indiriliyor...")
        _docker_client.images.pull(SANDBOX_IMAGE)
except Exception:
    DOCKER_AVAILABLE = False
    _docker_client = None
    print("[TOOLS] Docker not found. Subprocess mode.")

try:
    from playwright.async_api import async_playwright
    PLAYWRIGHT_AVAILABLE = True
except Exception:
    PLAYWRIGHT_AVAILABLE = False

try:
    import pyautogui
    pyautogui.FAILSAFE = True
    PYAUTOGUI_AVAILABLE = True
except Exception:
    PYAUTOGUI_AVAILABLE = False

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

try:
    import mss
    from PIL import Image
    import google.generativeai as genai
    VISION_AVAILABLE = True
except Exception:
    VISION_AVAILABLE = False

try:
    from tavily import TavilyClient
    TAVILY_AVAILABLE = True
except Exception:
    TAVILY_AVAILABLE = False


# ==========================================
# WS CALLBACK TİPİ
# ==========================================
WsCallback = Optional[Callable]

# Onay bekleme mekanizması
_pending_approval: asyncio.Event | None = None
_approval_result: bool = False


def set_approval_event(event: asyncio.Event):
    global _pending_approval
    _pending_approval = event


def get_approval_result() -> bool:
    return _approval_result


def grant_approval():
    global _approval_result, _pending_approval
    _approval_result = True
    if _pending_approval:
        _pending_approval.set()


# ==========================================
# ARAÇ TANIMLARI (LLM'e gönderilecek schema)
# ==========================================
TOOLS = [
    # Faz 0-1: Temel dosya ve sistem araçları
    {"type": "function", "function": {"name": "create_file", "description": "Workspace içinde dosya oluşturur.", "parameters": {"type": "object", "properties": {"filename": {"type": "string"}, "content": {"type": "string"}}, "required": ["filename", "content"]}}},
    {"type": "function", "function": {"name": "list_files", "description": "Workspace dosyalarını listeler.", "parameters": {"type": "object", "properties": {}}}},
    {"type": "function", "function": {"name": "analyze_screen", "description": "Ekran görüntüsü alıp analiz eder.", "parameters": {"type": "object", "properties": {"query": {"type": "string"}}, "required": ["query"]}}},
    {"type": "function", "function": {"name": "web_search", "description": "İnternette arama yapar.", "parameters": {"type": "object", "properties": {"query": {"type": "string"}}, "required": ["query"]}}},
    {"type": "function", "function": {"name": "run_python_code", "description": "Docker sandbox içinde Python kodu çalıştırır. Matplotlib grafikleri otomatik yakalanıp gösterilir.", "parameters": {"type": "object", "properties": {"code": {"type": "string"}, "timeout": {"type": "integer"}}, "required": ["code"]}}},
    {"type": "function", "function": {"name": "run_command", "description": "Docker sandbox içinde shell komutu çalıştırır. KRİTİK KOMUTLAR İÇİN ONAY GEREKTİRİR.", "parameters": {"type": "object", "properties": {"command": {"type": "string"}}, "required": ["command"]}}},
    {"type": "function", "function": {"name": "read_file", "description": "Workspace'den dosya okur.", "parameters": {"type": "object", "properties": {"path": {"type": "string"}}, "required": ["path"]}}},
    {"type": "function", "function": {"name": "edit_file", "description": "Workspace'deki dosyayı günceller.", "parameters": {"type": "object", "properties": {"path": {"type": "string"}, "content": {"type": "string"}}, "required": ["path", "content"]}}},

    # Faz 2: Tarayıcı otomasyonu (Playwright)
    {"type": "function", "function": {"name": "browser_navigate", "description": "Gerçek bir tarayıcıda (Playwright/Chromium) verilen URL'ye gider.", "parameters": {"type": "object", "properties": {"url": {"type": "string"}}, "required": ["url"]}}},
    {"type": "function", "function": {"name": "browser_click", "description": "Açık tarayıcı sayfasında CSS selector ile belirtilen elemente tıklar.", "parameters": {"type": "object", "properties": {"selector": {"type": "string"}}, "required": ["selector"]}}},
    {"type": "function", "function": {"name": "browser_type", "description": "Açık tarayıcı sayfasında CSS selector ile belirtilen input alanına metin yazar.", "parameters": {"type": "object", "properties": {"selector": {"type": "string"}, "text": {"type": "string"}}, "required": ["selector", "text"]}}},
    {"type": "function", "function": {"name": "browser_screenshot", "description": "Açık tarayıcı sayfasının ekran görüntüsünü alır ve Gemini Vision ile analiz eder.", "parameters": {"type": "object", "properties": {"query": {"type": "string"}}, "required": ["query"]}}},

    # Faz 2: Computer Use (pyautogui)
    {"type": "function", "function": {"name": "computer_click", "description": "Kullanıcının gerçek masaüstünde belirtilen koordinata tıklar. ONAY GEREKTİRİR.", "parameters": {"type": "object", "properties": {"x": {"type": "integer"}, "y": {"type": "integer"}, "button": {"type": "string"}}, "required": ["x", "y"]}}},
    {"type": "function", "function": {"name": "computer_type", "description": "Aktif pencereye klavye ile metin yazar. ONAY GEREKTİRİR.", "parameters": {"type": "object", "properties": {"text": {"type": "string"}}, "required": ["text"]}}},
    {"type": "function", "function": {"name": "computer_find_on_screen", "description": "Workspace'deki bir görsel dosyasını ekranda arar, bulursa merkez koordinatını döner.", "parameters": {"type": "object", "properties": {"image_path": {"type": "string"}}, "required": ["image_path"]}}},

    # Faz 2: Git entegrasyonu
    {"type": "function", "function": {"name": "git_status", "description": "Workspace git deposunun durumunu gösterir.", "parameters": {"type": "object", "properties": {}}}},
    {"type": "function", "function": {"name": "git_diff", "description": "Workspace'deki commit edilmemiş değişikliklerin diff'ini gösterir.", "parameters": {"type": "object", "properties": {"file": {"type": "string"}}, "required": []}}},
    {"type": "function", "function": {"name": "git_commit", "description": "Workspace'deki tüm değişiklikleri commit eder.", "parameters": {"type": "object", "properties": {"message": {"type": "string"}}, "required": ["message"]}}},
    {"type": "function", "function": {"name": "git_log", "description": "Son commit geçmişini gösterir.", "parameters": {"type": "object", "properties": {"n": {"type": "integer"}}, "required": []}}},

    # Faz 2: Gelişmiş dosya, HTTP, süreç
    {"type": "function", "function": {"name": "diff_files", "description": "Workspace içindeki iki dosyayı karşılaştırır (unified diff).", "parameters": {"type": "object", "properties": {"path1": {"type": "string"}, "path2": {"type": "string"}}, "required": ["path1", "path2"]}}},
    {"type": "function", "function": {"name": "search_in_files", "description": "Workspace içinde belirtilen uzantılı dosyalarda metin arar (grep benzeri).", "parameters": {"type": "object", "properties": {"pattern": {"type": "string"}, "extension": {"type": "string"}}, "required": ["pattern"]}}},
    {"type": "function", "function": {"name": "http_request", "description": "Herhangi bir REST API'ye HTTP isteği gönderir.", "parameters": {"type": "object", "properties": {"method": {"type": "string"}, "url": {"type": "string"}, "body": {"type": "object"}}, "required": ["method", "url"]}}},
    {"type": "function", "function": {"name": "list_processes", "description": "Sistemde çalışan süreçleri CPU kullanımına göre listeler.", "parameters": {"type": "object", "properties": {}}}},

    # Faz 6: Voice Interface
    {"type": "function", "function": {"name": "voice_listen", "description": "Mikrofondan ses kaydedip Whisper ile metne çevirir. Kullanıcıdan sesli komut almak için kullan.", "parameters": {"type": "object", "properties": {"seconds": {"type": "integer"}}, "required": []}}},
    {"type": "function", "function": {"name": "voice_speak", "description": "Metni sese çevirip hoparlörden okur. Kullanıcıya sesli yanıt vermek için kullan.", "parameters": {"type": "object", "properties": {"text": {"type": "string"}, "lang": {"type": "string"}, "engine": {"type": "string"}}, "required": ["text"]}}},

    # Faz 6: Screen Monitor
    {"type": "function", "function": {"name": "start_screen_monitor", "description": "Arka planda sürekli ekran izlemeyi başlatır. Hata mesajları algılanırsa ajana otomatik bildirir. triggers boş bırakılırsa Error/Exception/FATAL algılar.", "parameters": {"type": "object", "properties": {"triggers": {"type": "string"}}, "required": []}}},
    {"type": "function", "function": {"name": "stop_screen_monitor", "description": "Arka plan ekran izlemeyi durdurur.", "parameters": {"type": "object", "properties": {}, "required": []}}},
    {"type": "function", "function": {"name": "check_screen_monitor", "description": "Ekran izleme durumunu sorgular (aktif/pasif).", "parameters": {"type": "object", "properties": {}, "required": []}}},
]

# ==========================================
# MATPLOTLIB SARMALAYICI
# ==========================================
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


# ==========================================
# DOCKER / SUBPROCESS YARDIMCI FONKSİYONLARI
# ==========================================
def _kill_container_after(container, timeout: int):
    time.sleep(timeout)
    try:
        container.reload()
        if container.status == "running":
            container.kill()
    except Exception:
        pass


def _docker_run_streaming(command_list: list, timeout: int, ws_callback: WsCallback = None) -> str:
    lines: list[str] = []
    container = None
    exit_code = -1
    try:
        container = _docker_client.containers.run(
            SANDBOX_IMAGE,
            command=command_list,
            volumes={WORKSPACE_DIR: {"bind": "/workspace", "mode": "rw"}},
            working_dir="/workspace",
            mem_limit="512m",
            network_mode="none",
            detach=True,
        )
        killer = threading.Thread(target=_kill_container_after, args=(container, timeout), daemon=True)
        killer.start()

        for chunk in container.logs(stream=True, follow=True):
            for line in chunk.decode("utf-8", errors="replace").splitlines():
                lines.append(line)
        try:
            result = container.wait(timeout=5)
            exit_code = result.get("StatusCode", -1)
        except Exception:
            exit_code = -1
    except Exception as e:
        lines.append(f"[DOCKER HATASI]: {str(e)}")
    finally:
        if container is not None:
            try:
                container.remove(force=True)
            except Exception:
                pass
    return "STDOUT/STDERR (canlı akış):\n" + "\n".join(lines) + f"\nReturn Code: {exit_code}"


def _subprocess_run_streaming(cmd, timeout: int, shell: bool = False) -> str:
    lines: list[str] = []
    try:
        proc = subprocess.Popen(
            cmd, shell=shell, cwd=WORKSPACE_DIR,
            stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
            text=True, bufsize=1,
        )
        start = time.time()
        for line in proc.stdout:
            lines.append(line.rstrip())
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


def _extract_figures(output: str) -> tuple[str, list[str]]:
    clean_lines: list[str] = []
    figures: list[str] = []
    for line in output.splitlines():
        if line.startswith("__FIGS__:"):
            try:
                figs = json.loads(line[len("__FIGS__:"):])
                figures.extend(figs)
            except Exception:
                pass
        else:
            clean_lines.append(line)
    cleaned = "\n".join(clean_lines)
    if figures:
        cleaned += f"\n[SİSTEM]: {len(figures)} grafik üretildi."
    return cleaned, figures


# ==========================================
# ASYNC EXECUTOR FONKSİYONLARI
# ==========================================
async def execute_create_file(filename: str, content: str, **_) -> dict:
    try:
        safe_path = os.path.join(WORKSPACE_DIR, os.path.basename(filename))
        await asyncio.to_thread(_write_file, safe_path, content)
        return {"ok": True, "text": f"Başarılı: '{filename}' oluşturuldu.", "filename": filename}
    except Exception as e:
        return {"ok": False, "text": f"Hata: {str(e)}"}


def _write_file(path: str, content: str):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        f.write(content)


async def execute_list_files(**_) -> dict:
    try:
        files = await asyncio.to_thread(os.listdir, WORKSPACE_DIR)
        return {"ok": True, "text": json.dumps(files, ensure_ascii=False)}
    except Exception as e:
        return {"ok": False, "text": f"Hata: {str(e)}"}


async def execute_read_file(path: str, **_) -> dict:
    try:
        full = os.path.join(WORKSPACE_DIR, os.path.basename(path))
        content = await asyncio.to_thread(_read_file, full)
        return {"ok": True, "text": content}
    except Exception as e:
        return {"ok": False, "text": f"Hata: {str(e)}"}


def _read_file(path: str) -> str:
    with open(path, "r", encoding="utf-8") as f:
        return f.read()


async def execute_edit_file(path: str, content: str, **_) -> dict:
    try:
        full = os.path.join(WORKSPACE_DIR, os.path.basename(path))
        await asyncio.to_thread(_write_file, full, content)
        return {"ok": True, "text": f"Başarılı: '{path}' güncellendi."}
    except Exception as e:
        return {"ok": False, "text": f"Hata: {str(e)}"}


async def execute_analyze_screen(query: str, **_) -> dict:
    if not VISION_AVAILABLE:
        return {"ok": False, "text": "Hata: Görüntü analiz kütüphaneleri kurulu değil (mss, PIL, google-generativeai)."}
    gemini_key = get_key("gemini")
    if not gemini_key:
        return {"ok": False, "text": "Hata: Gemini API Key eksik."}
    try:
        def _capture_and_analyze():
            with mss.mss() as sct:
                monitor = sct.monitors[1]
                screenshot = sct.grab(monitor)
                img = Image.frombytes("RGB", screenshot.size, screenshot.bgra, "raw", "BGRX")
                img.thumbnail((1024, 1024))
                genai.configure(api_key=gemini_key)
                response = genai.GenerativeModel("gemini-2.5-flash").generate_content([query, img])
                return response.text
        result = await asyncio.to_thread(_capture_and_analyze)
        return {"ok": True, "text": result}
    except Exception as e:
        return {"ok": False, "text": f"Vision Hatası: {str(e)}"}


async def execute_web_search(query: str, **_) -> dict:
    if not TAVILY_AVAILABLE:
        return {"ok": False, "text": "Hata: Tavily kütüphanesi kurulu değil."}
    tavily_key = get_key("tavily")
    if not tavily_key:
        return {"ok": False, "text": "Hata: Tavily Key eksik."}
    try:
        def _search():
            response = TavilyClient(api_key=tavily_key).search(query, max_results=3)
            return "\n---\n".join(
                [f"[{i+1}] {r['title']}\n{r['content']}" for i, r in enumerate(response.get("results", []))]
            )
        result = await asyncio.to_thread(_search)
        return {"ok": True, "text": result}
    except Exception as e:
        return {"ok": False, "text": f"Web Hatası: {str(e)}"}


async def execute_run_python_code(code: str, timeout: int = 10, ws_callback: WsCallback = None, **_) -> dict:
    wrapped = MPL_WRAP_HEADER + code + MPL_WRAP_FOOTER
    try:
        if DOCKER_AVAILABLE:
            raw = await asyncio.to_thread(_docker_run_streaming, ["python", "-c", wrapped], timeout, ws_callback)
        else:
            raw = await asyncio.to_thread(_subprocess_run_streaming, ["python", "-c", wrapped], timeout)
        cleaned, figures = _extract_figures(raw)
        result: dict[str, Any] = {"ok": True, "text": cleaned}
        if figures:
            result["images"] = figures
        return result
    except Exception as e:
        return {"ok": False, "text": f"Hata: {str(e)}"}


async def execute_run_command(command: str, timeout: int = 30, ws_callback: WsCallback = None, **_) -> dict:
    if any(p in command.lower() for p in ["rm -rf /", "mkfs", "format c:", ":(){:|:&};:"]):
        return {"ok": False, "text": "HATA: Yıkıcı sistem komutu engellendi."}

    critical_patterns = ["rm ", "rm -", "del ", "pip uninstall", "rmdir", "sudo ", "drop table", "git reset --hard"]
    is_critical = any(p in command.lower() for p in critical_patterns)
    if is_critical:
        return {
            "ok": False,
            "text": f"[ONAY GEREKLİ] Bu komut kritik/yıkıcı bir işlem içeriyor: `{command}`. "
                    "Lütfen araç çağırmayı BIRAK ve kullanıcıdan bu komutu çalıştırmak için onay iste. "
                    "Kullanıcı 'onaylıyorum' veya 'evet' dedikten sonra bu aracı TEKRAR çağır.",
            "approval_needed": True,
            "command": command,
        }
    try:
        if DOCKER_AVAILABLE:
            raw = await asyncio.to_thread(_docker_run_streaming, ["/bin/bash", "-c", command], timeout, ws_callback)
        else:
            raw = await asyncio.to_thread(_subprocess_run_streaming, command, timeout, shell=True)
        return {"ok": True, "text": raw}
    except Exception as e:
        return {"ok": False, "text": f"Hata: {str(e)}"}


# ==========================================
# TARAYICI OTOMASYONU (PLAYWRIGHT)
# ==========================================
_playwright_instance = None
_browser_instance = None
_browser_page = None


async def _get_browser_page():
    global _playwright_instance, _browser_instance, _browser_page
    if _browser_page is not None:
        return _browser_page
    pw = await async_playwright().start()
    _playwright_instance = pw
    _browser_instance = await pw.chromium.launch(headless=True)
    _browser_page = await _browser_instance.new_page()
    return _browser_page


async def reset_browser():
    global _playwright_instance, _browser_instance, _browser_page
    try:
        if _browser_instance:
            await _browser_instance.close()
        if _playwright_instance:
            await _playwright_instance.stop()
    except Exception:
        pass
    _playwright_instance = None
    _browser_instance = None
    _browser_page = None


async def execute_browser_navigate(url: str, **_) -> dict:
    if not PLAYWRIGHT_AVAILABLE:
        return {"ok": False, "text": "Hata: Playwright kurulu değil. `pip install playwright && playwright install chromium` çalıştırın."}
    try:
        page = await _get_browser_page()
        await page.goto(url, wait_until="networkidle", timeout=15000)
        title = await page.title()
        return {"ok": True, "text": f"Navigated: {title}"}
    except Exception as e:
        return {"ok": False, "text": f"Tarayıcı Hatası: {str(e)}"}


async def execute_browser_click(selector: str, **_) -> dict:
    if not PLAYWRIGHT_AVAILABLE:
        return {"ok": False, "text": "Hata: Playwright kurulu değil."}
    try:
        page = await _get_browser_page()
        await page.click(selector, timeout=5000)
        return {"ok": True, "text": f"Clicked: {selector}"}
    except Exception as e:
        return {"ok": False, "text": f"Tarayıcı Hatası: {str(e)}"}


async def execute_browser_type(selector: str, text: str, **_) -> dict:
    if not PLAYWRIGHT_AVAILABLE:
        return {"ok": False, "text": "Hata: Playwright kurulu değil."}
    try:
        page = await _get_browser_page()
        await page.fill(selector, text, timeout=5000)
        return {"ok": True, "text": f"Yazıldı: {selector} <- {text[:40]}"}
    except Exception as e:
        return {"ok": False, "text": f"Tarayıcı Hatası: {str(e)}"}


async def execute_browser_screenshot(query: str = "Bu sayfada ne var?", **_) -> dict:
    if not PLAYWRIGHT_AVAILABLE:
        return {"ok": False, "text": "Hata: Playwright kurulu değil."}
    gemini_key = get_key("gemini")
    if not gemini_key:
        return {"ok": False, "text": "Hata: Gemini API Key eksik (görsel analiz için gerekli)."}
    try:
        page = await _get_browser_page()
        img_bytes = await page.screenshot(full_page=True)
        def _analyze():
            img = Image.open(io.BytesIO(img_bytes))
            img.thumbnail((1280, 1280))
            genai.configure(api_key=gemini_key)
            response = genai.GenerativeModel("gemini-2.5-flash").generate_content([query, img])
            return response.text
        result = await asyncio.to_thread(_analyze)
        return {"ok": True, "text": result}
    except Exception as e:
        return {"ok": False, "text": f"Tarayıcı/Vision Hatası: {str(e)}"}


# ==========================================
# COMPUTER USE (PYAUTOGUI)
# ==========================================
async def execute_computer_click(x: int, y: int, button: str = "left", **_) -> dict:
    if not PYAUTOGUI_AVAILABLE:
        return {"ok": False, "text": "Hata: pyautogui kullanılamıyor."}
    return {
        "ok": False,
        "text": f"[ONAY GEREKLİ] Masaüstünde ({x},{y}) konumuna tıklanacak. Lütfen kullanıcıdan onay iste.",
        "approval_needed": True,
        "action": "computer_click",
        "params": {"x": x, "y": y, "button": button},
    }


async def execute_computer_click_approved(x: int, y: int, button: str = "left") -> dict:
    try:
        await asyncio.to_thread(pyautogui.click, x, y, button=button)
        return {"ok": True, "text": f"Tıklandı: ({x},{y})"}
    except Exception as e:
        return {"ok": False, "text": f"Hata: {str(e)}"}


async def execute_computer_type(text: str, **_) -> dict:
    if not PYAUTOGUI_AVAILABLE:
        return {"ok": False, "text": "Hata: pyautogui kullanılamıyor."}
    return {
        "ok": False,
        "text": f"[ONAY GEREKLİ] Aktif pencereye '{text[:40]}...' yazılacak. Lütfen kullanıcıdan onay iste.",
        "approval_needed": True,
        "action": "computer_type",
        "params": {"text": text},
    }


async def execute_computer_type_approved(text: str) -> dict:
    try:
        await asyncio.to_thread(pyautogui.typewrite, text, interval=0.02)
        return {"ok": True, "text": f"Yazıldı: {text[:60]}"}
    except Exception as e:
        return {"ok": False, "text": f"Hata: {str(e)}"}


async def execute_computer_find_on_screen(image_path: str, **_) -> dict:
    if not PYAUTOGUI_AVAILABLE:
        return {"ok": False, "text": "Hata: pyautogui kullanılamıyor."}
    try:
        full_path = os.path.join(WORKSPACE_DIR, os.path.basename(image_path))
        def _find():
            loc = pyautogui.locateOnScreen(full_path, confidence=0.8)
            if loc:
                center = pyautogui.center(loc)
                return f"Bulundu: merkez=({center.x},{center.y})"
            return "Ekranda bulunamadı."
        result = await asyncio.to_thread(_find)
        return {"ok": True, "text": result}
    except Exception as e:
        return {"ok": False, "text": f"Hata: {str(e)}"}


# ==========================================
# GIT ENTEGRASYONU
# ==========================================
def _get_repo():
    try:
        return Repo(WORKSPACE_DIR)
    except InvalidGitRepositoryError:
        return Repo.init(WORKSPACE_DIR)


async def execute_git_status(**_) -> dict:
    if not GIT_AVAILABLE:
        return {"ok": False, "text": "Hata: gitpython kurulu değil."}
    try:
        result = await asyncio.to_thread(lambda: _get_repo().git.status())
        return {"ok": True, "text": result or "Temiz çalışma dizini."}
    except Exception as e:
        return {"ok": False, "text": f"Hata: {str(e)}"}


async def execute_git_diff(file: str = None, **_) -> dict:
    if not GIT_AVAILABLE:
        return {"ok": False, "text": "Hata: gitpython kurulu değil."}
    try:
        def _diff():
            repo = _get_repo()
            return repo.git.diff(file) if file else repo.git.diff()
        result = await asyncio.to_thread(_diff)
        return {"ok": True, "text": result or "Değişiklik yok."}
    except Exception as e:
        return {"ok": False, "text": f"Hata: {str(e)}"}


async def execute_git_commit(message: str, **_) -> dict:
    if not GIT_AVAILABLE:
        return {"ok": False, "text": "Hata: gitpython kurulu değil."}
    try:
        def _commit():
            repo = _get_repo()
            repo.git.add(A=True)
            if not repo.is_dirty(untracked_files=True):
                return "Commit edilecek değişiklik yok."
            commit = repo.index.commit(message)
            return f"Commit: {commit.hexsha[:8]} — {message}"
        result = await asyncio.to_thread(_commit)
        return {"ok": True, "text": result}
    except Exception as e:
        return {"ok": False, "text": f"Hata: {str(e)}"}


async def execute_git_log(n: int = 5, **_) -> dict:
    if not GIT_AVAILABLE:
        return {"ok": False, "text": "Hata: gitpython kurulu değil."}
    try:
        def _log():
            repo = _get_repo()
            if not repo.head.is_valid():
                return "Henüz commit yok."
            return "\n".join(f"{c.hexsha[:8]} {c.message.strip()[:60]}" for c in repo.iter_commits(max_count=n))
        result = await asyncio.to_thread(_log)
        return {"ok": True, "text": result}
    except Exception as e:
        return {"ok": False, "text": f"Hata: {str(e)}"}


# ==========================================
# GELİŞMİŞ DOSYA İŞLEMLERİ + HTTP + SÜREÇ
# ==========================================
async def execute_diff_files(path1: str, path2: str, **_) -> dict:
    try:
        def _diff():
            p1 = os.path.join(WORKSPACE_DIR, os.path.basename(path1))
            p2 = os.path.join(WORKSPACE_DIR, os.path.basename(path2))
            with open(p1, "r", encoding="utf-8") as f1, open(p2, "r", encoding="utf-8") as f2:
                diff = difflib.unified_diff(f1.readlines(), f2.readlines(), fromfile=path1, tofile=path2)
            result = "".join(diff)
            return result or "Fark yok."
        result = await asyncio.to_thread(_diff)
        return {"ok": True, "text": result}
    except Exception as e:
        return {"ok": False, "text": f"Hata: {str(e)}"}


async def execute_search_in_files(pattern: str, extension: str = ".py", **_) -> dict:
    try:
        def _search():
            matches: list[str] = []
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
        result = await asyncio.to_thread(_search)
        return {"ok": True, "text": result}
    except Exception as e:
        return {"ok": False, "text": f"Hata: {str(e)}"}


async def execute_http_request(method: str, url: str, body: dict = None, **_) -> dict:
    if not HTTPX_AVAILABLE:
        return {"ok": False, "text": "Hata: httpx kurulu değil."}
    try:
        def _request():
            with httpx.Client(timeout=30) as client:
                r = client.request(method.upper(), url, json=body)
            return json.dumps({"status": r.status_code, "body": r.text[:2000]}, indent=2, ensure_ascii=False)
        result = await asyncio.to_thread(_request)
        return {"ok": True, "text": result}
    except Exception as e:
        return {"ok": False, "text": f"HTTP Hatası: {str(e)}"}


async def execute_list_processes(**_) -> dict:
    if not PSUTIL_AVAILABLE:
        return {"ok": False, "text": "Hata: psutil kurulu değil."}
    try:
        def _list():
            procs = [p.info for p in psutil.process_iter(["pid", "name", "cpu_percent"])]
            procs = sorted(procs, key=lambda x: x.get("cpu_percent") or 0, reverse=True)[:20]
            return json.dumps(procs, indent=2, ensure_ascii=False)
        result = await asyncio.to_thread(_list)
        return {"ok": True, "text": result}
    except Exception as e:
        return {"ok": False, "text": f"Hata: {str(e)}"}


# ==========================================
# FAZ 6: VOICE INTERFACE EXECUTORS
# ==========================================
async def execute_voice_listen(seconds: int = 5, **_) -> dict:
    """Mikrofondan ses kaydedip Whisper STT ile metne çevirir."""
    return await _voice_listen(seconds=seconds)


async def execute_voice_speak(text: str, lang: str = "tr", engine: str = "gtts", **_) -> dict:
    """Metni sese çevirip hoparlörden okur."""
    return await _voice_speak(text=text, lang=lang, engine=engine)


# ==========================================
# FAZ 6: SCREEN MONITOR EXECUTORS
# ==========================================
async def execute_start_screen_monitor(triggers: str = "", **_) -> dict:
    """Arka planda sürekli ekran izlemeyi başlatır."""
    trigger_list = None
    if triggers.strip():
        # Virgülle ayrılmış tetikleyicileri parse et
        trigger_list = [t.strip() for t in triggers.split(",") if t.strip()]
    try:
        _start_sm(triggers=trigger_list)
        return {"ok": True, "text": f"Ekran izleme başlatıldı. Tetikleyiciler: {trigger_list or ['Error','Exception','FAILED','Traceback','FATAL']}"}
    except Exception as e:
        return {"ok": False, "text": f"Ekran izleme başlatılamadı: {str(e)}"}


async def execute_stop_screen_monitor(**_) -> dict:
    """Arka plan ekran izlemeyi durdurur."""
    try:
        _stop_sm()
        return {"ok": True, "text": "Ekran izleme durduruldu."}
    except Exception as e:
        return {"ok": False, "text": f"Ekran izleme durdurulamadı: {str(e)}"}


async def execute_check_screen_monitor(**_) -> dict:
    """Ekran izleme durumunu sorgular."""
    active = _is_monitoring()
    return {"ok": True, "text": f"Ekran izleme: {'AKTİF' if active else 'PASİF'}"}


# ==========================================
# PLUGİN SİSTEMİ
# ==========================================
def _load_plugins() -> tuple[list[dict], dict[str, Callable]]:
    plugin_defs: list[dict] = []
    plugin_executors: dict[str, Callable] = {}

    if not os.path.isdir(PLUGINS_DIR):
        return plugin_defs, plugin_executors

    for fname in sorted(os.listdir(PLUGINS_DIR)):
        if not fname.endswith(".py") or fname.startswith("_"):
            continue
        fpath = os.path.join(PLUGINS_DIR, fname)
        try:
            spec = importlib.util.spec_from_file_location(fname[:-3], fpath)
            module = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(module)
            tool_def = getattr(module, "TOOL_DEF", None)
            executor = getattr(module, "execute", None)
            if tool_def and callable(executor):
                name = tool_def["function"]["name"]
                plugin_defs.append(tool_def)
                original_exec = executor

                async def _async_wrapper(_exec=original_exec, **kwargs):
                    result = await asyncio.to_thread(_exec, **kwargs)
                    if isinstance(result, dict):
                        return result
                    return {"ok": True, "text": str(result)}

                plugin_executors[name] = _async_wrapper
                print(f"[PLUGIN] Yüklendi: {fname} → {name}")
        except Exception as e:
            print(f"[PLUGIN HATA] {fname}: {e}")

    return plugin_defs, plugin_executors


_PLUGIN_DEFS, _PLUGIN_EXECUTORS = _load_plugins()

# Plugin araç tanımlarını ana listeye ekle
TOOLS = TOOLS + _PLUGIN_DEFS

# ==========================================
# TOOL EXECUTOR HARİTASI
# ==========================================
TOOL_EXECUTORS: dict[str, Callable] = {
    "create_file": execute_create_file,
    "list_files": execute_list_files,
    "analyze_screen": execute_analyze_screen,
    "web_search": execute_web_search,
    "run_python_code": execute_run_python_code,
    "run_command": execute_run_command,
    "read_file": execute_read_file,
    "edit_file": execute_edit_file,

    "browser_navigate": execute_browser_navigate,
    "browser_click": execute_browser_click,
    "browser_type": execute_browser_type,
    "browser_screenshot": execute_browser_screenshot,

    "computer_click": execute_computer_click,
    "computer_type": execute_computer_type,
    "computer_find_on_screen": execute_computer_find_on_screen,

    "git_status": execute_git_status,
    "git_diff": execute_git_diff,
    "git_commit": execute_git_commit,
    "git_log": execute_git_log,

    "diff_files": execute_diff_files,
    "search_in_files": execute_search_in_files,
    "http_request": execute_http_request,
    "list_processes": execute_list_processes,

    # Faz 6: Voice
    "voice_listen": execute_voice_listen,
    "voice_speak": execute_voice_speak,

    # Faz 6: Screen Monitor
    "start_screen_monitor": execute_start_screen_monitor,
    "stop_screen_monitor": execute_stop_screen_monitor,
    "check_screen_monitor": execute_check_screen_monitor,

    **_PLUGIN_EXECUTORS,
}


def get_system_capabilities() -> dict:
    """Sistem yeteneklerini özetleyen sözlük döndürür."""
    caps = {
        "docker": DOCKER_AVAILABLE,
        "chromadb": True,
        "playwright": PLAYWRIGHT_AVAILABLE,
        "pyautogui": PYAUTOGUI_AVAILABLE,
        "git": GIT_AVAILABLE,
        "httpx": HTTPX_AVAILABLE,
        "psutil": PSUTIL_AVAILABLE,
        "vision": VISION_AVAILABLE,
        "tavily": TAVILY_AVAILABLE,
        "plugins_count": len(_PLUGIN_DEFS),
        "workspace": WORKSPACE_DIR,
        "tools_count": len(TOOLS),
    }
    # Faz 6 capabilities
    if VOICE_AVAILABLE or SCREEN_MONITOR_AVAILABLE:
        try:
            caps["voice"] = get_voice_capabilities()
        except Exception:
            caps["voice"] = {}
        try:
            caps["screen_monitor"] = get_screen_capabilities()
        except Exception:
            caps["screen_monitor"] = {}
    return caps