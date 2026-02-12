from aiadapter.core.interfaces.provider import AIProvider
from aiadapter.core.entities.airequest import AIRequest
from aiadapter.core.entities.airesponse import AIResponse


class LocalProvider(AIProvider):

    def __init__(self, model):
        self._model = model

    def generate(self, request: AIRequest) -> AIResponse:
        output = self._model.generate(request.prompt)

        return AIResponse(
            content=output,
            model="local-model",
            provider="local"
        )
