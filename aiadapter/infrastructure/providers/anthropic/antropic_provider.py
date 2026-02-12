from aiadapter.core.interfaces.provider import AIProvider
from aiadapter.core.entities.airequest import AIRequest
from aiadapter.core.entities.airesponse import AIResponse


class AnthropicProvider(AIProvider):

    def __init__(self, client):
        self._client = client

    def generate(self, request: AIRequest) -> AIResponse:
        response = self._client.messages.create(
            model=request.model,
            messages=request.messages,
            max_tokens=1024
        )

        return AIResponse(
            content=response.content[0].text,
            model=request.model,
            provider="anthropic"
        )
