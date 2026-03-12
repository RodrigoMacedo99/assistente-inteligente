from typing import List, Dict, Any, Generator, Optional
from aiadapter.core.interfaces.provider import AIProvider
from aiadapter.core.entities.airequest import AIRequest
from aiadapter.core.entities.airesponse import AIResponse
from aiadapter.core.entities.aiprovidermedata import AIProviderMetadata
from aiadapter.core.enums.aicapability import AICapability

DEFAULT_MODEL = "claude-3-haiku-20240307"


class ClaudeProvider(AIProvider):

    def __init__(self, client):
        self._client = client

    def generate(self, request: AIRequest) -> AIResponse | Generator[AIResponse, None, None]:
        model = request.model or DEFAULT_MODEL
        messages = request.messages or [{"role": "user", "content": request.prompt}]

        kwargs = {
            "model": model,
            "messages": messages,
            "max_tokens": request.max_tokens,
        }
        if request.tools:
            kwargs["tools"] = request.tools

        if request.stream:
            with self._client.messages.stream(**kwargs) as stream:
                return self._generate_stream(stream, model)

        response = self._client.messages.create(**kwargs)

        # Extrai texto e tool_use do content (lista de blocos)
        output_text = None
        tool_calls = None
        for block in response.content:
            if block.type == "text":
                output_text = block.text
            elif block.type == "tool_use":
                if tool_calls is None:
                    tool_calls = []
                tool_calls.append({
                    "id": block.id,
                    "function": {"name": block.name, "arguments": block.input},
                })

        tokens = response.usage.input_tokens + response.usage.output_tokens
        cost = self._estimate_cost(model, response.usage.input_tokens, response.usage.output_tokens)

        return AIResponse(
            output=output_text,
            tokens_used=tokens,
            provider_name="anthropic",
            cost=cost,
            tool_calls=tool_calls,
        )

    def _generate_stream(self, stream, model: str) -> Generator[AIResponse, None, None]:
        for text in stream.text_stream:
            yield AIResponse(
                output=text,
                tokens_used=0,
                provider_name="anthropic",
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
            name="anthropic",
            models=[
                "claude-3-5-sonnet-20241022",
                "claude-3-5-haiku-20241022",
                "claude-3-haiku-20240307",
                "claude-3-opus-20240229",
            ],
            supports_streaming=True,
            cost_per_1k_tokens=0.00125,
            avg_latency_ms=1200,
            capabilities=["text", "vision", "function_calling"],
        )

    def _estimate_cost(self, model: str, input_tokens: int, output_tokens: int) -> float:
        pricing = {
            "claude-3-5-sonnet-20241022": (0.003, 0.015),
            "claude-3-5-haiku-20241022": (0.001, 0.005),
            "claude-3-haiku-20240307": (0.00025, 0.00125),
            "claude-3-opus-20240229": (0.015, 0.075),
        }
        input_rate, output_rate = pricing.get(model, (0.003, 0.015))
        return (input_tokens / 1000) * input_rate + (output_tokens / 1000) * output_rate
