from aiadapter.core.interfaces.provider import AIProvider
from aiadapter.core.entities.airequest import AIRequest
from aiadapter.core.entities.airesponse import AIResponse
from aiadapter.core.entities.aiprovidermedata import AIProviderMetadata
from aiadapter.core.enums.aicapability import AICapability


class OpenAIProvider(AIProvider):

    def __init__(self, client):
        self._client = client

    def generate(self, request: AIRequest) -> AIResponse:
        response = self._client.chat.completions.create(
            model=request.model,
            messages=request.messages,
            temperature=request.temperature,
        )

        return AIResponse(
            content=response.choices[0].message.content,
            model=response.model,
            provider="openai",
            usage=response.usage.total_tokens
        )

    # 👇 IMPLEMENTAÇÃO OBRIGATÓRIA
    def supports(self, capability: AICapability) -> bool:
        supported = {
            AICapability.TEXT,
            AICapability.FUNCTION_CALLING,
        }
        return capability in supported

    # 👇 IMPLEMENTAÇÃO OBRIGATÓRIA
    def get_metadata(self) -> AIProviderMetadata:
        return AIProviderMetadata(
            name="openai",
            models=["gpt-4o", "gpt-4o-mini"],
            supports_streaming=True
        )
