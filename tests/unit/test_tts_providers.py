"""Testes unitários para providers TTS (sem chamadas de rede)."""

from unittest.mock import MagicMock, mock_open, patch

import pytest

from aiadapter.core.entities.audiorequest import AudioRequest


class TestPyttsx3TTSProvider:
    """Testa Pyttsx3TTSProvider com motor mockado."""

    def _make_provider(self):
        from aiadapter.infrastructure.providers.tts.pyttsx3_provider import Pyttsx3TTSProvider

        with patch("pyttsx3.init") as mock_init:
            engine = MagicMock()
            engine.getProperty.return_value = []
            mock_init.return_value = engine
            p = Pyttsx3TTSProvider(rate=150, volume=1.0)
        p._engine = engine
        p._available = True
        return p, engine

    def test_get_name(self):
        from aiadapter.infrastructure.providers.tts.pyttsx3_provider import Pyttsx3TTSProvider

        with patch("pyttsx3.init", side_effect=ImportError):
            p = Pyttsx3TTSProvider()
        assert p.get_name() == "pyttsx3"

    def test_is_available_false_when_import_error(self):
        from aiadapter.infrastructure.providers.tts.pyttsx3_provider import Pyttsx3TTSProvider

        with patch("pyttsx3.init", side_effect=ImportError):
            p = Pyttsx3TTSProvider()
        assert not p.is_available()

    def test_speak_raises_when_unavailable(self):
        from aiadapter.infrastructure.providers.tts.pyttsx3_provider import Pyttsx3TTSProvider

        with patch("pyttsx3.init", side_effect=ImportError):
            p = Pyttsx3TTSProvider()
        with pytest.raises(RuntimeError, match="Pyttsx3 indisponível"):
            p.speak(AudioRequest(text="hello"))

    def test_speak_raises_on_empty_text(self):
        from aiadapter.infrastructure.providers.tts.pyttsx3_provider import Pyttsx3TTSProvider

        with patch("pyttsx3.init", side_effect=ImportError):
            p = Pyttsx3TTSProvider()
        p._available = True
        p._engine = MagicMock()
        with pytest.raises(ValueError, match="Texto não pode ser vazio"):
            p.speak(AudioRequest(text=""))

    def test_speak_returns_wav_response(self, tmp_path):
        from aiadapter.infrastructure.providers.tts.pyttsx3_provider import Pyttsx3TTSProvider

        fake_wav = b"RIFF....WAVEfmt " + b"\x00" * 100

        with patch("pyttsx3.init") as mock_init:
            engine = MagicMock()
            engine.getProperty.return_value = []
            mock_init.return_value = engine
            p = Pyttsx3TTSProvider()

        p._available = True
        p._engine = engine

        with (
            patch("tempfile.NamedTemporaryFile") as mock_tmp,
            patch("builtins.open", mock_open(read_data=fake_wav)),
            patch("os.path.exists", return_value=True),
            patch("os.unlink"),
        ):
            mock_tmp.return_value.__enter__.return_value.name = str(tmp_path / "test.wav")
            engine.save_to_file = MagicMock()
            engine.runAndWait = MagicMock()

            resp = p.speak(AudioRequest(text="Olá mundo, como vai você?"))

        assert resp.provider_name == "pyttsx3"
        assert resp.audio_format == "wav"
        assert resp.cost == 0.0
        assert resp.audio_data == fake_wav

    def test_list_voices_empty_when_unavailable(self):
        from aiadapter.infrastructure.providers.tts.pyttsx3_provider import Pyttsx3TTSProvider

        with patch("pyttsx3.init", side_effect=ImportError):
            p = Pyttsx3TTSProvider()
        assert p.list_voices("pt") == []


class TestEdgeTTSProvider:
    """Testa EdgeTTSProvider com asyncio mockado."""

    def test_get_name(self):
        from aiadapter.infrastructure.providers.tts.edge_tts_provider import EdgeTTSProvider

        with patch("builtins.__import__", side_effect=ImportError):
            pass
        p = EdgeTTSProvider.__new__(EdgeTTSProvider)
        p._default_voice = "pt-BR-FranciscaNeural"
        p._available = False
        assert p.get_name() == "edge_tts"

    def test_is_available_false_when_import_error(self):
        from aiadapter.infrastructure.providers.tts.edge_tts_provider import EdgeTTSProvider

        with patch.object(EdgeTTSProvider, "_check_available", return_value=False):
            p = EdgeTTSProvider()
        assert not p.is_available()

    def test_speak_raises_when_unavailable(self):
        from aiadapter.infrastructure.providers.tts.edge_tts_provider import EdgeTTSProvider

        with patch.object(EdgeTTSProvider, "_check_available", return_value=False):
            p = EdgeTTSProvider()
        with pytest.raises(RuntimeError, match="EdgeTTS indisponível"):
            p.speak(AudioRequest(text="hello"))

    def test_speak_raises_empty_text(self):
        from aiadapter.infrastructure.providers.tts.edge_tts_provider import EdgeTTSProvider

        with patch.object(EdgeTTSProvider, "_check_available", return_value=True):
            p = EdgeTTSProvider()
        with pytest.raises(ValueError, match="Texto não pode ser vazio"):
            p.speak(AudioRequest(text="   "))

    def test_speed_to_rate_conversion(self):
        from aiadapter.infrastructure.providers.tts.edge_tts_provider import EdgeTTSProvider

        with patch.object(EdgeTTSProvider, "_check_available", return_value=False):
            p = EdgeTTSProvider()

        assert p._speed_to_rate(1.0) == "+0%"
        assert p._speed_to_rate(1.5) == "+50%"
        assert p._speed_to_rate(0.5) == "-50%"
        assert p._speed_to_rate(2.0) == "+100%"

    def test_list_voices_pt(self):
        from aiadapter.infrastructure.providers.tts.edge_tts_provider import (
            VOICES_PT,
            EdgeTTSProvider,
        )

        with patch.object(EdgeTTSProvider, "_check_available", return_value=False):
            p = EdgeTTSProvider()
        voices = p.list_voices("pt")
        assert len(voices) == len(VOICES_PT)
        assert all(v["language"].startswith("pt") for v in voices)

    def test_list_voices_en(self):
        from aiadapter.infrastructure.providers.tts.edge_tts_provider import (
            VOICES_EN,
            EdgeTTSProvider,
        )

        with patch.object(EdgeTTSProvider, "_check_available", return_value=False):
            p = EdgeTTSProvider()
        voices = p.list_voices("en")
        assert len(voices) == len(VOICES_EN)
        assert all(v["language"].startswith("en") for v in voices)

    def test_speak_returns_mp3_response(self):
        from aiadapter.infrastructure.providers.tts.edge_tts_provider import EdgeTTSProvider

        with patch.object(EdgeTTSProvider, "_check_available", return_value=True):
            p = EdgeTTSProvider()

        fake_audio = b"\xff\xfb\x90" + b"\x00" * 100
        with (
            patch.object(p, "_synthesize_async", return_value=fake_audio),
            patch("asyncio.run", return_value=fake_audio),
        ):
            resp = p.speak(AudioRequest(text="Olá mundo, isso é um teste."))

        assert resp.provider_name == "edge_tts"
        assert resp.audio_format == "mp3"
        assert resp.cost == 0.0


class TestOpenAITTSProvider:
    """Testa OpenAITTSProvider com cliente mockado."""

    def _make_provider(self):
        from aiadapter.infrastructure.providers.tts.openai_tts_provider import OpenAITTSProvider

        with patch("openai.OpenAI"):
            p = OpenAITTSProvider(api_key="sk-test")
        return p

    def test_get_name(self):
        p = self._make_provider()
        assert p.get_name() == "openai_tts"

    def test_is_available_true_with_client(self):
        p = self._make_provider()
        assert p.is_available()

    def test_is_available_false_without_key(self):
        from aiadapter.infrastructure.providers.tts.openai_tts_provider import OpenAITTSProvider

        with patch("openai.OpenAI"):
            p = OpenAITTSProvider(api_key="")
        assert not p.is_available()

    def test_speak_raises_when_unavailable(self):
        from aiadapter.infrastructure.providers.tts.openai_tts_provider import OpenAITTSProvider

        with patch.object(OpenAITTSProvider, "_init_client"):
            p = OpenAITTSProvider.__new__(OpenAITTSProvider)
            p._api_key = ""
            p._client = None
            p._model = "tts-1"
        with pytest.raises(RuntimeError):
            p.speak(AudioRequest(text="hello"))

    def test_speak_raises_empty_text(self):
        p = self._make_provider()
        with pytest.raises(ValueError):
            p.speak(AudioRequest(text=""))

    def test_speak_returns_response_with_cost(self):
        p = self._make_provider()
        fake_audio = b"\xff\xfb" + b"\x00" * 500
        mock_response = MagicMock()
        mock_response.content = fake_audio
        p._client.audio.speech.create.return_value = mock_response

        resp = p.speak(AudioRequest(text="Olá mundo"))

        assert resp.provider_name == "openai_tts"
        assert resp.audio_format == "mp3"
        assert resp.audio_data == fake_audio
        assert resp.cost > 0.0

    def test_cost_calculation(self):
        p = self._make_provider()
        mock_response = MagicMock()
        mock_response.content = b"x" * 100
        p._client.audio.speech.create.return_value = mock_response

        # 1_000_000 chars * $15/1M = $15.0
        text = "a" * 1_000_000
        resp = p.speak(AudioRequest(text=text))
        assert resp.cost == pytest.approx(15.0, abs=0.001)

    def test_format_defaults_to_mp3(self):
        p = self._make_provider()
        mock_response = MagicMock()
        mock_response.content = b"audio"
        p._client.audio.speech.create.return_value = mock_response

        resp = p.speak(AudioRequest(text="test", audio_format_out="invalid"))
        assert resp.audio_format == "mp3"

    def test_list_voices(self):
        p = self._make_provider()
        voices = p.list_voices("pt")
        assert len(voices) == 6
        names = [v["name"] for v in voices]
        assert "nova" in names
        assert "alloy" in names
