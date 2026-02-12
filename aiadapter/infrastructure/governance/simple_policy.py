from aiadapter.core.interfaces.policy import AIPolicy
from aiadapter.core.entities.airequest import AIRequest


class SimplePolicy(AIPolicy):

    def validate(self, request: AIRequest) -> None:

        if len(request.prompt) > 5000:
            raise ValueError("Prompt too long")

        if "forbidden_word" in request.prompt:
            raise ValueError("Forbidden content detected")
