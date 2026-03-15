from abc import ABC, abstractmethod

from aiadapter.core.entities.airequest import AIRequest
from aiadapter.core.entities.airesponse import AIResponse


class AIObservability(ABC):

    @abstractmethod
    def log_request(self, request: AIRequest):
        pass

    @abstractmethod
    def log_response(self, response: AIResponse):
        pass

    @abstractmethod
    def log_error(self, message: str):
        pass

    @abstractmethod
    def log_info(self, message: str):
        pass
