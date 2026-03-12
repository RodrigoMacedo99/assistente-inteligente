# Re-exporta o CostRouter do módulo de routing para compatibilidade.
# A implementação real está em aiadapter.infrastructure.routing.cost_router
from aiadapter.infrastructure.routing.cost_router import CostRouter

__all__ = ["CostRouter"]
