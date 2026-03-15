from aiadapter.core.entities.airequest import AIRequest
from aiadapter.core.entities.airesponse import AIResponse
from aiadapter.core.interfaces.cache import AICache


class SimpleCache(AICache):
    def __init__(self):
        self._cache: dict[str, AIResponse] = {}

    def get(self, request: AIRequest) -> AIResponse | None:
        # For simplicity, using prompt as key. In a real scenario, a more robust hashing of the request would be used.
        key = request.prompt
        return self._cache.get(key)

    def set(self, request: AIRequest, response: AIResponse) -> None:
        key = request.prompt
        self._cache[key] = response
