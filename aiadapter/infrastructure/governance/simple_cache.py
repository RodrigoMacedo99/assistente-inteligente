from typing import Optional, Dict
from aiadapter.core.interfaces.cache import AICache
from aiadapter.core.entities.airequest import AIRequest
from aiadapter.core.entities.airesponse import AIResponse

class SimpleCache(AICache):
    def __init__(self):
        self._cache: Dict[str, AIResponse] = {}

    def get(self, request: AIRequest) -> Optional[AIResponse]:
        # For simplicity, using prompt as key. In a real scenario, a more robust hashing of the request would be used.
        key = request.prompt
        return self._cache.get(key)

    def set(self, request: AIRequest, response: AIResponse) -> None:
        key = request.prompt
        self._cache[key] = response
