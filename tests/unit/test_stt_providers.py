"""Testes unitários para providers STT (sem chamadas de rede)."""
from unittest.mock import MagicMock, patch

import pytest

from aiadapter.core.entities.audiorequest import AudioRequest


class TestWhisperLocalSTTProvider:
    """Testa WhisperLocalProvider com modelo mockado."""

    def _make_provider(self, model_size="base"):
        from aiadapter.infrastructure.providers.stt.whisper_local_provider import (
            WhisperLocalProvider,
        )
        with patch.object(WhisperLocalProvider, "_try_load"):
            p = WhisperLocalProvider(model_size=model_size)
        return p

    def test_get_name(self):
        p = self._make_provider()
        assert p.get_name() == "whisper_local"

    def test_is_available_false_without_model(self):
        p = self._make_provider()
        p._model = None
        assert not p.is_available()

    def test_is_available_true_with_model(self):
        p = self._make_provider()
        p._model = MagicMock()
        assert p.is_available()

    def test_transcribe_raises_when_unavailable(self):
        p = self._make_provider()
        p._model = None
        p._load_error = "faster-whisper não instalado"
        with pytest.raises(RuntimeError, match="WhisperLocal indisponível"):
            p.transcribe(AudioRequest(audio_data=b"audio", audio_format="wav"))

    def test_transcribe_raises_no_audio(self):
        p = self._make_provider()
        p._model = MagicMock()
        with pytest.raises(ValueError, match="audio_data não fornecido"):
            p.transcribe(AudioRequest())

    def test_transcribe_returns_response(self):
        from aiadapter.infrastructure.providers.stt.whisper_local_provider import (
            WhisperLocalProvider,
        )
        with patch.object(WhisperLocalProvider, "_try_load"):
            p = WhisperLocalProvider()

        p._model = MagicMock()
        mock_segment = MagicMock()
        mock_segment.start = 0.0
        mock_segment.end = 2.5
        mock_segment.text = " Olá mundo"
        mock_info = MagicMock()
        mock_info.language = "pt"
        mock_info.language_probability = 0.98

        p._model.transcribe.return_value = ([mock_segment], mock_info)

        with patch("tempfile.NamedTemporaryFile") as mock_tmp, \
             patch("os.unlink"):
            mock_tmp.return_value.__enter__.return_value.name = "/tmp/test.wav"
            resp = p.transcribe(AudioRequest(audio_data=b"fake_wav", audio_format="wav"))

        assert resp.provider_name == "whisper_local"
        assert resp.transcription == "Olá mundo"
        assert resp.language_detected == "pt"
        assert resp.confidence == pytest.approx(0.98)
        assert resp.cost == 0.0
        assert len(resp.segments) == 1
        assert resp.segments[0]["text"] == "Olá mundo"

    def test_supported_formats(self):
        p = self._make_provider()
        formats = p.supported_formats()
        assert "wav" in formats
        assert "mp3" in formats

    def test_model_size_stored(self):
        p = self._make_provider(model_size="small")
        assert p._model_size == "small"


class TestGroqSTTProvider:
    """Testa GroqSTTProvider com cliente mockado."""

    def _make_provider(self):
        from aiadapter.infrastructure.providers.stt.groq_stt_provider import GroqSTTProvider
        with patch("groq.Groq"):
            p = GroqSTTProvider(api_key="gsk_test123")
        return p

    def test_get_name(self):
        p = self._make_provider()
        assert p.get_name() == "groq_stt"

    def test_is_available_false_without_key(self):
        from aiadapter.infrastructure.providers.stt.groq_stt_provider import GroqSTTProvider
        with patch("groq.Groq"):
            p = GroqSTTProvider(api_key="")
        assert not p.is_available()

    def test_is_available_false_on_import_error(self):
        from aiadapter.infrastructure.providers.stt.groq_stt_provider import GroqSTTProvider
        with patch.object(GroqSTTProvider, "_init_client"):
            p = GroqSTTProvider.__new__(GroqSTTProvider)
            p._api_key = "key"
            p._client = None
        assert not p.is_available()

    def test_transcribe_raises_when_unavailable(self):
        p = self._make_provider()
        p._client = None
        with pytest.raises(RuntimeError, match="GroqSTT indisponível"):
            p.transcribe(AudioRequest(audio_data=b"audio", audio_format="wav"))

    def test_transcribe_raises_no_audio(self):
        p = self._make_provider()
        with pytest.raises(ValueError, match="audio_data não fornecido"):
            p.transcribe(AudioRequest())

    def test_transcribe_returns_response(self):
        p = self._make_provider()
        mock_transcription = MagicMock()
        mock_transcription.text = "Olá mundo"
        mock_transcription.x_groq = MagicMock()
        mock_transcription.x_groq.id = "req_abc123"

        mock_seg = MagicMock()
        mock_seg.start = 0.0
        mock_seg.end = 1.8
        mock_seg.text = " Olá mundo"
        mock_transcription.segments = [mock_seg]
        mock_transcription.language = "portuguese"

        p._client.audio.transcriptions.create.return_value = mock_transcription

        resp = p.transcribe(AudioRequest(audio_data=b"fake_wav", audio_format="wav", language="pt"))

        assert resp.provider_name == "groq_stt"
        assert resp.transcription == "Olá mundo"
        assert resp.cost == 0.0

    def test_supported_formats(self):
        p = self._make_provider()
        formats = p.supported_formats()
        assert "wav" in formats
        assert "mp3" in formats


class TestOpenAISTTProvider:
    """Testa OpenAISTTProvider com cliente mockado."""

    def _make_provider(self):
        from aiadapter.infrastructure.providers.stt.openai_stt_provider import OpenAISTTProvider
        with patch("openai.OpenAI"):
            p = OpenAISTTProvider(api_key="sk-test")
        return p

    def test_get_name(self):
        p = self._make_provider()
        assert p.get_name() == "openai_stt"

    def test_is_available_true_with_client(self):
        p = self._make_provider()
        assert p.is_available()

    def test_is_available_false_without_key(self):
        from aiadapter.infrastructure.providers.stt.openai_stt_provider import OpenAISTTProvider
        with patch("openai.OpenAI"):
            p = OpenAISTTProvider(api_key="")
        assert not p.is_available()

    def test_transcribe_raises_no_audio(self):
        p = self._make_provider()
        with pytest.raises(ValueError, match="audio_data não fornecido"):
            p.transcribe(AudioRequest())

    def test_transcribe_returns_response(self):
        p = self._make_provider()
        mock_transcription = MagicMock()
        mock_transcription.text = "  Hello world  "
        mock_transcription.language = "english"
        mock_transcription.duration = 2.0
        mock_transcription.segments = []

        p._client.audio.transcriptions.create.return_value = mock_transcription

        resp = p.transcribe(AudioRequest(audio_data=b"fake_wav", audio_format="wav"))

        assert resp.provider_name == "openai_stt"
        assert resp.transcription == "Hello world"
        assert resp.cost > 0.0

    def test_cost_calculation(self):
        p = self._make_provider()
        mock_transcription = MagicMock()
        mock_transcription.text = "test"
        mock_transcription.language = "en"
        mock_transcription.duration = 60.0  # 1 minuto
        mock_transcription.segments = []

        p._client.audio.transcriptions.create.return_value = mock_transcription

        resp = p.transcribe(AudioRequest(audio_data=b"audio", audio_format="mp3"))

        # $0.006 por minuto x 1 minuto = $0.006
        assert resp.cost == pytest.approx(0.006, abs=0.0001)

    def test_language_auto_becomes_none(self):
        """Quando language='auto', deve passar None para a API."""
        p = self._make_provider()
        mock_transcription = MagicMock()
        mock_transcription.text = "text"
        mock_transcription.language = "en"
        mock_transcription.duration = 1.0
        mock_transcription.segments = []
        p._client.audio.transcriptions.create.return_value = mock_transcription

        p.transcribe(AudioRequest(audio_data=b"audio", audio_format="wav", language="auto"))

        call_kwargs = p._client.audio.transcriptions.create.call_args.kwargs
        assert call_kwargs.get("language") is None

    def test_supported_formats(self):
        p = self._make_provider()
        formats = p.supported_formats()
        assert "mp3" in formats
        assert "wav" in formats
        assert "webm" in formats
