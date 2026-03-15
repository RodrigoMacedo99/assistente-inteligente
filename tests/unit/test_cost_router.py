"""
Testes do CostRouter — roteamento inteligente por tier.
"""
from unittest.mock import MagicMock

import pytest

from aiadapter.core.entities.aiprovidermedata import AIProviderMetadata
from aiadapter.core.entities.airequest import AIRequest
from aiadapter.infrastructure.governance.daily_quota_manager import DailyQuotaManager
from aiadapter.infrastructure.routing.cost_router import CostRouter


def make_provider(name: str):
    p = MagicMock()
    p.get_metadata.return_value = AIProviderMetadata(name=name, models=[f"{name}-model"])
    return p


@pytest.fixture
def providers():
    return {
        "ollama": make_provider("ollama"),
        "groq": make_provider("groq"),
        "gemini": make_provider("gemini"),
        "openrouter": make_provider("openrouter"),
        "deepseek": make_provider("deepseek"),
        "mistral": make_provider("mistral"),
        "openai": make_provider("openai"),
        "anthropic": make_provider("anthropic"),
    }


@pytest.fixture
def router(providers, tmp_path):
    quota = DailyQuotaManager(quota_file=str(tmp_path / "q.json"))
    return CostRouter(providers=providers, quota_manager=quota)


class TestCostRouterTierSelection:
    def test_easy_free_retorna_tier_free(self, router):
        req = AIRequest(prompt="Olá", difficulty="easy", complexity=0.1,
                        max_cost="free", priority="normal")
        lista = router.route(req)
        assert len(lista) > 0
        # Primeiro deve ser ollama (local, free)
        assert lista[0].get_metadata().name == "ollama"

    def test_expert_high_retorna_providers_premium(self, router):
        req = AIRequest(prompt="Análise", difficulty="expert", complexity=0.95,
                        max_cost="high", priority="high")
        lista = router.route(req)
        nomes = [p.get_metadata().name for p in lista]
        # GPT-4o ou Claude devem estar no início para tier high
        assert nomes[0] in {"openai", "anthropic"}

    def test_priority_low_forca_tier_baixo(self, router):
        req = AIRequest(prompt="Teste", difficulty="hard", complexity=0.8,
                        max_cost="high", priority="low")
        lista = router.route(req)
        # Com priority=low, deve usar tier mais baixo
        assert len(lista) > 0
        primeiro = lista[0].get_metadata().name
        # Deve ser um provider de tier free/low (ollama, openrouter, groq, gemini)
        assert primeiro in {"ollama", "openrouter", "groq", "gemini", "deepseek"}

    def test_preferred_provider_vem_primeiro(self, router):
        req = AIRequest(prompt="Teste", preferred_provider="openai")
        lista = router.route(req)
        assert lista[0].get_metadata().name == "openai"

    def test_preferred_provider_invalido_ignorado(self, router):
        req = AIRequest(prompt="Teste", preferred_provider="provider_inexistente")
        # Não deve lançar, apenas retorna ordem normal
        lista = router.route(req)
        assert len(lista) > 0

    def test_retorna_lista_nao_vazia(self, router):
        req = AIRequest(prompt="Teste")
        lista = router.route(req)
        assert isinstance(lista, list)
        assert len(lista) > 0


class TestCostRouterQuota:
    def test_pula_provider_com_quota_esgotada(self, providers, tmp_path):
        quota = DailyQuotaManager(quota_file=str(tmp_path / "q.json"))
        quota.mark_exhausted("groq")

        router = CostRouter(providers=providers, quota_manager=quota)
        req = AIRequest(prompt="Teste", difficulty="easy", max_cost="free",
                        complexity=0.1, priority="normal")
        lista = router.route(req)
        nomes = [p.get_metadata().name for p in lista]
        assert "groq" not in nomes

    def test_todos_providers_esgotados_retorna_qualquer(self, tmp_path):
        # Apenas um provider configurado e esgotado
        p = make_provider("groq")
        quota = DailyQuotaManager(quota_file=str(tmp_path / "q.json"))
        quota.mark_exhausted("groq")

        router = CostRouter(providers={"groq": p}, quota_manager=quota)
        req = AIRequest(prompt="Teste", difficulty="easy", max_cost="free",
                        complexity=0.1, priority="normal")
        lista = router.route(req)
        # Fallback: retorna qualquer disponível
        assert len(lista) > 0

    def test_sem_quota_manager_nao_filtra(self, providers):
        router = CostRouter(providers=providers, quota_manager=None)
        req = AIRequest(prompt="Teste")
        lista = router.route(req)
        assert len(lista) > 0


class TestCostRouterTierLogic:
    @pytest.mark.parametrize("complexity,expected_tier", [
        (0.1, "free"),
        (0.3, "low"),
        (0.6, "medium"),
        (0.9, "high"),
    ])
    def test_complexity_to_tier(self, router, complexity, expected_tier):
        assert router._complexity_to_tier(complexity) == expected_tier

    @pytest.mark.parametrize("tier,level", [
        ("free", 0), ("low", 1), ("medium", 2), ("high", 3)
    ])
    def test_tier_level(self, router, tier, level):
        assert router._tier_level(tier) == level

    def test_tier_desconhecido_retorna_nivel_1(self, router):
        assert router._tier_level("unknown") == 1

    def test_select_tier_difficulty_domina_max_cost_baixo(self, router):
        # difficulty=expert exige tier high mesmo com max_cost=free
        req = AIRequest(prompt="Teste", difficulty="expert", complexity=0.1,
                        max_cost="free", priority="normal")
        tier = router._select_tier(req)
        assert tier == "high"

    def test_select_tier_max_cost_alto_com_easy(self, router):
        # max_cost=high + difficulty=easy + complexity=0.1 → high wins
        req = AIRequest(prompt="Teste", difficulty="easy", complexity=0.1,
                        max_cost="high", priority="normal")
        tier = router._select_tier(req)
        assert tier == "high"

    def test_select_tier_priority_high_garante_minimum_medium(self, router):
        req = AIRequest(prompt="Teste", difficulty="easy", complexity=0.1,
                        max_cost="free", priority="high")
        tier = router._select_tier(req)
        assert router._tier_level(tier) >= router._tier_level("medium")


class TestCostRouterProvidersFaltando:
    def test_provider_nao_configurado_nao_aparece_na_lista(self, tmp_path):
        # Apenas groq e ollama configurados (sem openai/anthropic)
        providers = {
            "ollama": make_provider("ollama"),
            "groq": make_provider("groq"),
        }
        quota = DailyQuotaManager(quota_file=str(tmp_path / "q.json"))
        router = CostRouter(providers=providers, quota_manager=quota)

        req = AIRequest(prompt="Teste", difficulty="expert", max_cost="high",
                        complexity=0.9, priority="normal")
        lista = router.route(req)
        nomes = [p.get_metadata().name for p in lista]
        assert "openai" not in nomes
        assert "anthropic" not in nomes
