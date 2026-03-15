"""
TTS REMOTO — OpenAI Text-to-Speech.

Vozes de alta qualidade neural com 6 opções de voz.
Custo: $15 por 1M caracteres (tts-1) ou $30 por 1M (tts-1-hd).

Vozes disponíveis:
  alloy   — neutro, informativo
  echo    — masculino, claro
  fable   — britânico, expressivo
  onyx    — masculino profundo, autoritário
  nova    — feminino, rápido
  shimmer — feminino suave, empático

Instalação: pip install openai
"""

import logging

from aiadapter.core.entities.audiorequest import AudioRequest
from aiadapter.core.entities.audioresponse import AudioResponse
from aiadapter.core.interfaces.tts_provider import AITTSProvider

logger = logging.getLogger("aiadapter.tts.openai")

OPENAI_VOICES = [
    {"name": "alloy", "gender": "neutral", "language": "multilingual", "style": "informative"},
    {"name": "echo", "gender": "male", "language": "multilingual", "style": "clear"},
    {"name": "fable", "gender": "male", "language": "multilingual", "style": "expressive"},
    {"name": "onyx", "gender": "male", "language": "multilingual", "style": "authoritative"},
    {"name": "nova", "gender": "female", "language": "multilingual", "style": "quick"},
    {"name": "shimmer", "gender": "female", "language": "multilingual", "style": "soft"},
]

COST_PER_1M_CHARS = {"tts-1": 15.0, "tts-1-hd": 30.0}
DEFAULT_MODEL = "tts-1"
DEFAULT_VOICE = "nova"


class OpenAITTSProvider(AITTSProvider):
    """Síntese de voz via OpenAI TTS API — alta qualidade neural."""

    def __init__(self, api_key: str, model: str = DEFAULT_MODEL):
        self._api_key = api_key
        self._model = model
        self._client = None
        self._init_client()

    def _init_client(self):
        try:
            from openai import OpenAI

            self._client = OpenAI(api_key=self._api_key)
        except ImportError:
            logger.warning("[OPENAI-TTS] openai SDK não instalado.")

    def speak(self, request: AudioRequest) -> AudioResponse:
        if not self.is_available():
            raise RuntimeError("OpenAITTS indisponível")

        if not request.text or not request.text.strip():
            raise ValueError("Texto não pode ser vazio")

        voice = request.voice or DEFAULT_VOICE
        fmt = (
            request.audio_format_out
            if request.audio_format_out in ("mp3", "opus", "aac", "flac")
            else "mp3"
        )
        speed = max(0.25, min(4.0, request.speed))

        response = self._client.audio.speech.create(
            model=self._model,
            voice=voice,
            input=request.text,
            response_format=fmt,
            speed=speed,
        )

        audio_bytes = response.content
        cost = (len(request.text) / 1_000_000) * COST_PER_1M_CHARS.get(self._model, 15.0)

        logger.info(f"[OPENAI-TTS] '{voice}': {len(request.text)} chars → {len(audio_bytes)} bytes")

        return AudioResponse(
            provider_name="openai_tts",
            audio_data=audio_bytes,
            audio_format=fmt,
            cost=round(cost, 6),
        )

    def is_available(self) -> bool:
        return self._client is not None and bool(self._api_key)

    def get_name(self) -> str:
        return "openai_tts"

    def list_voices(self, language: str = "pt") -> list[dict]:
        # OpenAI TTS é multilingual, todas as vozes funcionam em pt-BR
        return OPENAI_VOICES
