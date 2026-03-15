from dataclasses import dataclass, field


@dataclass
class AIProviderMetadata:
    """
    Descreve as características de um provider.

    name: Nome lógico do provedor (ex: "openai", "groq").
    models: Lista de modelos disponíveis neste provedor.
    supports_streaming: Se o provedor suporta respostas em streaming.
    cost_per_1k_tokens: Custo médio por 1000 tokens em USD (output).
    avg_latency_ms: Latência média estimada em milissegundos.
    is_local: Se o provedor roda localmente (sem custo de API).
    daily_free_limit: Limite de requisições/tokens gratuitos por dia (0 = sem limite ou pago).
    capabilities: Lista de capacidades suportadas (text, vision, function_calling, etc).
    """
    name: str
    models: list[str] = field(default_factory=list)
    supports_streaming: bool = True
    cost_per_1k_tokens: float = 0.0
    avg_latency_ms: int = 0
    is_local: bool = False
    daily_free_limit: int = 0
    capabilities: list[str] = field(default_factory=lambda: ["text"])
