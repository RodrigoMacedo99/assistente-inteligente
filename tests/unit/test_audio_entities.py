"""Testes das entidades AudioRequest e AudioResponse."""
import pytest

from aiadapter.core.entities.audiorequest import AudioRequest
from aiadapter.core.entities.audioresponse import AudioResponse


class TestAudioRequest:
    def test_default_values(self):
        req = AudioRequest()
        assert req.text is None
        assert req.audio_data is None
        assert req.voice is None
        assert req.speed == 1.0
        assert req.audio_format == "wav"
        assert req.language is None  # None = auto-detect
        assert req.preferred_provider is None

    def test_tts_request(self):
        req = AudioRequest(text="Olá mundo", voice="nova", speed=1.2)
        assert req.is_tts()
        assert not req.is_stt()
        assert req.text == "Olá mundo"
        assert req.voice == "nova"
        assert req.speed == 1.2

    def test_stt_request(self):
        audio = b"\x00\x01\x02\x03"
        req = AudioRequest(audio_data=audio, audio_format="mp3", language="pt")
        assert req.is_stt()
        assert not req.is_tts()
        assert req.audio_data == audio
        assert req.audio_format == "mp3"

    def test_both_tts_and_stt(self):
        req = AudioRequest(text="hello", audio_data=b"bytes")
        assert req.is_tts()
        assert req.is_stt()

    def test_neither_tts_nor_stt(self):
        req = AudioRequest()
        assert not req.is_tts()
        assert not req.is_stt()

    def test_preferred_provider(self):
        req = AudioRequest(text="test", preferred_provider="edge_tts")
        assert req.preferred_provider == "edge_tts"


class TestAudioResponse:
    def test_tts_response_defaults(self):
        resp = AudioResponse(provider_name="edge_tts", audio_data=b"audio", audio_format="mp3")
        assert resp.provider_name == "edge_tts"
        assert resp.audio_data == b"audio"
        assert resp.audio_format == "mp3"
        assert resp.transcription is None
        assert resp.cost == 0.0
        assert resp.duration_seconds == 0.0  # default é 0.0

    def test_stt_response_defaults(self):
        resp = AudioResponse(
            provider_name="groq_stt",
            transcription="Olá mundo",
            language_detected="pt",
            confidence=0.95,
        )
        assert resp.provider_name == "groq_stt"
        assert resp.transcription == "Olá mundo"
        assert resp.language_detected == "pt"
        assert resp.confidence == 0.95
        assert resp.audio_data is None

    def test_with_segments(self):
        segments = [{"start": 0.0, "end": 1.5, "text": "Olá"}]
        resp = AudioResponse(
            provider_name="whisper_local",
            transcription="Olá",
            segments=segments,
        )
        assert resp.segments == segments

    def test_cost_field(self):
        resp = AudioResponse(provider_name="openai_tts", audio_data=b"x", cost=0.000015)
        assert resp.cost == pytest.approx(0.000015)

    def test_duration_seconds(self):
        resp = AudioResponse(provider_name="edge_tts", audio_data=b"x", duration_seconds=3.5)
        assert resp.duration_seconds == pytest.approx(3.5)
