from abc import ABC, abstractmethod

from aiadapter.core.entities.airequest import AIRequest
from aiadapter.core.interfaces.provider import AIProvider


class AIRouter(ABC):

    @abstractmethod
    def route(self, request: AIRequest) -> list[AIProvider]:
        pass
