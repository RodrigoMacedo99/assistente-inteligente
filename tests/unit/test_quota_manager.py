"""
Testes do DailyQuotaManager — quotas diárias com reset automático.
"""

from datetime import date, timedelta
import json
import os

import pytest

from aiadapter.infrastructure.governance.daily_quota_manager import DailyQuotaManager


@pytest.fixture
def quota_file(tmp_path) -> str:
    return str(tmp_path / "test_quotas.json")


@pytest.fixture
def manager(quota_file) -> DailyQuotaManager:
    return DailyQuotaManager(quota_file=quota_file)


class TestDailyQuotaManager:
    def test_inicializa_sem_arquivo(self, quota_file):
        assert not os.path.exists(quota_file)
        mgr = DailyQuotaManager(quota_file=quota_file)
        assert mgr.get_usage("groq") == 0

    def test_get_usage_inicial_zero(self, manager):
        assert manager.get_usage("groq") == 0
        assert manager.get_usage("gemini") == 0

    def test_record_request_incrementa(self, manager):
        manager.record_request("groq")
        assert manager.get_usage("groq") == 1
        manager.record_request("groq")
        assert manager.get_usage("groq") == 2

    def test_record_request_com_count(self, manager):
        manager.record_request("groq", count=10)
        assert manager.get_usage("groq") == 10

    def test_is_available_abaixo_do_limite(self, manager):
        assert manager.is_available("groq") is True

    def test_is_available_acima_do_limite(self, manager):
        limite = manager.get_limit("groq")
        manager.record_request("groq", count=limite)
        assert manager.is_available("groq") is False

    def test_mark_exhausted_bloqueia_provider(self, manager):
        manager.mark_exhausted("gemini")
        assert manager.is_available("gemini") is False

    def test_mark_exhausted_nao_afeta_outros_providers(self, manager):
        manager.mark_exhausted("gemini")
        assert manager.is_available("groq") is True

    def test_provider_sem_limite_sempre_disponivel(self, manager):
        # Provider não cadastrado em DAILY_LIMITS → limite=0 → sem restrição
        assert manager.is_available("openai") is True
        manager.record_request("openai", count=9999)
        assert manager.is_available("openai") is True

    def test_persistencia_em_arquivo(self, quota_file):
        mgr1 = DailyQuotaManager(quota_file=quota_file)
        mgr1.record_request("groq", count=42)

        # Nova instância deve ler do mesmo arquivo
        mgr2 = DailyQuotaManager(quota_file=quota_file)
        assert mgr2.get_usage("groq") == 42

    def test_reset_automatico_novo_dia(self, quota_file):
        ontem = str(date.today() - timedelta(days=1))

        # Cria arquivo com data de ontem e uso alto
        data = {"date": ontem, "usage": {"groq": 9999, "gemini": 500}}
        with open(quota_file, "w") as f:
            json.dump(data, f)

        mgr = DailyQuotaManager(quota_file=quota_file)
        # Ao carregar, deve detectar data antiga e resetar
        assert mgr.get_usage("groq") == 0
        assert mgr.get_usage("gemini") == 0

    def test_data_hoje_nao_reseta(self, quota_file):
        hoje = str(date.today())
        data = {"date": hoje, "usage": {"groq": 100}}
        with open(quota_file, "w") as f:
            json.dump(data, f)

        mgr = DailyQuotaManager(quota_file=quota_file)
        assert mgr.get_usage("groq") == 100

    def test_get_all_status_formato(self, manager):
        manager.record_request("groq", count=50)
        status = manager.get_all_status()

        assert "groq" in status
        assert status["groq"]["usage"] == 50
        assert status["groq"]["limit"] == manager.get_limit("groq")
        assert status["groq"]["remaining"] == manager.get_limit("groq") - 50
        assert status["groq"]["available"] is True
        assert "reset_at" in status["groq"]

    def test_reload_se_dia_mudou_durante_uso(self, manager):
        """Simula virada do dia enquanto a instância está rodando."""
        manager.record_request("groq", count=100)
        assert manager.get_usage("groq") == 100

        # Força a data interna para ontem
        manager._data["date"] = str(date.today() - timedelta(days=1))

        # Próxima chamada deve detectar o novo dia e resetar
        assert manager.is_available("groq") is True
        assert manager.get_usage("groq") == 0

    def test_arquivo_json_corrompido_reseta(self, quota_file):
        with open(quota_file, "w") as f:
            f.write("{ json inválido }")

        # Não deve lançar exceção
        mgr = DailyQuotaManager(quota_file=quota_file)
        assert mgr.get_usage("groq") == 0
