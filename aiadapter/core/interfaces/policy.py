from abc import ABC, abstractmethod
from aiadapter.core.entities.airequest import AIRequest


class AIPolicy(ABC):

    @abstractmethod
    def validate(self, request: AIRequest) -> None:
        """Valida a requisição. Lança ValueError se inválida."""
        pass
