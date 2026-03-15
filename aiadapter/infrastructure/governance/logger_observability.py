import logging

from aiadapter.core.entities.airequest import AIRequest
from aiadapter.core.entities.airesponse import AIResponse
from aiadapter.core.interfaces.observability import AIObservability


class LoggerObservability(AIObservability):

    def __init__(self):
        self._logger = logging.getLogger("aiadapter")

    def log_request(self, request: AIRequest):
        self._logger.info(
            f"[REQUEST] client={request.client_id} model={request.model} "
            f"difficulty={request.difficulty} complexity={request.complexity:.2f} "
            f"max_cost={request.max_cost} tokens={request.max_tokens}"
        )

    def log_response(self, response: AIResponse):
        self._logger.info(
            f"[RESPONSE] provider={response.provider_name} "
            f"tokens={response.tokens_used} cost=${response.cost:.6f}"
        )

    def log_error(self, message: str):
        self._logger.error(f"[ERROR] {message}")

    def log_info(self, message: str):
        self._logger.info(f"[INFO] {message}")
