from collections.abc import Generator
from typing import Any

from aiadapter.core.entities.airequest import AIRequest
from aiadapter.core.entities.airesponse import AIResponse
from aiadapter.core.interfaces.cache import AICache
from aiadapter.core.interfaces.observability import AIObservability
from aiadapter.core.interfaces.policy import AIPolicy
from aiadapter.core.interfaces.rate_limiter import AIRateLimiter
from aiadapter.core.interfaces.router import AIRouter
from aiadapter.core.interfaces.tool import AITool


class AIService:

    def __init__(
        self,
        router: AIRouter,
        policy: AIPolicy,
        observability: AIObservability,
        rate_limiter: AIRateLimiter,
        cache: AICache,
        tools: dict[str, AITool] | None = None,
    ):
        self._router = router
        self._policy = policy
        self._observability = observability
        self._rate_limiter = rate_limiter
        self._cache = cache
        self._tools = tools if tools is not None else {}

    def execute(self, request: AIRequest) -> AIResponse | Generator[AIResponse, None, None]:

        # 1️⃣ valida
        self._policy.validate(request)

        # 1.1️⃣ Rate Limiting
        if not self._rate_limiter.allow_request(request):
            raise Exception("Rate limit exceeded")
        self._rate_limiter.record_request(request)

        # 1.2️⃣ Cache
        cached_response = self._cache.get(request)
        if cached_response:
            self._observability.log_request(request)
            self._observability.log_response(cached_response)
            return cached_response

        # 2️⃣ log request
        self._observability.log_request(request)

        # 3️⃣ escolhe providers (com fallback)
        providers = self._router.route(request)
        response_or_generator = None
        selected_provider_name = ""

        for provider in providers:
            try:
                selected_provider_name = provider.get_metadata().name
                response_or_generator = provider.generate(request)
                if response_or_generator: # Se houver resposta ou gerador, sai do loop
                    break
            except Exception as e:
                self._observability.log_error(f"Provider {selected_provider_name} failed: {e}")
                continue

        if not response_or_generator:
            raise RuntimeError("All providers failed to generate a response.")

        if request.stream:
            return self._handle_streaming_response(request, response_or_generator, selected_provider_name)
        else:
            response = response_or_generator
            if response.tool_calls:
                tool_outputs = self._handle_tool_calls(response.tool_calls)
                # Here we would typically send the tool outputs back to the AI for a new response
                # For now, we'll just log them and return the original response
                self._observability.log_info(f"Tool calls executed: {tool_outputs}")

            # 5️⃣ Cache response
            self._cache.set(request, response)

            # 6️⃣ log response
            self._observability.log_response(response)
            return response

    def _handle_streaming_response(self, request: AIRequest, generator: Generator[AIResponse, None, None], provider_name: str) -> Generator[AIResponse, None, None]:
        full_response_content = ""
        total_tokens = 0
        for chunk in generator:
            full_response_content += chunk.output
            # Assuming tokens_used in chunk is for that chunk only, or 0 if not available
            # For simplicity, we'll aggregate tokens at the end or if the provider gives total
            yield chunk

        # After streaming, create a full response for caching and logging
        final_response = AIResponse(
            output=full_response_content,
            tokens_used=total_tokens, # Placeholder, actual calculation might be more complex
            provider_name=provider_name,
            cost=0.0, # Placeholder, actual calculation might be more complex
            is_streaming_chunk=False
        )
        self._cache.set(request, final_response)
        self._observability.log_response(final_response)

    def _handle_tool_calls(self, tool_calls: list[dict[str, Any]]) -> list[dict[str, Any]]:
        tool_outputs = []
        for tool_call in tool_calls:
            function_name = tool_call["function"]["name"]
            function_args = tool_call["function"]["arguments"]
            if function_name in self._tools:
                tool_instance = self._tools[function_name]
                try:
                    output = tool_instance.execute(**function_args)
                    tool_outputs.append({"tool_call_id": tool_call["id"], "output": output})
                except Exception as e:
                    self._observability.log_error(f"Error executing tool {function_name}: {e}")
                    tool_outputs.append({"tool_call_id": tool_call["id"], "error": str(e)})
            else:
                self._observability.log_error(f"Tool {function_name} not found.")
                tool_outputs.append({"tool_call_id": tool_call["id"], "error": f"Tool {function_name} not found."})
        return tool_outputs
