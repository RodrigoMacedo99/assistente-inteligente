"""
STT REMOTO — Groq Whisper API (GRATUITO).

Groq oferece transcrição com whisper-large-v3 gratuitamente como parte do
free tier (mesma quota de 14.400 req/dia do LLM).
Latência extremamente baixa (~0.3s para áudios curtos).

Instalação: pip install groq
Cadastro gratuito: https://console.groq.com
"""
import logging
import io
from typing import Optional

from aiadapter.core.interfaces.stt_provider import AISTTProvider
from aiadapter.core.entities.audiorequest import AudioRequest
from aiadapter.core.entities.audioresponse import AudioResponse

logger = logging.getLogger("aiadapter.stt.groq")

GROQ_STT_MODEL = "whisper-large-v3"
GROQ_STT_TURBO = "whisper-large-v3-turbo"  # mais rápido, levemente menos preciso


class GroqSTTProvider(AISTTProvider):
    """
    Transcrição via Groq API — usa whisper-large-v3 (melhor qualidade)
    ou whisper-large-v3-turbo (mais rápido) gratuitamente.
    """

    def __init__(self, api_key: str, use_turbo: bool = False):
        self._api_key = api_key
        self._model = GROQ_STT_TURBO if use_turbo else GROQ_STT_MODEL
        self._client = None
        self._init_client()

    def _init_client(self):
        try:
            from groq import Groq
            self._client = Groq(api_key=self._api_key)
        except ImportError:
            logger.warning("[GROQ-STT] SDK Groq não instalado. Execute: pip install groq")

    def transcribe(self, request: AudioRequest) -> AudioResponse:
        if not self.is_available():
            raise RuntimeError("GroqSTT indisponível: SDK não instalado ou chave inválida")

        if not request.audio_data:
            raise ValueError("audio_data não fornecido para transcrição")

        filename = f"audio.{request.audio_format}"
        language = request.language if request.language not in (None, "auto") else None

        transcription = self._client.audio.transcriptions.create(
            file=(filename, request.audio_data),
            model=self._model,
            language=language,
            response_format="verbose_json",
            temperature=0.0,
        )

        segments = []
        if hasattr(transcription, "segments") and transcription.segments:
            segments = [
                {
                    "start": round(s.start, 2),
                    "end": round(s.end, 2),
                    "text": s.text.strip(),
                }
                for s in transcription.segments
            ]

        logger.info(f"[GROQ-STT] Transcrição concluída: {len(transcription.text)} chars")

        return AudioResponse(
            provider_name="groq_stt",
            transcription=transcription.text.strip(),
            language_detected=getattr(transcription, "language", None),
            confidence=1.0,  # Groq não expõe confiança
            segments=segments,
            cost=0.0,  # Gratuito no free tier
        )

    def is_available(self) -> bool:
        return self._client is not None and bool(self._api_key)

    def get_name(self) -> str:
        return "groq_stt"

    def supported_formats(self) -> list[str]:
        return ["mp3", "mp4", "mpeg", "mpga", "m4a", "wav", "webm", "ogg", "flac"]
