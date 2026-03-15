import contextlib
import json
import logging
from typing import Any

from fastapi import (
    Depends,
    FastAPI,
    File,
    Form,
    Header,
    HTTPException,
    UploadFile,
    WebSocket,
    WebSocketDisconnect,
)
from fastapi.responses import Response, StreamingResponse
from pydantic import BaseModel, Field

from aiadapter.application.ai_service import AIService
from aiadapter.application.audio_service import AudioService
from aiadapter.config.settings import load_settings
from aiadapter.core.entities.airequest import AIRequest
from aiadapter.core.entities.audiorequest import AudioRequest
from aiadapter.infrastructure.governance.daily_quota_manager import DailyQuotaManager
from aiadapter.infrastructure.governance.logger_observability import LoggerObservability
from aiadapter.infrastructure.governance.simple_cache import SimpleCache
from aiadapter.infrastructure.governance.simple_policy import SimplePolicy
from aiadapter.infrastructure.governance.simple_rate_limiter import SimpleRateLimiter
from aiadapter.infrastructure.providers.anthropic.calude_provider import ClaudeProvider
from aiadapter.infrastructure.providers.deepseek.deepseek_provider import DeepSeekProvider
from aiadapter.infrastructure.providers.google.gemini_provider import GeminiProvider
from aiadapter.infrastructure.providers.groq.groq_provider import GroqProvider
from aiadapter.infrastructure.providers.local.ollama_provider import OllamaProvider
from aiadapter.infrastructure.providers.mistral.mistral_provider import MistralProvider

# ─── Providers ────────────────────────────────────────────────────────────────
from aiadapter.infrastructure.providers.openai.openai_provider import OpenAIProvider
from aiadapter.infrastructure.providers.openrouter.openrouter_provider import OpenRouterProvider
from aiadapter.infrastructure.routing.cost_router import CostRouter
from aiadapter.infrastructure.system.hardware_analyzer import HardwareAnalyzer

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
tenants: dict[str, AIService] = {}

# AudioService singleton (providers inicializam sob demanda)
_audio_service: AudioService | None = None


def _build_audio_service() -> AudioService:
    """Constrói o AudioService com todos os providers de voz disponíveis."""
    from aiadapter.infrastructure.providers.stt.groq_stt_provider import GroqSTTProvider
    from aiadapter.infrastructure.providers.stt.openai_stt_provider import OpenAISTTProvider
    from aiadapter.infrastructure.providers.stt.whisper_local_provider import (
        WhisperLocalProvider as WhisperLocalSTTProvider,
    )
    from aiadapter.infrastructure.providers.tts.edge_tts_provider import EdgeTTSProvider
    from aiadapter.infrastructure.providers.tts.elevenlabs_provider import ElevenLabsTTSProvider
    from aiadapter.infrastructure.providers.tts.openai_tts_provider import OpenAITTSProvider
    from aiadapter.infrastructure.providers.tts.pyttsx3_provider import Pyttsx3TTSProvider

    # TTS — ordem: local → gratuito → pago
    tts_providers = [
        Pyttsx3TTSProvider(),
        EdgeTTSProvider(),
    ]
    if settings.elevenlabs_api_key:
        tts_providers.append(ElevenLabsTTSProvider(api_key=settings.elevenlabs_api_key))
    if settings.openai_api_key:
        tts_providers.append(OpenAITTSProvider(api_key=settings.openai_api_key))

    # STT — ordem: local → gratuito → pago
    stt_providers = [
        WhisperLocalSTTProvider(model_size=settings.whisper_model_size),
    ]
    if settings.groq_api_key:
        stt_providers.append(GroqSTTProvider(api_key=settings.groq_api_key))
    if settings.openai_api_key:
        stt_providers.append(OpenAISTTProvider(api_key=settings.openai_api_key))

    svc = AudioService(tts_providers=tts_providers, stt_providers=stt_providers)
    logger.info(f"[AUDIO] Providers TTS: {[p.get_name() for p in tts_providers if p.is_available()]}")
    logger.info(f"[AUDIO] Providers STT: {[p.get_name() for p in stt_providers if p.is_available()]}")
    return svc


def get_audio_service() -> AudioService:
    global _audio_service
    if _audio_service is None:
        _audio_service = _build_audio_service()
    return _audio_service


# ─── Request / Response Models ─────────────────────────────────────────────────
class AIRequestModel(BaseModel):
    prompt: str
    model: str | None = None
    messages: list[dict[str, Any]] | None = None
    temperature: float = Field(default=0.7, ge=0.0, le=2.0)
    max_tokens: int = Field(default=512, ge=1, le=32768)
    context: dict[str, Any] | None = None
    stream: bool = False
    tools: list[dict[str, Any]] | None = None
    priority: str = Field(default="normal", pattern="^(low|normal|high)$")
    difficulty: str = Field(default="medium", pattern="^(easy|medium|hard|expert)$")
    complexity: float = Field(default=0.5, ge=0.0, le=1.0)
    max_cost: str = Field(default="medium", pattern="^(free|low|medium|high)$")
    preferred_provider: str | None = None


class AIResponseModel(BaseModel):
    output: str | None = None
    tokens_used: int
    provider_name: str
    cost: float
    is_streaming_chunk: bool = False
    tool_calls: list[dict[str, Any]] | None = None


# ─── Helpers ──────────────────────────────────────────────────────────────────
def get_tenant_id(x_tenant_id: str = Header(...)) -> str:
    if not x_tenant_id:
        raise HTTPException(status_code=400, detail="X-Tenant-ID header é obrigatório")
    return x_tenant_id


def _build_providers() -> dict:
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
        raise HTTPException(status_code=500, detail=str(e)) from e


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
        raise HTTPException(status_code=422, detail=str(e)) from e
    except RuntimeError as e:
        raise HTTPException(status_code=503, detail=str(e)) from e
    except Exception as e:
        logger.error(f"Erro em create_completion: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e)) from e


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
        raise HTTPException(status_code=500, detail=str(e)) from e


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


# ─── Voice Routes ─────────────────────────────────────────────────────────────

@app.post(
    "/v1/speak",
    summary="Síntese de voz (TTS)",
    description=(
        "Converte texto em áudio. "
        "Usa pyttsx3 (offline) → Edge TTS (gratuito) → ElevenLabs → OpenAI conforme disponibilidade."
    ),
    response_class=Response,
)
async def text_to_speech(
    text: str = Form(..., description="Texto a ser sintetizado"),
    voice: str | None = Form(default=None, description="Nome ou ID da voz"),
    speed: float = Form(default=1.0, ge=0.25, le=4.0, description="Velocidade da fala"),
    preferred_provider: str | None = Form(default=None, description="Provider preferido (pyttsx3, edge_tts, elevenlabs_tts, openai_tts)"),
):
    try:
        audio_svc = get_audio_service()
        request = AudioRequest(
            text=text,
            voice=voice,
            speed=speed,
            preferred_provider=preferred_provider,
        )
        response = audio_svc.speak(request)

        media_type = {
            "mp3": "audio/mpeg",
            "wav": "audio/wav",
            "opus": "audio/ogg",
            "aac": "audio/aac",
            "flac": "audio/flac",
        }.get(response.audio_format, "audio/mpeg")

        return Response(
            content=response.audio_data,
            media_type=media_type,
            headers={
                "X-Provider": response.provider_name,
                "X-Cost": str(response.cost),
                "X-Audio-Format": response.audio_format,
            },
        )
    except ValueError as e:
        raise HTTPException(status_code=422, detail=str(e)) from e
    except RuntimeError as e:
        raise HTTPException(status_code=503, detail=str(e)) from e
    except Exception as e:
        logger.error(f"Erro em text_to_speech: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e)) from e


@app.post(
    "/v1/transcribe",
    summary="Transcrição de voz (STT)",
    description=(
        "Transcreve arquivo de áudio para texto. "
        "Usa faster-whisper (offline) → Groq Whisper (gratuito) → OpenAI Whisper conforme disponibilidade."
    ),
)
async def speech_to_text(
    file: UploadFile = File(..., description="Arquivo de áudio (wav, mp3, m4a, webm)"),
    language: str | None = Form(default=None, description="Código do idioma (ex: pt, en). None = auto-detect"),
    preferred_provider: str | None = Form(default=None, description="Provider preferido (whisper_local, groq_stt, openai_stt)"),
):
    try:
        audio_data = await file.read()
        if not audio_data:
            raise HTTPException(status_code=422, detail="Arquivo de áudio vazio")

        ext = (file.filename or "audio.wav").rsplit(".", 1)[-1].lower()

        audio_svc = get_audio_service()
        request = AudioRequest(
            audio_data=audio_data,
            audio_format=ext,
            language=language,
            preferred_provider=preferred_provider,
        )
        response = audio_svc.transcribe(request)

        return {
            "transcription": response.transcription,
            "language_detected": response.language_detected,
            "confidence": response.confidence,
            "segments": response.segments,
            "provider": response.provider_name,
            "cost": response.cost,
        }
    except ValueError as e:
        raise HTTPException(status_code=422, detail=str(e)) from e
    except RuntimeError as e:
        raise HTTPException(status_code=503, detail=str(e)) from e
    except Exception as e:
        logger.error(f"Erro em speech_to_text: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e)) from e


@app.get("/v1/voices")
async def list_voices(language: str = "pt"):
    """Lista todas as vozes TTS disponíveis nos providers configurados."""
    audio_svc = get_audio_service()
    return {"voices": audio_svc.list_tts_voices(language)}


@app.get("/v1/audio/status")
async def get_audio_status():
    """Retorna disponibilidade dos providers de voz (TTS e STT)."""
    audio_svc = get_audio_service()
    return audio_svc.status()


@app.websocket("/v1/transcribe/stream")
async def transcribe_stream(websocket: WebSocket):
    """
    WebSocket para transcrição em tempo real.
    Cliente envia chunks de áudio (bytes) e recebe transcrições parciais.

    Protocolo:
      → bytes   : chunk de áudio PCM 16kHz mono int16
      → {"done": true}  : sinaliza fim do stream
      ← {"transcription": "...", "final": false}  : parcial
      ← {"transcription": "...", "final": true}   : final
    """
    await websocket.accept()
    audio_svc = get_audio_service()
    chunks: list[bytes] = []

    try:
        while True:
            msg = await websocket.receive()

            if "bytes" in msg:
                chunks.append(msg["bytes"])
                # Envia ACK a cada chunk recebido
                await websocket.send_json({"status": "chunk_received", "total_bytes": sum(len(c) for c in chunks)})

            elif "text" in msg:
                import json as _json
                data = _json.loads(msg["text"])
                if data.get("done"):
                    # Processa áudio acumulado
                    if chunks:
                        import io
                        import wave
                        raw_audio = b"".join(chunks)
                        buf = io.BytesIO()
                        with wave.open(buf, "wb") as wf:
                            wf.setnchannels(1)
                            wf.setsampwidth(2)
                            wf.setframerate(16000)
                            wf.writeframes(raw_audio)
                        wav_bytes = buf.getvalue()

                        request = AudioRequest(audio_data=wav_bytes, audio_format="wav", language=data.get("language"))
                        try:
                            response = audio_svc.transcribe(request)
                            await websocket.send_json({
                                "transcription": response.transcription,
                                "language_detected": response.language_detected,
                                "segments": response.segments,
                                "provider": response.provider_name,
                                "final": True,
                            })
                        except Exception as e:
                            await websocket.send_json({"error": str(e), "final": True})
                    else:
                        await websocket.send_json({"error": "Nenhum áudio recebido", "final": True})
                    break

    except WebSocketDisconnect:
        logger.info("[WS] Cliente desconectou do transcribe/stream")
    except Exception as e:
        logger.error(f"[WS] Erro no transcribe/stream: {e}", exc_info=True)
        with contextlib.suppress(Exception):
            await websocket.send_json({"error": str(e)})


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host=settings.host, port=settings.port, log_level=settings.log_level.lower())
