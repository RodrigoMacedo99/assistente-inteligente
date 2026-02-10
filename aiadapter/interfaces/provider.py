from abc import ABC, abstractmethod
from aiadapter.interfaces.aiprovidermedata import AIProviderMetadata
from aiadapter.interfaces.airequest import AIRequest
from aiadapter.interfaces.airesponse import AIResponse
from aiadapter.interfaces.aicapability import AICapability
from typing import List, Dict, Any


class AIProvider(ABC):

    @abstractmethod
    def generate(self, request: "AIRequest") -> "AIResponse":
        """
        Método principal para gerar uma resposta de IA com base em uma requisição.
        """
        pass

    @abstractmethod
    def get_metadata(self) -> "AIProviderMetadata":
        """
        Retorna metadados sobre o provedor, como nome, versão, latência e custo.
        """
        pass

    @abstractmethod
    def supports(self, capability: "AICapability") -> bool:
        """
        Verifica se o provedor suporta uma determinada capacidade de IA (e.g., TEXT, EMBEDDINGS).
        """
        pass