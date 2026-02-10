from aiadapter.interfaces.provider import AIProvider
from abc import ABC, abstractmethod

class AIProviderFactory(ABC):
    @abstractmethod
    def create(self, config: dict) -> AIProvider:
        pass
