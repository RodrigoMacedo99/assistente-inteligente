"""
Testes do fallback automático com circuit breaker — AudioService.

Cobre:
  - Retry por provider antes do fallback
  - Circuit breaker abre após threshold de falhas consecutivas
  - Provider com circuit aberto é pulado (skipped) no fallback_chain
  - Circuit fecha automaticamente após cooldown (half-open reset)
  - Success reseta contagem de falhas consecutivas e fecha circuit
  - fallback_chain no AudioResponse reflete o histórico de tentativas
  - Saúde é refletida no status()
"""
import time
import pytest
from unittest.mock import MagicMock, call

from aiadapter.application.audio_service import AudioService
from aiadapter.application.provider_health import ProviderHealth
from aiadapter.core.entities.audiorequest import AudioRequest
from aiadapter.core.entities.audioresponse import AudioResponse


# ── Helpers ───────────────────────────────────────────────────────────────────

def _tts(name: str, available: bool = True, fail: bool = False) -> MagicMock:
    p = MagicMock()
    p.get_name.return_value = name
    p.is_available.return_value = available
    if fail:
        p.speak.side_effect = RuntimeError(f"{name} erro")
    else:
        p.speak.return_value = AudioResponse(
            provider_name=name, audio_data=b"audio", audio_format="mp3"
        )
    p.list_voices.return_value = []
    return p


def _stt(name: str, available: bool = True, fail: bool = False) -> MagicMock:
    p = MagicMock()
    p.get_name.return_value = name
    p.is_available.return_value = available
    if fail:
        p.transcribe.side_effect = RuntimeError(f"{name} erro")
    else:
        p.transcribe.return_value = AudioResponse(
            provider_name=name, transcription="ok", language_detected="pt"
        )
    return p


_TTS_REQ = AudioRequest(text="Olá")
_STT_REQ = AudioRequest(audio_data=b"audio", audio_format="wav")


# ── ProviderHealth unit tests ─────────────────────────────────────────────────

class TestProviderHealth:
    def test_initial_state(self):
        h = ProviderHealth(name="p1")
        assert h.consecutive_failures == 0
        assert h.total_failures == 0
        assert h.total_successes == 0
        assert h.circuit_open is False
        assert h.is_open() is False

    def test_record_success_resets_failures(self):
        h = ProviderHealth(name="p1", consecutive_failures=2, total_failures=2)
        h.record_success()
        assert h.consecutive_failures == 0
        assert h.total_successes == 1
        assert h.is_open() is False

    def test_circuit_opens_after_threshold(self):
        h = ProviderHealth(name="p1")
        for _ in range(3):
            h.record_failure(cooldown_seconds=60, threshold=3)
        assert h.circuit_open is True
        assert h.is_open() is True

    def test_circuit_does_not_open_below_threshold(self):
        h = ProviderHealth(name="p1")
        h.record_failure(cooldown_seconds=60, threshold=3)
        h.record_failure(cooldown_seconds=60, threshold=3)
        assert h.is_open() is False

    def test_circuit_auto_closes_after_cooldown(self):
        h = ProviderHealth(name="p1")
        for _ in range(3):
            h.record_failure(cooldown_seconds=0.01, threshold=3)  # 10ms cooldown
        assert h.is_open() is True

        time.sleep(0.02)  # espera o cooldown

        assert h.is_open() is False  # deve ter fechado
        assert h.consecutive_failures == 0

    def test_success_closes_open_circuit(self):
        h = ProviderHealth(name="p1")
        for _ in range(3):
            h.record_failure(cooldown_seconds=60, threshold=3)
        assert h.is_open() is True

        h.record_success()
        assert h.is_open() is False

    def test_to_dict_structure(self):
        h = ProviderHealth(name="p1")
        d = h.to_dict()
        assert set(d.keys()) == {"consecutive_failures", "total_failures", "total_successes", "circuit_open"}


# ── Retry por provider ────────────────────────────────────────────────────────

class TestRetryPerProvider:
    def test_tts_retries_before_fallback(self):
        """Com max_retries=2 deve tentar o provider 2x antes de cair para o próximo."""
        p1 = _tts("p1", fail=True)
        p2 = _tts("p2")
        svc = AudioService(tts_providers=[p1, p2], max_retries=2)

        resp = svc.speak(_TTS_REQ)

        assert resp.provider_name == "p2"
        assert p1.speak.call_count == 2

    def test_stt_retries_before_fallback(self):
        p1 = _stt("p1", fail=True)
        p2 = _stt("p2")
        svc = AudioService(stt_providers=[p1, p2], max_retries=2)

        resp = svc.transcribe(_STT_REQ)

        assert resp.provider_name == "p2"
        assert p1.transcribe.call_count == 2

    def test_no_fallback_when_succeeds_on_second_attempt(self):
        """Provider falha na 1ª tentativa mas sucede na 2ª — não cai para o próximo."""
        p1 = MagicMock()
        p1.get_name.return_value = "p1"
        p1.is_available.return_value = True
        p1.speak.side_effect = [
            RuntimeError("falha temporária"),
            AudioResponse(provider_name="p1", audio_data=b"ok", audio_format="mp3"),
        ]
        p2 = _tts("p2")

        svc = AudioService(tts_providers=[p1, p2], max_retries=2)
        resp = svc.speak(_TTS_REQ)

        assert resp.provider_name == "p1"
        assert p1.speak.call_count == 2
        p2.speak.assert_not_called()


# ── Circuit breaker ───────────────────────────────────────────────────────────

class TestCircuitBreaker:
    def test_tts_circuit_opens_after_threshold_and_skips_provider(self):
        """Provider é ignorado após o circuit abrir (threshold=2 → abre após 2 falhas)."""
        p1 = _tts("p1", fail=True)
        p2 = _tts("p2")
        svc = AudioService(tts_providers=[p1, p2], circuit_breaker_threshold=2)

        svc.speak(_TTS_REQ)  # 1ª falha de p1 — circuit ainda fechado
        svc.speak(_TTS_REQ)  # 2ª falha de p1 — circuit abre (threshold atingido)
        resp = svc.speak(_TTS_REQ)  # 3ª chamada: p1 skipped, p2 atende

        assert resp.provider_name == "p2"
        # p1 foi chamado apenas nas 2 primeiras chamadas; 3ª foi skipped
        assert p1.speak.call_count == 2

    def test_stt_circuit_opens_after_threshold(self):
        p1 = _stt("p1", fail=True)
        p2 = _stt("p2")
        svc = AudioService(stt_providers=[p1, p2], circuit_breaker_threshold=1)

        svc.transcribe(_STT_REQ)  # p1 falha → circuit abre (threshold=1)
        resp = svc.transcribe(_STT_REQ)  # p1 skipped → p2 atende

        assert resp.provider_name == "p2"
        assert p1.transcribe.call_count == 1

    def test_circuit_closed_provider_recovers_after_cooldown(self):
        """Após o cooldown o circuit fecha e o provider pode ser tentado novamente."""
        p1 = MagicMock()
        p1.get_name.return_value = "p1"
        p1.is_available.return_value = True
        p1.speak.return_value = AudioResponse(
            provider_name="p1", audio_data=b"ok", audio_format="mp3"
        )

        svc = AudioService(
            tts_providers=[p1],
            circuit_breaker_threshold=1,
            circuit_breaker_cooldown=0.02,  # 20ms
        )
        health = svc._get_health("p1")

        # Força circuit aberto manualmente
        health.record_failure(cooldown_seconds=0.02, threshold=1)
        assert health.is_open() is True

        time.sleep(0.03)  # espera cooldown expirar

        resp = svc.speak(_TTS_REQ)
        assert resp.provider_name == "p1"

    def test_success_resets_health_in_service(self):
        p1 = _tts("p1")
        svc = AudioService(tts_providers=[p1])
        health = svc._get_health("p1")
        health.consecutive_failures = 2

        svc.speak(_TTS_REQ)

        assert health.consecutive_failures == 0
        assert health.total_successes == 1


# ── fallback_chain no AudioResponse ──────────────────────────────────────────

class TestFallbackChain:
    def test_tts_chain_has_single_success_entry(self):
        p1 = _tts("pyttsx3")
        svc = AudioService(tts_providers=[p1])

        resp = svc.speak(_TTS_REQ)

        assert len(resp.fallback_chain) == 1
        assert resp.fallback_chain[0]["provider"] == "pyttsx3"
        assert resp.fallback_chain[0]["success"] is True

    def test_tts_chain_records_failure_then_success(self):
        p1 = _tts("p1", fail=True)
        p2 = _tts("p2")
        svc = AudioService(tts_providers=[p1, p2])

        resp = svc.speak(_TTS_REQ)

        assert len(resp.fallback_chain) == 2
        assert resp.fallback_chain[0]["provider"] == "p1"
        assert resp.fallback_chain[0]["success"] is False
        assert "error" in resp.fallback_chain[0]
        assert resp.fallback_chain[1]["provider"] == "p2"
        assert resp.fallback_chain[1]["success"] is True

    def test_tts_chain_records_skipped_circuit(self):
        p1 = _tts("p1", fail=True)
        p2 = _tts("p2")
        svc = AudioService(tts_providers=[p1, p2], circuit_breaker_threshold=1)

        svc.speak(_TTS_REQ)  # p1 falha → circuit abre
        resp = svc.speak(_TTS_REQ)  # p1 skipped

        skipped = [e for e in resp.fallback_chain if e.get("skipped")]
        assert len(skipped) == 1
        assert skipped[0]["provider"] == "p1"
        assert skipped[0]["reason"] == "circuit_open"

    def test_stt_chain_records_failure_then_success(self):
        p1 = _stt("p1", fail=True)
        p2 = _stt("p2")
        svc = AudioService(stt_providers=[p1, p2])

        resp = svc.transcribe(_STT_REQ)

        assert resp.fallback_chain[0]["provider"] == "p1"
        assert resp.fallback_chain[0]["success"] is False
        assert resp.fallback_chain[1]["provider"] == "p2"
        assert resp.fallback_chain[1]["success"] is True

    def test_default_fallback_chain_empty_before_call(self):
        """AudioResponse criado diretamente deve ter fallback_chain vazio."""
        resp = AudioResponse(provider_name="p1")
        assert resp.fallback_chain == []


# ── Health refletida no status() ─────────────────────────────────────────────

class TestStatusWithHealth:
    def test_status_reflects_failures(self):
        p1 = _tts("p1", fail=True)
        p2 = _tts("p2")
        svc = AudioService(tts_providers=[p1, p2])

        svc.speak(_TTS_REQ)

        status = svc.status()
        p1_status = next(s for s in status["tts"] if s["name"] == "p1")
        assert p1_status["total_failures"] == 1
        assert p1_status["consecutive_failures"] == 1

    def test_status_shows_circuit_open(self):
        p1 = _tts("p1", fail=True)
        p2 = _tts("p2")
        svc = AudioService(tts_providers=[p1, p2], circuit_breaker_threshold=1)

        svc.speak(_TTS_REQ)  # p1 falha → circuit abre

        status = svc.status()
        p1_status = next(s for s in status["tts"] if s["name"] == "p1")
        assert p1_status["circuit_open"] is True

    def test_status_shows_successes(self):
        p1 = _tts("p1")
        svc = AudioService(tts_providers=[p1])

        svc.speak(_TTS_REQ)
        svc.speak(_TTS_REQ)

        status = svc.status()
        assert status["tts"][0]["total_successes"] == 2
        assert status["tts"][0]["circuit_open"] is False
