"""
Testes de integração com Ollama (local).
Só rodam se o Ollama estiver disponível em localhost:11434.
Execute com: pytest tests/integration/ -v -m integration
"""
import pytest
import requests

from aiadapter.core.entities.airequest import AIRequest
from aiadapter.infrastructure.providers.local.ollama_provider import OllamaProvider


def ollama_disponivel() -> bool:
    try:
        resp = requests.get("http://localhost:11434/api/tags", timeout=3)
        return resp.status_code == 200
    except Exception:
        return False


pytestmark = pytest.mark.integration

skip_sem_ollama = pytest.mark.skipif(
    not ollama_disponivel(),
    reason="Ollama não está rodando em localhost:11434",
)


@pytest.fixture
def ollama() -> OllamaProvider:
    return OllamaProvider(base_url="http://localhost:11434")


@skip_sem_ollama
class TestOllamaIntegration:
    def test_is_available(self, ollama):
        assert ollama.is_available() is True

    def test_list_models_retorna_lista(self, ollama):
        modelos = ollama.list_local_models()
        assert isinstance(modelos, list)

    def test_get_metadata_retorna_modelos_instalados(self, ollama):
        meta = ollama.get_metadata()
        assert meta.name == "ollama"
        assert meta.is_local is True
        assert meta.cost_per_1k_tokens == 0.0

    def test_generate_resposta_simples(self, ollama):
        modelos = ollama.list_local_models()
        if not modelos:
            pytest.skip("Nenhum modelo instalado no Ollama")

        req = AIRequest(
            prompt="Responda apenas: OK",
            model=modelos[0],
            max_tokens=10,
            temperature=0.0,
        )
        resp = ollama.generate(req)
        assert resp.provider_name == "ollama"
        assert resp.output is not None
        assert len(resp.output) > 0

    def test_generate_streaming(self, ollama):
        modelos = ollama.list_local_models()
        if not modelos:
            pytest.skip("Nenhum modelo instalado no Ollama")

        req = AIRequest(
            prompt="Responda: Olá",
            model=modelos[0],
            max_tokens=10,
            temperature=0.0,
            stream=True,
        )
        chunks = list(ollama.generate(req))
        assert len(chunks) > 0
        assert all(c.is_streaming_chunk for c in chunks)
        texto_completo = "".join(c.output for c in chunks if c.output)
        assert len(texto_completo) > 0
