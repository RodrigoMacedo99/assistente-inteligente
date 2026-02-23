from fastapi import FastAPI, HTTPException, Depends, Header
from fastapi.responses import StreamingResponse
from pydantic import BaseModel
from typing import Optional, List, Dict, Any
import logging
import json

from aiadapter.config.settings import load_settings
from aiadapter.infrastructure.providers.openai.openai_provider import OpenAIProvider
from aiadapter.infrastructure.providers.anthropic.calude_provider import AnthropicProvider
from aiadapter.infrastructure.routing.cost_router import CostRouter
from aiadapter.infrastructure.governance.simple_policy import SimplePolicy
from aiadapter.infrastructure.governance.logger_observability import LoggerObservability
from aiadapter.infrastructure.governance.simple_rate_limiter import SimpleRateLimiter
from aiadapter.infrastructure.governance.simple_cache import SimpleCache
from aiadapter.application.ai_service import AIService
from aiadapter.core.entities.airequest import AIRequest
from openai import OpenAI
from anthropic import Anthropic

# Initialize FastAPI app
app = FastAPI(
    title="AI Adapter API",
    description="Multi-provider AI Gateway with Clean Architecture",
    version="1.0.0"
)

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Load settings
settings = load_settings()

# Multi-tenant support: Dictionary to store tenant-specific services
tenants: Dict[str, AIService] = {}

# Request/Response models
class AIRequestModel(BaseModel):
    prompt: str
    messages: Optional[List[Dict[str, Any]]] = None
    temperature: float = 0.7
    max_tokens: int = 512
    context: Optional[Dict[str, Any]] = None
    stream: bool = False
    tools: Optional[List[Dict[str, Any]]] = None

class AIResponseModel(BaseModel):
    output: Optional[str] = None
    tokens_used: int
    provider_name: str
    cost: float
    is_streaming_chunk: bool = False
    tool_calls: Optional[List[Dict[str, Any]]] = None

# Dependency to get tenant ID from header
def get_tenant_id(x_tenant_id: str = Header(...)) -> str:
    if not x_tenant_id:
        raise HTTPException(status_code=400, detail="X-Tenant-ID header is required")
    return x_tenant_id

# Initialize or get tenant service
def get_or_create_tenant_service(tenant_id: str) -> AIService:
    if tenant_id not in tenants:
        # Initialize providers for this tenant
        openai_client = OpenAI(api_key=settings.openai_api_key)
        openai_provider = OpenAIProvider(client=openai_client)

        providers = {
            "openai": openai_provider,
        }

        router = CostRouter(providers)
        policy = SimplePolicy()
        observability = LoggerObservability()
        rate_limiter = SimpleRateLimiter()
        cache = SimpleCache()

        tenants[tenant_id] = AIService(
            router=router,
            policy=policy,
            observability=observability,
            rate_limiter=rate_limiter,
            cache=cache
        )

    return tenants[tenant_id]

# Routes
@app.get("/health")
async def health_check():
    return {"status": "ok"}

@app.post("/v1/completions")
async def create_completion(
    request: AIRequestModel,
    tenant_id: str = Depends(get_tenant_id)
):
    try:
        ai_service = get_or_create_tenant_service(tenant_id)
        
        ai_request = AIRequest(
            prompt=request.prompt,
            messages=request.messages,
            temperature=request.temperature,
            max_tokens=request.max_tokens,
            context=request.context,
            client_id=tenant_id,
            stream=request.stream,
            tools=request.tools
        )

        if request.stream:
            return StreamingResponse(
                stream_generator(ai_service, ai_request),
                media_type="application/x-ndjson"
            )
        else:
            response = ai_service.execute(ai_request)
            return AIResponseModel(
                output=response.output,
                tokens_used=response.tokens_used,
                provider_name=response.provider_name,
                cost=response.cost,
                is_streaming_chunk=response.is_streaming_chunk,
                tool_calls=response.tool_calls
            )
    except Exception as e:
        logger.error(f"Error in create_completion: {e}")
        raise HTTPException(status_code=500, detail=str(e))

async def stream_generator(ai_service: AIService, request: AIRequest):
    try:
        response_or_generator = ai_service.execute(request)
        if hasattr(response_or_generator, '__iter__') and not isinstance(response_or_generator, str):
            for chunk in response_or_generator:
                yield json.dumps({
                    "output": chunk.output,
                    "tokens_used": chunk.tokens_used,
                    "provider_name": chunk.provider_name,
                    "cost": chunk.cost,
                    "is_streaming_chunk": chunk.is_streaming_chunk,
                    "tool_calls": chunk.tool_calls
                }).encode() + b"\n"
        else:
            yield json.dumps({
                "output": response_or_generator.output,
                "tokens_used": response_or_generator.tokens_used,
                "provider_name": response_or_generator.provider_name,
                "cost": response_or_generator.cost,
                "is_streaming_chunk": response_or_generator.is_streaming_chunk,
                "tool_calls": response_or_generator.tool_calls
            }).encode() + b"\n"
    except Exception as e:
        logger.error(f"Error in stream_generator: {e}")
        yield json.dumps({"error": str(e)}).encode() + b"\n"

@app.get("/v1/models")
async def list_models(tenant_id: str = Depends(get_tenant_id)):
    try:
        ai_service = get_or_create_tenant_service(tenant_id)
        # Return available models from providers
        return {
            "models": [
                {
                    "name": "gpt-4o",
                    "provider": "openai",
                    "supports_streaming": True
                },
                {
                    "name": "gpt-4o-mini",
                    "provider": "openai",
                    "supports_streaming": True
                }
            ]
        }
    except Exception as e:
        logger.error(f"Error in list_models: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/v1/tenants/{tenant_id}/stats")
async def get_tenant_stats(tenant_id: str):
    try:
        if tenant_id not in tenants:
            raise HTTPException(status_code=404, detail="Tenant not found")
        
        # Return tenant-specific statistics
        return {
            "tenant_id": tenant_id,
            "requests_processed": 0,  # TODO: Implement request counting
            "cache_hits": 0,  # TODO: Implement cache hit counting
            "total_tokens_used": 0  # TODO: Implement token counting
        }
    except Exception as e:
        logger.error(f"Error in get_tenant_stats: {e}")
        raise HTTPException(status_code=500, detail=str(e))

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
