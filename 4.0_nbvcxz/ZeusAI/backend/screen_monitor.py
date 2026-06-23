"""
ZeusAI Faz 6 — Sürekli Ekran İzleme (Screen Monitor)
============================================================
Event-driven screen watcher. Arka planda periyodik olarak ekran
görüntüsü alır, OCR ile metin çıkarır. Tetikleyici kelimeler
(trigger) algılanırsa ajana otomatik olay gönderir.

Kullanım:
    watcher = ScreenWatcher(triggers=["Error", "Exception", "FAILED"])
    watcher.start()
    # ... bir süre sonra ...
    watcher.stop()
"""
import os
import time
import threading
import asyncio
from typing import Callable, Optional
from dataclasses import dataclass, field

# ==========================================
# OPSİYONEL BAĞIMLILIKLAR
# ==========================================
MSS_AVAILABLE = False
try:
    import mss
    MSS_AVAILABLE = True
except ImportError:
    pass

PIL_AVAILABLE = False
try:
    from PIL import Image
    PIL_AVAILABLE = True
except ImportError:
    pass

PYTESSERACT_AVAILABLE = False
try:
    import pytesseract
    PYTESSERACT_AVAILABLE = True
except ImportError:
    pass

VISION_AVAILABLE = False
_vision_model = None
try:
    import google.generativeai as genai
    VISION_AVAILABLE = True
except ImportError:
    pass


# ==========================================
# SCREEN WATCHER
# ==========================================
@dataclass
class ScreenEvent:
    """Ekran izleme olayı."""
    timestamp: float
    trigger_word: str
    context: str           # Etraftaki metin (max 300 karakter)
    screenshot_b64: Optional[str] = None  # Base64 PNG (opsiyonel)
    monitor_index: int = 1


class ScreenWatcher:
    """
    Arka plan thread'inde sürekli ekran görüntüsü alır,
    OCR ile metin çıkarır ve tetikleyici kelimeleri arar.

    Tetikleyici bulursa callback fonksiyonunu çağırır.
    """

    def __init__(
        self,
        triggers: list[str] = None,
        callback: Callable = None,
        interval: float = 5.0,
        use_ocr: bool = True,
        use_vision: bool = False,
        capture_screenshot: bool = False,
        monitor_index: int = 1,
    ):
        """
        Args:
            triggers: Tetikleyici kelime listesi (case-insensitive)
            callback: Tetikleyici bulunduğunda çağrılacak async fonksiyon
            interval: İki kontrol arası süre (saniye)
            use_ocr: Tesseract OCR kullan (lokal, offline)
            use_vision: Gemini Vision kullan (cloud, daha akıllı)
            capture_screenshot: Olayla birlikte base64 ekran görüntüsü de gönder
            monitor_index: mss monitör indeksi (1 = birincil)
        """
        self.triggers = triggers or ["Error", "Exception", "FAILED", "Traceback", "FATAL"]
        self.callback = callback
        self.interval = max(1.0, float(interval))
        self.use_ocr = use_ocr and PYTESSERACT_AVAILABLE and PIL_AVAILABLE and MSS_AVAILABLE
        self.use_vision = use_vision and VISION_AVAILABLE
        self.capture_screenshot = capture_screenshot
        self.monitor_index = monitor_index

        self._thread: Optional[threading.Thread] = None
        self._stop_event = threading.Event()
        self._running = False
        self._mss_client = None

        if not self.use_ocr and not self.use_vision:
            print("[SCREEN] OCR ve Vision kullanılamıyor. Ekran izleme pasif.")
        else:
            print(f"[SCREEN] {len(self.triggers)} tetikleyici ile başlatıldı."
                  f" OCR={'✅' if self.use_ocr else '❌'}"
                  f" Vision={'✅' if self.use_vision else '❌'}")

    def start(self):
        """Arka plan izleme thread'ini başlatır."""
        if self._running:
            return
        if not self.use_ocr and not self.use_vision:
            print("[SCREEN] Kullanılabilir OCR/Vision motoru yok, başlatılamadı.")
            return

        self._stop_event.clear()
        self._thread = threading.Thread(target=self._watch_loop, daemon=True, name="ScreenWatcher")
        self._thread.start()
        self._running = True
        print("[SCREEN] İzleme başladı (event-driven).")

    def stop(self):
        """İzleme thread'ini durdurur."""
        if not self._running:
            return
        self._stop_event.set()
        if self._thread:
            self._thread.join(timeout=10)
        self._running = False
        if self._mss_client:
            try:
                self._mss_client.close()
            except Exception:
                pass
            self._mss_client = None
        print("[SCREEN] İzleme durdu.")

    @property
    def is_running(self) -> bool:
        return self._running

    def _watch_loop(self):
        """Ana izleme döngüsü (thread içinde çalışır)."""
        while not self._stop_event.is_set():
            try:
                text = self._capture_and_extract_text()
                if text:
                    matched = self._check_triggers(text)
                    if matched:
                        event = ScreenEvent(
                            timestamp=time.time(),
                            trigger_word=matched,
                            context=text[:300],
                            monitor_index=self.monitor_index,
                        )
                        if self.capture_screenshot:
                            event.screenshot_b64 = self._capture_screenshot_b64()

                        # Callback'i güvenli şekilde çağır
                        if self.callback:
                            self._invoke_callback(event)
            except Exception as e:
                print(f"[SCREEN] İzleme hatası: {e}")

            # Aralıklı bekle (stop event ile kesilebilir)
            self._stop_event.wait(self.interval)

    def _capture_and_extract_text(self) -> Optional[str]:
        """Ekran görüntüsü alır ve metin çıkarır."""
        if self.use_vision and VISION_AVAILABLE:
            return self._extract_with_vision()
        elif self.use_ocr:
            return self._extract_with_ocr()
        return None

    def _extract_with_ocr(self) -> Optional[str]:
        """Tesseract OCR ile ekrandaki metni çıkarır."""
        try:
            if self._mss_client is None:
                self._mss_client = mss.mss()

            screenshot = self._mss_client.grab(self._mss_client.monitors[self.monitor_index])
            img = Image.frombytes("RGB", screenshot.size, screenshot.bgra, "raw", "BGRX")

            # Performans için resize (OCR çok büyük resimlerde yavaş)
            if img.width > 1920:
                img.thumbnail((1920, 1080))

            text = pytesseract.image_to_string(img, lang="eng+tur")
            return text.strip() if text else None

        except Exception as e:
            print(f"[SCREEN OCR] Hata: {e}")
            return None

    def _extract_with_vision(self) -> Optional[str]:
        """Gemini Vision ile ekran analizi."""
        try:
            from backend.config import get_key

            gemini_key = get_key("gemini")
            if not gemini_key:
                return self._extract_with_ocr()  # OCR fallback

            if self._mss_client is None:
                self._mss_client = mss.mss()

            screenshot = self._mss_client.grab(self._mss_client.monitors[self.monitor_index])
            img = Image.frombytes("RGB", screenshot.size, screenshot.bgra, "raw", "BGRX")
            img.thumbnail((1024, 1024))

            genai.configure(api_key=gemini_key)
            model = genai.GenerativeModel("gemini-2.5-flash")

            # Prompt: sadece ekrandaki tüm metni çıkar
            prompt = (
                "List all text visible on this screen. "
                "If you see any error messages, stack traces, or warning dialogs, "
                "describe them in detail. Return only the text/diagnostic, no commentary."
            )

            response = model.generate_content([prompt, img])
            text = response.text.strip() if response.text else None
            return text

        except Exception as e:
            print(f"[SCREEN Vision] Hata: {e}")
            # Fallback to OCR
            return self._extract_with_ocr()

    def _check_triggers(self, text: str) -> Optional[str]:
        """Metin içinde tetikleyici kelime arar (case-insensitive)."""
        text_lower = text.lower()
        for trigger in self.triggers:
            if trigger.lower() in text_lower:
                return trigger
        return None

    def _capture_screenshot_b64(self) -> Optional[str]:
        """Anlık ekran görüntüsünü base64 PNG olarak döndürür."""
        try:
            import base64
            import io as _io

            if self._mss_client is None:
                self._mss_client = mss.mss()

            screenshot = self._mss_client.grab(self._mss_client.monitors[self.monitor_index])
            img = Image.frombytes("RGB", screenshot.size, screenshot.bgra, "raw", "BGRX")
            img.thumbnail((1280, 720))

            buf = _io.BytesIO()
            img.save(buf, format="PNG")
            return base64.b64encode(buf.getvalue()).decode()

        except Exception as e:
            print(f"[SCREEN] Screenshot b64 hatası: {e}")
            return None

    def _invoke_callback(self, event: ScreenEvent):
        """
        Callback'i çağırır. Async function ise event loop'ta,
        sync function ise thread'de çalıştırır.
        """
        try:
            if asyncio.iscoroutinefunction(self.callback):
                # Asenkron callback — ana event loop'ta çalıştır
                try:
                    loop = asyncio.get_event_loop()
                    if loop.is_running():
                        asyncio.run_coroutine_threadsafe(self.callback(event), loop)
                    else:
                        asyncio.run(self.callback(event))
                except RuntimeError:
                    # Loop yoksa yeni loop oluştur
                    asyncio.run(self.callback(event))
            elif callable(self.callback):
                self.callback(event)
        except Exception as e:
            print(f"[SCREEN] Callback hatası: {e}")


# ==========================================
# KOLAY BAŞLATMA / DURDURMA
# ==========================================
_global_watcher: Optional[ScreenWatcher] = None


def start_screen_monitor(
    triggers: list[str] = None,
    callback: Callable = None,
    interval: float = 5.0,
) -> ScreenWatcher:
    """
    Global ekran izleyiciyi başlatır (singleton pattern).
    Zaten çalışıyorsa durdurup yeniden başlatır.
    """
    global _global_watcher

    if _global_watcher is not None and _global_watcher.is_running:
        _global_watcher.stop()

    _global_watcher = ScreenWatcher(
        triggers=triggers,
        callback=callback,
        interval=interval,
    )
    _global_watcher.start()
    return _global_watcher


def stop_screen_monitor():
    """Global ekran izleyiciyi durdurur."""
    global _global_watcher
    if _global_watcher is not None:
        _global_watcher.stop()
        _global_watcher = None


def is_monitoring() -> bool:
    """Ekran izleyici çalışıyor mu?"""
    return _global_watcher is not None and _global_watcher.is_running


def get_screen_capabilities() -> dict:
    """Ekran izleme yeteneklerini döndürür."""
    return {
        "mss": MSS_AVAILABLE,
        "pil": PIL_AVAILABLE,
        "pytesseract": PYTESSERACT_AVAILABLE,
        "vision": VISION_AVAILABLE,
        "ocr_ready": MSS_AVAILABLE and PIL_AVAILABLE and PYTESSERACT_AVAILABLE,
        "vision_ready": MSS_AVAILABLE and PIL_AVAILABLE and VISION_AVAILABLE,
        "monitoring": is_monitoring(),
    }