"""
Captura de áudio do microfone em tempo real.

Suporta dois backends:
  sounddevice — recomendado, mais leve, baseado em PortAudio
  pyaudio     — alternativo, amplamente compatível

Funcionalidades:
  - Gravação por duração fixa
  - Gravação com detecção de silêncio (VAD simples por RMS)
  - Exporta como WAV em bytes ou arquivo

Instalação (escolha um):
  pip install sounddevice scipy    # recomendado
  pip install pyaudio              # alternativo
"""

import io
import logging
import struct
import wave

logger = logging.getLogger("aiadapter.microphone")

DEFAULT_SAMPLE_RATE = 16000  # Hz — ideal para Whisper
DEFAULT_CHANNELS = 1  # mono
DEFAULT_CHUNK_MS = 100  # ms por chunk de captura
SILENCE_THRESHOLD_RMS = 500  # nível RMS abaixo = silêncio
MIN_SPEECH_DURATION = 0.3  # segundos de fala para considerar válida


class MicrophoneCapture:
    """
    Captura áudio do microfone e retorna bytes WAV prontos para STT.
    Detecta automaticamente o backend disponível (sounddevice ou pyaudio).
    """

    def __init__(
        self,
        sample_rate: int = DEFAULT_SAMPLE_RATE,
        channels: int = DEFAULT_CHANNELS,
        device_index: int | None = None,
    ):
        self._sample_rate = sample_rate
        self._channels = channels
        self._device_index = device_index
        self._backend = self._detect_backend()

    def _detect_backend(self) -> str | None:
        try:
            import sounddevice  # noqa: F401

            logger.info("[MIC] Backend: sounddevice")
            return "sounddevice"
        except ImportError:
            pass

        try:
            import pyaudio  # noqa: F401

            logger.info("[MIC] Backend: pyaudio")
            return "pyaudio"
        except ImportError:
            pass

        logger.warning(
            "[MIC] Nenhum backend de áudio disponível. "
            "Execute: pip install sounddevice scipy  ou  pip install pyaudio"
        )
        return None

    def is_available(self) -> bool:
        return self._backend is not None

    def record_fixed(self, duration_seconds: float) -> bytes:
        """Grava por duração fixa e retorna bytes WAV."""
        if not self.is_available():
            raise RuntimeError("Nenhum backend de microfone disponível")

        if self._backend == "sounddevice":
            return self._record_sounddevice(duration_seconds)
        return self._record_pyaudio(duration_seconds)

    def record_until_silence(
        self,
        max_duration_seconds: float = 30.0,
        silence_duration_seconds: float = 1.5,
    ) -> bytes:
        """
        Grava até detectar silêncio contínuo ou atingir max_duration_seconds.
        Retorna bytes WAV.
        """
        if not self.is_available():
            raise RuntimeError("Nenhum backend de microfone disponível")

        if self._backend == "sounddevice":
            return self._record_vad_sounddevice(max_duration_seconds, silence_duration_seconds)
        return self._record_vad_pyaudio(max_duration_seconds, silence_duration_seconds)

    # ── sounddevice backend ───────────────────────────────────────────────────

    def _record_sounddevice(self, duration: float) -> bytes:
        import sounddevice as sd

        frames = sd.rec(
            int(duration * self._sample_rate),
            samplerate=self._sample_rate,
            channels=self._channels,
            dtype="int16",
            device=self._device_index,
        )
        sd.wait()
        logger.info(f"[MIC] Gravado {duration:.1f}s via sounddevice")
        return self._numpy_to_wav(frames)

    def _record_vad_sounddevice(self, max_dur: float, silence_dur: float) -> bytes:
        import numpy as np
        import sounddevice as sd

        chunk_size = int(self._sample_rate * DEFAULT_CHUNK_MS / 1000)
        all_frames: list[np.ndarray] = []
        silence_chunks = 0
        max_silence_chunks = int(silence_dur * 1000 / DEFAULT_CHUNK_MS)
        max_chunks = int(max_dur * 1000 / DEFAULT_CHUNK_MS)
        has_speech = False

        logger.info("[MIC] Aguardando fala... (VAD ativo)")

        with sd.InputStream(
            samplerate=self._sample_rate,
            channels=self._channels,
            dtype="int16",
            blocksize=chunk_size,
            device=self._device_index,
        ) as stream:
            for _ in range(max_chunks):
                data, _ = stream.read(chunk_size)
                all_frames.append(data.copy())

                rms = self._rms(data.flatten().tolist())
                if rms > SILENCE_THRESHOLD_RMS:
                    has_speech = True
                    silence_chunks = 0
                elif has_speech:
                    silence_chunks += 1
                    if silence_chunks >= max_silence_chunks:
                        logger.info(f"[MIC] Silêncio detectado após {len(all_frames)} chunks")
                        break

        if not has_speech:
            logger.warning("[MIC] Nenhuma fala detectada")

        import numpy as np

        combined = np.concatenate(all_frames, axis=0)
        return self._numpy_to_wav(combined)

    def _numpy_to_wav(self, frames) -> bytes:
        import numpy as np

        buf = io.BytesIO()
        with wave.open(buf, "wb") as wf:
            wf.setnchannels(self._channels)
            wf.setsampwidth(2)  # int16 = 2 bytes
            wf.setframerate(self._sample_rate)
            wf.writeframes(frames.astype(np.int16).tobytes())
        return buf.getvalue()

    # ── pyaudio backend ───────────────────────────────────────────────────────

    def _record_pyaudio(self, duration: float) -> bytes:
        import pyaudio

        chunk = int(self._sample_rate * DEFAULT_CHUNK_MS / 1000)
        pa = pyaudio.PyAudio()
        stream = pa.open(
            format=pyaudio.paInt16,
            channels=self._channels,
            rate=self._sample_rate,
            input=True,
            frames_per_buffer=chunk,
            input_device_index=self._device_index,
        )

        num_chunks = int(duration * 1000 / DEFAULT_CHUNK_MS)
        frames = []
        for _ in range(num_chunks):
            data = stream.read(chunk, exception_on_overflow=False)
            frames.append(data)

        stream.stop_stream()
        stream.close()
        pa.terminate()

        logger.info(f"[MIC] Gravado {duration:.1f}s via pyaudio")
        return self._raw_to_wav(b"".join(frames))

    def _record_vad_pyaudio(self, max_dur: float, silence_dur: float) -> bytes:
        import pyaudio

        chunk = int(self._sample_rate * DEFAULT_CHUNK_MS / 1000)
        pa = pyaudio.PyAudio()
        stream = pa.open(
            format=pyaudio.paInt16,
            channels=self._channels,
            rate=self._sample_rate,
            input=True,
            frames_per_buffer=chunk,
            input_device_index=self._device_index,
        )

        max_chunks = int(max_dur * 1000 / DEFAULT_CHUNK_MS)
        max_silence_chunks = int(silence_dur * 1000 / DEFAULT_CHUNK_MS)
        silence_chunks = 0
        has_speech = False
        frames = []

        logger.info("[MIC] Aguardando fala... (VAD ativo)")

        for _ in range(max_chunks):
            data = stream.read(chunk, exception_on_overflow=False)
            frames.append(data)

            samples = struct.unpack(f"{len(data) // 2}h", data)
            rms = self._rms(list(samples))
            if rms > SILENCE_THRESHOLD_RMS:
                has_speech = True
                silence_chunks = 0
            elif has_speech:
                silence_chunks += 1
                if silence_chunks >= max_silence_chunks:
                    break

        stream.stop_stream()
        stream.close()
        pa.terminate()

        if not has_speech:
            logger.warning("[MIC] Nenhuma fala detectada")

        return self._raw_to_wav(b"".join(frames))

    def _raw_to_wav(self, raw_bytes: bytes) -> bytes:
        buf = io.BytesIO()
        with wave.open(buf, "wb") as wf:
            wf.setnchannels(self._channels)
            wf.setsampwidth(2)
            wf.setframerate(self._sample_rate)
            wf.writeframes(raw_bytes)
        return buf.getvalue()

    @staticmethod
    def _rms(samples: list[int]) -> float:
        """Root mean square — mede o volume médio do chunk."""
        if not samples:
            return 0.0
        return (sum(s * s for s in samples) / len(samples)) ** 0.5

    def list_devices(self) -> list[dict]:
        """Lista dispositivos de entrada de áudio disponíveis."""
        if self._backend == "sounddevice":
            return self._list_sounddevice()
        if self._backend == "pyaudio":
            return self._list_pyaudio()
        return []

    def _list_sounddevice(self) -> list[dict]:
        import sounddevice as sd

        devices = []
        for i, d in enumerate(sd.query_devices()):
            if d["max_input_channels"] > 0:
                devices.append({"index": i, "name": d["name"], "channels": d["max_input_channels"]})
        return devices

    def _list_pyaudio(self) -> list[dict]:
        import pyaudio

        pa = pyaudio.PyAudio()
        devices = []
        for i in range(pa.get_device_count()):
            info = pa.get_device_info_by_index(i)
            if info["maxInputChannels"] > 0:
                devices.append(
                    {"index": i, "name": info["name"], "channels": info["maxInputChannels"]}
                )
        pa.terminate()
        return devices
