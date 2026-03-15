"""Testes do AudioService — orquestrador TTS/STT."""
from unittest.mock import MagicMock

import pytest

from aiadapter.application.audio_service import AudioService
from aiadapter.core.entities.audiorequest import AudioRequest
from aiadapter.core.entities.audioresponse import AudioResponse


def _make_tts_provider(name: str, available: bool = True, fail: bool = False) -> MagicMock:
    p = MagicMock()
    p.get_name.return_value = name
    p.is_available.return_value = available
    if fail:
        p.speak.side_effect = RuntimeError(f"{name} falhou")
    else:
        p.speak.return_value = AudioResponse(
            provider_name=name, audio_data=b"audio", audio_format="mp3"
        )
    p.list_voices.return_value = [{"name": "voz1", "gender": "female", "language": "pt"}]
    return p


def _make_stt_provider(name: str, available: bool = True, fail: bool = False) -> MagicMock:
    p = MagicMock()
    p.get_name.return_value = name
    p.is_available.return_value = available
    if fail:
        p.transcribe.side_effect = RuntimeError(f"{name} falhou")
    else:
        p.transcribe.return_value = AudioResponse(
            provider_name=name, transcription="Olá mundo", language_detected="pt"
        )
    return p


class TestAudioServiceTTS:
    def test_speak_uses_first_available_provider(self):
        tts1 = _make_tts_provider("pyttsx3", available=True)
        tts2 = _make_tts_provider("edge_tts", available=True)
        svc = AudioService(tts_providers=[tts1, tts2])

        req = AudioRequest(text="Olá")
        resp = svc.speak(req)

        assert resp.provider_name == "pyttsx3"
        tts1.speak.assert_called_once()
        tts2.speak.assert_not_called()

    def test_speak_skips_unavailable_providers(self):
        tts1 = _make_tts_provider("pyttsx3", available=False)
        tts2 = _make_tts_provider("edge_tts", available=True)
        svc = AudioService(tts_providers=[tts1, tts2])

        req = AudioRequest(text="Olá")
        resp = svc.speak(req)

        assert resp.provider_name == "edge_tts"

    def test_speak_falls_back_on_failure(self):
        tts1 = _make_tts_provider("pyttsx3", available=True, fail=True)
        tts2 = _make_tts_provider("edge_tts", available=True)
        svc = AudioService(tts_providers=[tts1, tts2])

        req = AudioRequest(text="Olá")
        resp = svc.speak(req)

        assert resp.provider_name == "edge_tts"

    def test_speak_raises_when_all_fail(self):
        tts1 = _make_tts_provider("pyttsx3", available=True, fail=True)
        tts2 = _make_tts_provider("edge_tts", available=True, fail=True)
        svc = AudioService(tts_providers=[tts1, tts2])

        with pytest.raises(RuntimeError, match="Todos os providers TTS falharam"):
            svc.speak(AudioRequest(text="Olá"))

    def test_speak_raises_no_providers(self):
        svc = AudioService(tts_providers=[])

        with pytest.raises(RuntimeError, match="Nenhum provider TTS disponível"):
            svc.speak(AudioRequest(text="Olá"))

    def test_speak_raises_empty_text(self):
        tts1 = _make_tts_provider("edge_tts")
        svc = AudioService(tts_providers=[tts1])

        with pytest.raises(ValueError, match="Texto não pode ser vazio"):
            svc.speak(AudioRequest(text=""))

    def test_speak_raises_whitespace_text(self):
        tts1 = _make_tts_provider("edge_tts")
        svc = AudioService(tts_providers=[tts1])

        with pytest.raises(ValueError):
            svc.speak(AudioRequest(text="   "))

    def test_preferred_provider_is_tried_first(self):
        tts1 = _make_tts_provider("pyttsx3", available=True)
        tts2 = _make_tts_provider("edge_tts", available=True)
        svc = AudioService(tts_providers=[tts1, tts2])

        req = AudioRequest(text="Olá", preferred_provider="edge_tts")
        resp = svc.speak(req)

        assert resp.provider_name == "edge_tts"
        tts2.speak.assert_called_once()
        tts1.speak.assert_not_called()

    def test_list_tts_voices_aggregates_all_providers(self):
        tts1 = _make_tts_provider("pyttsx3")
        tts2 = _make_tts_provider("edge_tts")
        svc = AudioService(tts_providers=[tts1, tts2])

        voices = svc.list_tts_voices("pt")
        assert len(voices) == 2
        assert voices[0]["provider"] == "pyttsx3"
        assert voices[1]["provider"] == "edge_tts"


class TestAudioServiceSTT:
    def test_transcribe_uses_first_available_provider(self):
        stt1 = _make_stt_provider("whisper_local", available=True)
        stt2 = _make_stt_provider("groq_stt", available=True)
        svc = AudioService(stt_providers=[stt1, stt2])

        req = AudioRequest(audio_data=b"audio", audio_format="wav")
        resp = svc.transcribe(req)

        assert resp.provider_name == "whisper_local"
        stt1.transcribe.assert_called_once()

    def test_transcribe_skips_unavailable(self):
        stt1 = _make_stt_provider("whisper_local", available=False)
        stt2 = _make_stt_provider("groq_stt", available=True)
        svc = AudioService(stt_providers=[stt1, stt2])

        req = AudioRequest(audio_data=b"audio", audio_format="wav")
        resp = svc.transcribe(req)

        assert resp.provider_name == "groq_stt"

    def test_transcribe_falls_back_on_failure(self):
        stt1 = _make_stt_provider("whisper_local", available=True, fail=True)
        stt2 = _make_stt_provider("groq_stt", available=True)
        svc = AudioService(stt_providers=[stt1, stt2])

        req = AudioRequest(audio_data=b"audio", audio_format="wav")
        resp = svc.transcribe(req)

        assert resp.provider_name == "groq_stt"

    def test_transcribe_raises_when_all_fail(self):
        stt1 = _make_stt_provider("whisper_local", available=True, fail=True)
        svc = AudioService(stt_providers=[stt1])

        with pytest.raises(RuntimeError, match="Todos os providers STT falharam"):
            svc.transcribe(AudioRequest(audio_data=b"audio", audio_format="wav"))

    def test_transcribe_raises_no_audio_data(self):
        stt1 = _make_stt_provider("whisper_local")
        svc = AudioService(stt_providers=[stt1])

        with pytest.raises(ValueError, match="audio_data não fornecido"):
            svc.transcribe(AudioRequest())

    def test_transcribe_preferred_provider(self):
        stt1 = _make_stt_provider("whisper_local", available=True)
        stt2 = _make_stt_provider("groq_stt", available=True)
        svc = AudioService(stt_providers=[stt1, stt2])

        req = AudioRequest(audio_data=b"audio", audio_format="wav", preferred_provider="groq_stt")
        resp = svc.transcribe(req)

        assert resp.provider_name == "groq_stt"


class TestAudioServiceStatus:
    def test_status_returns_all_providers(self):
        tts1 = _make_tts_provider("pyttsx3", available=True)
        tts2 = _make_tts_provider("edge_tts", available=False)
        stt1 = _make_stt_provider("whisper_local", available=True)
        svc = AudioService(tts_providers=[tts1, tts2], stt_providers=[stt1])

        status = svc.status()

        assert len(status["tts"]) == 2
        assert status["tts"][0]["name"] == "pyttsx3"
        assert status["tts"][0]["available"] is True
        assert status["tts"][1]["name"] == "edge_tts"
        assert status["tts"][1]["available"] is False
        assert len(status["stt"]) == 1
        assert status["stt"][0]["name"] == "whisper_local"
        assert status["stt"][0]["available"] is True

    def test_status_includes_health_fields(self):
        tts1 = _make_tts_provider("pyttsx3", available=True)
        svc = AudioService(tts_providers=[tts1])

        status = svc.status()

        entry = status["tts"][0]
        assert "consecutive_failures" in entry
        assert "total_failures" in entry
        assert "total_successes" in entry
        assert "circuit_open" in entry
        assert entry["consecutive_failures"] == 0
        assert entry["circuit_open"] is False

    def test_status_empty_providers(self):
        svc = AudioService()
        status = svc.status()
        assert status["tts"] == []
        assert status["stt"] == []
