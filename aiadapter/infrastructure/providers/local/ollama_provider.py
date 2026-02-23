from aiadapter.core.interfaces.provider import AIProvider
from aiadapter.core.entities.airequest import AIRequest
from aiadapter.core.entities.airesponse import AIResponse
from aiadapter.core.entities.aiprovidermedata import AIProviderMetadata
from aiadapter.core.enums.aicapability import AICapability
from typing import List, Dict, Any, Generator
import requests
import json

class OllamaProvider(AIProvider):

    def __init__(self, base_url: str = "http://localhost:11434"):
        self._base_url = base_url

    def generate(self, request: AIRequest) -> AIResponse | Generator[AIResponse, None, None]:
        # Ollama expects messages in a specific format
        messages = []
        if request.messages:
            messages = request.messages
        else:
            messages.append({"role": "user", "content": request.prompt})

        payload = {
            "model": request.model if request.model else "llama3", # Default to llama3
            "messages": messages,
            "temperature": request.temperature,
            "options": {
                "num_predict": request.max_tokens
            },
            "stream": request.stream
        }

        if request.stream:
            return self._generate_stream(payload)
        else:
            response = requests.post(f"{self._base_url}/api/chat", json=payload)
            response.raise_for_status()
            data = response.json()
            
            return AIResponse(
                output=data["message"]["content"],
                tokens_used=data["prompt_eval_count"] + data["eval_count"], # Approximation
                provider_name="ollama",
                cost=0.0 # Local models usually have no direct cost
            )

    def _generate_stream(self, payload: Dict[str, Any]) -> Generator[AIResponse, None, None]:
        with requests.post(f"{self._base_url}/api/chat", json=payload, stream=True) as response:
            response.raise_for_status()
            for chunk in response.iter_lines():
                if chunk:
                    decoded_chunk = chunk.decode("utf-8")
                    try:
                        data = json.loads(decoded_chunk)
                        if "content" in data["message"] and data["message"]["content"]:
                            yield AIResponse(
                                output=data["message"]["content"],
                                tokens_used=0, # Tokens used will be calculated at the end of the stream
                                provider_name="ollama",
                                cost=0.0, # Cost will be calculated at the end of the stream
                                is_streaming_chunk=True
                            )
                    except json.JSONDecodeError:
                        # Handle cases where chunk is not a complete JSON object
                        pass

    def supports(self, capability: AICapability) -> bool:
        supported = {
            AICapability.TEXT,
        }
        return capability in supported

    def get_metadata(self) -> AIProviderMetadata:
        return AIProviderMetadata(
            name="ollama",
            models=["llama3", "mistral", "gemma"], # Example models, can be dynamic
            supports_streaming=True
        )