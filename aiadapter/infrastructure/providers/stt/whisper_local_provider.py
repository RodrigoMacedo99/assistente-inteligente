"""
STT LOCAL — Whisper via faster-whisper (CPU/GPU).

Funciona completamente offline. Ideal para Raspberry Pi.
Modelos disponíveis por tamanho/qualidade:
  tiny   (~39M params) — mínimo de RAM, ótimo para Pi Zero/3
  base   (~74M params) — bom equilíbrio para Pi 4
  small  (~244M params) — qualidade melhor, Pi 4 com 4GB+
  medium (~769M params) — alta qualidade, requer hardware mais robusto
  large  (~1.5B params) — máxima qualidade, requer GPU ou servidor

Instalação:
  pip install faster-whisper
  # Linux (para suporte a áudio com ffmpeg):
  sudo apt-get install ffmpeg
"""

import logging
import os
import tempfile

from aiadapter.core.entities.audiorequest import AudioRequest
from aiadapter.core.entities.audioresponse import AudioResponse
from aiadapter.core.interfaces.stt_provider import AISTTProvider

logger = logging.getLogger("aiadapter.stt.whisper_local")

# Modelo padrão — tiny é o mais leve, funciona bem na Raspberry Pi
DEFAULT_MODEL = os.getenv("WHISPER_MODEL", "base")


class WhisperLocalProvider(AISTTProvider):
    """
    Transcrição offline usando faster-whisper (CTranslate2).
    Carrega o modelo uma vez e reutiliza para todas as transcrições.
    Suporta CPU (int8 quantizado) e GPU (float16).
    """

    def __init__(self, model_size: str = DEFAULT_MODEL, device: str = "auto"):
        self._model_size = model_size
        self._device = device
        self._model = None
        self._load_error: str | None = None
        self._try_load()

    def _try_load(self):
        try:
            from faster_whisper import WhisperModel

            # auto: usa CUDA se disponível, senão CPU
            device = "cuda" if self._device == "auto" else self._device
            compute_type = "float16" if device == "cuda" else "int8"

            logger.info(f"[WHISPER] Carregando modelo '{self._model_size}' em {device}...")
            self._model = WhisperModel(
                self._model_size,
                device=device,
                compute_type=compute_type,
            )
            logger.info(f"[WHISPER] Modelo '{self._model_size}' carregado.")
        except ImportError:
            self._load_error = "faster-whisper não instalado. Execute: pip install faster-whisper"
            logger.warning(f"[WHISPER] {self._load_error}")
        except Exception as e:
            self._load_error = str(e)
            logger.error(f"[WHISPER] Falha ao carregar modelo: {e}")

    def transcribe(self, request: AudioRequest) -> AudioResponse:
        if not self.is_available():
            raise RuntimeError(f"WhisperLocal indisponível: {self._load_error}")

        if not request.audio_data:
            raise ValueError("audio_data não fornecido para transcrição")

        # Salva bytes em arquivo temporário (faster-whisper lê de arquivo)
        suffix = f".{request.audio_format}"
        with tempfile.NamedTemporaryFile(suffix=suffix, delete=False) as tmp:
            tmp.write(request.audio_data)
            tmp_path = tmp.name

        try:
            language = request.language if request.language != "auto" else None
            segments_iter, info = self._model.transcribe(
                tmp_path,
                language=language,
                beam_size=5,
                word_timestamps=False,
                vad_filter=True,  # Remove silêncio automaticamente
                vad_parameters={"min_silence_duration_ms": 500},
            )

            segments = []
            full_text_parts = []
            for seg in segments_iter:
                segments.append(
                    {
                        "start": round(seg.start, 2),
                        "end": round(seg.end, 2),
                        "text": seg.text.strip(),
                    }
                )
                full_text_parts.append(seg.text.strip())

            transcription = " ".join(full_text_parts)
            logger.info(
                f"[WHISPER] Transcrição concluída: {len(transcription)} chars, "
                f"idioma={info.language} ({info.language_probability:.0%})"
            )

            return AudioResponse(
                provider_name="whisper_local",
                transcription=transcription,
                language_detected=info.language,
                confidence=round(info.language_probability, 3),
                segments=segments,
                cost=0.0,
            )
        finally:
            os.unlink(tmp_path)

    def is_available(self) -> bool:
        return self._model is not None

    def get_name(self) -> str:
        return "whisper_local"

    def supported_formats(self) -> list[str]:
        return ["wav", "mp3", "ogg", "flac", "m4a", "webm", "mp4"]

    @property
    def model_size(self) -> str:
        return self._model_size
