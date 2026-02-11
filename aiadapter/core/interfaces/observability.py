from abc import ABC, abstractmethod
from aiadapter.core.entities.aiprovidermedata import AIProviderMetadata
from aiadapter.core.entities.airequest import AIRequest
from aiadapter.core.entities.airesponse import AIResponse

class AIObservability(ABC):

    @abstractmethod
    def record(self, request: AIRequest, response: AIResponse):
        pass
