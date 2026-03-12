import logging
import json
from typing import Optional, List, Dict, Any

from fastapi import FastAPI, HTTPException, Depends, Header
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field

from aiadapter.config.settings import load_settings
from aiadapter.infrastructure.routing.cost_router import CostRouter
from aiadapter.infrastructure.governance.simple_policy import SimplePolicy
from aiadapter.infrastructure.governance.logger_observability import LoggerObservability
from aiadapter.infrastructure.governance.simple_rate_limiter import SimpleRateLimiter
from aiadapter.infrastructure.governance.simple_cache import SimpleCache
from aiadapter.infrastructure.governance.daily_quota_manager import DailyQuotaManager
from aiadapter.infrastructure.system.hardware_analyzer import HardwareAnalyzer
from aiadapter.application.ai_service import AIService
from aiadapter.core.entities.airequest import AIRequest

# ─── Providers ────────────────────────────────────────────────────────────────
from aiadapter.infrastructure.providers.openai.openai_provider import OpenAIProvider
from aiadapter.infrastructure.providers.anthropic.calude_provider import ClaudeProvider
from aiadapter.infrastructure.providers.google.gemini_provider import GeminiProvider
from aiadapter.infrastructure.providers.local.ollama_provider import OllamaProvider
from aiadapter.infrastructure.providers.groq.groq_provider import GroqProvider
from aiadapter.infrastructure.providers.mistral.mistral_provider import MistralProvider
from aiadapter.infrastructure.providers.deepseek.deepseek_provider import DeepSeekProvider
from aiadapter.infrastructure.providers.openrouter.openrouter_provider import OpenRouterProvider

# ─── App Setup ────────────────────────────────────────────────────────────────
app = FastAPI(
    title="AI Adapter API",
    description=(
        "Gateway multi-provider de IA com seleção inteligente baseada em "
        "custo, dificuldade, complexidade e quotas diárias. "
        "Suporte a: OpenAI, Anthropic, Gemini, Groq, Mistral, DeepSeek, OpenRouter e Ollama (local)."
    ),
    version="2.0.0",
)

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(name)s %(levelname)s %(message)s")
logger = logging.getLogger(__name__)

settings = load_settings()
quota_manager = DailyQuotaManager()
hardware_analyzer = HardwareAnalyzer(ollama_base_url=settings.ollama_base_url)

# Cache de serviços por tenant
tenants: Dict[str, AIService] = {}


# ─── Request / Response Models ─────────────────────────────────────────────────
class AIRequestModel(BaseModel):
    prompt: str
    model: Optional[str] = None
    messages: Optional[List[Dict[str, Any]]] = None
    temperature: float = Field(default=0.7, ge=0.0, le=2.0)
    max_tokens: int = Field(default=512, ge=1, le=32768)
    context: Optional[Dict[str, Any]] = None
    stream: bool = False
    tools: Optional[List[Dict[str, Any]]] = None
    priority: str = Field(default="normal", pattern="^(low|normal|high)$")
    difficulty: str = Field(default="medium", pattern="^(easy|medium|hard|expert)$")
    complexity: float = Field(default=0.5, ge=0.0, le=1.0)
    max_cost: str = Field(default="medium", pattern="^(free|low|medium|high)$")
    preferred_provider: Optional[str] = None


class AIResponseModel(BaseModel):
    output: Optional[str] = None
    tokens_used: int
    provider_name: str
    cost: float
    is_streaming_chunk: bool = False
    tool_calls: Optional[List[Dict[str, Any]]] = None


# ─── Helpers ──────────────────────────────────────────────────────────────────
def get_tenant_id(x_tenant_id: str = Header(...)) -> str:
    if not x_tenant_id:
        raise HTTPException(status_code=400, detail="X-Tenant-ID header é obrigatório")
    return x_tenant_id


def _build_providers() -> Dict:
    """Instancia todos os providers disponíveis (apenas os que têm chave configurada)."""
    providers = {}

    # Ollama local (sem chave de API)
    ollama = OllamaProvider(base_url=settings.ollama_base_url)
    if ollama.is_available():
        providers["ollama"] = ollama
        logger.info("[INIT] Ollama disponível localmente")

        # Analisa hardware e garante melhor modelo local
        try:
            profile = hardware_analyzer.analyze()
            best_model = hardware_analyzer.pull_best_model(ollama)
            if best_model:
                logger.info(f"[INIT] Melhor modelo local: {best_model} (RAM={profile.ram_gb}GB)")
        except Exception as e:
            logger.warning(f"[INIT] Análise de hardware falhou: {e}")
    else:
        logger.info("[INIT] Ollama não disponível (não está rodando)")

    if settings.groq_api_key:
        providers["groq"] = GroqProvider(api_key=settings.groq_api_key)
        logger.info("[INIT] Groq provider ativo")

    if settings.gemini_api_key:
        providers["gemini"] = GeminiProvider(api_key=settings.gemini_api_key)
        logger.info("[INIT] Gemini provider ativo")

    if settings.deepseek_api_key:
        providers["deepseek"] = DeepSeekProvider(api_key=settings.deepseek_api_key)
        logger.info("[INIT] DeepSeek provider ativo")

    if settings.mistral_api_key:
        providers["mistral"] = MistralProvider(api_key=settings.mistral_api_key)
        logger.info("[INIT] Mistral provider ativo")

    if settings.openrouter_api_key:
        providers["openrouter"] = OpenRouterProvider(
            api_key=settings.openrouter_api_key,
            site_url=settings.openrouter_site_url,
            site_name=settings.openrouter_site_name,
        )
        logger.info("[INIT] OpenRouter provider ativo")

    if settings.openai_api_key:
        from openai import OpenAI
        providers["openai"] = OpenAIProvider(client=OpenAI(api_key=settings.openai_api_key))
        logger.info("[INIT] OpenAI provider ativo")

    if settings.anthropic_api_key:
        from anthropic import Anthropic
        providers["anthropic"] = ClaudeProvider(client=Anthropic(api_key=settings.anthropic_api_key))
        logger.info("[INIT] Anthropic provider ativo")

    if not providers:
        logger.warning("[INIT] Nenhum provider configurado! Configure ao menos uma API key ou inicie o Ollama.")

    return providers


def get_or_create_tenant_service(tenant_id: str) -> AIService:
    if tenant_id not in tenants:
        providers = _build_providers()
        router = CostRouter(providers=providers, quota_manager=quota_manager)
        tenants[tenant_id] = AIService(
            router=router,
            policy=SimplePolicy(),
            observability=LoggerObservability(),
            rate_limiter=SimpleRateLimiter(),
            cache=SimpleCache(),
        )
    return tenants[tenant_id]


# ─── Routes ───────────────────────────────────────────────────────────────────
@app.get("/health")
async def health_check():
    providers_status = {}
    for name, provider in _build_providers().items():
        try:
            meta = provider.get_metadata()
            providers_status[name] = {"available": True, "models": meta.models[:3]}
        except Exception as e:
            providers_status[name] = {"available": False, "error": str(e)}

    return {
        "status": "ok",
        "providers": providers_status,
        "quota_status": quota_manager.get_all_status(),
    }


@app.get("/v1/hardware")
async def get_hardware_info():
    """Retorna informações de hardware e modelos locais recomendados."""
    try:
        return hardware_analyzer.summary()
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/v1/completions")
async def create_completion(
    request: AIRequestModel,
    tenant_id: str = Depends(get_tenant_id),
):
    try:
        ai_service = get_or_create_tenant_service(tenant_id)

        ai_request = AIRequest(
            prompt=request.prompt,
            model=request.model,
            messages=request.messages,
            temperature=request.temperature,
            max_tokens=request.max_tokens,
            context=request.context,
            client_id=tenant_id,
            stream=request.stream,
            tools=request.tools,
            priority=request.priority,
            difficulty=request.difficulty,
            complexity=request.complexity,
            max_cost=request.max_cost,
            preferred_provider=request.preferred_provider,
        )

        if request.stream:
            return StreamingResponse(
                _stream_generator(ai_service, ai_request),
                media_type="application/x-ndjson",
            )

        response = ai_service.execute(ai_request)

        # Registra uso na quota do provider
        quota_manager.record_request(response.provider_name)

        return AIResponseModel(
            output=response.output,
            tokens_used=response.tokens_used,
            provider_name=response.provider_name,
            cost=response.cost,
            is_streaming_chunk=response.is_streaming_chunk,
            tool_calls=response.tool_calls,
        )

    except ValueError as e:
        raise HTTPException(status_code=422, detail=str(e))
    except RuntimeError as e:
        raise HTTPException(status_code=503, detail=str(e))
    except Exception as e:
        logger.error(f"Erro em create_completion: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


async def _stream_generator(ai_service: AIService, request: AIRequest):
    try:
        response_or_gen = ai_service.execute(request)
        if hasattr(response_or_gen, "__iter__") and not isinstance(response_or_gen, str):
            for chunk in response_or_gen:
                quota_manager.record_request(chunk.provider_name)
                yield json.dumps({
                    "output": chunk.output,
                    "tokens_used": chunk.tokens_used,
                    "provider_name": chunk.provider_name,
                    "cost": chunk.cost,
                    "is_streaming_chunk": chunk.is_streaming_chunk,
                }).encode() + b"\n"
        else:
            quota_manager.record_request(response_or_gen.provider_name)
            yield json.dumps({
                "output": response_or_gen.output,
                "tokens_used": response_or_gen.tokens_used,
                "provider_name": response_or_gen.provider_name,
                "cost": response_or_gen.cost,
                "is_streaming_chunk": False,
            }).encode() + b"\n"
    except Exception as e:
        logger.error(f"Erro no stream: {e}", exc_info=True)
        yield json.dumps({"error": str(e)}).encode() + b"\n"


@app.get("/v1/models")
async def list_models(tenant_id: str = Depends(get_tenant_id)):
    """Lista todos os modelos disponíveis nos providers configurados."""
    try:
        providers = _build_providers()
        models = []
        for provider in providers.values():
            meta = provider.get_metadata()
            for model in meta.models:
                models.append({
                    "id": model,
                    "provider": meta.name,
                    "supports_streaming": meta.supports_streaming,
                    "cost_per_1k_tokens": meta.cost_per_1k_tokens,
                    "is_free": meta.cost_per_1k_tokens == 0.0 or ":free" in model,
                    "is_local": meta.is_local,
                    "capabilities": meta.capabilities,
                })
        return {"models": models, "total": len(models)}
    except Exception as e:
        logger.error(f"Erro em list_models: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/v1/quotas")
async def get_quota_status():
    """Retorna o status atual das quotas diárias de todos os provedores gratuitos."""
    return quota_manager.get_all_status()


@app.get("/v1/tenants/{tenant_id}/stats")
async def get_tenant_stats(tenant_id: str):
    if tenant_id not in tenants:
        raise HTTPException(status_code=404, detail="Tenant não encontrado")
    return {
        "tenant_id": tenant_id,
        "active": True,
        "quota_status": quota_manager.get_all_status(),
    }


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host=settings.host, port=settings.port, log_level=settings.log_level.lower())
