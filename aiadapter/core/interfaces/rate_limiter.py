from abc import ABC, abstractmethod

from aiadapter.core.entities.airequest import AIRequest


class AIRateLimiter(ABC):

    @abstractmethod
    def allow_request(self, request: AIRequest) -> bool:
        pass

    @abstractmethod
    def record_request(self, request: AIRequest) -> None:
        pass
