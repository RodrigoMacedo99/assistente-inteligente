"""
Testes do SimplePolicy — validação de requisições.
"""
import pytest

from aiadapter.core.entities.airequest import AIRequest
from aiadapter.infrastructure.governance.simple_policy import SimplePolicy


@pytest.fixture
def policy() -> SimplePolicy:
    return SimplePolicy()


@pytest.fixture
def valid_request() -> AIRequest:
    return AIRequest(
        prompt="Qual é a capital do Brasil?",
        difficulty="medium",
        complexity=0.5,
        priority="normal",
        max_cost="medium",
    )


class TestSimplePolicy:
    def test_request_valido_nao_lanca(self, policy, valid_request):
        policy.validate(valid_request)  # Não deve lançar

    def test_prompt_vazio_lanca(self, policy):
        req = AIRequest(prompt="")
        with pytest.raises(ValueError, match="vazio"):
            policy.validate(req)

    def test_prompt_so_espacos_lanca(self, policy):
        req = AIRequest(prompt="   \n\t  ")
        with pytest.raises(ValueError, match="vazio"):
            policy.validate(req)

    def test_prompt_muito_longo_lanca(self, policy):
        req = AIRequest(prompt="x" * 10001)
        with pytest.raises(ValueError, match="longo"):
            policy.validate(req)

    def test_prompt_no_limite_maximo_aceito(self, policy):
        req = AIRequest(
            prompt="x" * 10000,
            difficulty="medium",
            complexity=0.5,
            priority="normal",
            max_cost="medium",
        )
        policy.validate(req)  # Exatamente 10000 chars → OK

    def test_difficulty_invalida_lanca(self, policy):
        req = AIRequest(prompt="Teste", difficulty="impossible")
        with pytest.raises(ValueError, match="[Dd]ificuldade"):
            policy.validate(req)

    @pytest.mark.parametrize("difficulty", ["easy", "medium", "hard", "expert"])
    def test_difficulty_validas_aceitas(self, policy, difficulty):
        req = AIRequest(
            prompt="Teste",
            difficulty=difficulty,
            complexity=0.5,
            priority="normal",
            max_cost="medium",
        )
        policy.validate(req)

    def test_priority_invalida_lanca(self, policy):
        req = AIRequest(prompt="Teste", priority="urgent")
        with pytest.raises(ValueError, match="[Pp]rioridade"):
            policy.validate(req)

    @pytest.mark.parametrize("priority", ["low", "normal", "high"])
    def test_prioridades_validas_aceitas(self, policy, priority):
        req = AIRequest(
            prompt="Teste",
            difficulty="medium",
            complexity=0.5,
            priority=priority,
            max_cost="medium",
        )
        policy.validate(req)

    def test_max_cost_invalido_lanca(self, policy):
        req = AIRequest(prompt="Teste", max_cost="gratis")
        with pytest.raises(ValueError, match="max_cost"):
            policy.validate(req)

    @pytest.mark.parametrize("max_cost", ["free", "low", "medium", "high"])
    def test_max_cost_validos_aceitos(self, policy, max_cost):
        req = AIRequest(
            prompt="Teste",
            difficulty="medium",
            complexity=0.5,
            priority="normal",
            max_cost=max_cost,
        )
        policy.validate(req)

    def test_complexity_negativa_lanca(self, policy):
        req = AIRequest(prompt="Teste", complexity=-0.1)
        with pytest.raises(ValueError, match="[Cc]omplexity"):
            policy.validate(req)

    def test_complexity_acima_de_1_lanca(self, policy):
        req = AIRequest(prompt="Teste", complexity=1.1)
        with pytest.raises(ValueError, match="[Cc]omplexity"):
            policy.validate(req)

    @pytest.mark.parametrize("complexity", [0.0, 0.5, 1.0])
    def test_complexity_limites_validos(self, policy, complexity):
        req = AIRequest(
            prompt="Teste",
            difficulty="medium",
            complexity=complexity,
            priority="normal",
            max_cost="medium",
        )
        policy.validate(req)
