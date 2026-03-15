"""
STT REMOTO — OpenAI Whisper API.

Usa whisper-1 da OpenAI. Pago mas de alta qualidade.
Custo: $0.006 por minuto de áudio.

Instalação: pip install openai
"""
import logging

from aiadapter.core.entities.audiorequest import AudioRequest
from aiadapter.core.entities.audioresponse import AudioResponse
from aiadapter.core.interfaces.stt_provider import AISTTProvider

logger = logging.getLogger("aiadapter.stt.openai")

OPENAI_STT_MODEL = "whisper-1"
COST_PER_MINUTE = 0.006


class OpenAISTTProvider(AISTTProvider):
    """Transcrição via OpenAI Whisper API (whisper-1)."""

    def __init__(self, api_key: str):
        self._api_key = api_key
        self._client = None
        self._init_client()

    def _init_client(self):
        try:
            from openai import OpenAI
            self._client = OpenAI(api_key=self._api_key)
        except ImportError:
            logger.warning("[OPENAI-STT] openai SDK não instalado.")

    def transcribe(self, request: AudioRequest) -> AudioResponse:
        if not self.is_available():
            raise RuntimeError("OpenAISTT indisponível")

        if not request.audio_data:
            raise ValueError("audio_data não fornecido")

        filename = f"audio.{request.audio_format}"
        language = request.language if request.language not in (None, "auto") else None

        transcription = self._client.audio.transcriptions.create(
            model=OPENAI_STT_MODEL,
            file=(filename, request.audio_data),
            language=language,
            response_format="verbose_json",
            timestamp_granularities=["segment"],
        )

        segments = []
        if hasattr(transcription, "segments") and transcription.segments:
            segments = [
                {"start": round(s.start, 2), "end": round(s.end, 2), "text": s.text.strip()}
                for s in transcription.segments
            ]

        duration = getattr(transcription, "duration", 0.0) or 0.0
        cost = (duration / 60.0) * COST_PER_MINUTE

        logger.info(f"[OPENAI-STT] Transcrição: {len(transcription.text)} chars, {duration:.1f}s")

        return AudioResponse(
            provider_name="openai_stt",
            transcription=transcription.text.strip(),
            language_detected=getattr(transcription, "language", None),
            confidence=1.0,
            segments=segments,
            cost=round(cost, 6),
        )

    def is_available(self) -> bool:
        return self._client is not None and bool(self._api_key)

    def get_name(self) -> str:
        return "openai_stt"

    def supported_formats(self) -> list[str]:
        return ["mp3", "mp4", "mpeg", "mpga", "m4a", "wav", "webm"]
