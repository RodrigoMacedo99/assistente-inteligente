from abc import ABC, abstractmethod
from aiadapter.core.entities.aiprovidermedata import AIProviderMetadata
from aiadapter.core.entities.airequest import AIRequest
from aiadapter.core.interfaces.provider import AIProvider

class AIRouter(ABC):

    @abstractmethod
    def route(self, request: AIRequest) -> AIProvider:
        pass
