"""
AudioService — orquestrador de TTS e STT com fallback automático.

Fallback automático com circuit breaker
---------------------------------------
Cada provider possui um ProviderHealth que monitora falhas consecutivas.

• Retry por provider: antes de passar para o próximo, tenta o provider atual
  até `max_retries` vezes (default: 1).
• Circuit breaker: após `circuit_breaker_threshold` falhas consecutivas o
  circuit abre e o provider é ignorado por `circuit_breaker_cooldown` segundos.
  Após o cooldown o circuit fecha automaticamente (half-open reset).
• Fallback chain: o AudioResponse inclui `fallback_chain` com o registro de
  cada provider tentado, quantas tentativas foram feitas e o motivo da falha.

Prioridade de providers (ordem padrão de preferência):
  TTS: local (pyttsx3) → gratuito (edge-tts) → pago barato (elevenlabs) → pago (openai-tts)
  STT: local (faster-whisper) → gratuito (groq-whisper) → pago (openai-whisper)
"""

import logging

from aiadapter.application.provider_health import ProviderHealth
from aiadapter.core.entities.audiorequest import AudioRequest
from aiadapter.core.entities.audioresponse import AudioResponse
from aiadapter.core.interfaces.stt_provider import AISTTProvider
from aiadapter.core.interfaces.tts_provider import AITTSProvider

logger = logging.getLogger("aiadapter.audio_service")

_DEFAULT_MAX_RETRIES = 1
_DEFAULT_CIRCUIT_THRESHOLD = 3  # falhas consecutivas para abrir o circuit
_DEFAULT_CIRCUIT_COOLDOWN = 60.0  # segundos que o circuit permanece aberto


class AudioService:
    """
    Camada de aplicação para TTS e STT com seleção inteligente de provider
    e fallback automático com circuit breaker.

    Parâmetros
    ----------
    tts_providers : list[AITTSProvider]
        Providers TTS em ordem de preferência (primeiro = maior prioridade).
    stt_providers : list[AISTTProvider]
        Providers STT em ordem de preferência.
    local_first : bool
        Reservado para uso futuro; não altera a ordem atual.
    max_retries : int
        Tentativas por provider antes de cair para o próximo (default: 1).
    circuit_breaker_threshold : int
        Falhas consecutivas para abrir o circuit de um provider (default: 3).
    circuit_breaker_cooldown : float
        Segundos que o circuit permanece aberto após abertura (default: 60).
    """

    def __init__(
        self,
        tts_providers: list[AITTSProvider] | None = None,
        stt_providers: list[AISTTProvider] | None = None,
        local_first: bool = True,
        max_retries: int = _DEFAULT_MAX_RETRIES,
        circuit_breaker_threshold: int = _DEFAULT_CIRCUIT_THRESHOLD,
        circuit_breaker_cooldown: float = _DEFAULT_CIRCUIT_COOLDOWN,
    ):
        self._tts_providers: list[AITTSProvider] = tts_providers or []
        self._stt_providers: list[AISTTProvider] = stt_providers or []
        self._local_first = local_first
        self._max_retries = max_retries
        self._circuit_threshold = circuit_breaker_threshold
        self._circuit_cooldown = circuit_breaker_cooldown

        # Saúde por provider (chave = get_name())
        self._health: dict[str, ProviderHealth] = {}
        for p in self._tts_providers + self._stt_providers:
            self._health[p.get_name()] = ProviderHealth(name=p.get_name())

    # ── TTS ──────────────────────────────────────────────────────────────────

    def speak(self, request: AudioRequest) -> AudioResponse:
        """
        Sintetiza voz com fallback automático entre providers TTS.

        Tenta cada provider disponível na ordem de preferência (respeitando
        circuit breakers abertos). Para cada provider, faz até `max_retries`
        tentativas antes de cair para o próximo.
        """
        if not request.text or not request.text.strip():
            raise ValueError("Texto não pode ser vazio para TTS")

        providers = self._get_available_tts(request.preferred_provider)
        if not providers:
            raise RuntimeError("Nenhum provider TTS disponível")

        fallback_chain: list[dict] = []
        last_error: Exception | None = None

        for provider in providers:
            name = provider.get_name()
            health = self._get_health(name)

            if health.is_open():
                logger.info(f"[FALLBACK] TTS '{name}' circuit aberto — pulando")
                fallback_chain.append({"provider": name, "skipped": True, "reason": "circuit_open"})
                continue

            for attempt in range(1, self._max_retries + 1):
                try:
                    logger.info(
                        f"[AUDIO-SVC] TTS via '{name}' (tentativa {attempt}/{self._max_retries})"
                    )
                    response = provider.speak(request)
                    health.record_success()
                    fallback_chain.append({"provider": name, "attempt": attempt, "success": True})
                    response.fallback_chain = fallback_chain
                    return response
                except Exception as e:
                    logger.warning(f"[FALLBACK] TTS '{name}' tentativa {attempt} falhou: {e}")
                    last_error = e
                    if attempt == self._max_retries:
                        health.record_failure(self._circuit_cooldown, self._circuit_threshold)
                        fallback_chain.append(
                            {
                                "provider": name,
                                "attempts": attempt,
                                "success": False,
                                "error": str(e),
                            }
                        )

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
        Transcreve áudio com fallback automático entre providers STT.

        Tenta cada provider disponível na ordem de preferência (respeitando
        circuit breakers abertos). Para cada provider, faz até `max_retries`
        tentativas antes de cair para o próximo.
        """
        if not request.audio_data:
            raise ValueError("audio_data não fornecido para STT")

        providers = self._get_available_stt(request.preferred_provider)
        if not providers:
            raise RuntimeError("Nenhum provider STT disponível")

        fallback_chain: list[dict] = []
        last_error: Exception | None = None

        for provider in providers:
            name = provider.get_name()
            health = self._get_health(name)

            if health.is_open():
                logger.info(f"[FALLBACK] STT '{name}' circuit aberto — pulando")
                fallback_chain.append({"provider": name, "skipped": True, "reason": "circuit_open"})
                continue

            for attempt in range(1, self._max_retries + 1):
                try:
                    logger.info(
                        f"[AUDIO-SVC] STT via '{name}' (tentativa {attempt}/{self._max_retries})"
                    )
                    response = provider.transcribe(request)
                    health.record_success()
                    fallback_chain.append({"provider": name, "attempt": attempt, "success": True})
                    response.fallback_chain = fallback_chain
                    return response
                except Exception as e:
                    logger.warning(f"[FALLBACK] STT '{name}' tentativa {attempt} falhou: {e}")
                    last_error = e
                    if attempt == self._max_retries:
                        health.record_failure(self._circuit_cooldown, self._circuit_threshold)
                        fallback_chain.append(
                            {
                                "provider": name,
                                "attempts": attempt,
                                "success": False,
                                "error": str(e),
                            }
                        )

        raise RuntimeError(f"Todos os providers STT falharam. Último erro: {last_error}")

    # ── Provider selection ────────────────────────────────────────────────────

    def _get_available_tts(self, preferred: str | None = None) -> list[AITTSProvider]:
        available = [p for p in self._tts_providers if p.is_available()]
        if preferred:
            preferred_providers = [p for p in available if p.get_name() == preferred]
            rest = [p for p in available if p.get_name() != preferred]
            return preferred_providers + rest
        return available

    def _get_available_stt(self, preferred: str | None = None) -> list[AISTTProvider]:
        available = [p for p in self._stt_providers if p.is_available()]
        if preferred:
            preferred_providers = [p for p in available if p.get_name() == preferred]
            rest = [p for p in available if p.get_name() != preferred]
            return preferred_providers + rest
        return available

    def _get_health(self, name: str) -> ProviderHealth:
        if name not in self._health:
            self._health[name] = ProviderHealth(name=name)
        return self._health[name]

    # ── Status ───────────────────────────────────────────────────────────────

    def status(self) -> dict:
        """Retorna status de disponibilidade e saúde de todos os providers."""
        return {
            "tts": [
                {
                    "name": p.get_name(),
                    "available": p.is_available(),
                    **self._get_health(p.get_name()).to_dict(),
                }
                for p in self._tts_providers
            ],
            "stt": [
                {
                    "name": p.get_name(),
                    "available": p.is_available(),
                    **self._get_health(p.get_name()).to_dict(),
                }
                for p in self._stt_providers
            ],
        }
