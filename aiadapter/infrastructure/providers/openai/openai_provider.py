from aiadapter.core.interfaces.provider import AIProvider
from aiadapter.core.entities.airequest import AIRequest
from aiadapter.core.entities.airesponse import AIResponse
from aiadapter.core.entities.aiprovidermedata import AIProviderMetadata
from aiadapter.core.enums.aicapability import AICapability


class OpenAIProvider(AIProvider):

    def __init__(self, client):
        self._client = client

    def generate(self, request: AIRequest) -> AIResponse | Generator[AIResponse, None, None]:
        response = self._client.chat.completions.create(
            model=request.model,
            messages=request.messages,
            temperature=request.temperature,
            stream=request.stream,
            tools=request.tools,
        )

        if request.stream:
            return self._generate_stream(response)
        else:
            return AIResponse(
                output=response.choices[0].message.content,
                tokens_used=response.usage.total_tokens,
                provider_name="openai",
                cost=0.0, # TODO: Calculate cost
                tool_calls=response.choices[0].message.tool_calls
            )

    # 👇 IMPLEMENTAÇÃO OBRIGATÓRIA
    def supports(self, capability: AICapability) -> bool:
        supported = {
            AICapability.TEXT,
            AICapability.FUNCTION_CALLING,
        }
        return capability in supported

    # 👇 IMPLEMENTAÇÃO OBRIGATÓRIA
    def _generate_stream(self, stream_response) -> Generator[AIResponse, None, None]:
        for chunk in stream_response:
            if chunk.choices and chunk.choices[0].delta.content:
                yield AIResponse(
                    output=chunk.choices[0].delta.content,
                    tokens_used=0, # Tokens used will be calculated at the end of the stream
                    provider_name="openai",
                    cost=0.0, # Cost will be calculated at the end of the stream
                    is_streaming_chunk=True,
                    tool_calls=chunk.choices[0].delta.tool_calls
                )

    def get_metadata(self) -> AIProviderMetadata:
        return AIProviderMetadata(
            name="openai",
            models=["gpt-4o", "gpt-4o-mini"],
            supports_streaming=True
        )
