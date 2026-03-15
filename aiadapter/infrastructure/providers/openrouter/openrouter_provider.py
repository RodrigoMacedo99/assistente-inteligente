"""
Provider OpenRouter - Agregador de modelos com muitas opções GRATUITAS.
API compatível com OpenAI SDK.

Modelos gratuitos disponíveis (sem custo):
  - meta-llama/llama-3.2-3b-instruct:free
  - meta-llama/llama-3.2-1b-instruct:free
  - google/gemma-2-9b-it:free
  - mistralai/mistral-7b-instruct:free
  - microsoft/phi-3-mini-128k-instruct:free
  - nousresearch/hermes-3-llama-3.1-405b:free
  - huggingfaceh4/zephyr-7b-beta:free

Free tier: ~200 req/dia com modelos gratuitos, sem cartão de crédito.
"""

from collections.abc import Generator

from aiadapter.core.entities.aiprovidermedata import AIProviderMetadata
from aiadapter.core.entities.airequest import AIRequest
from aiadapter.core.entities.airesponse import AIResponse
from aiadapter.core.enums.aicapability import AICapability
from aiadapter.core.interfaces.provider import AIProvider

DEFAULT_MODEL = "meta-llama/llama-3.2-3b-instruct:free"

# Modelos gratuitos no OpenRouter (sufixo :free = sem custo)
FREE_MODELS = [
    "meta-llama/llama-3.2-3b-instruct:free",
    "meta-llama/llama-3.2-1b-instruct:free",
    "google/gemma-2-9b-it:free",
    "mistralai/mistral-7b-instruct:free",
    "microsoft/phi-3-mini-128k-instruct:free",
    "nousresearch/hermes-3-llama-3.1-405b:free",
    "huggingfaceh4/zephyr-7b-beta:free",
    "qwen/qwen-2-7b-instruct:free",
]

# Modelos pagos de alta qualidade disponíveis via OpenRouter
PAID_MODELS = [
    "anthropic/claude-3.5-sonnet",
    "openai/gpt-4o",
    "openai/gpt-4o-mini",
    "google/gemini-1.5-pro",
    "meta-llama/llama-3.1-70b-instruct",
    "deepseek/deepseek-chat",
]


class OpenRouterProvider(AIProvider):
    """
    Provider OpenRouter - Acessa dezenas de modelos via API unificada.
    Prioriza modelos gratuitos por padrão.
    """

    def __init__(
        self, api_key: str, site_url: str = "http://localhost", site_name: str = "AI Adapter"
    ):
        from openai import OpenAI

        self._client = OpenAI(
            api_key=api_key,
            base_url="https://openrouter.ai/api/v1",
            default_headers={
                "HTTP-Referer": site_url,
                "X-Title": site_name,
            },
        )

    def generate(self, request: AIRequest) -> AIResponse | Generator[AIResponse, None, None]:
        model = request.model or DEFAULT_MODEL
        messages = request.messages or [{"role": "user", "content": request.prompt}]

        kwargs = {
            "model": model,
            "messages": messages,
            "temperature": request.temperature,
            "max_tokens": request.max_tokens,
            "stream": request.stream,
        }

        response = self._client.chat.completions.create(**kwargs)

        if request.stream:
            return self._generate_stream(response, model)

        tokens = response.usage.total_tokens if response.usage else 0
        is_free = model.endswith(":free")
        cost = 0.0 if is_free else self._estimate_cost(model, tokens)

        return AIResponse(
            output=response.choices[0].message.content,
            tokens_used=tokens,
            provider_name="openrouter",
            cost=cost,
        )

    def _generate_stream(self, stream_response, model: str) -> Generator[AIResponse, None, None]:
        for chunk in stream_response:
            if chunk.choices and chunk.choices[0].delta.content:
                yield AIResponse(
                    output=chunk.choices[0].delta.content,
                    tokens_used=0,
                    provider_name="openrouter",
                    cost=0.0,
                    is_streaming_chunk=True,
                )

    def supports(self, capability: AICapability) -> bool:
        return capability in {AICapability.TEXT}

    def get_metadata(self) -> AIProviderMetadata:
        return AIProviderMetadata(
            name="openrouter",
            models=FREE_MODELS + PAID_MODELS,
            supports_streaming=True,
            cost_per_1k_tokens=0.0,
            avg_latency_ms=1500,
            daily_free_limit=200,
            capabilities=["text"],
        )

    def get_free_models(self) -> list[str]:
        return FREE_MODELS.copy()

    def _estimate_cost(self, model: str, tokens: int) -> float:
        # OpenRouter cobra preços variáveis; estimativa conservadora
        return (tokens / 1_000_000) * 0.5
