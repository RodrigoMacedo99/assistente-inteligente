"""
AudioService — orquestrador de TTS e STT.

Lógica de prioridade:
  TTS: local (pyttsx3) → gratuito (edge-tts) → pago barato (elevenlabs free) → pago (openai-tts)
  STT: local (faster-whisper) → gratuito (groq-whisper) → pago (openai-whisper)

O serviço seleciona automaticamente o melhor provider disponível com base
em preferências (local_first, free_first) e no estado de disponibilidade de
cada provider (is_available()).
"""
import logging
from typing import Optional

from aiadapter.core.entities.audiorequest import AudioRequest
from aiadapter.core.entities.audioresponse import AudioResponse
from aiadapter.core.interfaces.tts_provider import AITTSProvider
from aiadapter.core.interfaces.stt_provider import AISTTProvider

logger = logging.getLogger("aiadapter.audio_service")


class AudioService:
    """
    Camada de aplicação para TTS e STT com seleção inteligente de provider.

    Parâmetros
    ----------
    tts_providers : list[AITTSProvider]
        Lista de providers TTS em ordem de preferência (primeiro = maior prioridade).
    stt_providers : list[AISTTProvider]
        Lista de providers STT em ordem de preferência.
    local_first : bool
        Se True, providers locais (is_local=True) são movidos para o topo.
    """

    def __init__(
        self,
        tts_providers: Optional[list[AITTSProvider]] = None,
        stt_providers: Optional[list[AISTTProvider]] = None,
        local_first: bool = True,
    ):
        self._tts_providers: list[AITTSProvider] = tts_providers or []
        self._stt_providers: list[AISTTProvider] = stt_providers or []
        self._local_first = local_first

    # ── TTS ──────────────────────────────────────────────────────────────────

    def speak(self, request: AudioRequest) -> AudioResponse:
        """
        Sintetiza voz a partir do texto no request.
        Seleciona automaticamente o melhor provider disponível.
        """
        if not request.text or not request.text.strip():
            raise ValueError("Texto não pode ser vazio para TTS")

        providers = self._get_available_tts(request.preferred_provider)
        if not providers:
            raise RuntimeError("Nenhum provider TTS disponível")

        last_error: Optional[Exception] = None
        for provider in providers:
            try:
                logger.info(f"[AUDIO-SVC] TTS via '{provider.get_name()}'")
                return provider.speak(request)
            except Exception as e:
                logger.warning(f"[AUDIO-SVC] TTS '{provider.get_name()}' falhou: {e}")
                last_error = e
                continue

        raise RuntimeError(f"Todos os providers TTS falharam. Último erro: {last_error}")

    def list_tts_voices(self, language: str = "pt") -> list[dict]:
        """Retorna vozes disponíveis de todos os providers TTS ativos."""
        voices = []
        for provider in self._tts_providers:
            if provider.is_available():
                for voice in provider.list_voices(language):
                    voices.append({**voice, "provider": provider.get_name()})
        return voices

    # ── STT ──────────────────────────────────────────────────────────────────

    def transcribe(self, request: AudioRequest) -> AudioResponse:
        """
        Transcreve áudio para texto.
        Seleciona automaticamente o melhor provider disponível.
        """
        if not request.audio_data:
            raise ValueError("audio_data não fornecido para STT")

        providers = self._get_available_stt(request.preferred_provider)
        if not providers:
            raise RuntimeError("Nenhum provider STT disponível")

        last_error: Optional[Exception] = None
        for provider in providers:
            try:
                logger.info(f"[AUDIO-SVC] STT via '{provider.get_name()}'")
                return provider.transcribe(request)
            except Exception as e:
                logger.warning(f"[AUDIO-SVC] STT '{provider.get_name()}' falhou: {e}")
                last_error = e
                continue

        raise RuntimeError(f"Todos os providers STT falharam. Último erro: {last_error}")

    # ── Provider selection ────────────────────────────────────────────────────

    def _get_available_tts(self, preferred: Optional[str] = None) -> list[AITTSProvider]:
        available = [p for p in self._tts_providers if p.is_available()]

        if preferred:
            preferred_providers = [p for p in available if p.get_name() == preferred]
            rest = [p for p in available if p.get_name() != preferred]
            return preferred_providers + rest

        return available

    def _get_available_stt(self, preferred: Optional[str] = None) -> list[AISTTProvider]:
        available = [p for p in self._stt_providers if p.is_available()]

        if preferred:
            preferred_providers = [p for p in available if p.get_name() == preferred]
            rest = [p for p in available if p.get_name() != preferred]
            return preferred_providers + rest

        return available

    # ── Status ───────────────────────────────────────────────────────────────

    def status(self) -> dict:
        """Retorna status de disponibilidade de todos os providers configurados."""
        return {
            "tts": [
                {"name": p.get_name(), "available": p.is_available()}
                for p in self._tts_providers
            ],
            "stt": [
                {"name": p.get_name(), "available": p.is_available()}
                for p in self._stt_providers
            ],
        }
