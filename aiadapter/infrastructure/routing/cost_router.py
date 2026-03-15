"""
Router inteligente que seleciona providers baseado em:
- Dificuldade/complexidade da tarefa
- Custo máximo aceitável
- Prioridade da requisição
- Quotas diárias disponíveis (para provedores gratuitos)
- Disponibilidade do provedor local (Ollama)

Tier de seleção:
  free   → Ollama local > OpenRouter free > Groq (free tier) > Gemini flash free
  low    → Groq > DeepSeek > Gemini flash > Mistral small
  medium → DeepSeek > Mistral medium > GPT-4o-mini > Claude haiku
  high   → GPT-4o > Claude sonnet > Gemini pro > DeepSeek reasoner
"""

import logging
from typing import ClassVar

from aiadapter.core.entities.airequest import AIRequest
from aiadapter.core.interfaces.provider import AIProvider
from aiadapter.core.interfaces.router import AIRouter

logger = logging.getLogger("aiadapter.router")


class CostRouter(AIRouter):
    """
    Seleciona provedores em ordem de preferência com base em:
    difficulty, complexity, priority e max_cost do AIRequest.

    Retorna lista ordenada de providers (do preferido ao fallback).
    Respeita quotas diárias dos provedores gratuitos.
    """

    # Mapeamento de tier → ordem de providers preferidos
    TIER_ORDER: ClassVar[dict[str, list[str]]] = {
        "free": [
            "ollama",  # 1º: local, zero custo
            "openrouter_free",  # 2º: OpenRouter modelos gratuitos
            "groq",  # 3º: Groq free tier (14.4k req/dia)
            "gemini",  # 4º: Gemini Flash (1500 req/dia grátis)
            "deepseek",  # 5º: DeepSeek (muito barato)
        ],
        "low": [
            "groq",  # 1º: Groq free tier ultra-rápido
            "gemini",  # 2º: Gemini Flash (barato)
            "deepseek",  # 3º: DeepSeek chat (baratíssimo)
            "mistral",  # 4º: Mistral small
            "ollama",  # 5º: Ollama local (fallback)
            "openai",  # 6º: GPT-4o-mini
        ],
        "medium": [
            "deepseek",  # 1º: DeepSeek (ótimo custo-benefício)
            "mistral",  # 2º: Mistral medium
            "groq",  # 3º: Groq 70B
            "gemini",  # 4º: Gemini Pro
            "openai",  # 5º: GPT-4o-mini
            "anthropic",  # 6º: Claude haiku
        ],
        "high": [
            "openai",  # 1º: GPT-4o
            "anthropic",  # 2º: Claude Sonnet
            "gemini",  # 3º: Gemini Pro
            "deepseek",  # 4º: DeepSeek reasoner
            "mistral",  # 5º: Mistral large
        ],
    }

    def __init__(
        self,
        providers: dict[str, AIProvider],
        quota_manager=None,
    ):
        self._providers = providers
        self._quota_manager = quota_manager

    def route(self, request: AIRequest) -> list[AIProvider]:
        tier = self._select_tier(request)

        # Provider específico solicitado
        if request.preferred_provider and request.preferred_provider in self._providers:
            preferred = self._providers[request.preferred_provider]
            rest = self._build_fallback_list(tier, exclude=request.preferred_provider)
            logger.info(
                f"[ROUTER] preferred_provider={request.preferred_provider} → fallback={[p.get_metadata().name for p in rest]}"
            )
            return [preferred, *rest]

        ordered = self._build_fallback_list(tier)
        logger.info(
            f"[ROUTER] difficulty={request.difficulty} complexity={request.complexity:.2f} "
            f"max_cost={request.max_cost} → tier={tier} "
            f"order={[p.get_metadata().name for p in ordered]}"
        )
        return ordered

    def _select_tier(self, request: AIRequest) -> str:
        """Determina o tier de custo com base nos campos da requisição."""
        # max_cost explícito tem precedência
        if request.max_cost in {"free", "low", "medium", "high"}:
            cost_tier = request.max_cost
        else:
            cost_tier = "medium"

        # Dificuldade eleva o tier mínimo necessário
        difficulty_tier = {
            "easy": "free",
            "medium": "low",
            "hard": "medium",
            "expert": "high",
        }.get(request.difficulty, "medium")

        # Complexidade numérica também influencia
        complexity_tier = self._complexity_to_tier(request.complexity)

        # Prioridade low força tier free/low
        if request.priority == "low":
            return min(
                [cost_tier, difficulty_tier, complexity_tier, "low"],
                key=lambda t: self._tier_level(t),
            )

        # Prioridade high garante pelo menos medium
        if request.priority == "high":
            tiers = [cost_tier, difficulty_tier, complexity_tier]
            result = max(tiers, key=lambda t: self._tier_level(t))
            return max(result, "medium", key=lambda t: self._tier_level(t))

        # Normal: usa o maior nível entre dificuldade, complexidade e max_cost
        candidates = [cost_tier, difficulty_tier, complexity_tier]
        return max(candidates, key=lambda t: self._tier_level(t))

    def _complexity_to_tier(self, complexity: float) -> str:
        if complexity <= 0.25:
            return "free"
        elif complexity <= 0.5:
            return "low"
        elif complexity <= 0.75:
            return "medium"
        else:
            return "high"

    def _tier_level(self, tier: str) -> int:
        return {"free": 0, "low": 1, "medium": 2, "high": 3}.get(tier, 1)

    def _build_fallback_list(self, tier: str, exclude: str | None = None) -> list[AIProvider]:
        """
        Constrói a lista de providers para o tier dado,
        filtrando providers indisponíveis e sem quota.
        """
        order = self.TIER_ORDER.get(tier, self.TIER_ORDER["medium"])
        result = []

        for name in order:
            if name == exclude:
                continue

            # openrouter_free é um alias - usa o provider "openrouter" com modelo free
            actual_name = "openrouter" if name == "openrouter_free" else name

            if actual_name not in self._providers:
                continue

            # Verifica quota diária
            if self._quota_manager and not self._quota_manager.is_available(name):
                logger.warning(f"[ROUTER] Pulando {name}: quota diária esgotada")
                continue

            result.append(self._providers[actual_name])

        # Garante pelo menos um provider como fallback total
        if not result:
            available = list(self._providers.values())
            if available:
                logger.warning(
                    "[ROUTER] Nenhum provider disponível no tier selecionado, usando qualquer disponível"
                )
                result = available

        return result
