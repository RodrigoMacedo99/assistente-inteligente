# Assistente Inteligente — AI Adapter Multi-Provider

## Objetivo

AI Adapter multi-provider com Clean Architecture capaz de:

- Integrar múltiplos providers de LLM (OpenAI, Anthropic, Groq, Gemini, DeepSeek, Mistral, Ollama, OpenRouter)
- Roteamento inteligente por custo/dificuldade/prioridade com fallback automático e circuit breaker
- Providers de voz TTS/STT com fallback automático e circuit breaker
- Políticas de governança, rate limiting, quota diária e cache
- Observabilidade e streaming de tokens
- API REST multi-tenant via FastAPI
- Sistema de agentes modular

---

## Comandos de Desenvolvimento

```bash
# Instalar dependências (cria .venv automaticamente)
uv sync --extra dev

# Rodar testes
uv run pytest

# Linting (Ruff)
uv run --with ruff ruff check aiadapter/ tests/

# Autofix de linting
uv run --with ruff ruff check --fix --unsafe-fixes aiadapter/ tests/

# Formatação (Black)
uv run --with black black aiadapter/ tests/

# Rodar o servidor
uv run python main.py
```

---

## Arquitetura

Baseada em **Clean Architecture**:

```text
aiadapter/
├── core/                  # Domínio — contratos e entidades (sem dependências externas)
│   ├── entities/          # AIRequest, AIResponse, AudioRequest, AudioResponse
│   ├── interfaces/        # AIProvider, AIRouter, AIPolicy, AITTSProvider, AISTTProvider...
│   └── enums/             # AICapability
├── infrastructure/        # Implementações concretas
│   ├── providers/         # LLM: openai, anthropic, groq, gemini, deepseek, mistral, ollama
│   │   ├── tts/           # pyttsx3, edge_tts, elevenlabs, openai_tts
│   │   └── stt/           # whisper_local, groq_stt, openai_stt
│   ├── governance/        # SimplePolicy, SimpleCache, RateLimiter, QuotaManager
│   ├── routing/           # CostRouter (tier-based: free/low/medium/high)
│   └── system/            # HardwareAnalyzer, MicrophoneCapture
├── application/           # Orquestração
│   ├── ai_service.py      # Pipeline LLM com fallback
│   ├── audio_service.py   # Pipeline TTS/STT com circuit breaker
│   └── provider_health.py # ProviderHealth — circuit breaker por provider
├── config/                # Settings (carrega .env)
├── api/                   # FastAPI — endpoints REST e WebSocket
├── agents/                # BaseAgent, SimpleAgent, AgentManager
└── factory/               # AbstractFactory, FactoryProvider
```

---

## Convenções de Código

- **Python 3.10+** — usar `X | None` em vez de `Optional[X]`, `list[T]` em vez de `List[T]`
- **Black** para formatação (line-length 100)
- **Ruff** para linting — `N999` ignorado (diretório do projeto tem hífen, aceito via config)
- **Imports**: stdlib → third-party → first-party (isort, `force-sort-within-sections = true`)
- **`raise X from e`** dentro de blocos `except` (B904)
- **`ClassVar`** para atributos mutáveis de classe (RUF012)

---

## Providers de Voz

### TTS (ordem de prioridade)

| Provider | Custo | Modo |
| --- | --- | --- |
| `pyttsx3` | Grátis | Offline |
| `edge_tts` | Grátis | Online (Microsoft Neural) |
| `elevenlabs_tts` | $0.18/1k chars | Online |
| `openai_tts` | $15/1M chars | Online |

### STT (ordem de prioridade)

| Provider | Custo | Modo |
| --- | --- | --- |
| `whisper_local` | Grátis | Offline (faster-whisper) |
| `groq_stt` | Grátis | Online (Whisper large-v3) |
| `openai_stt` | $0.006/min | Online |

### Fallback automático com Circuit Breaker

O `AudioService` implementa fallback automático entre providers com circuit breaker:

- **Retry por provider**: tenta `max_retries` vezes antes de cair para o próximo (default: 1)
- **Circuit breaker**: após `circuit_breaker_threshold` falhas consecutivas (default: 3), o provider é ignorado por `circuit_breaker_cooldown` segundos (default: 60s)
- **Half-open reset**: após o cooldown, o circuit fecha automaticamente e o provider pode ser tentado novamente
- **Fallback chain**: `AudioResponse.fallback_chain` registra quais providers foram tentados e por quê

```python
svc = AudioService(
    tts_providers=[pyttsx3, edge_tts, elevenlabs, openai_tts],
    stt_providers=[whisper_local, groq_stt, openai_stt],
    max_retries=1,
    circuit_breaker_threshold=3,
    circuit_breaker_cooldown=60.0,
)
```

---

## Pipeline LLM

```text
Request → Policy check → Rate Limiting → Cache → Router (tier) →
Provider (com fallback) → Tool Calling → Observability → Cache → Response
```

### Roteamento por tier (CostRouter)

| Tier | Providers (ordem) |
| --- | --- |
| `free` | ollama → openrouter_free → groq → gemini → deepseek |
| `low` | groq → gemini → deepseek → mistral → ollama → openai |
| `medium` | deepseek → mistral → groq → gemini → openai → anthropic |
| `high` | openai → anthropic → gemini → deepseek → mistral |

---

## API REST

| Método | Endpoint | Descrição |
| --- | --- | --- |
| `POST` | `/v1/completions` | LLM completion (streaming opcional) |
| `GET` | `/v1/models` | Lista modelos disponíveis |
| `GET` | `/v1/status` | Status dos providers |
| `GET` | `/v1/hardware` | Perfil de hardware e modelos Ollama recomendados |
| `GET` | `/v1/quotas` | Quotas diárias dos providers gratuitos |
| `POST` | `/v1/speak` | TTS com fallback automático |
| `POST` | `/v1/transcribe` | STT com fallback automático |
| `GET` | `/v1/voices` | Lista vozes TTS disponíveis |
| `GET` | `/v1/audio/status` | Saúde dos providers de voz |
| `WS` | `/v1/transcribe/stream` | STT em tempo real via WebSocket |

**Multi-tenant**: header `X-Tenant-ID` isola rate limiting e quota por cliente.

---

## Variáveis de Ambiente

```bash
# LLM Providers
OPENAI_API_KEY=
ANTHROPIC_API_KEY=
GROQ_API_KEY=
GOOGLE_API_KEY=
DEEPSEEK_API_KEY=
MISTRAL_API_KEY=
OPENROUTER_API_KEY=

# Voz
ELEVENLABS_API_KEY=
WHISPER_MODEL_SIZE=base   # tiny | base | small | medium | large-v3

# Servidor
HOST=0.0.0.0
PORT=8000
LOG_LEVEL=INFO
```

---

## Testes

```bash
# Todos os testes unitários
uv run pytest tests/unit/

# Testes do AudioService e fallback
uv run pytest tests/unit/test_audio_service.py tests/unit/test_audio_service_fallback.py -v

# Com cobertura
uv run pytest --cov=aiadapter --cov-report=term-missing
```

Cobertura mínima exigida: **70%** (configurado em `pyproject.toml`).

---

## Nota sobre N999

O erro `N999 Invalid module name` é causado pelo hífen no diretório `assistente-inteligente`.
Está suprimido no `pyproject.toml` (`ignore = ["N999"]`) pois renomear o diretório raiz
quebraria referências externas. O pacote Python em si (`aiadapter/`) usa nome válido.
