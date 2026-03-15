"""
ProviderHealth — rastreamento de saúde e circuit breaker por provider.

O circuit breaker abre automaticamente quando um provider atinge
`threshold` falhas consecutivas. Após `cooldown_seconds` sem tentativas,
o circuit fecha novamente (half-open → reset automático na próxima chamada).
"""
from dataclasses import dataclass, field
import time


@dataclass
class ProviderHealth:
    """
    Rastreia saúde e estado do circuit breaker de um provider de áudio.

    O circuit abre após `threshold` falhas consecutivas e fecha sozinho
    quando `cooldown_seconds` passam sem novas tentativas.
    """

    name: str
    consecutive_failures: int = 0
    total_failures: int = 0
    total_successes: int = 0
    last_failure_at: float | None = field(default=None, repr=False)
    last_success_at: float | None = field(default=None, repr=False)
    circuit_open: bool = False
    circuit_open_until: float | None = field(default=None, repr=False)

    def record_success(self) -> None:
        """Registra sucesso e fecha o circuit breaker se estiver aberto."""
        self.consecutive_failures = 0
        self.total_successes += 1
        self.last_success_at = time.monotonic()
        self.circuit_open = False
        self.circuit_open_until = None

    def record_failure(self, cooldown_seconds: float, threshold: int) -> None:
        """
        Registra falha e abre o circuit breaker se atingir o threshold.

        Parâmetros
        ----------
        cooldown_seconds : float
            Duração do período de cooldown em segundos.
        threshold : int
            Número de falhas consecutivas para abrir o circuit.
        """
        self.consecutive_failures += 1
        self.total_failures += 1
        self.last_failure_at = time.monotonic()

        if self.consecutive_failures >= threshold:
            self.circuit_open = True
            self.circuit_open_until = time.monotonic() + cooldown_seconds

    def is_open(self) -> bool:
        """
        Retorna True se o circuit está aberto (provider deve ser ignorado).

        Se o cooldown expirou, fecha o circuit automaticamente (half-open reset).
        """
        if not self.circuit_open:
            return False

        if self.circuit_open_until is not None and time.monotonic() >= self.circuit_open_until:
            # Cooldown expirado — reset para half-open (próxima tentativa passa)
            self.circuit_open = False
            self.circuit_open_until = None
            self.consecutive_failures = 0
            return False

        return True

    def to_dict(self) -> dict:
        """Retorna snapshot do estado de saúde (sem nome — use junto ao provider_name)."""
        return {
            "consecutive_failures": self.consecutive_failures,
            "total_failures": self.total_failures,
            "total_successes": self.total_successes,
            "circuit_open": self.is_open(),
        }
