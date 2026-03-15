from dataclasses import dataclass, field
from typing import Optional


@dataclass
class AudioResponse:
    """
    Resposta padronizada para operações de áudio.

    STT (transcrição):
        transcription: texto transcrito do áudio
        language_detected: idioma detectado automaticamente
        confidence: confiança da transcrição (0.0 a 1.0)
        segments: lista de segmentos com timestamp [{start, end, text}]

    TTS (síntese de voz):
        audio_data: bytes do áudio gerado
        audio_format: formato do áudio gerado ("mp3", "wav", "ogg")
        duration_seconds: duração estimada do áudio

    Comuns:
        provider_name: nome do provider que gerou a resposta
        cost: custo estimado em USD
        fallback_chain: histórico de tentativas de fallback automático.
            Cada entrada: {"provider": str, "success": bool, "attempts": int, "error"?: str}
            ou {"provider": str, "skipped": True, "reason": "circuit_open"}
    """

    provider_name: str
    cost: float = 0.0

    # STT
    transcription: Optional[str] = None
    language_detected: Optional[str] = None
    confidence: float = 0.0
    segments: Optional[list] = None

    # TTS
    audio_data: Optional[bytes] = None
    audio_format: str = "mp3"
    duration_seconds: float = 0.0

    # Fallback metadata
    fallback_chain: list = field(default_factory=list)
