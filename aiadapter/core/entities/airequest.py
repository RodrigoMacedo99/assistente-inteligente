from dataclasses import dataclass
from typing import Optional, Dict, Any, List

@dataclass
class AIRequest:
    """
    Intenção de uso de IA:

    Prompt:Texto base enviado para a IA.
    temperature: Controla a aleatóriedade da resposta do modelo de IA.
    max_tokens: Limite maximo de tokens para responder em uma menssagem.
    context: Metadados da execcução para controle de uso e mapeamentos de seleção com o Router(script de seleção de modelo para o caso específico).
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