"""
ZeusAI Faz 7+8 — Yapılandırma, API Key Yönetimi & Model Hub
====================================================================
.env / ortam değişkeni > OS Keychain > çalışma-zamanı bellek sırasıyla
API anahtarlarını çözer. Derin model seçici, otomatik yedek zinciri,
maliyet-bazlı akıllı yönlendirme.
"""
import os
from dotenv import load_dotenv

# ==========================================
# .env yükleme — proje kökünde .env varsa oku
# ==========================================
load_dotenv(dotenv_path=os.path.join(os.path.dirname(os.path.dirname(__file__)), ".env"))
load_dotenv()

# ==========================================
# SABİTLER
# ==========================================
KEYRING_SERVICE = "zeusai"
WORKSPACE_DIR = os.path.abspath(
    os.environ.get("ZEUS_WORKSPACE", os.path.join(os.path.dirname(os.path.dirname(__file__)), "zeus_workspace"))
)
os.makedirs(WORKSPACE_DIR, exist_ok=True)

PLUGINS_DIR = os.path.abspath(
    os.environ.get("ZEUS_PLUGINS", os.path.join(os.path.dirname(os.path.dirname(__file__)), "plugins"))
)
os.makedirs(PLUGINS_DIR, exist_ok=True)

CHROMA_DB_PATH = os.path.abspath(
    os.environ.get("ZEUS_CHROMA_DB", os.path.join(os.path.dirname(os.path.dirname(__file__)), "chroma_db"))
)
os.makedirs(CHROMA_DB_PATH, exist_ok=True)

EPISODES_DB = os.path.abspath(
    os.environ.get("ZEUS_EPISODES_DB", os.path.join(os.path.dirname(os.path.dirname(__file__)), "zeus_episodes.db"))
)

SANDBOX_IMAGE = "python:3.11-slim"

# Maksimum otonom adım sayısı — Faz 7 ile birlikte artık sert sınır değil,
# döngü tespiti (is_stuck) ile değiştirildi. Bu değer sadece güvenlik üst sınırı.
MAX_AGENT_STEPS = 200

# Context sıkıştırma eşiği (token) — Faz 7 ile dynamic_limit() kullanılıyor,
# bu sadece fallback
CONTEXT_TOKEN_LIMIT = 80_000

# ==========================================
# ÇALIŞMA ZAMANI ANAHTAR DEPOSU (bellekte)
# ==========================================
_runtime_keys: dict[str, str] = {}

try:
    import keyring as _keyring
    _KEYRING_AVAILABLE = True
except Exception:
    _KEYRING_AVAILABLE = False


def get_key(service: str) -> str:
    """
    API anahtarını şu sırayla arar:
    1. Ortam değişkeni (ÖRN: DEEPSEEK_API_KEY)
    2. OS Keychain (keyring)
    3. Çalışma-zamanı bellek deposu
    """
    env_val = os.getenv(f"{service.upper()}_API_KEY")
    if env_val:
        return env_val

    if _KEYRING_AVAILABLE:
        try:
            kr_val = _keyring.get_password(KEYRING_SERVICE, service)
            if kr_val:
                return kr_val
        except Exception:
            pass

    return _runtime_keys.get(service, "")


def save_key(service: str, key: str):
    if not key:
        return
    _runtime_keys[service] = key
    if _KEYRING_AVAILABLE:
        try:
            _keyring.set_password(KEYRING_SERVICE, service, key)
        except Exception:
            pass


# ==========================================
# MODEL ID ÇÖZÜMLEME + DEEPSEEK BULUT (FAZ 8)
# ==========================================
def resolve_model_id(model_choice: str) -> str:
    """
    Kullanıcının seçtiği model adını litellm uyumlu model_id'ye çevirir.
    Gerekli API anahtarlarını ortam değişkenlerine set eder.
    """
    # Zaten litellm formatındaysa direkt döndür
    if "/" in model_choice and not any(x in model_choice for x in ["(", "Local:", "Gemini (", "OpenRouter:", "HuggingFace:", "DeepSeek (", "DeepSeek Bulut"]):
        provider = model_choice.split("/")[0].lower()
        if provider == "gemini":
            gemini_key = get_key("gemini")
            if not gemini_key:
                raise ValueError("Gemini API Key eksik!")
            os.environ["GEMINI_API_KEY"] = gemini_key
        elif provider == "openrouter":
            or_key = get_key("openrouter")
            if not or_key:
                raise ValueError("OpenRouter API Key eksik!")
            os.environ["OPENROUTER_API_KEY"] = or_key
        elif provider == "groq":
            groq_key = get_key("groq")
            if not groq_key:
                raise ValueError("Groq API Key eksik!")
            os.environ["GROQ_API_KEY"] = groq_key
        elif provider == "huggingface":
            hf_key = get_key("huggingface")
            if not hf_key:
                raise ValueError("HuggingFace API Key eksik!")
            os.environ["HUGGINGFACE_API_KEY"] = hf_key
        elif provider == "deepseek":
            ds_key = get_key("deepseek")
            if not ds_key:
                raise ValueError("DeepSeek API Key eksik!")
            os.environ["DEEPSEEK_API_KEY"] = ds_key
        elif provider == "ollama":
            pass
        return model_choice

    # --- YEREL MODELLER (Ollama) ---
    if "Local: DeepSeek" in model_choice or ("DeepSeek" in model_choice and "Bulut" not in model_choice and "deepseek/" not in model_choice):
        return "ollama/deepseek-coder"
    elif "Local: Llama 3.1" in model_choice:
        return "ollama/llama3.1"
    elif "Dolphin Llama 3" in model_choice:
        return "ollama/dolphin-llama3"
    elif "Dolphin Mistral" in model_choice:
        return "ollama/dolphin-mistral"

    # --- DEEPSEEK BULUT (FAZ 8) ---
    elif "DeepSeek Bulut" in model_choice or "DeepSeek Reasoner" in model_choice or "DeepSeek Chat" in model_choice:
        ds_key = get_key("deepseek")
        if not ds_key:
            raise ValueError("DeepSeek API Key eksik! Lütfen ayarlardan girin veya .env dosyasına DEEPSEEK_API_KEY ekleyin.")
        os.environ["DEEPSEEK_API_KEY"] = ds_key

        if "Reasoner" in model_choice:
            return "deepseek/deepseek-reasoner"
        return "deepseek/deepseek-chat"

    # --- GERÇEK GEMINI AİLESİ ---
    elif "Gemini" in model_choice:
        gemini_key = get_key("gemini")
        if not gemini_key:
            raise ValueError("Gemini API Key eksik!")
        os.environ["GEMINI_API_KEY"] = gemini_key

        if "3.1 Pro" in model_choice or "2.5 Pro" in model_choice:
            return "gemini/gemini-2.5-pro"
        else:
            return "gemini/gemini-2.5-flash"

    # --- OPENROUTER ---
    elif "OpenRouter" in model_choice:
        or_key = get_key("openrouter")
        if not or_key:
            raise ValueError("OpenRouter API Key eksik!")
        os.environ["OPENROUTER_API_KEY"] = or_key

        if "70B" in model_choice or "70b" in model_choice:
            return "openrouter/meta-llama/llama-3.3-70b-instruct:free"
        else:
            return "openrouter/meta-llama/llama-3.1-8b-instruct:free"

    # --- HUGGINGFACE ---
    elif "HuggingFace" in model_choice:
        hf_key = get_key("huggingface")
        if not hf_key:
            raise ValueError("HuggingFace API Key eksik!")
        os.environ["HUGGINGFACE_API_KEY"] = hf_key
        return "huggingface/Qwen/Qwen2.5-Coder-32B-Instruct"

    # --- GROQ (Yedek) ---
    else:
        groq_key = get_key("groq")
        if not groq_key:
            raise ValueError("Groq API Key eksik!")
        os.environ["GROQ_API_KEY"] = groq_key
        return "groq/llama-3.1-8b-instant"


# ==========================================
# MODEL SEÇENEKLERİ (FAZ 8: Sağlayıcı gruplu)
# ==========================================
MODEL_CHOICES = [
    # DeepSeek Bulut
    "DeepSeek Chat (Bulut) 🧠",
    "DeepSeek Reasoner (Bulut) 🧠🔥",
    # Yerel
    "Local: DeepSeek Coder 💻",
    "Local: Llama 3.1 (8B) 💻",
    "Local: Dolphin Llama 3 💻",
    "Local: Dolphin Mistral 💻",
    # Gemini
    "Gemini (2.5 Flash)",
    "Gemini (2.5 Pro)",
    "Gemini (3.1 Pro)",
    # OpenRouter
    "OpenRouter: Llama 3.1 8B (Ücretsiz) 🌐",
    "OpenRouter: Llama 3.3 70B (Ücretsiz) 🌐",
    # HuggingFace
    "HuggingFace: Qwen 2.5 Coder 🤗",
    # Groq
    "Groq: Llama 3.1 8B (Hızlı Yedek) ☁️",
]

# ==========================================
# OTOMATİK YEDEK ZİNCİRİ (FAZ 8)
# ==========================================
FALLBACK_CHAIN = [
    {"model_name": "deepseek/deepseek-chat"},
    {"model_name": "gemini/gemini-2.5-flash"},
    {"model_name": "groq/llama-3.1-8b-instant"},
]

_router = None


def get_router():
    """litellm Router singleton — otomatik fallback zinciri."""
    global _router
    if _router is None:
        try:
            from litellm import Router
            _router = Router(
                model_list=FALLBACK_CHAIN,
                fallbacks=[{"deepseek/deepseek-chat": ["gemini/gemini-2.5-flash", "groq/llama-3.1-8b-instant"]}],
                num_retries=2,
            )
        except ImportError:
            _router = None
    return _router


# ==========================================
# MALİYET-BAZLI OTOMATİK MODEL YÖNLENDİRME (FAZ 8)
# ==========================================
def route_model_by_complexity(task_complexity: str = "normal", user_override: str = None) -> str:
    """
    Basit görevler → ucuz/hızlı model (DeepSeek Chat / Groq)
    Karmaşık görevler → güçlü model (DeepSeek Reasoner / Gemini Pro / Claude)
    Kullanıcı override ederse onun seçimi geçerli.
    """
    if user_override:
        return resolve_model_id(user_override)

    complexity = task_complexity.lower()
    if complexity in ("simple", "basit", "okuma", "dosya"):
        try:
            if get_key("deepseek"):
                return "deepseek/deepseek-chat"
        except Exception:
            pass
        return "groq/llama-3.1-8b-instant"

    # Normal veya karmaşık
    try:
        if get_key("deepseek"):
            return "deepseek/deepseek-reasoner"
    except Exception:
        pass

    try:
        if get_key("gemini"):
            return "gemini/gemini-2.5-pro"
    except Exception:
        pass

    try:
        if get_key("deepseek"):
            return "deepseek/deepseek-chat"
    except Exception:
        pass

    return "groq/llama-3.1-8b-instant"


# ==========================================
# KEY TEST (FAZ 8: "Bağlantıyı Test Et" butonu)
# ==========================================
def test_api_key(provider: str, key: str = "") -> bool:
    """Verilen sağlayıcı ve API anahtarının çalışıp çalışmadığını test eder."""
    if not key:
        key = get_key(provider)
    if not key:
        return False

    try:
        # Provider'a göre minimal model seç
        test_models = {
            "deepseek": "deepseek/deepseek-chat",
            "gemini": "gemini/gemini-2.5-flash",
            "openrouter": "openrouter/meta-llama/llama-3.1-8b-instruct:free",
            "groq": "groq/llama-3.1-8b-instant",
            "huggingface": "huggingface/Qwen/Qwen2.5-Coder-32B-Instruct",
        }
        model = test_models.get(provider)
        if not model:
            return False

        # Geçici ortam değişkeni set et
        env_var = f"{provider.upper()}_API_KEY"
        old_val = os.environ.get(env_var)
        os.environ[env_var] = key

        try:
            from litellm import completion
            resp = completion(model=model, messages=[{"role": "user", "content": "ping"}], max_tokens=1, timeout=10)
            return resp is not None and resp.choices is not None
        finally:
            if old_val is not None:
                os.environ[env_var] = old_val
            else:
                os.environ.pop(env_var, None)
    except Exception:
        return False