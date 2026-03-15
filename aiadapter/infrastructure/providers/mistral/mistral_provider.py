"""
Provider Mistral AI - Modelos de alta qualidade com free tier.
Free tier: La Plateforme com créditos iniciais.
Modelos: mistral-small, mistral-medium, mistral-large, open-mistral (gratuito)

API compatível com OpenAI SDK via base_url.
"""
from collections.abc import Generator

from aiadapter.core.entities.aiprovidermedata import AIProviderMetadata
from aiadapter.core.entities.airequest import AIRequest
from aiadapter.core.entities.airesponse import AIResponse
from aiadapter.core.enums.aicapability import AICapability
from aiadapter.core.interfaces.provider import AIProvider

DEFAULT_MODEL = "mistral-small-latest"

MISTRAL_PRICING = {
    "open-mistral-7b": 0.25,
    "open-mixtral-8x7b": 0.70,
    "open-mixtral-8x22b": 2.0,
    "mistral-small-latest": 0.60,
    "mistral-medium-latest": 2.7,
    "mistral-large-latest": 8.0,
    "codestral-latest": 0.60,
}


class MistralProvider(AIProvider):
    """
    Provider para a API da Mistral AI.
    Usa SDK oficial ou OpenAI-compat via base_url.
    """

    def __init__(self, api_key: str):
        try:
            from mistralai import Mistral
            self._client = Mistral(api_key=api_key)
            self._use_sdk = True
        except ImportError:
            from openai import OpenAI
            self._client = OpenAI(
                api_key=api_key,
                base_url="https://api.mistral.ai/v1",
            )
            self._use_sdk = False

    def generate(self, request: AIRequest) -> AIResponse | Generator[AIResponse, None, None]:
        model = request.model or DEFAULT_MODEL
        messages = request.messages or [{"role": "user", "content": request.prompt}]

        if self._use_sdk:
            return self._generate_sdk(request, model, messages)
        else:
            return self._generate_openai_compat(request, model, messages)

    def _generate_sdk(self, request: AIRequest, model: str, messages: list) -> AIResponse | Generator:
        if request.stream:
            return self._stream_sdk(model, messages, request)

        response = self._client.chat.complete(
            model=model,
            messages=messages,
            temperature=request.temperature,
            max_tokens=request.max_tokens,
        )
        tokens = response.usage.total_tokens if response.usage else 0
        return AIResponse(
            output=response.choices[0].message.content,
            tokens_used=tokens,
            provider_name="mistral",
            cost=self._estimate_cost(model, tokens),
        )

    def _stream_sdk(self, model: str, messages: list, request: AIRequest) -> Generator:
        with self._client.chat.stream(
            model=model,
            messages=messages,
            temperature=request.temperature,
            max_tokens=request.max_tokens,
        ) as stream:
            for chunk in stream:
                if chunk.data.choices and chunk.data.choices[0].delta.content:
                    yield AIResponse(
                        output=chunk.data.choices[0].delta.content,
                        tokens_used=0,
                        provider_name="mistral",
                        cost=0.0,
                        is_streaming_chunk=True,
                    )

    def _generate_openai_compat(self, request: AIRequest, model: str, messages: list) -> AIResponse | Generator:
        kwargs = {
            "model": model,
            "messages": messages,
            "temperature": request.temperature,
            "max_tokens": request.max_tokens,
            "stream": request.stream,
        }
        response = self._client.chat.completions.create(**kwargs)
        if request.stream:
            return self._stream_openai_compat(response, model)
        tokens = response.usage.total_tokens if response.usage else 0
        return AIResponse(
            output=response.choices[0].message.content,
            tokens_used=tokens,
            provider_name="mistral",
            cost=self._estimate_cost(model, tokens),
        )

    def _stream_openai_compat(self, stream_response, model: str) -> Generator:
        for chunk in stream_response:
            if chunk.choices and chunk.choices[0].delta.content:
                yield AIResponse(
                    output=chunk.choices[0].delta.content,
                    tokens_used=0,
                    provider_name="mistral",
                    cost=0.0,
                    is_streaming_chunk=True,
                )

    def supports(self, capability: AICapability) -> bool:
        return capability in {AICapability.TEXT, AICapability.FUNCTION_CALLING}

    def get_metadata(self) -> AIProviderMetadata:
        return AIProviderMetadata(
            name="mistral",
            models=list(MISTRAL_PRICING.keys()),
            supports_streaming=True,
            cost_per_1k_tokens=0.0006,
            avg_latency_ms=900,
            capabilities=["text", "function_calling"],
        )

    def _estimate_cost(self, model: str, tokens: int) -> float:
        rate_per_1m = MISTRAL_PRICING.get(model, 0.60)
        return (tokens / 1_000_000) * rate_per_1m
