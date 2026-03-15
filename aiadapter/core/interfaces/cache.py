from abc import ABC, abstractmethod

from aiadapter.core.entities.airequest import AIRequest
from aiadapter.core.entities.airesponse import AIResponse


class AICache(ABC):

    @abstractmethod
    def get(self, request: AIRequest) -> AIResponse | None:
        pass

    @abstractmethod
    def set(self, request: AIRequest, response: AIResponse) -> None:
        pass
