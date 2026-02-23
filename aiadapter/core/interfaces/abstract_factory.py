from abc import ABC, abstractmethod
from aiadapter.factory.factory_provider import AIProviderFactory


class AIProviderFactoryRegistry(ABC):

    @abstractmethod
    def get_factory(self, provider_type: str) -> AIProviderFactory:
        pass