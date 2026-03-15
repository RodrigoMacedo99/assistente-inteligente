from collections.abc import Generator

from aiadapter.core.entities.aiprovidermedata import AIProviderMetadata
from aiadapter.core.entities.airequest import AIRequest
from aiadapter.core.entities.airesponse import AIResponse
from aiadapter.core.enums.aicapability import AICapability
from aiadapter.core.interfaces.provider import AIProvider

DEFAULT_MODEL = "gpt-4o-mini"


class OpenAIProvider(AIProvider):

    def __init__(self, client):
        self._client = client

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
            return self._generate_stream(response)

        tool_calls = None
        if response.choices[0].message.tool_calls:
            tool_calls = [
                {
                    "id": tc.id,
                    "function": {"name": tc.function.name, "arguments": tc.function.arguments},
                }
                for tc in response.choices[0].message.tool_calls
            ]

        tokens = response.usage.total_tokens if response.usage else 0
        cost = self._estimate_cost(model, tokens)

        return AIResponse(
            output=response.choices[0].message.content,
            tokens_used=tokens,
            provider_name="openai",
            cost=cost,
            tool_calls=tool_calls,
        )

    def _generate_stream(self, stream_response) -> Generator[AIResponse, None, None]:
        for chunk in stream_response:
            if chunk.choices and chunk.choices[0].delta.content:
                yield AIResponse(
                    output=chunk.choices[0].delta.content,
                    tokens_used=0,
                    provider_name="openai",
                    cost=0.0,
                    is_streaming_chunk=True,
                )

    def supports(self, capability: AICapability) -> bool:
        return capability in {
            AICapability.TEXT,
            AICapability.FUNCTION_CALLING,
            AICapability.VISION,
        }

    def get_metadata(self) -> AIProviderMetadata:
        return AIProviderMetadata(
            name="openai",
            models=["gpt-4o", "gpt-4o-mini", "gpt-3.5-turbo"],
            supports_streaming=True,
            cost_per_1k_tokens=0.0006,
            avg_latency_ms=800,
            capabilities=["text", "vision", "function_calling"],
        )

    def _estimate_cost(self, model: str, tokens: int) -> float:
        pricing = {
            "gpt-4o": 0.0025,
            "gpt-4o-mini": 0.00015,
            "gpt-3.5-turbo": 0.000002,
        }
        rate = pricing.get(model, 0.001)
        return (tokens / 1000) * rate
