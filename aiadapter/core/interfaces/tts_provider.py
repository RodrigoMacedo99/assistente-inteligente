from abc import ABC, abstractmethod
from aiadapter.core.entities.audiorequest import AudioRequest
from aiadapter.core.entities.audioresponse import AudioResponse


class AITTSProvider(ABC):
    """Contrato para provedores de Text-to-Speech (síntese de voz)."""

    @abstractmethod
    def speak(self, request: AudioRequest) -> AudioResponse:
        """
        Sintetiza request.text em áudio.
        Retorna AudioResponse com audio_data preenchido.
        """
        pass

    @abstractmethod
    def is_available(self) -> bool:
        """Retorna True se o provider está configurado e acessível."""
        pass

    @abstractmethod
    def get_name(self) -> str:
        """Retorna o nome lógico do provider (ex: 'edge_tts')."""
        pass

    @abstractmethod
    def list_voices(self, language: str = "pt") -> list[dict]:
        """
        Lista vozes disponíveis filtradas por idioma.
        Retorna lista de dicts: [{name, gender, language, preview}]
        """
        pass
