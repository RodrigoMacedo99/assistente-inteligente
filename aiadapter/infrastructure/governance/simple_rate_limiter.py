import time
from collections import defaultdict
from aiadapter.core.interfaces.rate_limiter import AIRateLimiter
from aiadapter.core.entities.airequest import AIRequest

class SimpleRateLimiter(AIRateLimiter):
    def __init__(self, rate_limit_per_minute: int = 60):
        self.rate_limit_per_minute = rate_limit_per_minute
        self.requests = defaultdict(list)

    def allow_request(self, request: AIRequest) -> bool:
        current_time = time.time()
        # Remove requests older than 1 minute
        self.requests[request.client_id] = [t for t in self.requests[request.client_id] if current_time - t < 60]
        return len(self.requests[request.client_id]) < self.rate_limit_per_minute

    def record_request(self, request: AIRequest) -> None:
        self.requests[request.client_id].append(time.time())
