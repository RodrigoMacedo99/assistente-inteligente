from abc import ABC, abstractmethod

from aiadapter.core.interfaces.provider import AIProvider


class AIProviderFactory(ABC):
    @abstractmethod
    def create(self, config: dict) -> AIProvider:
        pass
