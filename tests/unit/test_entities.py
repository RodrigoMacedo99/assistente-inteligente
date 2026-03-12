"""
Testes das entidades do domínio: AIRequest, AIResponse, AIProviderMetadata, AICapability.
"""
import pytest
from dataclasses import fields

from aiadapter.core.entities.airequest import AIRequest
from aiadapter.core.entities.airesponse import AIResponse
from aiadapter.core.entities.aiprovidermedata import AIProviderMetadata
from aiadapter.core.enums.aicapability import AICapability


class TestAIRequest:
    def test_prompt_obrigatorio(self):
        req = AIRequest(prompt="Olá")
        assert req.prompt == "Olá"

    def test_defaults_aplicados(self):
        req = AIRequest(prompt="Teste")
        assert req.model is None
        assert req.messages is None
        assert req.temperature == 0.7
        assert req.max_tokens == 512
        assert req.context is None
        assert req.client_id is None
        assert req.stream is False
        assert req.tools is None
        assert req.priority == "normal"
        assert req.difficulty == "medium"
        assert req.complexity == 0.5
        assert req.max_cost == "medium"
        assert req.preferred_provider is None

    def test_campos_customizados(self):
        req = AIRequest(
            prompt="Análise complexa",
            model="gpt-4o",
            temperature=0.2,
            max_tokens=1024,
            priority="high",
            difficulty="expert",
            complexity=0.9,
            max_cost="high",
            client_id="tenant-123",
            preferred_provider="openai",
            stream=True,
        )
        assert req.model == "gpt-4o"
        assert req.temperature == 0.2
        assert req.max_tokens == 1024
        assert req.priority == "high"
        assert req.difficulty == "expert"
        assert req.complexity == 0.9
        assert req.max_cost == "high"
        assert req.client_id == "tenant-123"
        assert req.preferred_provider == "openai"
        assert req.stream is True

    def test_messages_lista(self):
        msgs = [{"role": "user", "content": "Olá"}]
        req = AIRequest(prompt="Olá", messages=msgs)
        assert req.messages == msgs

    def test_context_dict(self):
        ctx = {"session_id": "abc", "user_lang": "pt-BR"}
        req = AIRequest(prompt="Olá", context=ctx)
        assert req.context["session_id"] == "abc"

    def test_instancias_independentes(self):
        r1 = AIRequest(prompt="A")
        r2 = AIRequest(prompt="B")
        assert r1.prompt != r2.prompt


class TestAIResponse:
    def test_provider_name_obrigatorio(self):
        resp = AIResponse(provider_name="openai")
        assert resp.provider_name == "openai"

    def test_defaults_aplicados(self):
        resp = AIResponse(provider_name="groq")
        assert resp.tokens_used == 0
        assert resp.cost == 0.0
        assert resp.output is None
        assert resp.is_streaming_chunk is False
        assert resp.tool_calls is None

    def test_campos_completos(self):
        resp = AIResponse(
            provider_name="anthropic",
            tokens_used=500,
            cost=0.00125,
            output="Resposta completa aqui.",
            is_streaming_chunk=False,
            tool_calls=[{"id": "call_1", "function": {"name": "search"}}],
        )
        assert resp.tokens_used == 500
        assert resp.cost == 0.00125
        assert resp.output == "Resposta completa aqui."
        assert resp.tool_calls[0]["function"]["name"] == "search"

    def test_streaming_chunk(self):
        chunk = AIResponse(
            provider_name="groq",
            output="parte do texto",
            is_streaming_chunk=True,
        )
        assert chunk.is_streaming_chunk is True
        assert chunk.tokens_used == 0

    def test_ordering_dataclass_valido(self):
        """Garante que a ordenação dos campos não causa TypeError no Python dataclass."""
        # Este teste falha se o bug original (output antes de tokens_used) existir
        try:
            resp = AIResponse(provider_name="test")
            assert resp is not None
        except TypeError as e:
            pytest.fail(f"Dataclass AIResponse com bug de ordenação: {e}")

    def test_output_pode_ser_none(self):
        resp = AIResponse(provider_name="test", output=None)
        assert resp.output is None

    def test_custo_zero_modelos_locais(self):
        resp = AIResponse(provider_name="ollama", cost=0.0, output="texto")
        assert resp.cost == 0.0


class TestAIProviderMetadata:
    def test_name_obrigatorio(self):
        meta = AIProviderMetadata(name="groq")
        assert meta.name == "groq"

    def test_defaults(self):
        meta = AIProviderMetadata(name="test")
        assert meta.models == []
        assert meta.supports_streaming is True
        assert meta.cost_per_1k_tokens == 0.0
        assert meta.avg_latency_ms == 0
        assert meta.is_local is False
        assert meta.daily_free_limit == 0
        assert meta.capabilities == ["text"]

    def test_modelos_lista(self):
        meta = AIProviderMetadata(
            name="openai",
            models=["gpt-4o", "gpt-4o-mini"],
        )
        assert len(meta.models) == 2
        assert "gpt-4o" in meta.models

    def test_provider_local(self):
        meta = AIProviderMetadata(
            name="ollama",
            is_local=True,
            cost_per_1k_tokens=0.0,
        )
        assert meta.is_local is True
        assert meta.cost_per_1k_tokens == 0.0

    def test_quota_diaria(self):
        meta = AIProviderMetadata(
            name="groq",
            daily_free_limit=14400,
        )
        assert meta.daily_free_limit == 14400

    def test_capabilities_customizadas(self):
        meta = AIProviderMetadata(
            name="gpt-4o",
            capabilities=["text", "vision", "function_calling"],
        )
        assert "vision" in meta.capabilities
        assert "function_calling" in meta.capabilities

    def test_independencia_de_listas(self):
        """Garante que dois objetos não compartilham a mesma lista (mutable default)."""
        m1 = AIProviderMetadata(name="a")
        m2 = AIProviderMetadata(name="b")
        m1.models.append("model-x")
        assert "model-x" not in m2.models


class TestAICapability:
    def test_valores_existem(self):
        assert AICapability.TEXT.value == "text"
        assert AICapability.EMBEDDINGS.value == "embeddings"
        assert AICapability.VISION.value == "vision"
        assert AICapability.FUNCTION_CALLING.value == "function_calling"
        assert AICapability.AUDIO.value == "audio"
        assert AICapability.VIDEO.value == "video"

    def test_enum_comparacao(self):
        assert AICapability.TEXT == AICapability.TEXT
        assert AICapability.TEXT != AICapability.VISION

    def test_enum_em_set(self):
        suportadas = {AICapability.TEXT, AICapability.VISION}
        assert AICapability.TEXT in suportadas
        assert AICapability.EMBEDDINGS not in suportadas
