from dataclasses import dataclass, field
from typing import Optional, Dict, Any, List


@dataclass
class AIRequest:
    """
    Intenção de uso de IA.

    prompt: Texto base enviado para a IA.
    model: Modelo específico a usar (opcional, o router decide se não informado).
    messages: Histórico de mensagens no formato [{role, content}].
    temperature: Controla a aleatoriedade da resposta (0.0 = determinístico, 1.0 = criativo).
    max_tokens: Limite máximo de tokens na resposta.
    context: Metadados extras de execução.
    client_id: Identificador do tenant/cliente para multi-tenancy e rate limiting.
    stream: Se True, retorna resposta em streaming.
    tools: Ferramentas (function calling) disponíveis para a IA.
    priority: Prioridade da requisição - "low", "normal", "high".
    difficulty: Dificuldade estimada da tarefa - "easy", "medium", "hard", "expert".
    complexity: Complexidade numérica de 0.0 (trivial) a 1.0 (máxima).
    max_cost: Custo máximo aceitável - "free", "low", "medium", "high".
    preferred_provider: Nome do provider preferido (opcional).
    """
    prompt: str
    model: Optional[str] = None
    messages: Optional[List[Dict[str, Any]]] = None
    temperature: float = 0.7
    max_tokens: int = 512
    context: Optional[Dict[str, Any]] = None
    client_id: Optional[str] = None
    stream: bool = False
    tools: Optional[List[Dict[str, Any]]] = None
    priority: str = "normal"
    difficulty: str = "medium"
    complexity: float = 0.5
    max_cost: str = "medium"
    preferred_provider: Optional[str] = None
