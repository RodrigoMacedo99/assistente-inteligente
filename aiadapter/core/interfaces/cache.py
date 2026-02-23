from abc import ABC, abstractmethod
from typing import Optional
from aiadapter.core.entities.airequest import AIRequest
from aiadapter.core.entities.airesponse import AIResponse

class AICache(ABC):

    @abstractmethod
    def get(self, request: AIRequest) -> Optional[AIResponse]:
        pass

    @abstractmethod
    def set(self, request: AIRequest, response: AIResponse) -> None:
        pass
