from aiadapter.core.entities.airequest import AIRequest
from aiadapter.core.interfaces.policy import AIPolicy


class SimplePolicy(AIPolicy):

    def validate(self, request: AIRequest) -> None:
        if not request.prompt or not request.prompt.strip():
            raise ValueError("Prompt não pode ser vazio")

        if len(request.prompt) > 10000:
            raise ValueError("Prompt muito longo (máximo 10.000 caracteres)")

        valid_difficulties = {"easy", "medium", "hard", "expert"}
        if request.difficulty not in valid_difficulties:
            raise ValueError(
                f"Dificuldade inválida: {request.difficulty}. Use: {valid_difficulties}"
            )

        valid_priorities = {"low", "normal", "high"}
        if request.priority not in valid_priorities:
            raise ValueError(f"Prioridade inválida: {request.priority}. Use: {valid_priorities}")

        valid_max_costs = {"free", "low", "medium", "high"}
        if request.max_cost not in valid_max_costs:
            raise ValueError(f"max_cost inválido: {request.max_cost}. Use: {valid_max_costs}")

        if not (0.0 <= request.complexity <= 1.0):
            raise ValueError("Complexity deve estar entre 0.0 e 1.0")
