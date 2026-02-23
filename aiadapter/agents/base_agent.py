from abc import ABC, abstractmethod
from typing import Any, Dict, List, Optional
from aiadapter.core.entities.airequest import AIRequest
from aiadapter.core.entities.airesponse import AIResponse
from aiadapter.application.ai_service import AIService

class BaseAgent(ABC):
    """
    Base class for AI agents that use the AIService to generate responses.
    Agents can have memory, tools, and specific behaviors.
    """

    def __init__(self, name: str, ai_service: AIService, system_prompt: Optional[str] = None):
        self.name = name
        self.ai_service = ai_service
        self.system_prompt = system_prompt
        self.conversation_history: List[Dict[str, str]] = []

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

    def get_conversation_history(self) -> List[Dict[str, str]]:
        """
        Get the conversation history.
        """
        return self.conversation_history

    def clear_history(self):
        """
        Clear the conversation history.
        """
        self.conversation_history = []

    def _build_messages(self, user_input: str) -> List[Dict[str, str]]:
        """
        Build the messages list for the AI request, including system prompt and conversation history.
        """
        messages = []
        
        if self.system_prompt:
            messages.append({"role": "system", "content": self.system_prompt})
        
        messages.extend(self.conversation_history)
        messages.append({"role": "user", "content": user_input})
        
        return messages
