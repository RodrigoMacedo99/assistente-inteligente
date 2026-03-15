from abc import ABC, abstractmethod
from typing import Any


class AITool(ABC):

    @abstractmethod
    def get_name(self) -> str:
        pass

    @abstractmethod
    def get_description(self) -> str:
        pass

    @abstractmethod
    def get_parameters(self) -> dict[str, Any]:
        pass

    @abstractmethod
    def execute(self, **kwargs) -> Any:
        pass
