"""
TTS REMOTO — ElevenLabs Text-to-Speech.

Tier gratuito: 10.000 caracteres/mês.
Qualidade excepcional — vozes ultra-realistas com clonagem de voz.
Custo pago: $0.30/1k chars (Starter) a $0.18/1k chars (Creator+).

Vozes padrão notáveis:
  Rachel     — feminina, americana, narrativa
  Domi       — feminina, americana, estilo forte
  Bella      — feminina, americana, suave
  Antoni     — masculina, americana, bem elaborada
  Elli       — feminina, americana, emocional
  Josh       — masculina, americana, jovem
  Arnold     — masculina, americana, narrador
  Adam       — masculina, americana, profundo
  Sam        — masculina, americana, rápida

Instalação: pip install elevenlabs
"""
import logging

from aiadapter.core.entities.audiorequest import AudioRequest
from aiadapter.core.entities.audioresponse import AudioResponse
from aiadapter.core.interfaces.tts_provider import AITTSProvider

logger = logging.getLogger("aiadapter.tts.elevenlabs")

DEFAULT_VOICE_ID = "21m00Tcm4TlvDq8ikWAM"  # Rachel
DEFAULT_MODEL_ID = "eleven_multilingual_v2"

# Vozes pré-configuradas da ElevenLabs com suporte multilingual
ELEVENLABS_VOICES = [
    {"name": "Rachel",  "id": "21m00Tcm4TlvDq8ikWAM", "gender": "female", "language": "multilingual", "style": "narrative"},
    {"name": "Domi",    "id": "AZnzlk1XvdvUeBnXmlld", "gender": "female", "language": "multilingual", "style": "strong"},
    {"name": "Bella",   "id": "EXAVITQu4vr4xnSDxMaL", "gender": "female", "language": "multilingual", "style": "soft"},
    {"name": "Antoni",  "id": "ErXwobaYiN019PkySvjV", "gender": "male",   "language": "multilingual", "style": "well-rounded"},
    {"name": "Elli",    "id": "MF3mGyEYCl7XYWbV9V6O", "gender": "female", "language": "multilingual", "style": "emotional"},
    {"name": "Josh",    "id": "TxGEqnHWrfWFTfGW9XjX", "gender": "male",   "language": "multilingual", "style": "young"},
    {"name": "Arnold",  "id": "VR6AewLTigWG4xSOukaG", "gender": "male",   "language": "multilingual", "style": "crisp"},
    {"name": "Adam",    "id": "pNInz6obpgDQGcFmaJgB", "gender": "male",   "language": "multilingual", "style": "deep"},
    {"name": "Sam",     "id": "yoZ06aMxZJJ28mfd3POQ", "gender": "male",   "language": "multilingual", "style": "raspy"},
]

# Custo aproximado (tier Creator+): $0.18 por 1k chars
COST_PER_1K_CHARS = 0.18


class ElevenLabsTTSProvider(AITTSProvider):
    """
    Síntese de voz via ElevenLabs API — qualidade ultra-realista.
    Tier gratuito: 10.000 chars/mês. Suporte a pt-BR com eleven_multilingual_v2.
    """

    def __init__(
        self,
        api_key: str,
        default_voice_id: str | None = None,
        model_id: str = DEFAULT_MODEL_ID,
    ):
        self._api_key = api_key
        self._default_voice_id = default_voice_id or DEFAULT_VOICE_ID
        self._model_id = model_id
        self._client = None
        self._init_client()

    def _init_client(self):
        try:
            from elevenlabs.client import ElevenLabs
            self._client = ElevenLabs(api_key=self._api_key)
        except ImportError:
            logger.warning("[ELEVENLABS] elevenlabs SDK não instalado. Execute: pip install elevenlabs")

    def speak(self, request: AudioRequest) -> AudioResponse:
        if not self.is_available():
            raise RuntimeError("ElevenLabsTTS indisponível: execute 'pip install elevenlabs'")

        if not request.text or not request.text.strip():
            raise ValueError("Texto não pode ser vazio")

        voice_id = request.voice or self._default_voice_id

        audio_bytes = self._synthesize(request.text, voice_id)

        cost = (len(request.text) / 1000.0) * COST_PER_1K_CHARS

        logger.info(f"[ELEVENLABS] '{voice_id}': {len(request.text)} chars → {len(audio_bytes)} bytes")

        return AudioResponse(
            provider_name="elevenlabs_tts",
            audio_data=audio_bytes,
            audio_format="mp3",
            cost=round(cost, 6),
        )

    def _synthesize(self, text: str, voice_id: str) -> bytes:
        from elevenlabs import VoiceSettings

        audio_generator = self._client.text_to_speech.convert(
            voice_id=voice_id,
            text=text,
            model_id=self._model_id,
            voice_settings=VoiceSettings(
                stability=0.5,
                similarity_boost=0.75,
                style=0.0,
                use_speaker_boost=True,
            ),
            output_format="mp3_44100_128",
        )
        return b"".join(audio_generator)

    def is_available(self) -> bool:
        return self._client is not None and bool(self._api_key)

    def get_name(self) -> str:
        return "elevenlabs_tts"

    def list_voices(self, language: str = "pt") -> list[dict]:
        # ElevenLabs eleven_multilingual_v2 funciona com qualquer idioma
        return ELEVENLABS_VOICES
