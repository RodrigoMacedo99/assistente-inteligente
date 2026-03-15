from abc import ABC, abstractmethod

from aiadapter.core.entities.audiorequest import AudioRequest
from aiadapter.core.entities.audioresponse import AudioResponse


class AISTTProvider(ABC):
    """Contrato para provedores de Speech-to-Text (transcrição de áudio)."""

    @abstractmethod
    def transcribe(self, request: AudioRequest) -> AudioResponse:
        """
        Transcreve o áudio em request.audio_data para texto.
        Retorna AudioResponse com transcription preenchida.
        """
        pass

    @abstractmethod
    def is_available(self) -> bool:
        """Retorna True se o provider está configurado e acessível."""
        pass

    @abstractmethod
    def get_name(self) -> str:
        """Retorna o nome lógico do provider (ex: 'whisper_local')."""
        pass

    @abstractmethod
    def supported_formats(self) -> list[str]:
        """Retorna formatos de áudio suportados (ex: ['wav', 'mp3', 'ogg'])."""
        pass
