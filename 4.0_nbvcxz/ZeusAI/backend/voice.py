"""
ZeusAI Faz 6 — Ses Arayüzü (Voice Interface)
====================================================
Whisper ile Speech-to-Text (konuşmayı metne çevir)
gTTS / ElevenLabs ile Text-to-Speech (metni sese çevir)
"""
import os
import io
import tempfile
import asyncio
from typing import Optional

from backend.config import WORKSPACE_DIR

# ==========================================
# OPSİYONEL BAĞIMLILIKLAR
# ==========================================
WHISPER_AVAILABLE = False
_whisper_model = None

try:
    import whisper
    WHISPER_AVAILABLE = True
except ImportError:
    pass

try:
    import sounddevice as sd
    import numpy as np
    SOUNDDEVICE_AVAILABLE = True
except ImportError:
    SOUNDDEVICE_AVAILABLE = False
    np = None

GTTS_AVAILABLE = False
try:
    from gtts import gTTS
    GTTS_AVAILABLE = True
except ImportError:
    pass

ELEVENLABS_AVAILABLE = False
try:
    from elevenlabs import generate, set_api_key
    ELEVENLABS_AVAILABLE = True
except ImportError:
    pass


# ==========================================
# WHISPER SPEECH-TO-TEXT (STT)
# ==========================================
def load_whisper_model(model_size: str = "medium"):
    """
    Whisper modelini tembel yükler (lazy load).
    model_size: tiny, base, small, medium, large
    Türkçe için medium önerilir.
    """
    global _whisper_model
    if not WHISPER_AVAILABLE:
        return None
    if _whisper_model is None:
        print(f"[VOICE] Whisper {model_size} modeli yükleniyor...")
        _whisper_model = whisper.load_model(model_size)
        print("[VOICE] Whisper hazır.")
    return _whisper_model


async def listen(seconds: int = 5, sample_rate: int = 44100) -> dict:
    """
    Mikrofondan belirtilen süre kadar ses kaydeder ve Whisper ile metne çevirir.
    
    Dönüş: {"ok": True, "text": "kullanıcının söylediği metin", "language": "tr"}
    """
    if not WHISPER_AVAILABLE:
        return {"ok": False, "text": "Hata: whisper kütüphanesi kurulu değil. `pip install openai-whisper` çalıştırın."}
    if not SOUNDDEVICE_AVAILABLE:
        return {"ok": False, "text": "Hata: sounddevice kütüphanesi kurulu değil. `pip install sounddevice` çalıştırın."}

    try:
        model = load_whisper_model("medium")

        def _record():
            import numpy as _np
            audio = sd.rec(
                int(seconds * sample_rate),
                samplerate=sample_rate,
                channels=1,
                dtype='float32',
            )
            sd.wait()
            # 16kHz'e downsample (Whisper bekler)
            if sample_rate != 16000:
                from scipy.signal import resample
                target_len = int(len(audio) * 16000 / sample_rate)
                audio = resample(audio.flatten(), target_len)
            else:
                audio = audio.flatten()
            return audio

        audio_data = await asyncio.to_thread(_record)

        def _transcribe():
            result = model.transcribe(audio_data, language="tr", fp16=False)
            return result.get("text", "")

        text = await asyncio.to_thread(_transcribe)

        if text.strip():
            return {"ok": True, "text": text.strip(), "language": "tr"}
        else:
            return {"ok": False, "text": "Ses algılanamadı veya sessizlik."}

    except Exception as e:
        return {"ok": False, "text": f"Ses kayıt/çeviri hatası: {str(e)}"}


async def transcribe_file(filepath: str) -> dict:
    """
    Var olan bir ses dosyasını Whisper ile metne çevirir.
    Desteklenen formatlar: wav, mp3, ogg, flac, m4a
    """
    if not WHISPER_AVAILABLE:
        return {"ok": False, "text": "Hata: whisper kütüphanesi kurulu değil."}

    if not os.path.exists(filepath):
        return {"ok": False, "text": f"Hata: '{filepath}' bulunamadı."}

    try:
        model = load_whisper_model("medium")

        def _transcribe_file():
            result = model.transcribe(filepath, language="tr", fp16=False)
            return result.get("text", "")

        text = await asyncio.to_thread(_transcribe_file)

        return {"ok": True, "text": text.strip() or "(sessizlik)", "language": "tr",
                "file": os.path.basename(filepath)}

    except Exception as e:
        return {"ok": False, "text": f"Transkripsiyon hatası: {str(e)}"}


# ==========================================
# TEXT-TO-SPEECH (TTS)
# ==========================================
async def speak(text: str, lang: str = "tr", engine: str = "gtts") -> dict:
    """
    Metni sese çevirir ve çalar.
    
    engine: "gtts" (ücretsiz, çevrimiçi) veya "elevenlabs" (yüksek kalite, API key gerekir)
    
    Dönüş: {"ok": True, "audio_path": "/tmp/resp.mp3", "text": "...", "engine": "gtts"}
    """
    if not text or not text.strip():
        return {"ok": False, "text": "Çevrilecek metin boş."}

    try:
        if engine == "elevenlabs" and ELEVENLABS_AVAILABLE:
            return await _speak_elevenlabs(text, lang)
        elif GTTS_AVAILABLE:
            return await _speak_gtts(text, lang)
        else:
            return {"ok": False, "text": "Hata: gTTS kütüphanesi kurulu değil. `pip install gtts` çalıştırın."}
    except Exception as e:
        return {"ok": False, "text": f"TTS hatası: {str(e)}"}


async def _speak_gtts(text: str, lang: str = "tr") -> dict:
    """gTTS (Google Text-to-Speech) ile ücretsiz ses sentezi."""
    # gTTS sync bir kütüphane, thread'de çalıştır
    def _generate_and_play():
        tts = gTTS(text=text[:500], lang=lang, slow=False)
        # Geçici dosyaya kaydet
        tmp_path = os.path.join(tempfile.gettempdir(), f"zeusai_tts_{os.getpid()}.mp3")
        tts.save(tmp_path)
        return tmp_path

    audio_path = await asyncio.to_thread(_generate_and_play)

    # Çalma (platform bağımsız)
    def _play():
        try:
            # Windows
            import winsound
            # winsound mp3 desteklemez, alternatif:
            os.startfile(audio_path)
        except Exception:
            try:
                # macOS
                os.system(f"afplay '{audio_path}' &")
            except Exception:
                try:
                    # Linux
                    os.system(f"mpg321 '{audio_path}' &")
                except Exception:
                    pass

    await asyncio.to_thread(_play)

    return {
        "ok": True,
        "audio_path": audio_path,
        "text": text[:200],
        "engine": "gtts",
    }


async def _speak_elevenlabs(text: str, lang: str = "tr") -> dict:
    """ElevenLabs ile yüksek kalite ses sentezi."""
    from backend.config import get_key

    api_key = get_key("elevenlabs")
    if not api_key:
        # ElevenLabs API key yoksa gTTS'e fallback
        if GTTS_AVAILABLE:
            return await _speak_gtts(text, lang)
        return {"ok": False, "text": "Hata: ElevenLabs API Key eksik ve gTTS fallback kullanılamıyor."}

    def _generate():
        set_api_key(api_key)
        audio = generate(
            text=text[:500],
            voice="Rachel",  # Varsayılan ses
            model="eleven_multilingual_v2",
        )
        tmp_path = os.path.join(tempfile.gettempdir(), f"zeusai_tts_{os.getpid()}.mp3")
        with open(tmp_path, "wb") as f:
            f.write(audio)
        return tmp_path

    audio_path = await asyncio.to_thread(_generate)

    # Çalma
    def _play():
        try:
            os.startfile(audio_path)
        except Exception:
            try:
                os.system(f"afplay '{audio_path}' &")
            except Exception:
                try:
                    os.system(f"mpg321 '{audio_path}' &")
                except Exception:
                    pass

    await asyncio.to_thread(_play)

    return {
        "ok": True,
        "audio_path": audio_path,
        "text": text[:200],
        "engine": "elevenlabs",
    }


# ==========================================
# KULLANILABİLİRLİK KONTROLÜ
# ==========================================
def get_voice_capabilities() -> dict:
    """Ses sisteminin yeteneklerini döndürür."""
    return {
        "whisper": WHISPER_AVAILABLE,
        "sounddevice": SOUNDDEVICE_AVAILABLE,
        "gtts": GTTS_AVAILABLE,
        "elevenlabs": ELEVENLABS_AVAILABLE,
        "stt_ready": WHISPER_AVAILABLE and SOUNDDEVICE_AVAILABLE,
        "tts_ready": GTTS_AVAILABLE or ELEVENLABS_AVAILABLE,
    }