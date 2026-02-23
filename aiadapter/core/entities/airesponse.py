from dataclasses import dataclass
from typing import Optional, Dict, Any, List

@dataclass
class AIResponse:
    """
    Padronização das repostas de todas as IAs.
    
    output:Interface da resposta da IA. 
    tokens_used: Quantidade total de tokens consumidos.
    provider_name: Nome do provider que respondeu.
    cost: Custo estimado da chamada
    """
    output: Optional[str] = None
    tokens_used: int
    provider_name: str 
    cost: float
    is_streaming_chunk: bool = False
    tool_calls: Optional[List[Dict[str, Any]]] = None