"""
TTS LOCAL — pyttsx3 (100% offline, zero dependências de rede).

Usa o motor de síntese nativo do sistema operacional:
  Linux   → espeak  (sudo apt-get install espeak)
  Windows → SAPI5   (já incluso no Windows)
  macOS   → nsss    (já incluso no macOS)

Qualidade básica, mas funciona em qualquer ambiente sem internet.
Ideal para Raspberry Pi sem conexão ou para fallback local.

Instalação:
  pip install pyttsx3
  sudo apt-get install espeak espeak-ng  # Linux
"""
import logging
import os
import tempfile

from aiadapter.core.entities.audiorequest import AudioRequest
from aiadapter.core.entities.audioresponse import AudioResponse
from aiadapter.core.interfaces.tts_provider import AITTSProvider

logger = logging.getLogger("aiadapter.tts.pyttsx3")

# Vozes pt-BR conhecidas no espeak
PT_BR_VOICES_ESPEAK = ["pt-br", "pt+f3", "pt"]


class Pyttsx3TTSProvider(AITTSProvider):
    """
    Síntese de voz 100% local usando motor nativo do SO.
    Gera arquivo WAV em diretório temporário e retorna os bytes.
    """

    def __init__(self, rate: int = 150, volume: float = 1.0, voice_id: str | None = None):
        self._rate = rate
        self._volume = volume
        self._voice_id = voice_id
        self._engine = None
        self._available = False
        self._init_engine()

    def _init_engine(self):
        try:
            import pyttsx3
            self._engine = pyttsx3.init()
            self._engine.setProperty("rate", self._rate)
            self._engine.setProperty("volume", self._volume)

            if self._voice_id:
                self._engine.setProperty("voice", self._voice_id)
            else:
                # Tenta selecionar uma voz pt-BR se disponível
                voices = self._engine.getProperty("voices")
                for v in voices or []:
                    vid = (v.id or "").lower()
                    if any(pt in vid for pt in PT_BR_VOICES_ESPEAK):
                        self._engine.setProperty("voice", v.id)
                        logger.info(f"[PYTTSX3] Voz pt-BR selecionada: {v.id}")
                        break

            self._available = True
            logger.info("[PYTTSX3] Motor inicializado com sucesso.")
        except ImportError:
            logger.warning("[PYTTSX3] pyttsx3 não instalado. Execute: pip install pyttsx3")
        except Exception as e:
            logger.warning(f"[PYTTSX3] Falha na inicialização: {e}")

    def speak(self, request: AudioRequest) -> AudioResponse:
        if not self.is_available():
            raise RuntimeError("Pyttsx3 indisponível: motor não inicializado")

        if not request.text or not request.text.strip():
            raise ValueError("Texto não pode ser vazio")

        with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as tmp:
            tmp_path = tmp.name

        try:
            self._engine.save_to_file(request.text, tmp_path)
            self._engine.runAndWait()

            with open(tmp_path, "rb") as f:
                audio_bytes = f.read()

            # Estimativa de duração: ~150 palavras/min com taxa padrão
            words = len(request.text.split())
            duration = (words / (self._rate / 60.0))

            logger.info(f"[PYTTSX3] Síntese: {len(request.text)} chars → {len(audio_bytes)} bytes")

            return AudioResponse(
                provider_name="pyttsx3",
                audio_data=audio_bytes,
                audio_format="wav",
                duration_seconds=round(duration, 2),
                cost=0.0,
            )
        finally:
            if os.path.exists(tmp_path):
                os.unlink(tmp_path)

    def is_available(self) -> bool:
        return self._available and self._engine is not None

    def get_name(self) -> str:
        return "pyttsx3"

    def list_voices(self, language: str = "pt") -> list[dict]:
        if not self.is_available():
            return []
        voices = self._engine.getProperty("voices") or []
        result = []
        for v in voices:
            vid = (v.id or "").lower()
            if language.lower() in vid:
                result.append({
                    "name": v.name or v.id,
                    "id": v.id,
                    "gender": "unknown",
                    "language": language,
                })
        return result
