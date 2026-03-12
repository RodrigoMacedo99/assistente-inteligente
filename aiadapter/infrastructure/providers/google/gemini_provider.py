from typing import List, Dict, Any, Generator
from aiadapter.core.interfaces.provider import AIProvider
from aiadapter.core.entities.airequest import AIRequest
from aiadapter.core.entities.airesponse import AIResponse
from aiadapter.core.entities.aiprovidermedata import AIProviderMetadata
from aiadapter.core.enums.aicapability import AICapability

DEFAULT_MODEL = "gemini-1.5-flash"


class GeminiProvider(AIProvider):

    def __init__(self, api_key: str):
        try:
            from google import genai
            from google.genai import types as genai_types
            self._genai = genai
            self._types = genai_types
            self._client = genai.Client(api_key=api_key)
        except ImportError:
            # Fallback para SDK legado
            import google.generativeai as genai_legacy
            genai_legacy.configure(api_key=api_key)
            self._genai = None
            self._genai_legacy = genai_legacy
            self._client = None

    def generate(self, request: AIRequest) -> AIResponse | Generator[AIResponse, None, None]:
        model = request.model or DEFAULT_MODEL

        if self._client:
            return self._generate_new_sdk(request, model)
        else:
            return self._generate_legacy_sdk(request, model)

    def _generate_new_sdk(self, request: AIRequest, model: str) -> AIResponse | Generator[AIResponse, None, None]:
        contents = []
        if request.messages:
            for msg in request.messages:
                role = "user" if msg["role"] == "user" else "model"
                contents.append({"role": role, "parts": [{"text": msg["content"]}]})
        else:
            contents.append({"role": "user", "parts": [{"text": request.prompt}]})

        config = self._types.GenerateContentConfig(
            temperature=request.temperature,
            max_output_tokens=request.max_tokens,
        )

        if request.stream:
            return self._generate_stream_new(model, contents, config)

        response = self._client.models.generate_content(
            model=model,
            contents=contents,
            config=config,
        )

        tokens = 0
        if hasattr(response, "usage_metadata") and response.usage_metadata:
            tokens = response.usage_metadata.total_token_count or 0

        return AIResponse(
            output=response.text,
            tokens_used=tokens,
            provider_name="gemini",
            cost=self._estimate_cost(model, tokens),
        )

    def _generate_stream_new(self, model: str, contents, config) -> Generator[AIResponse, None, None]:
        for chunk in self._client.models.generate_content_stream(
            model=model,
            contents=contents,
            config=config,
        ):
            if chunk.text:
                yield AIResponse(
                    output=chunk.text,
                    tokens_used=0,
                    provider_name="gemini",
                    cost=0.0,
                    is_streaming_chunk=True,
                )

    def _generate_legacy_sdk(self, request: AIRequest, model: str) -> AIResponse | Generator[AIResponse, None, None]:
        client = self._genai_legacy.GenerativeModel(model)
        formatted = []
        if request.messages:
            for msg in request.messages:
                role = "user" if msg["role"] == "user" else "model"
                formatted.append({"role": role, "parts": [msg["content"]]})
        else:
            formatted.append({"role": "user", "parts": [request.prompt]})

        config = self._genai_legacy.GenerationConfig(
            temperature=request.temperature,
            max_output_tokens=request.max_tokens,
        )

        if request.stream:
            return self._stream_legacy(client, formatted, config)

        response = client.generate_content(formatted, generation_config=config)
        return AIResponse(
            output=response.text,
            tokens_used=0,
            provider_name="gemini",
            cost=0.0,
        )

    def _stream_legacy(self, client, formatted, config) -> Generator[AIResponse, None, None]:
        for chunk in client.generate_content(formatted, generation_config=config, stream=True):
            if chunk.text:
                yield AIResponse(
                    output=chunk.text,
                    tokens_used=0,
                    provider_name="gemini",
                    cost=0.0,
                    is_streaming_chunk=True,
                )

    def supports(self, capability: AICapability) -> bool:
        return capability in {AICapability.TEXT, AICapability.VISION}

    def get_metadata(self) -> AIProviderMetadata:
        return AIProviderMetadata(
            name="gemini",
            models=["gemini-1.5-flash", "gemini-1.5-pro", "gemini-2.0-flash-exp"],
            supports_streaming=True,
            cost_per_1k_tokens=0.000075,
            avg_latency_ms=600,
            daily_free_limit=1500,
            capabilities=["text", "vision"],
        )

    def _estimate_cost(self, model: str, tokens: int) -> float:
        pricing = {
            "gemini-1.5-flash": 0.000075,
            "gemini-1.5-pro": 0.00125,
            "gemini-2.0-flash-exp": 0.0,  # experimental gratuito
        }
        rate = pricing.get(model, 0.000075)
        return (tokens / 1000) * rate
