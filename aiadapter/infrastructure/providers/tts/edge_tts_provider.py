"""
TTS REMOTO GRATUITO — Microsoft Edge TTS (edge-tts).

Usa as vozes neurais do Microsoft Edge/Azure gratuitamente,
sem necessidade de conta ou chave de API.
Qualidade excelente — as mesmas vozes usadas no Windows 11.

Requer conexão com internet.

Vozes pt-BR disponíveis:
  pt-BR-AntonioNeural  (masculina)
  pt-BR-FranciscaNeural (feminina) ← padrão
  pt-BR-ThalitaNeural   (feminina, conversacional)

Vozes pt-PT:
  pt-PT-DuarteNeural    (masculina)
  pt-PT-RaquelNeural    (feminina)

Instalação: pip install edge-tts
"""
import asyncio
import logging
from typing import Optional

from aiadapter.core.interfaces.tts_provider import AITTSProvider
from aiadapter.core.entities.audiorequest import AudioRequest
from aiadapter.core.entities.audioresponse import AudioResponse

logger = logging.getLogger("aiadapter.tts.edge")

DEFAULT_VOICE_PT = "pt-BR-FranciscaNeural"
DEFAULT_VOICE_EN = "en-US-JennyNeural"

VOICES_PT = [
    {"name": "pt-BR-AntonioNeural",   "gender": "male",   "language": "pt-BR", "style": "general"},
    {"name": "pt-BR-FranciscaNeural", "gender": "female", "language": "pt-BR", "style": "general"},
    {"name": "pt-BR-ThalitaNeural",   "gender": "female", "language": "pt-BR", "style": "conversation"},
    {"name": "pt-PT-DuarteNeural",    "gender": "male",   "language": "pt-PT", "style": "general"},
    {"name": "pt-PT-RaquelNeural",    "gender": "female", "language": "pt-PT", "style": "general"},
]

VOICES_EN = [
    {"name": "en-US-JennyNeural",  "gender": "female", "language": "en-US", "style": "general"},
    {"name": "en-US-GuyNeural",    "gender": "male",   "language": "en-US", "style": "general"},
    {"name": "en-GB-SoniaNeural",  "gender": "female", "language": "en-GB", "style": "general"},
]


class EdgeTTSProvider(AITTSProvider):
    """
    Text-to-Speech usando Microsoft Edge TTS — gratuito, alta qualidade neural.
    Usa asyncio internamente; a interface pública é síncrona.
    """

    def __init__(self, default_voice: Optional[str] = None):
        self._default_voice = default_voice or DEFAULT_VOICE_PT
        self._available = self._check_available()

    def _check_available(self) -> bool:
        try:
            import edge_tts  # noqa: F401
            return True
        except ImportError:
            logger.warning("[EDGE-TTS] edge-tts não instalado. Execute: pip install edge-tts")
            return False

    def speak(self, request: AudioRequest) -> AudioResponse:
        if not self.is_available():
            raise RuntimeError("EdgeTTS indisponível: execute 'pip install edge-tts'")

        if not request.text or not request.text.strip():
            raise ValueError("Texto não pode ser vazio")

        voice = request.voice or self._default_voice
        speed = self._speed_to_rate(request.speed)

        audio_bytes = asyncio.run(self._synthesize_async(request.text, voice, speed))

        # Estimativa de duração: ~140 palavras/min para pt-BR
        words = len(request.text.split())
        duration = words / 140.0 * 60.0

        logger.info(f"[EDGE-TTS] '{voice}': {len(request.text)} chars → {len(audio_bytes)} bytes")

        return AudioResponse(
            provider_name="edge_tts",
            audio_data=audio_bytes,
            audio_format="mp3",
            duration_seconds=round(duration, 2),
            cost=0.0,
        )

    async def _synthesize_async(self, text: str, voice: str, rate: str) -> bytes:
        import edge_tts

        communicate = edge_tts.Communicate(text, voice=voice, rate=rate)
        chunks = []
        async for chunk in communicate.stream():
            if chunk["type"] == "audio":
                chunks.append(chunk["data"])
        return b"".join(chunks)

    def _speed_to_rate(self, speed: float) -> str:
        """Converte speed float para formato edge-tts (+N% ou -N%)."""
        if speed == 1.0:
            return "+0%"
        pct = int((speed - 1.0) * 100)
        return f"+{pct}%" if pct >= 0 else f"{pct}%"

    def is_available(self) -> bool:
        return self._available

    def get_name(self) -> str:
        return "edge_tts"

    def list_voices(self, language: str = "pt") -> list[dict]:
        lang_lower = language.lower()
        all_voices = VOICES_PT + VOICES_EN
        return [v for v in all_voices if v["language"].lower().startswith(lang_lower)]

    async def list_voices_async(self) -> list[dict]:
        """Lista TODAS as vozes disponíveis diretamente da API da Microsoft."""
        try:
            import edge_tts
            voices = await edge_tts.list_voices()
            return [
                {
                    "name": v["ShortName"],
                    "gender": v["Gender"].lower(),
                    "language": v["Locale"],
                    "style": "neural",
                }
                for v in voices
            ]
        except Exception:
            return self.list_voices()
