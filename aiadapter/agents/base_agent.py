from abc import ABC, abstractmethod

from aiadapter.application.ai_service import AIService
from aiadapter.core.entities.airesponse import AIResponse


class BaseAgent(ABC):
    """
    Base class for AI agents that use the AIService to generate responses.
    Agents can have memory, tools, and specific behaviors.
    """

    def __init__(self, name: str, ai_service: AIService, system_prompt: str | None = None):
        self.name = name
        self.ai_service = ai_service
        self.system_prompt = system_prompt
        self.conversation_history: list[dict[str, str]] = []

    @abstractmethod
    def process(self, user_input: str) -> AIResponse:
        """
        Process user input and generate a response.
        """
        pass

    def add_to_history(self, role: str, content: str):
        """
        Add a message to the conversation history.
        """
        self.conversation_history.append({"role": role, "content": content})

    def get_conversation_history(self) -> list[dict[str, str]]:
        """
        Get the conversation history.
        """
        return self.conversation_history

    def clear_history(self):
        """
        Clear the conversation history.
        """
        self.conversation_history = []

    def _build_messages(self, user_input: str) -> list[dict[str, str]]:
        """
        Build the messages list for the AI request, including system prompt and conversation history.
        """
        messages = []

        if self.system_prompt:
            messages.append({"role": "system", "content": self.system_prompt})

        messages.extend(self.conversation_history)
        messages.append({"role": "user", "content": user_input})

        return messages
