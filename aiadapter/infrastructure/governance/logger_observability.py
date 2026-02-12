import logging
from aiadapter.core.interfaces.observability import AIObservability
from aiadapter.core.entities.airequest import AIRequest
from aiadapter.core.entities.airesponse import AIResponse


class LoggerObservability(AIObservability):

    def __init__(self):
        self._logger = logging.getLogger("aiadapter")

    def log_request(self, request: AIRequest):
        self._logger.info(f"Request: model={request.model}")

    def log_response(self, response: AIResponse):
        self._logger.info(f"Response: provider={response.provider}")
