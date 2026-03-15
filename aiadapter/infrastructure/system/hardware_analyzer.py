"""
Analisador de hardware para seleção inteligente de modelos locais.

Detecta CPU, RAM, GPU e recomenda modelos Ollama compatíveis.
Oferece download automático do melhor modelo local disponível.
"""

from dataclasses import dataclass, field
import logging
import os
import subprocess

logger = logging.getLogger("aiadapter.hardware")


@dataclass
class HardwareProfile:
    """Perfil do hardware do servidor/computador."""

    ram_gb: float = 0.0
    cpu_cores: int = 0
    cpu_threads: int = 0
    gpu_name: str | None = None
    gpu_vram_gb: float = 0.0
    has_cuda: bool = False
    has_metal: bool = False  # macOS Apple Silicon
    has_rocm: bool = False  # AMD GPUs
    platform: str = ""
    recommended_models: list[str] = field(default_factory=list)


# Requisitos mínimos de RAM para cada modelo Ollama (em GB)
MODEL_REQUIREMENTS: dict[str, dict] = {
    # Modelos pequenos (1-4B params) - rodam em quase qualquer máquina
    "llama3.2:1b": {
        "ram_gb": 2.0,
        "vram_gb": 1.5,
        "quality": "basic",
        "description": "Llama 3.2 1B - ultra leve, respostas básicas",
    },
    "llama3.2:3b": {
        "ram_gb": 4.0,
        "vram_gb": 2.5,
        "quality": "low",
        "description": "Llama 3.2 3B - leve, bom para tarefas simples",
    },
    "phi3.5": {
        "ram_gb": 4.0,
        "vram_gb": 2.5,
        "quality": "low",
        "description": "Phi-3.5 Mini 3.8B - excelente para hardware fraco",
    },
    "gemma2:2b": {
        "ram_gb": 4.0,
        "vram_gb": 2.0,
        "quality": "low",
        "description": "Gemma 2 2B - Google, rápido e eficiente",
    },
    # Modelos médios (7-9B params) - precisam de ~8GB RAM
    "llama3.1:8b": {
        "ram_gb": 8.0,
        "vram_gb": 5.0,
        "quality": "medium",
        "description": "Llama 3.1 8B - bom equilíbrio velocidade/qualidade",
    },
    "mistral:7b": {
        "ram_gb": 8.0,
        "vram_gb": 4.5,
        "quality": "medium",
        "description": "Mistral 7B - excelente para código e raciocínio",
    },
    "gemma2:9b": {
        "ram_gb": 8.0,
        "vram_gb": 5.5,
        "quality": "medium",
        "description": "Gemma 2 9B - Google, qualidade sólida",
    },
    "qwen2.5:7b": {
        "ram_gb": 8.0,
        "vram_gb": 5.0,
        "quality": "medium",
        "description": "Qwen 2.5 7B - ótimo para código e multilingual",
    },
    # Modelos grandes (13B params) - precisam de ~16GB RAM
    "llama3.1:latest": {
        "ram_gb": 16.0,
        "vram_gb": 9.0,
        "quality": "high",
        "description": "Llama 3.1 8B instruct (default)",
    },
    "mistral:latest": {
        "ram_gb": 8.0,
        "vram_gb": 5.0,
        "quality": "medium",
        "description": "Mistral 7B instruct (default)",
    },
    # Modelos grandes (30B+) - precisam de muita RAM/VRAM
    "llama3.3:70b": {
        "ram_gb": 48.0,
        "vram_gb": 40.0,
        "quality": "excellent",
        "description": "Llama 3.3 70B - qualidade próxima a GPT-4",
    },
    "qwen2.5:72b": {
        "ram_gb": 48.0,
        "vram_gb": 40.0,
        "quality": "excellent",
        "description": "Qwen 2.5 72B - excelente para código",
    },
}


class HardwareAnalyzer:
    """
    Analisa o hardware disponível e recomenda/baixa modelos Ollama adequados.
    """

    def __init__(self, ollama_base_url: str = "http://localhost:11434"):
        self._ollama_url = ollama_base_url
        self._profile: HardwareProfile | None = None

    def analyze(self) -> HardwareProfile:
        """Analisa o hardware do sistema e retorna um perfil."""
        profile = HardwareProfile()
        profile.platform = self._get_platform()

        try:
            import psutil

            mem = psutil.virtual_memory()
            profile.ram_gb = round(mem.total / (1024**3), 1)
            profile.cpu_cores = psutil.cpu_count(logical=False) or 1
            profile.cpu_threads = psutil.cpu_count(logical=True) or 1
        except ImportError:
            logger.warning("[HARDWARE] psutil não disponível, estimando RAM...")
            profile.ram_gb = self._estimate_ram_fallback()
            profile.cpu_cores = os.cpu_count() or 1
            profile.cpu_threads = os.cpu_count() or 1

        gpu_info = self._detect_gpu()
        profile.gpu_name = gpu_info.get("name")
        profile.gpu_vram_gb = gpu_info.get("vram_gb", 0.0)
        profile.has_cuda = gpu_info.get("has_cuda", False)
        profile.has_metal = gpu_info.get("has_metal", False)
        profile.has_rocm = gpu_info.get("has_rocm", False)

        profile.recommended_models = self._recommend_models(profile)

        self._profile = profile
        logger.info(
            f"[HARDWARE] RAM={profile.ram_gb}GB CPU={profile.cpu_cores}c/{profile.cpu_threads}t "
            f"GPU={profile.gpu_name or 'N/A'} VRAM={profile.gpu_vram_gb}GB "
            f"CUDA={profile.has_cuda}"
        )
        return profile

    def _get_platform(self) -> str:
        import platform

        return platform.system().lower()  # "windows", "linux", "darwin"

    def _estimate_ram_fallback(self) -> float:
        """Estima RAM sem psutil via comandos do SO."""
        try:
            import platform

            sys = platform.system().lower()
            if sys == "linux":
                with open("/proc/meminfo") as f:
                    for line in f:
                        if line.startswith("MemTotal:"):
                            kb = int(line.split()[1])
                            return round(kb / (1024**2), 1)
            elif sys == "darwin":
                result = subprocess.run(
                    ["sysctl", "-n", "hw.memsize"], capture_output=True, text=True
                )
                return round(int(result.stdout.strip()) / (1024**3), 1)
            elif sys == "windows":
                result = subprocess.run(
                    ["wmic", "computersystem", "get", "TotalPhysicalMemory"],
                    capture_output=True,
                    text=True,
                )
                lines = [
                    ln.strip() for ln in result.stdout.strip().splitlines() if ln.strip().isdigit()
                ]
                if lines:
                    return round(int(lines[0]) / (1024**3), 1)
        except Exception:
            pass
        return 8.0  # assume 8GB se não conseguir detectar

    def _detect_gpu(self) -> dict:
        """Tenta detectar GPU via nvidia-smi, rocm-smi ou system_profiler."""
        info = {
            "name": None,
            "vram_gb": 0.0,
            "has_cuda": False,
            "has_metal": False,
            "has_rocm": False,
        }

        # NVIDIA (CUDA)
        try:
            result = subprocess.run(
                ["nvidia-smi", "--query-gpu=name,memory.total", "--format=csv,noheader,nounits"],
                capture_output=True,
                text=True,
                timeout=5,
            )
            if result.returncode == 0 and result.stdout.strip():
                parts = result.stdout.strip().split(",")
                info["name"] = parts[0].strip()
                info["vram_gb"] = round(float(parts[1].strip()) / 1024, 1)
                info["has_cuda"] = True
                return info
        except (FileNotFoundError, subprocess.TimeoutExpired):
            pass

        # AMD (ROCm)
        try:
            result = subprocess.run(
                ["rocm-smi", "--showmeminfo", "vram"], capture_output=True, text=True, timeout=5
            )
            if result.returncode == 0:
                info["has_rocm"] = True
                info["name"] = "AMD GPU (ROCm)"
                return info
        except (FileNotFoundError, subprocess.TimeoutExpired):
            pass

        # Apple Silicon (Metal)
        try:
            import platform

            if platform.system() == "Darwin" and platform.processor() == "arm":
                result = subprocess.run(
                    ["system_profiler", "SPDisplaysDataType"],
                    capture_output=True,
                    text=True,
                    timeout=5,
                )
                if "Apple" in result.stdout:
                    info["has_metal"] = True
                    info["name"] = "Apple Silicon GPU"
                    # Apple Silicon compartilha RAM - estima VRAM como metade da RAM
                    info["vram_gb"] = self._estimate_ram_fallback() / 2
                    return info
        except Exception:
            pass

        return info

    def _recommend_models(self, profile: HardwareProfile) -> list[str]:
        """
        Retorna modelos recomendados em ordem de qualidade decrescente,
        levando em conta RAM e VRAM disponíveis.
        """
        available_ram = profile.ram_gb
        # Se tem GPU, usa VRAM como referência; senão usa RAM (com overhead de OS ~2GB)
        available_vram = (
            profile.gpu_vram_gb
            if profile.has_cuda or profile.has_metal or profile.has_rocm
            else 0.0
        )
        usable_ram = max(0, available_ram - 2.0)  # reserva 2GB para o OS

        candidates = []
        for model_name, reqs in MODEL_REQUIREMENTS.items():
            if available_vram > 0:
                fits = reqs["vram_gb"] <= available_vram
            else:
                fits = reqs["ram_gb"] <= usable_ram

            if fits:
                candidates.append((model_name, reqs))

        # Ordena por qualidade (excellent > high > medium > low > basic)
        quality_order = {"excellent": 5, "high": 4, "medium": 3, "low": 2, "basic": 1}
        candidates.sort(key=lambda x: quality_order.get(x[1]["quality"], 0), reverse=True)

        return [c[0] for c in candidates[:5]]  # top 5

    def get_best_local_model(self, installed_models: list[str]) -> str | None:
        """
        Dentre os modelos já instalados no Ollama, retorna o melhor compatível.
        """
        if self._profile is None:
            self.analyze()

        recommended = self._profile.recommended_models
        # Normaliza nomes (ollama usa "model:tag")
        installed_normalized = {m.split(":")[0]: m for m in installed_models}

        for rec in recommended:
            base = rec.split(":")[0]
            if base in installed_normalized:
                return installed_normalized[base]
            if rec in installed_models:
                return rec

        # Nenhum recomendado instalado - tenta fallback
        if installed_models:
            return installed_models[0]
        return None

    def pull_best_model(self, ollama_provider) -> str | None:
        """
        Verifica se o melhor modelo recomendado está instalado.
        Se não estiver, baixa automaticamente via Ollama.
        Retorna o nome do modelo disponível.
        """
        if self._profile is None:
            self.analyze()

        installed = ollama_provider.list_local_models()
        installed_names = {m.split(":")[0] for m in installed}

        for model_name in self._profile.recommended_models:
            base = model_name.split(":")[0]

            if base in installed_names or model_name in installed:
                logger.info(f"[HARDWARE] Modelo recomendado já instalado: {model_name}")
                return model_name

            # Tenta baixar o modelo
            logger.info(f"[HARDWARE] Baixando modelo recomendado: {model_name} ...")
            try:
                result = subprocess.run(
                    ["ollama", "pull", model_name], capture_output=True, text=True, timeout=600
                )
                if result.returncode == 0:
                    logger.info(f"[HARDWARE] Modelo {model_name} baixado com sucesso!")
                    return model_name
                else:
                    logger.warning(f"[HARDWARE] Falha ao baixar {model_name}: {result.stderr}")
            except (FileNotFoundError, subprocess.TimeoutExpired) as e:
                logger.warning(f"[HARDWARE] Não foi possível baixar {model_name}: {e}")

        return installed[0] if installed else None

    def summary(self) -> dict:
        """Retorna um resumo legível do hardware detectado."""
        if self._profile is None:
            self.analyze()
        p = self._profile
        return {
            "ram_gb": p.ram_gb,
            "cpu_cores": p.cpu_cores,
            "cpu_threads": p.cpu_threads,
            "gpu": p.gpu_name,
            "gpu_vram_gb": p.gpu_vram_gb,
            "acceleration": (
                "CUDA"
                if p.has_cuda
                else "Metal" if p.has_metal else "ROCm" if p.has_rocm else "CPU only"
            ),
            "recommended_models": p.recommended_models,
        }
