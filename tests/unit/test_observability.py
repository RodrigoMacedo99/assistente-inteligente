"""
Testes do LoggerObservability — logging estruturado de requests e responses.
"""

import logging

import pytest

from aiadapter.core.entities.airequest import AIRequest
from aiadapter.core.entities.airesponse import AIResponse
from aiadapter.infrastructure.governance.logger_observability import LoggerObservability


@pytest.fixture
def obs() -> LoggerObservability:
    return LoggerObservability()


@pytest.fixture
def req() -> AIRequest:
    return AIRequest(
        prompt="Teste de log",
        model="gpt-4o-mini",
        difficulty="medium",
        complexity=0.5,
        priority="normal",
        max_cost="low",
        client_id="tenant-log",
        max_tokens=512,
    )


@pytest.fixture
def resp() -> AIResponse:
    return AIResponse(
        provider_name="groq",
        tokens_used=123,
        cost=0.0001,
        output="Resposta de teste",
    )


class TestLoggerObservability:
    def test_log_request_nao_lanca(self, obs, req):
        obs.log_request(req)  # Não deve lançar

    def test_log_response_nao_lanca(self, obs, resp):
        obs.log_response(resp)  # Não deve lançar

    def test_log_error_nao_lanca(self, obs):
        obs.log_error("Erro de teste")

    def test_log_info_nao_lanca(self, obs):
        obs.log_info("Mensagem informativa")

    def test_log_request_inclui_client_id(self, obs, req, caplog):
        with caplog.at_level(logging.INFO, logger="aiadapter"):
            obs.log_request(req)
        assert "tenant-log" in caplog.text

    def test_log_request_inclui_difficulty(self, obs, req, caplog):
        with caplog.at_level(logging.INFO, logger="aiadapter"):
            obs.log_request(req)
        assert "medium" in caplog.text

    def test_log_response_inclui_provider_name(self, obs, resp, caplog):
        with caplog.at_level(logging.INFO, logger="aiadapter"):
            obs.log_response(resp)
        assert "groq" in caplog.text

    def test_log_response_inclui_tokens(self, obs, resp, caplog):
        with caplog.at_level(logging.INFO, logger="aiadapter"):
            obs.log_response(resp)
        assert "123" in caplog.text

    def test_log_error_nivel_error(self, obs, caplog):
        with caplog.at_level(logging.ERROR, logger="aiadapter"):
            obs.log_error("conexão recusada")
        assert "conexão recusada" in caplog.text
        assert any(
            r.levelno == logging.ERROR for r in caplog.records if "conexão recusada" in r.message
        )

    def test_log_info_nivel_info(self, obs, caplog):
        with caplog.at_level(logging.INFO, logger="aiadapter"):
            obs.log_info("tool executada")
        assert "tool executada" in caplog.text

    def test_implementa_interface(self, obs):
        from aiadapter.core.interfaces.observability import AIObservability

        assert isinstance(obs, AIObservability)

    def test_usa_logger_aiadapter(self, obs):
        assert obs._logger.name == "aiadapter"

    def test_multiplas_chamadas_nao_interferem(self, obs, req, resp):
        for _ in range(5):
            obs.log_request(req)
            obs.log_response(resp)
            obs.log_error("erro recorrente")
            obs.log_info("info recorrente")
