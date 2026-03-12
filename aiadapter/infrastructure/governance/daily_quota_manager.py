"""
Gerenciador de quotas diárias para provedores gratuitos.

Armazena o consumo diário em um arquivo JSON local.
Reseta automaticamente no início de cada novo dia.
"""
import json
import os
import logging
from datetime import datetime, date
from typing import Dict, Optional

logger = logging.getLogger("aiadapter.quota")

QUOTA_FILE = os.path.join(os.path.dirname(__file__), "..", "..", "..", "data", "daily_quotas.json")

# Limites diários por provedor (requisições)
DAILY_LIMITS: Dict[str, int] = {
    "gemini": 1500,          # Gemini Free: 1500 req/dia
    "groq": 14400,           # Groq Free: 14400 req/dia (~10 req/min)
    "openrouter_free": 200,  # OpenRouter modelos gratuitos: ~200 req/dia
    "together_free": 300,    # Together AI free tier
    "cohere": 1000,          # Cohere trial: 1000 req/mês (~33/dia)
    "mistral": 500,          # Mistral free tier estimado
}


class DailyQuotaManager:
    """
    Controla o uso diário de cada provedor gratuito.
    Ao virar o dia, reseta automaticamente os contadores.
    """

    def __init__(self, quota_file: str = QUOTA_FILE):
        self._quota_file = quota_file
        self._ensure_data_dir()
        self._data = self._load()

    def _ensure_data_dir(self):
        os.makedirs(os.path.dirname(self._quota_file), exist_ok=True)

    def _load(self) -> dict:
        if not os.path.exists(self._quota_file):
            return {"date": str(date.today()), "usage": {}}
        try:
            with open(self._quota_file, "r", encoding="utf-8") as f:
                data = json.load(f)
            # Se mudou o dia, reseta
            if data.get("date") != str(date.today()):
                logger.info(f"[QUOTA] Novo dia detectado - resetando quotas diárias")
                data = {"date": str(date.today()), "usage": {}}
                self._save(data)
            return data
        except (json.JSONDecodeError, KeyError):
            return {"date": str(date.today()), "usage": {}}

    def _save(self, data: Optional[dict] = None):
        with open(self._quota_file, "w", encoding="utf-8") as f:
            json.dump(data or self._data, f, indent=2, ensure_ascii=False)

    def _reload_if_new_day(self):
        """Verifica se virou o dia e reseta se necessário."""
        if self._data.get("date") != str(date.today()):
            logger.info("[QUOTA] Novo dia - resetando contadores")
            self._data = {"date": str(date.today()), "usage": {}}
            self._save()

    def get_usage(self, provider: str) -> int:
        self._reload_if_new_day()
        return self._data["usage"].get(provider, 0)

    def get_limit(self, provider: str) -> int:
        return DAILY_LIMITS.get(provider, 0)

    def is_available(self, provider: str) -> bool:
        """Retorna True se o provedor ainda tem quota disponível hoje."""
        self._reload_if_new_day()
        limit = self.get_limit(provider)
        if limit == 0:
            return True  # sem limite definido = pago/ilimitado
        usage = self.get_usage(provider)
        available = usage < limit
        if not available:
            logger.warning(
                f"[QUOTA] Provider '{provider}' esgotou quota diária "
                f"({usage}/{limit}). Será liberado amanhã."
            )
        return available

    def record_request(self, provider: str, count: int = 1):
        """Registra N requisições para um provedor."""
        self._reload_if_new_day()
        current = self._data["usage"].get(provider, 0)
        self._data["usage"][provider] = current + count
        self._save()
        logger.debug(
            f"[QUOTA] {provider}: {self._data['usage'][provider]}/{self.get_limit(provider)}"
        )

    def get_all_status(self) -> Dict[str, dict]:
        """Retorna o status de todos os provedores rastreados."""
        self._reload_if_new_day()
        status = {}
        for provider, limit in DAILY_LIMITS.items():
            usage = self._data["usage"].get(provider, 0)
            status[provider] = {
                "usage": usage,
                "limit": limit,
                "remaining": max(0, limit - usage),
                "available": usage < limit,
                "reset_at": "amanhã 00:00",
            }
        return status

    def mark_exhausted(self, provider: str):
        """Marca manualmente um provedor como esgotado (quota atingida por erro da API)."""
        self._reload_if_new_day()
        limit = self.get_limit(provider)
        self._data["usage"][provider] = limit
        self._save()
        logger.warning(f"[QUOTA] Provider '{provider}' marcado como esgotado manualmente.")
