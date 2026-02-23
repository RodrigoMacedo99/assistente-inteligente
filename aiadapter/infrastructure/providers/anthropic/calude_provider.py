from aiadapter.core.interfaces.provider import AIProvider
from aiadapter.core.entities.airequest import AIRequest
from aiadapter.core.entities.airesponse import AIResponse
from aiadapter.core.entities.aiprovidermedata import AIProviderMetadata
from aiadapter.core.enums.aicapability import AICapability
from typing import List, Dict, Any, Generator


class ClaudeProvider(AIProvider):

    def _generate_stream(self, stream_response) -> Generator[AIResponse, None, None]:
        for chunk in stream_response:
            if chunk.type == "content_block_delta" and chunk.delta.text:
                yield AIResponse(
                    output=chunk.delta.text,
                    tokens_used=0, # Tokens used will be calculated at the end of the stream
                    provider_name="anthropic",
                    cost=0.0, # Cost will be calculated at the end of the stream
                    is_streaming_chunk=True
                )
            elif chunk.type == "message_delta" and chunk.delta.tool_calls:
                yield AIResponse(
                    output=None,
                    tokens_used=0,
                    provider_name="anthropic",
                    cost=0.0,
                    is_streaming_chunk=True,
                    tool_calls=chunk.delta.tool_calls
                )

    def supports(self, capability: AICapability) -> bool:
        supported = {
            AICapability.TEXT,
            AICapability.FUNCTION_CALLING,
        }
        return capability in supported

    def get_metadata(self) -> AIProviderMetadata:
        return AIProviderMetadata(
            name="anthropic",
            models=["claude-3-opus-20240229", "claude-3-sonnet-20240229", "claude-3-haiku-20240307"],
            supports_streaming=True
        )

    def __init__(self, client):
        self._client = client

    def generate(self, request: AIRequest) -> AIResponse | Generator[AIResponse, None, None]:
        response = self._client.messages.create(
            model=request.model,
            messages=request.messages,
            max_tokens=request.max_tokens,
            stream=request.stream,
            tools=request.tools,
        )

        if request.stream:
            return self._generate_stream(response)
        else:
            return AIResponse(
                output=response.content[0].text,
                tokens_used=response.usage.input_tokens + response.usage.output_tokens,
                provider_name="anthropic",
                cost=0.0, # TODO: Calculate cost
                tool_calls=response.tool_calls
            )