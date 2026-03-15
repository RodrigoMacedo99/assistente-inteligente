"""
Testes do SimpleRateLimiter — controle de taxa por tenant.
"""

import time
from unittest.mock import patch

import pytest

from aiadapter.core.entities.airequest import AIRequest
from aiadapter.infrastructure.governance.simple_rate_limiter import SimpleRateLimiter


@pytest.fixture
def limiter() -> SimpleRateLimiter:
    return SimpleRateLimiter(rate_limit_per_minute=5)


@pytest.fixture
def req(request) -> AIRequest:
    client = getattr(request, "param", "tenant-a")
    return AIRequest(prompt="Teste", client_id=client)


class TestSimpleRateLimiter:
    def test_primeira_requisicao_permitida(self, limiter, req):
        assert limiter.allow_request(req) is True

    def test_abaixo_do_limite_permitido(self, limiter, req):
        for _ in range(4):
            limiter.record_request(req)
        assert limiter.allow_request(req) is True

    def test_no_limite_bloqueado(self, limiter, req):
        for _ in range(5):
            limiter.record_request(req)
        assert limiter.allow_request(req) is False

    def test_acima_do_limite_bloqueado(self, limiter, req):
        for _ in range(10):
            limiter.record_request(req)
        assert limiter.allow_request(req) is False

    def test_tenants_isolados(self, limiter):
        req_a = AIRequest(prompt="Teste", client_id="tenant-a")
        req_b = AIRequest(prompt="Teste", client_id="tenant-b")

        for _ in range(5):
            limiter.record_request(req_a)

        # Tenant A bloqueado, B ainda livre
        assert limiter.allow_request(req_a) is False
        assert limiter.allow_request(req_b) is True

    def test_janela_deslizante_libera_requisicoes_antigas(self, limiter, req):
        """Requisições com mais de 60s de idade devem ser removidas."""
        now = time.time()
        # Simula 5 requisições feitas há 61 segundos
        with patch("time.time", return_value=now - 61):
            for _ in range(5):
                limiter.record_request(req)

        # No momento atual, a janela deve ter limpado os registros antigos
        assert limiter.allow_request(req) is True

    def test_record_incrementa_contador(self, limiter, req):
        assert len(limiter.requests[req.client_id]) == 0
        limiter.record_request(req)
        assert len(limiter.requests[req.client_id]) == 1
        limiter.record_request(req)
        assert len(limiter.requests[req.client_id]) == 2

    def test_limite_customizado(self):
        limiter_alto = SimpleRateLimiter(rate_limit_per_minute=100)
        req = AIRequest(prompt="Teste", client_id="t1")
        for _ in range(99):
            limiter_alto.record_request(req)
        assert limiter_alto.allow_request(req) is True
        limiter_alto.record_request(req)
        assert limiter_alto.allow_request(req) is False

    def test_client_id_none_nao_quebra(self, limiter):
        req = AIRequest(prompt="Sem tenant")  # client_id=None
        assert limiter.allow_request(req) is True
        limiter.record_request(req)
        assert limiter.allow_request(req) is True
