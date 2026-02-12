from abc import ABC, abstractmethod
from aiadapter.core.entities.aiprovidermedata import AIProviderMetadata
from aiadapter.core.entities.airequest import AIRequest

class AIPolicy(ABC):

    @abstractmethod
    def is_allowed(self, request: AIRequest) -> bool:
        pass
