from dataclasses import dataclass


@dataclass
class AudioRequest:
    """
    Requisição de áudio para STT (Speech-to-Text) ou TTS (Text-to-Speech).

    Para STT:
        audio_data: bytes do arquivo de áudio (wav, mp3, ogg, webm)
        audio_format: formato do áudio ("wav", "mp3", "ogg", "webm")
        language: código ISO do idioma ("pt", "en", "auto")

    Para TTS:
        text: texto a ser sintetizado
        voice: nome da voz (ex: "pt-BR-AntonioNeural", "alloy")
        speed: velocidade da fala (0.5 = lenta, 1.0 = normal, 2.0 = rápida)
        audio_format_out: formato de saída desejado ("mp3", "wav", "ogg")

    Comuns:
        client_id: identificador do tenant para rate limiting
        preferred_provider: nome do provider preferido
    """

    # STT fields
    audio_data: bytes | None = None
    audio_format: str = "wav"
    language: str | None = None  # None = autodetect

    # TTS fields
    text: str | None = None
    voice: str | None = None
    speed: float = 1.0
    audio_format_out: str = "mp3"

    # Shared
    client_id: str | None = None
    preferred_provider: str | None = None

    def is_stt(self) -> bool:
        return self.audio_data is not None

    def is_tts(self) -> bool:
        return self.text is not None and self.text.strip() != ""
