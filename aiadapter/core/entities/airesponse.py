from dataclasses import dataclass

@dataclass
class AIResponse:
    """
    Padronização das repostas de todas as IAs.
    
    output:Interface da resposta da IA. 
    tokens_used: Quantidade total de tokens consumidos.
    provider_name: Nome do provider que respondeu.
    cost: Custo estimado da chamada
    """
    output: str
    tokens_used: int
    provider_name: str 
    cost: float