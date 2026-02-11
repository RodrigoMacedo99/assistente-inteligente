from dataclasses import dataclass

@dataclass
class AIProviderMetadata:
    """
    Descreve as características de um provider, não uma chamada.

    name: Nome lógico do provedor
    model: versão do modelo
    avg_latency_ms: latência média estimada
    cost_per_1k_tokens: custo médio por 1000 tokens
    """
    name: str
    model: str
    avg_latencya_ms: int
    cost_per_1k_tokens: float