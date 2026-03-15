"""
Provider DeepSeek - Modelos de altíssima qualidade com custo extremamente baixo.
API 100% compatível com OpenAI SDK.

Preços (USD por 1M tokens):
  deepseek-chat   : $0.14 input / $0.28 output
  deepseek-reasoner: $0.55 input / $2.19 output (CoT - chain of thought)

Free tier: $5 de crédito no cadastro.
"""

from collections.abc import Generator

from aiadapter.core.entities.aiprovidermedata import AIProviderMetadata
from aiadapter.core.entities.airequest import AIRequest
from aiadapter.core.entities.airesponse import AIResponse
from aiadapter.core.enums.aicapability import AICapability
from aiadapter.core.interfaces.provider import AIProvider

DEFAULT_MODEL = "deepseek-chat"

DEEPSEEK_PRICING = {
    "deepseek-chat": (0.14, 0.28),  # (input, output) USD/1M tokens
    "deepseek-reasoner": (0.55, 2.19),  # CoT model, mais poderoso
}


class DeepSeekProvider(AIProvider):
    """
    Provider DeepSeek via API OpenAI-compatível.
    Excelente custo-benefício - qualidade próxima ao GPT-4 com 10x menos custo.
    """

    def __init__(self, api_key: str):
        from openai import OpenAI

        self._client = OpenAI(
            api_key=api_key,
            base_url="https://api.deepseek.com",
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
        if request.tools:
            kwargs["tools"] = request.tools

        response = self._client.chat.completions.create(**kwargs)

        if request.stream:
            return self._generate_stream(response, model)

        input_tokens = response.usage.prompt_tokens if response.usage else 0
        output_tokens = response.usage.completion_tokens if response.usage else 0

        return AIResponse(
            output=response.choices[0].message.content,
            tokens_used=input_tokens + output_tokens,
            provider_name="deepseek",
            cost=self._estimate_cost(model, input_tokens, output_tokens),
        )

    def _generate_stream(self, stream_response, model: str) -> Generator[AIResponse, None, None]:
        for chunk in stream_response:
            if chunk.choices and chunk.choices[0].delta.content:
                yield AIResponse(
                    output=chunk.choices[0].delta.content,
                    tokens_used=0,
                    provider_name="deepseek",
                    cost=0.0,
                    is_streaming_chunk=True,
                )

    def supports(self, capability: AICapability) -> bool:
        return capability in {AICapability.TEXT, AICapability.FUNCTION_CALLING}

    def get_metadata(self) -> AIProviderMetadata:
        return AIProviderMetadata(
            name="deepseek",
            models=list(DEEPSEEK_PRICING.keys()),
            supports_streaming=True,
            cost_per_1k_tokens=0.00028,
            avg_latency_ms=1000,
            capabilities=["text", "function_calling"],
        )

    def _estimate_cost(self, model: str, input_tokens: int, output_tokens: int) -> float:
        input_rate, output_rate = DEEPSEEK_PRICING.get(model, (0.14, 0.28))
        return (input_tokens / 1_000_000) * input_rate + (output_tokens / 1_000_000) * output_rate
