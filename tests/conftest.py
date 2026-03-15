"""
Fixtures compartilhadas entre todos os testes.
"""

from unittest.mock import MagicMock

import pytest

from aiadapter.core.entities.aiprovidermedata import AIProviderMetadata
from aiadapter.core.entities.airequest import AIRequest
from aiadapter.core.entities.airesponse import AIResponse
from aiadapter.core.interfaces.provider import AIProvider

# ─── Entidades base ────────────────────────────────────────────────────────────


@pytest.fixture
def sample_request() -> AIRequest:
    return AIRequest(
        prompt="Qual é a capital do Brasil?",
        difficulty="easy",
        complexity=0.1,
        priority="normal",
        max_cost="free",
        client_id="test-tenant",
        max_tokens=256,
    )


@pytest.fixture
def sample_request_hard() -> AIRequest:
    return AIRequest(
        prompt="Projete uma arquitetura de event sourcing para um sistema bancário",
        difficulty="expert",
        complexity=0.95,
        priority="high",
        max_cost="high",
        client_id="test-tenant",
        max_tokens=2048,
    )


@pytest.fixture
def sample_response() -> AIResponse:
    return AIResponse(
        provider_name="mock_provider",
        tokens_used=42,
        cost=0.000042,
        output="Brasília é a capital do Brasil.",
    )


@pytest.fixture
def streaming_chunks() -> list[AIResponse]:
    return [
        AIResponse(
            provider_name="mock_provider",
            tokens_used=0,
            cost=0.0,
            output="Brasília",
            is_streaming_chunk=True,
        ),
        AIResponse(
            provider_name="mock_provider",
            tokens_used=0,
            cost=0.0,
            output=" é a capital",
            is_streaming_chunk=True,
        ),
        AIResponse(
            provider_name="mock_provider",
            tokens_used=0,
            cost=0.0,
            output=" do Brasil.",
            is_streaming_chunk=True,
        ),
    ]


# ─── Mock Provider ─────────────────────────────────────────────────────────────


@pytest.fixture
def mock_provider(sample_response) -> MagicMock:
    """Provider mock que sempre retorna sample_response."""
    provider = MagicMock(spec=AIProvider)
    provider.generate.return_value = sample_response
    provider.get_metadata.return_value = AIProviderMetadata(
        name="mock_provider",
        models=["mock-model"],
        supports_streaming=True,
        cost_per_1k_tokens=0.001,
    )
    provider.supports.return_value = True
    return provider


@pytest.fixture
def failing_provider() -> MagicMock:
    """Provider mock que sempre lança exceção."""
    provider = MagicMock(spec=AIProvider)
    provider.generate.side_effect = ConnectionError("API indisponível")
    provider.get_metadata.return_value = AIProviderMetadata(
        name="failing_provider",
        models=["fail-model"],
    )
    provider.supports.return_value = True
    return provider


@pytest.fixture
def mock_provider_factory():
    """Fábrica para criar providers mock com nome customizado."""

    def _factory(name: str, response: AIResponse = None) -> MagicMock:
        p = MagicMock(spec=AIProvider)
        p.generate.return_value = response or AIResponse(
            provider_name=name, tokens_used=10, cost=0.001, output=f"Resposta de {name}"
        )
        p.get_metadata.return_value = AIProviderMetadata(name=name, models=[f"{name}-model"])
        p.supports.return_value = True
        return p

    return _factory
