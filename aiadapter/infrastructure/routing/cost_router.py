from aiadapter.core.interfaces.router import AIRouter
from aiadapter.core.entities.airequest import AIRequest
from aiadapter.core.interfaces.provider import AIProvider
from typing import List

class CostRouter(AIRouter):

    def __init__(self, providers: dict[str, AIProvider]):
        self._providers = providers

    def route(self, request: AIRequest) -> List[AIProvider]:
        priority = request.context.get("priority") if request.context else None
        max_cost = request.context.get("max_cost") if request.context else None
        model_preference = request.context.get("model_preference") if request.context else None

        # Prioritize specific models if requested
        if model_preference and model_preference in self._providers:
            return [self._providers[model_preference]] + [p for name, p in self._providers.items() if name != model_preference]

        # Example routing logic based on priority and cost
        if priority == "low" and "ollama" in self._providers:
            return [self._providers["ollama"], self._providers["anthropic"], self._providers["gemini"], self._providers["openai"]]
        elif max_cost == "low" and "anthropic" in self._providers:
            return [self._providers["anthropic"], self._providers["gemini"], self._providers["ollama"], self._providers["openai"]]
        elif "gemini" in self._providers:
            return [self._providers["gemini"], self._providers["openai"], self._providers["anthropic"], self._providers["ollama"]]
        else:
            # Default fallback order
            return [self._providers["openai"], self._providers["anthropic"], self._providers["gemini"], self._providers["ollama"]]