# infrastructure/routing/cost_router.py

from aiadapter.core.interfaces.router import AIRouter
from aiadapter.core.entities.airequest import AIRequest
from aiadapter.core.interfaces.provider import AIProvider


class CostRouter(AIRouter):

    def __init__(self, providers: dict[str, AIProvider]):
        self._providers = providers

    def route(self, request: AIRequest) -> AIProvider:

        # exemplo simples
        if request.priority == "low":
            return self._providers["local"]

        if request.max_cost == "low":
            return self._providers["anthropic"]

        return self._providers["openai"]
