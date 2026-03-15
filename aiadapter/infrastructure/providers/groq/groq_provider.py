"""
Provider Groq - Inferência ultra-rápida com modelos open-source.
Free tier: ~14.400 req/dia | Latência <500ms
Modelos: llama, mixtral, gemma

API compatível com OpenAI SDK.
"""
from collections.abc import Generator

from aiadapter.core.entities.aiprovidermedata import AIProviderMetadata
from aiadapter.core.entities.airequest import AIRequest
from aiadapter.core.entities.airesponse import AIResponse
from aiadapter.core.enums.aicapability import AICapability
from aiadapter.core.interfaces.provider import AIProvider

DEFAULT_MODEL = "llama-3.1-8b-instant"

# Modelos disponíveis no Groq com custo estimado (USD por 1M tokens output)
GROQ_MODELS = {
    "llama-3.1-8b-instant": 0.08,
    "llama-3.3-70b-versatile": 0.79,
    "llama-3.1-70b-versatile": 0.79,
    "mixtral-8x7b-32768": 0.27,
    "gemma2-9b-it": 0.20,
    "llama3-8b-8192": 0.08,
    "llama3-70b-8192": 0.79,
}


class GroqProvider(AIProvider):
    """
    Provider para a API Groq (groq.com).
    Usa o SDK oficial da Groq (compatível com interface OpenAI).
    Free tier generoso com quotas diárias altas.
    """

    def __init__(self, api_key: str):
        try:
            from groq import Groq
            self._client = Groq(api_key=api_key)
        except ImportError:
            # Fallback: usa openai SDK com base_url da Groq
            from openai import OpenAI
            self._client = OpenAI(
                api_key=api_key,
                base_url="https://api.groq.com/openai/v1",
            )

    def generate(self, request: AIRequest) -> AIResponse | Generator[AIResponse, None, None]:
        model = request.model or DEFAULT_MODEL
        messages = request.messages or [{"role": "user", "content": request.prompt}]

        kwargs = {
            "model": model,
            "messages": messages,
            "temperature": request.temperature,
            "max_tokens": request.max_tokens,
            "stream": request.stream,
        }

        response = self._client.chat.completions.create(**kwargs)

        if request.stream:
            return self._generate_stream(response, model)

        tokens = response.usage.total_tokens if response.usage else 0
        return AIResponse(
            output=response.choices[0].message.content,
            tokens_used=tokens,
            provider_name="groq",
            cost=self._estimate_cost(model, tokens),
        )

    def _generate_stream(self, stream_response, model: str) -> Generator[AIResponse, None, None]:
        for chunk in stream_response:
            if chunk.choices and chunk.choices[0].delta.content:
                yield AIResponse(
                    output=chunk.choices[0].delta.content,
                    tokens_used=0,
                    provider_name="groq",
                    cost=0.0,
                    is_streaming_chunk=True,
                )

    def supports(self, capability: AICapability) -> bool:
        return capability in {AICapability.TEXT, AICapability.FUNCTION_CALLING}

    def get_metadata(self) -> AIProviderMetadata:
        return AIProviderMetadata(
            name="groq",
            models=list(GROQ_MODELS.keys()),
            supports_streaming=True,
            cost_per_1k_tokens=0.00008,
            avg_latency_ms=300,
            daily_free_limit=14400,
            capabilities=["text", "function_calling"],
        )

    def _estimate_cost(self, model: str, tokens: int) -> float:
        rate_per_1m = GROQ_MODELS.get(model, 0.08)
        return (tokens / 1_000_000) * rate_per_1m
