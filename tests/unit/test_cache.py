"""
Testes do SimpleCache — cache em memória de respostas.
"""

import pytest

from aiadapter.core.entities.airequest import AIRequest
from aiadapter.core.entities.airesponse import AIResponse
from aiadapter.infrastructure.governance.simple_cache import SimpleCache


@pytest.fixture
def cache() -> SimpleCache:
    return SimpleCache()


@pytest.fixture
def req_a() -> AIRequest:
    return AIRequest(prompt="Qual é a capital do Brasil?")


@pytest.fixture
def req_b() -> AIRequest:
    return AIRequest(prompt="Qual é a capital da Argentina?")


@pytest.fixture
def resp_a() -> AIResponse:
    return AIResponse(provider_name="groq", tokens_used=10, output="Brasília")


@pytest.fixture
def resp_b() -> AIResponse:
    return AIResponse(provider_name="gemini", tokens_used=12, output="Buenos Aires")


class TestSimpleCache:
    def test_cache_vazio_retorna_none(self, cache, req_a):
        assert cache.get(req_a) is None

    def test_set_e_get_retornam_mesmo_objeto(self, cache, req_a, resp_a):
        cache.set(req_a, resp_a)
        resultado = cache.get(req_a)
        assert resultado is resp_a

    def test_prompts_diferentes_nao_colidem(self, cache, req_a, req_b, resp_a, resp_b):
        cache.set(req_a, resp_a)
        cache.set(req_b, resp_b)
        assert cache.get(req_a).output == "Brasília"
        assert cache.get(req_b).output == "Buenos Aires"

    def test_set_sobrescreve_entrada_existente(self, cache, req_a, resp_a):
        nova_resp = AIResponse(
            provider_name="openai", tokens_used=20, output="Brasília (atualizado)"
        )
        cache.set(req_a, resp_a)
        cache.set(req_a, nova_resp)
        assert cache.get(req_a).output == "Brasília (atualizado)"

    def test_mesmas_requests_distintas_mesmo_prompt_compartilham_cache(self, cache):
        r1 = AIRequest(prompt="Olá")
        r2 = AIRequest(prompt="Olá", temperature=0.9)  # prompt igual, campo diferente
        resp = AIResponse(provider_name="test", output="resposta")
        cache.set(r1, resp)
        # Cache usa apenas o prompt como chave
        assert cache.get(r2) is resp

    def test_cache_nao_afeta_outros_caches(self):
        c1 = SimpleCache()
        c2 = SimpleCache()
        req = AIRequest(prompt="Teste")
        resp = AIResponse(provider_name="x", output="y")
        c1.set(req, resp)
        assert c2.get(req) is None

    def test_multiplas_entradas(self, cache):
        for i in range(50):
            req = AIRequest(prompt=f"Pergunta {i}")
            resp = AIResponse(provider_name="test", output=f"Resposta {i}")
            cache.set(req, resp)

        for i in range(50):
            req = AIRequest(prompt=f"Pergunta {i}")
            assert cache.get(req).output == f"Resposta {i}"
