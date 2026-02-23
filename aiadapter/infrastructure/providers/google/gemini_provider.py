from aiadapter.core.interfaces.provider import AIProvider
from aiadapter.core.entities.airequest import AIRequest
from aiadapter.core.entities.airesponse import AIResponse
from aiadapter.core.entities.aiprovidermedata import AIProviderMetadata
from aiadapter.core.enums.aicapability import AICapability
from typing import List, Dict, Any, Generator
import google.generativeai as genai

class GeminiProvider(AIProvider):

    def __init__(self, api_key: str):
        genai.configure(api_key=api_key)
        self._client = genai.GenerativeModel('gemini-pro') # Default model

    def generate(self, request: AIRequest) -> AIResponse | Generator[AIResponse, None, None]:
        # Gemini expects messages in a specific format
        formatted_messages = []
        if request.messages:
            for msg in request.messages:
                role = "user" if msg["role"] == "user" else "model"
                formatted_messages.append({"role": role, "parts": [msg["content"]]})
        else:
            formatted_messages.append({"role": "user", "parts": [request.prompt]})

        if request.stream:
            return self._generate_stream(request, formatted_messages)
        else:
            response = self._client.generate_content(
                formatted_messages,
                generation_config=genai.GenerationConfig(
                    temperature=request.temperature,
                    max_output_tokens=request.max_tokens
                )
            )
            return AIResponse(
                output=response.text,
                tokens_used=0, # Gemini API does not directly provide token usage in this response type
                provider_name="gemini",
                cost=0.0 # TODO: Calculate cost
            )

    def _generate_stream(self, request: AIRequest, formatted_messages: List[Dict[str, Any]]) -> Generator[AIResponse, None, None]:
        stream_response = self._client.generate_content(
            formatted_messages,
            generation_config=genai.GenerationConfig(
                temperature=request.temperature,
                max_output_tokens=request.max_tokens
            ),
            stream=True
        )
        for chunk in stream_response:
            if chunk.text:
                yield AIResponse(
                    output=chunk.text,
                    tokens_used=0, # Tokens used will be calculated at the end of the stream
                    provider_name="gemini",
                    cost=0.0, # Cost will be calculated at the end of the stream
                    is_streaming_chunk=True
                )

    def supports(self, capability: AICapability) -> bool:
        supported = {
            AICapability.TEXT,
        }
        return capability in supported

    def get_metadata(self) -> AIProviderMetadata:
        return AIProviderMetadata(
            name="gemini",
            models=["gemini-pro"],
            supports_streaming=True
        )