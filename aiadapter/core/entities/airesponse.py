from dataclasses import dataclass
from typing import Optional, Dict, Any, List


@dataclass
class AIResponse:
    """
    Padronização das respostas de todas as IAs.

    provider_name: Nome do provider que respondeu.
    tokens_used: Quantidade total de tokens consumidos.
    cost: Custo estimado da chamada em USD.
    output: Interface da resposta da IA.
    is_streaming_chunk: Indica se é um chunk de streaming.
    tool_calls: Lista de chamadas de ferramentas solicitadas pela IA.
    """
    provider_name: str
    tokens_used: int = 0
    cost: float = 0.0
    output: Optional[str] = None
    is_streaming_chunk: bool = False
    tool_calls: Optional[List[Dict[str, Any]]] = None
