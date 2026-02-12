# application/ai_service.py

from aiadapter.core.interfaces.provider import AIProvider
from aiadapter.core.interfaces.router import AIRouter
from aiadapter.core.interfaces.policy import AIPolicy
from aiadapter.core.interfaces.observability import AIObservability
from aiadapter.core.entities.airequest import AIRequest
from aiadapter.core.entities.airesponse import AIResponse


class AIService:

    def __init__(
        self,
        router: AIRouter,
        policy: AIPolicy,
        observability: AIObservability,
    ):
        self._router = router
        self._policy = policy
        self._observability = observability

    def execute(self, request: AIRequest) -> AIResponse:

        # 1️⃣ valida
        self._policy.validate(request)

        # 2️⃣ log request
        self._observability.log_request(request)

        # 3️⃣ escolhe provider
        provider = self._router.route(request)

        # 4️⃣ executa
        response = provider.generate(request)

        # 5️⃣ log response
        self._observability.log_response(response)

        return response
