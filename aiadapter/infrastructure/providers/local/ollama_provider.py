from typing import List, Dict, Any, Generator
from aiadapter.core.interfaces.provider import AIProvider
from aiadapter.core.entities.airequest import AIRequest
from aiadapter.core.entities.airesponse import AIResponse
from aiadapter.core.entities.aiprovidermedata import AIProviderMetadata
from aiadapter.core.enums.aicapability import AICapability
import requests
import json

DEFAULT_MODEL = "llama3.2"


class OllamaProvider(AIProvider):

    def __init__(self, base_url: str = "http://localhost:11434"):
        self._base_url = base_url.rstrip("/")

    def is_available(self) -> bool:
        """Verifica se o Ollama está rodando e acessível."""
        try:
            resp = requests.get(f"{self._base_url}/api/tags", timeout=3)
            return resp.status_code == 200
        except Exception:
            return False

    def list_local_models(self) -> List[str]:
        """Lista modelos já baixados localmente."""
        try:
            resp = requests.get(f"{self._base_url}/api/tags", timeout=5)
            resp.raise_for_status()
            data = resp.json()
            return [m["name"] for m in data.get("models", [])]
        except Exception:
            return []

    def generate(self, request: AIRequest) -> AIResponse | Generator[AIResponse, None, None]:
        model = request.model or DEFAULT_MODEL
        messages = request.messages or [{"role": "user", "content": request.prompt}]

        payload = {
            "model": model,
            "messages": messages,
            "options": {
                "temperature": request.temperature,
                "num_predict": request.max_tokens,
            },
            "stream": request.stream,
        }

        if request.stream:
            return self._generate_stream(payload)

        response = requests.post(f"{self._base_url}/api/chat", json=payload, timeout=120)
        response.raise_for_status()
        data = response.json()

        tokens = data.get("prompt_eval_count", 0) + data.get("eval_count", 0)
        return AIResponse(
            output=data["message"]["content"],
            tokens_used=tokens,
            provider_name="ollama",
            cost=0.0,
        )

    def _generate_stream(self, payload: Dict[str, Any]) -> Generator[AIResponse, None, None]:
        with requests.post(
            f"{self._base_url}/api/chat",
            json=payload,
            stream=True,
            timeout=120,
        ) as response:
            response.raise_for_status()
            for chunk in response.iter_lines():
                if chunk:
                    try:
                        data = json.loads(chunk.decode("utf-8"))
                        content = data.get("message", {}).get("content", "")
                        if content:
                            yield AIResponse(
                                output=content,
                                tokens_used=0,
                                provider_name="ollama",
                                cost=0.0,
                                is_streaming_chunk=True,
                            )
                    except json.JSONDecodeError:
                        pass

    def supports(self, capability: AICapability) -> bool:
        return capability in {AICapability.TEXT}

    def get_metadata(self) -> AIProviderMetadata:
        models = self.list_local_models() or ["llama3.2", "mistral", "gemma2"]
        return AIProviderMetadata(
            name="ollama",
            models=models,
            supports_streaming=True,
            cost_per_1k_tokens=0.0,
            avg_latency_ms=500,
            is_local=True,
            capabilities=["text"],
        )
