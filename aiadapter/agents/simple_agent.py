from aiadapter.agents.base_agent import BaseAgent
from aiadapter.application.ai_service import AIService
from aiadapter.core.entities.airequest import AIRequest
from aiadapter.core.entities.airesponse import AIResponse


class SimpleAgent(BaseAgent):
    """
    A simple agent that processes user input and generates responses using the AIService.
    """

    def __init__(
        self,
        name: str,
        ai_service: AIService,
        system_prompt: str | None = None,
        model: str = "gpt-4o",
        temperature: float = 0.7,
        max_tokens: int = 512,
    ):
        super().__init__(name, ai_service, system_prompt)
        self.model = model
        self.temperature = temperature
        self.max_tokens = max_tokens

    def process(self, user_input: str) -> AIResponse:
        """
        Process user input and generate a response.
        """
        # Add user input to history
        self.add_to_history("user", user_input)

        # Build messages
        messages = self._build_messages(user_input)

        # Create AI request
        request = AIRequest(
            prompt=user_input,
            messages=messages,
            temperature=self.temperature,
            max_tokens=self.max_tokens,
            context={"agent_name": self.name},
        )

        # Execute request
        response = self.ai_service.execute(request)

        # Add response to history
        if response.output:
            self.add_to_history("assistant", response.output)

        return response

    def reset(self):
        """
        Reset the agent's conversation history.
        """
        self.clear_history()
