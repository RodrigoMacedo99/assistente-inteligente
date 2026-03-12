# AI Adapter — Documentação Técnica Completa

> Gateway multi-provider de Inteligência Artificial com seleção inteligente de modelos baseada em custo, capacidade de hardware e complexidade da tarefa. Suporta texto (LLM), síntese de voz (TTS) e transcrição de voz (STT).

---

## Índice

1. [Visão Geral](#1-visão-geral)
2. [Teoria e Motivação](#2-teoria-e-motivação)
3. [Arquitetura Clean Architecture](#3-arquitetura-clean-architecture)
4. [Padrões de Projeto](#4-padrões-de-projeto)
5. [Diagrama de Classes UML](#5-diagrama-de-classes-uml)
6. [Diagrama de Componentes](#6-diagrama-de-componentes)
7. [Diagrama de Sequência — Fluxo de Requisição](#7-diagrama-de-sequência--fluxo-de-requisição)
8. [Diagrama de Estado — Ciclo de Vida da Requisição](#8-diagrama-de-estado--ciclo-de-vida-da-requisição)
9. [Diagrama de Estado — Quota Diária](#9-diagrama-de-estado--quota-diária)
10. [Diagrama de Estado — Análise de Hardware](#10-diagrama-de-estado--análise-de-hardware)
11. [Diagrama de Atividades — Roteamento Inteligente](#11-diagrama-de-atividades--roteamento-inteligente)
12. [Diagrama de Implantação](#12-diagrama-de-implantação)
13. [Providers Disponíveis](#13-providers-disponíveis)
14. [Lógica de Roteamento por Tier](#14-lógica-de-roteamento-por-tier)
15. [Gerenciamento de Quotas Diárias](#15-gerenciamento-de-quotas-diárias)
16. [Análise de Hardware e Modelos Locais](#16-análise-de-hardware-e-modelos-locais)
17. [Providers de Voz — TTS e STT](#17-providers-de-voz--tts-e-stt)
18. [Diagrama de Classes — Voz](#18-diagrama-de-classes--voz)
19. [Diagrama de Sequência — Fluxo de Voz](#19-diagrama-de-sequência--fluxo-de-voz)
20. [Diagrama de Estado — Seleção de Provider de Voz](#20-diagrama-de-estado--seleção-de-provider-de-voz)
21. [Referência da API REST](#21-referência-da-api-rest)
22. [Configuração e Instalação](#22-configuração-e-instalação)
23. [Estrutura de Arquivos](#23-estrutura-de-arquivos)

---

## 1. Visão Geral

O **AI Adapter** é um microserviço que atua como **gateway unificado** para múltiplos provedores de IA — tanto para geração de texto (LLM) quanto para síntese de voz (TTS) e transcrição de voz (STT). Ele não expõe modelos diretamente ao consumidor — em vez disso, **decide qual modelo usar** com base em critérios objetivos.

### Responsabilidade Central

```
Sistema Consumidor
         │
         ├── POST /v1/completions  { prompt, difficulty, complexity }
         ├── POST /v1/speak        { text, voice, speed }
         ├── POST /v1/transcribe   { audio_file }
         └── WS   /v1/transcribe/stream
         ▼
    ┌─────────────┐
    │  AI Adapter │  ← decide o provider
    └─────────────┘
         │
    ┌────┴──────────────────────────────────────────────────────┐
    │  LLM: Ollama  Groq  Gemini  DeepSeek  Mistral  OpenAI    │
    │  TTS: pyttsx3 EdgeTTS  ElevenLabs  OpenAI-TTS            │
    │  STT: Whisper-local  Groq-Whisper  OpenAI-Whisper        │
    └───────────────────────────────────────────────────────────┘
```

### Princípio de Funcionamento — LLM

O sistema consumidor envia a tarefa com **metadados de contexto**:

| Campo | Tipo | Descrição |
|-------|------|-----------|
| `difficulty` | `easy\|medium\|hard\|expert` | Dificuldade estimada da tarefa |
| `complexity` | `float 0.0–1.0` | Complexidade numérica |
| `priority` | `low\|normal\|high` | Urgência da resposta |
| `max_cost` | `free\|low\|medium\|high` | Custo máximo aceitável |

O AI Adapter então **roteia automaticamente** para o provider mais adequado, considerando também quotas diárias disponíveis e hardware local.

### Princípio de Funcionamento — Voz

Para TTS e STT, o `AudioService` aplica uma estratégia de **fallback em cascata**:

```
TTS: pyttsx3 (offline) → Edge TTS (gratuito) → ElevenLabs (free tier) → OpenAI TTS (pago)
STT: Whisper local (offline) → Groq Whisper (gratuito) → OpenAI Whisper (pago)
```

O provider local é sempre tentado primeiro — garantindo funcionamento **sem internet** no Raspberry Pi. Providers remotos são ativados automaticamente quando o local não estiver disponível.

---

## 2. Teoria e Motivação

### 2.1 Problema: Proliferação de Provedores

O ecossistema de LLMs está fragmentado. Cada provedor tem:
- APIs incompatíveis entre si
- Modelos com diferentes capacidades
- Preços que variam de gratuito a muito caro
- Limites de requisições distintos
- Latências diferentes

Sem um gateway, cada consumidor precisaria conhecer todos os providers, gerenciar chaves de API, lidar com erros e decidir qual modelo usar — **alto acoplamento e baixa coesão**.

### 2.2 Solução: Gateway com Roteamento Inteligente

O padrão **Gateway** (derivado do Enterprise Integration Patterns) resolve isso com um único ponto de entrada que abstrai toda a complexidade.

```
SEM GATEWAY                          COM GATEWAY

App ──► OpenAI                       App ──► Gateway ──► OpenAI
App ──► Anthropic                                   └──► Anthropic
App ──► Groq                                        └──► Groq
App ──► Ollama                                      └──► Ollama
App ──► DeepSeek                                    └──► DeepSeek
```

### 2.3 Hierarquia de Decisão

O roteamento segue uma hierarquia de prioridades:

```
1. preferred_provider (explícito) → usa diretamente
2. max_cost (restrição de custo) → define teto
3. difficulty (complexidade da tarefa) → define mínimo de qualidade
4. complexity (numérico 0.0–1.0) → refina a escolha
5. priority (urgência) → afeta a trade-off velocidade/custo
6. quota disponível → pula providers esgotados
7. fallback → usa qualquer disponível
```

### 2.4 Teoria de Filas e Rate Limiting

O `SimpleRateLimiter` implementa um **token bucket simplificado** com janela deslizante:

- Remove requisições com timestamp > 60 segundos
- Limita a N requisições por minuto por `client_id`
- Isolamento por tenant (multi-tenancy)

### 2.5 Teoria de Cache

O `SimpleCache` implementa um cache **write-through** em memória:

- Chave = `prompt` (hash implícito por igualdade de string)
- Sem expiração (adequado para testes; produção exigiria TTL)
- Retorna resposta cacheada sem chamar o provider (zero custo)

### 2.6 Análise de Hardware para Modelos Locais

Modelos de linguagem têm requisitos mínimos de hardware. O sistema usa a regra:

```
Se tem GPU → usa VRAM como critério principal
Se não tem GPU → usa RAM disponível - 2GB (reserva para OS)
```

Para cada modelo, define-se `ram_gb` e `vram_gb` mínimos. O sistema lista candidatos compatíveis e os ordena por qualidade decrescente.

---

## 3. Arquitetura Clean Architecture

O projeto implementa a **Clean Architecture** de Robert C. Martin, organizada em 4 camadas concêntricas com dependências sempre apontando para dentro.

```
┌─────────────────────────────────────────────────────┐
│                    API Layer                         │
│              (FastAPI, HTTP, JSON)                   │
├─────────────────────────────────────────────────────┤
│                Application Layer                     │
│              (AIService, Orquestração)               │
├─────────────────────────────────────────────────────┤
│               Infrastructure Layer                   │
│    (Providers, Router, Cache, RateLimiter, etc.)     │
├─────────────────────────────────────────────────────┤
│                   Core Layer                         │
│        (Entidades, Interfaces, Enums)                │
└─────────────────────────────────────────────────────┘
         ↑ Dependências sempre apontam para DENTRO ↑
```

### 3.1 Core Layer (Núcleo de Domínio)

**Regra:** Não depende de nada externo. Não importa nenhum SDK de terceiros.

| Módulo | Responsabilidade |
|--------|-----------------|
| `entities/airequest.py` | Representa a intenção de uso da IA |
| `entities/airesponse.py` | Padroniza respostas de todos os providers |
| `entities/aiprovidermedata.py` | Descreve capacidades de um provider |
| `enums/aicapability.py` | Enumera capacidades: TEXT, VISION, EMBEDDINGS... |
| `interfaces/provider.py` | Contrato abstrato de qualquer provider |
| `interfaces/router.py` | Contrato abstrato de roteamento |
| `interfaces/policy.py` | Contrato abstrato de validação |
| `interfaces/cache.py` | Contrato abstrato de cache |
| `interfaces/rate_limiter.py` | Contrato abstrato de rate limiting |
| `interfaces/observability.py` | Contrato abstrato de logging/monitoramento |
| `interfaces/tool.py` | Contrato abstrato de function calling |

### 3.2 Infrastructure Layer

**Regra:** Implementa as interfaces do Core. Aqui vivem os SDKs externos.

```
infrastructure/
├── providers/          ← implementações concretas de AIProvider
│   ├── openai/
│   ├── anthropic/
│   ├── google/
│   ├── groq/
│   ├── mistral/
│   ├── deepseek/
│   ├── openrouter/
│   └── local/          ← Ollama
├── routing/            ← CostRouter (implementa AIRouter)
├── governance/         ← Policy, Cache, RateLimiter, Observability, QuotaManager
└── system/             ← HardwareAnalyzer
```

### 3.3 Application Layer

**Regra:** Orquestra o fluxo sem conhecer implementações concretas.

`AIService` recebe todas as dependências via injeção e executa o pipeline:

```
validate → rate_limit → cache_check → route → generate → cache_set → log
```

### 3.4 API Layer

**Regra:** Converte HTTP ↔ domain objects. Não contém lógica de negócio.

`FastAPI` recebe `AIRequestModel` (Pydantic), converte para `AIRequest` (domain), delega ao `AIService`, converte `AIResponse` para `AIResponseModel`.

### 3.5 Regra da Dependência

```
API ──► Application ──► Core ◄── Infrastructure
         │                           │
         └───────────────────────────┘
              (via interfaces do Core)
```

A Infrastructure **não é importada** pela Application diretamente — ela é **injetada** pela API Layer através dos construtores.

---

## 4. Padrões de Projeto

### 4.1 Strategy Pattern

**Onde:** Todos os `AIProvider`, `AIRouter`, `AIPolicy`, `AICache`, `AIRateLimiter`

**Teoria:** Define uma família de algoritmos, encapsula cada um e os torna intercambiáveis. O cliente (AIService) não conhece a implementação concreta — usa a interface.

```
        «interface»
        AIProvider
            │
    ┌───────┼───────────────┐
    │       │               │
OpenAI  Anthropic        Groq
(Strategy A) (Strategy B) (Strategy C)
```

**Por que usar:** O `AIService` funciona identicamente independente de qual provider está injetado. Novo provider = nova classe, zero alteração no serviço.

### 4.2 Template Method Pattern

**Onde:** `BaseAgent` → `SimpleAgent`

**Teoria:** Define o esqueleto de um algoritmo na classe base, delegando passos específicos às subclasses.

```python
# BaseAgent define o esqueleto:
def _build_messages(self, user_input):  # ← step concreto
    messages = [system_prompt, *history, user_input]

# Subclasse implementa:
def process(self, user_input) → AIResponse:  # ← abstract
```

### 4.3 Chain of Responsibility Pattern

**Onde:** Pipeline do `AIService` com fallback entre providers

**Teoria:** Passa a requisição por uma cadeia de handlers; cada um pode processar ou passar adiante.

```
Requisição → Provider1 → (falha) → Provider2 → (falha) → Provider3 → Resposta
```

O `CostRouter` retorna uma lista ordenada e o `AIService` itera até obter resposta.

### 4.4 Proxy Pattern

**Onde:** `AIService` em relação aos providers

**Teoria:** Fornece um substituto/representante de outro objeto, controlando acesso e adicionando comportamento (cache, rate limit, logging) sem alterar o objeto real.

```
Cliente ──► AIService (Proxy) ──► Provider (Real Subject)
              ├── valida
              ├── rate limit
              ├── cache
              └── log
```

### 4.5 Abstract Factory Pattern

**Onde:** `aiadapter/factory/` — criação de providers

**Teoria:** Interface para criação de famílias de objetos relacionados sem especificar classes concretas.

```
AbstractFactory
    └── create_provider(name) → AIProvider
```

### 4.6 Facade Pattern

**Onde:** `AIService` para os consumidores da Application Layer

**Teoria:** Fornece interface simplificada para um subsistema complexo.

```
Consumidor chama apenas: ai_service.execute(request)
    ├── Internamente orquestra: policy + rate_limiter + cache + router + providers + observability
    └── Consumidor não precisa conhecer nada disso
```

### 4.7 Dependency Injection (DI)

**Onde:** Construtor do `AIService` e `get_or_create_tenant_service()`

**Teoria:** Dependências são fornecidas externamente em vez de criadas internamente (Inversão de Controle).

```python
# SEM DI (ruim):
class AIService:
    def __init__(self):
        self._router = CostRouter(...)  # acoplado

# COM DI (bom):
class AIService:
    def __init__(self, router: AIRouter, policy: AIPolicy, ...):
        self._router = router  # desacoplado — pode ser mock nos testes
```

### 4.8 Repository Pattern (simplificado)

**Onde:** `SimpleCache` — abstrai o armazenamento de respostas

**Teoria:** Encapsula a lógica de acesso a dados, fornecendo interface orientada a coleções.

### 4.9 Observer Pattern (via Observability)

**Onde:** `LoggerObservability` implementa `AIObservability`

**Teoria:** Define dependência um-para-muitos onde mudanças de estado notificam todos os observadores.

```
AIService ──► AIObservability.log_request()
          ──► AIObservability.log_response()
          ──► AIObservability.log_error()
```

### 4.10 Resumo dos Padrões

| Padrão | Categoria | Onde Aplicado |
|--------|-----------|---------------|
| Strategy | Comportamental | Todos os providers, router, policy, cache, rate limiter |
| Template Method | Comportamental | BaseAgent → SimpleAgent |
| Chain of Responsibility | Comportamental | Fallback entre providers |
| Proxy | Estrutural | AIService sobre os providers |
| Abstract Factory | Criacional | Factory de providers |
| Facade | Estrutural | AIService para consumidores |
| Dependency Injection | Arquitetural | Construtores de AIService |
| Repository | Arquitetural | SimpleCache |
| Observer | Comportamental | AIObservability |

---

## 5. Diagrama de Classes UML

```mermaid
classDiagram
    %% ═══════════════════════════════════════
    %% CORE - Entidades
    %% ═══════════════════════════════════════
    class AIRequest {
        +prompt: str
        +model: Optional[str]
        +messages: Optional[List]
        +temperature: float
        +max_tokens: int
        +context: Optional[Dict]
        +client_id: Optional[str]
        +stream: bool
        +tools: Optional[List]
        +priority: str
        +difficulty: str
        +complexity: float
        +max_cost: str
        +preferred_provider: Optional[str]
    }

    class AIResponse {
        +provider_name: str
        +tokens_used: int
        +cost: float
        +output: Optional[str]
        +is_streaming_chunk: bool
        +tool_calls: Optional[List]
    }

    class AIProviderMetadata {
        +name: str
        +models: List[str]
        +supports_streaming: bool
        +cost_per_1k_tokens: float
        +avg_latency_ms: int
        +is_local: bool
        +daily_free_limit: int
        +capabilities: List[str]
    }

    class AICapability {
        <<enumeration>>
        TEXT
        EMBEDDINGS
        VISION
        FUNCTION_CALLING
        AUDIO
        VIDEO
    }

    %% ═══════════════════════════════════════
    %% CORE - Interfaces (Abstratas)
    %% ═══════════════════════════════════════
    class AIProvider {
        <<abstract>>
        +generate(request: AIRequest) AIResponse
        +get_metadata() AIProviderMetadata
        +supports(capability: AICapability) bool
    }

    class AIRouter {
        <<abstract>>
        +route(request: AIRequest) List[AIProvider]
    }

    class AIPolicy {
        <<abstract>>
        +validate(request: AIRequest) None
    }

    class AICache {
        <<abstract>>
        +get(request: AIRequest) Optional[AIResponse]
        +set(request: AIRequest, response: AIResponse) None
    }

    class AIRateLimiter {
        <<abstract>>
        +allow_request(request: AIRequest) bool
        +record_request(request: AIRequest) None
    }

    class AIObservability {
        <<abstract>>
        +log_request(request: AIRequest) None
        +log_response(response: AIResponse) None
        +log_error(message: str) None
        +log_info(message: str) None
    }

    class AITool {
        <<abstract>>
        +execute(**kwargs) Any
    }

    %% ═══════════════════════════════════════
    %% INFRASTRUCTURE - Providers
    %% ═══════════════════════════════════════
    class OpenAIProvider {
        -_client: OpenAI
        +generate(request) AIResponse
        +get_metadata() AIProviderMetadata
        +supports(capability) bool
        -_generate_stream(response) Generator
        -_estimate_cost(model, tokens) float
    }

    class ClaudeProvider {
        -_client: Anthropic
        +generate(request) AIResponse
        +get_metadata() AIProviderMetadata
        +supports(capability) bool
        -_generate_stream(stream, model) Generator
        -_estimate_cost(model, in, out) float
    }

    class GeminiProvider {
        -_client: genai.Client
        +generate(request) AIResponse
        +get_metadata() AIProviderMetadata
        +supports(capability) bool
        -_generate_new_sdk(request, model) AIResponse
        -_generate_legacy_sdk(request, model) AIResponse
    }

    class GroqProvider {
        -_client: Groq
        +generate(request) AIResponse
        +get_metadata() AIProviderMetadata
        +supports(capability) bool
        -_estimate_cost(model, tokens) float
    }

    class MistralProvider {
        -_client: Mistral
        -_use_sdk: bool
        +generate(request) AIResponse
        +get_metadata() AIProviderMetadata
        +supports(capability) bool
    }

    class DeepSeekProvider {
        -_client: OpenAI
        +generate(request) AIResponse
        +get_metadata() AIProviderMetadata
        +supports(capability) bool
        -_estimate_cost(model, in, out) float
    }

    class OpenRouterProvider {
        -_client: OpenAI
        +generate(request) AIResponse
        +get_metadata() AIProviderMetadata
        +get_free_models() List[str]
        +supports(capability) bool
    }

    class OllamaProvider {
        -_base_url: str
        +is_available() bool
        +list_local_models() List[str]
        +generate(request) AIResponse
        +get_metadata() AIProviderMetadata
        +supports(capability) bool
    }

    %% ═══════════════════════════════════════
    %% INFRASTRUCTURE - Governance
    %% ═══════════════════════════════════════
    class CostRouter {
        -_providers: Dict[str, AIProvider]
        -_quota_manager: DailyQuotaManager
        +route(request: AIRequest) List[AIProvider]
        -_select_tier(request) str
        -_build_fallback_list(tier, exclude) List
        -_complexity_to_tier(complexity) str
        -_tier_level(tier) int
    }

    class SimplePolicy {
        +validate(request: AIRequest) None
    }

    class SimpleCache {
        -_cache: Dict[str, AIResponse]
        +get(request) Optional[AIResponse]
        +set(request, response) None
    }

    class SimpleRateLimiter {
        -rate_limit_per_minute: int
        -requests: defaultdict
        +allow_request(request) bool
        +record_request(request) None
    }

    class LoggerObservability {
        -_logger: Logger
        +log_request(request) None
        +log_response(response) None
        +log_error(message) None
        +log_info(message) None
    }

    class DailyQuotaManager {
        -_quota_file: str
        -_data: dict
        +is_available(provider) bool
        +get_usage(provider) int
        +get_limit(provider) int
        +record_request(provider, count) None
        +mark_exhausted(provider) None
        +get_all_status() Dict
        -_reload_if_new_day() None
        -_load() dict
        -_save() None
    }

    %% ═══════════════════════════════════════
    %% INFRASTRUCTURE - System
    %% ═══════════════════════════════════════
    class HardwareProfile {
        +ram_gb: float
        +cpu_cores: int
        +cpu_threads: int
        +gpu_name: Optional[str]
        +gpu_vram_gb: float
        +has_cuda: bool
        +has_metal: bool
        +has_rocm: bool
        +platform: str
        +recommended_models: List[str]
    }

    class HardwareAnalyzer {
        -_ollama_url: str
        -_profile: Optional[HardwareProfile]
        +analyze() HardwareProfile
        +get_best_local_model(installed) Optional[str]
        +pull_best_model(ollama_provider) Optional[str]
        +summary() dict
        -_detect_gpu() dict
        -_recommend_models(profile) List[str]
        -_estimate_ram_fallback() float
    }

    %% ═══════════════════════════════════════
    %% APPLICATION
    %% ═══════════════════════════════════════
    class AIService {
        -_router: AIRouter
        -_policy: AIPolicy
        -_observability: AIObservability
        -_rate_limiter: AIRateLimiter
        -_cache: AICache
        -_tools: Dict[str, AITool]
        +execute(request) AIResponse
        -_handle_streaming_response(request, gen, name) Generator
        -_handle_tool_calls(tool_calls) List
    }

    %% ═══════════════════════════════════════
    %% AGENTS
    %% ═══════════════════════════════════════
    class BaseAgent {
        <<abstract>>
        +name: str
        +ai_service: AIService
        +system_prompt: Optional[str]
        +conversation_history: List
        +process(user_input) AIResponse
        +add_to_history(role, content) None
        +get_conversation_history() List
        +clear_history() None
        -_build_messages(user_input) List
    }

    class SimpleAgent {
        +process(user_input) AIResponse
    }

    %% ═══════════════════════════════════════
    %% RELACIONAMENTOS
    %% ═══════════════════════════════════════

    %% Herança - Providers
    AIProvider <|-- OpenAIProvider
    AIProvider <|-- ClaudeProvider
    AIProvider <|-- GeminiProvider
    AIProvider <|-- GroqProvider
    AIProvider <|-- MistralProvider
    AIProvider <|-- DeepSeekProvider
    AIProvider <|-- OpenRouterProvider
    AIProvider <|-- OllamaProvider

    %% Herança - Governance
    AIRouter <|-- CostRouter
    AIPolicy <|-- SimplePolicy
    AICache <|-- SimpleCache
    AIRateLimiter <|-- SimpleRateLimiter
    AIObservability <|-- LoggerObservability

    %% Herança - Agents
    BaseAgent <|-- SimpleAgent

    %% Composição - AIService
    AIService o-- AIRouter
    AIService o-- AIPolicy
    AIService o-- AIObservability
    AIService o-- AIRateLimiter
    AIService o-- AICache
    AIService o-- AITool

    %% Composição - CostRouter
    CostRouter o-- AIProvider
    CostRouter o-- DailyQuotaManager

    %% Composição - HardwareAnalyzer
    HardwareAnalyzer ..> HardwareProfile : cria
    HardwareAnalyzer ..> OllamaProvider : usa

    %% Dependências de Entidades
    AIService ..> AIRequest : usa
    AIService ..> AIResponse : usa
    AIProvider ..> AIRequest : consome
    AIProvider ..> AIResponse : produz
    AIProvider ..> AIProviderMetadata : retorna
    AIProvider ..> AICapability : usa
    AIRouter ..> AIRequest : analisa
```

---

## 6. Diagrama de Componentes

```mermaid
graph TB
    subgraph Externos["Sistemas Externos"]
        Consumer["Sistema Consumidor\n(Agente de Prompts)"]
    end

    subgraph API["Camada API (FastAPI)"]
        Router_API["POST /v1/completions\nGET /v1/models\nGET /v1/quotas\nGET /v1/hardware\nGET /health"]
    end

    subgraph Application["Camada Application"]
        AIService["AIService\n(Orquestrador)"]
    end

    subgraph Governance["Governance (Infrastructure)"]
        Policy["SimplePolicy\n(validação)"]
        RateLimiter["SimpleRateLimiter\n(controle de tráfego)"]
        Cache["SimpleCache\n(respostas em memória)"]
        Observability["LoggerObservability\n(logs)"]
        QuotaManager["DailyQuotaManager\n(quotas diárias)"]
    end

    subgraph Routing["Routing (Infrastructure)"]
        CostRouter["CostRouter\n(seleção por tier)"]
    end

    subgraph Providers["Providers (Infrastructure)"]
        direction LR
        Ollama["OllamaProvider\n🏠 Local • Free"]
        Groq["GroqProvider\n⚡ 14.4k/dia • Fast"]
        Gemini["GeminiProvider\n🆓 1.5k/dia"]
        OpenRouter["OpenRouterProvider\n🆓 200/dia"]
        DeepSeek["DeepSeekProvider\n💰 $0.14/1M"]
        Mistral["MistralProvider\n🇫🇷 Mid-tier"]
        OpenAI["OpenAIProvider\n💎 High-tier"]
        Anthropic["ClaudeProvider\n💎 High-tier"]
    end

    subgraph System["System (Infrastructure)"]
        HardwareAnalyzer["HardwareAnalyzer\n(detecção GPU/RAM)"]
    end

    subgraph ExternalAPIs["APIs Externas"]
        OllamaAPI["Ollama\nlocalhost:11434"]
        GroqAPI["api.groq.com"]
        GeminiAPI["generativelanguage\n.googleapis.com"]
        OpenRouterAPI["openrouter.ai/api/v1"]
        DeepSeekAPI["api.deepseek.com"]
        MistralAPI["api.mistral.ai"]
        OpenAIAPI["api.openai.com"]
        AnthropicAPI["api.anthropic.com"]
    end

    Consumer -->|HTTP Request| Router_API
    Router_API -->|AIRequest| AIService
    AIService --> Policy
    AIService --> RateLimiter
    AIService --> Cache
    AIService --> CostRouter
    AIService --> Observability
    CostRouter --> QuotaManager
    CostRouter -->|Lista ordenada| Providers
    AIService -->|Response| Router_API
    Router_API -->|HTTP Response| Consumer

    HardwareAnalyzer -.->|recomenda modelo| Ollama

    Ollama --> OllamaAPI
    Groq --> GroqAPI
    Gemini --> GeminiAPI
    OpenRouter --> OpenRouterAPI
    DeepSeek --> DeepSeekAPI
    Mistral --> MistralAPI
    OpenAI --> OpenAIAPI
    Anthropic --> AnthropicAPI
```

---

## 7. Diagrama de Sequência — Fluxo de Requisição

```mermaid
sequenceDiagram
    actor Cliente as Sistema Consumidor
    participant API as FastAPI (API Layer)
    participant Service as AIService (Application)
    participant Policy as SimplePolicy
    participant RateLimit as SimpleRateLimiter
    participant Cache as SimpleCache
    participant Router as CostRouter
    participant Quota as DailyQuotaManager
    participant P1 as Provider1 (preferido)
    participant P2 as Provider2 (fallback)
    participant Obs as LoggerObservability

    Cliente->>+API: POST /v1/completions\n{prompt, difficulty, complexity, max_cost}
    API->>API: Valida AIRequestModel (Pydantic)
    API->>API: get_or_create_tenant_service(tenant_id)
    API->>+Service: execute(AIRequest)

    Service->>+Policy: validate(request)
    alt Prompt inválido / campos errados
        Policy-->>Service: raise ValueError
        Service-->>API: raise ValueError
        API-->>Cliente: 422 Unprocessable Entity
    end
    Policy-->>-Service: OK

    Service->>+RateLimit: allow_request(request)
    alt Limite excedido
        RateLimit-->>Service: False
        Service-->>API: raise Exception("Rate limit exceeded")
        API-->>Cliente: 500 Internal Server Error
    end
    RateLimit-->>-Service: True
    Service->>RateLimit: record_request(request)

    Service->>+Cache: get(request)
    alt Cache HIT
        Cache-->>Service: AIResponse (cached)
        Service->>Obs: log_request(request)
        Service->>Obs: log_response(cached)
        Service-->>API: AIResponse
        API-->>Cliente: 200 OK (do cache)
    end
    Cache-->>-Service: None (cache miss)

    Service->>+Obs: log_request(request)
    Obs-->>-Service: OK

    Service->>+Router: route(request)
    Router->>Router: _select_tier(request)\n→ "low" | "medium" | etc.
    Router->>+Quota: is_available("provider1")
    Quota-->>-Router: True
    Router-->>-Service: [Provider1, Provider2, ...]

    Service->>+P1: generate(request)
    alt Provider1 disponível
        P1->>P1: Chama API externa
        P1-->>-Service: AIResponse
    else Provider1 falha
        P1-->>Service: raise Exception
        Service->>Obs: log_error("Provider1 failed")
        Service->>+P2: generate(request) [fallback]
        P2-->>-Service: AIResponse
    end

    alt Streaming solicitado
        Service-->>API: Generator[AIResponse]
        loop Para cada chunk
            API-->>Cliente: chunk JSON (NDJSON)
        end
    else Resposta normal
        Service->>Cache: set(request, response)
        Service->>+Obs: log_response(response)
        Obs-->>-Service: OK
        Service-->>-API: AIResponse
        API->>Quota: record_request(provider_name)
        API-->>Cliente: 200 OK\n{output, provider_name, cost, tokens_used}
    end
```

---

## 8. Diagrama de Estado — Ciclo de Vida da Requisição

```mermaid
stateDiagram-v2
    [*] --> Recebida : POST /v1/completions

    Recebida --> Validando : parse Pydantic OK

    Recebida --> Rejeitada : parse Pydantic falhou
    Rejeitada --> [*] : 422 Unprocessable Entity

    Validando --> RateLimitando : campos válidos

    Validando --> Rejeitada : ValueError (prompt vazio,\ndifficulty inválido, etc.)

    RateLimitando --> ConsultandoCache : within limit

    RateLimitando --> Bloqueada : rate limit excedido
    Bloqueada --> [*] : 429 Too Many Requests

    ConsultandoCache --> Respondida : cache HIT

    ConsultandoCache --> Roteando : cache MISS

    Roteando --> SelecionandoProvider : tier determinado

    SelecionandoProvider --> Gerando : provider disponível

    SelecionandoProvider --> FalhaTotalProviders : todos os providers\nesgotados ou falharam

    FalhaTotalProviders --> [*] : 503 Service Unavailable

    Gerando --> StreamingAtivo : stream=true
    Gerando --> ProcessandoResposta : stream=false

    StreamingAtivo --> EnviandoChunks : provider gerando
    EnviandoChunks --> EnviandoChunks : próximo chunk
    EnviandoChunks --> Respondida : último chunk

    ProcessandoResposta --> CacheandoResposta : geração bem-sucedida
    ProcessandoResposta --> TentandoFallback : provider falhou

    TentandoFallback --> Gerando : fallback disponível
    TentandoFallback --> FalhaTotalProviders : sem mais fallbacks

    CacheandoResposta --> Respondida : cache atualizado

    Respondida --> RegistrandoQuota : registra uso
    RegistrandoQuota --> [*] : 200 OK
```

---

## 9. Diagrama de Estado — Quota Diária

```mermaid
stateDiagram-v2
    [*] --> Inicializando : DailyQuotaManager()

    Inicializando --> CarregandoArquivo : arquivo existe
    Inicializando --> CriandoArquivo : arquivo não existe

    CarregandoArquivo --> VerificandoData : JSON lido

    VerificandoData --> DiaAtual : data == hoje
    VerificandoData --> ResetandoContadores : data != hoje

    ResetandoContadores --> DiaAtual : nova data gravada
    CriandoArquivo --> DiaAtual : arquivo criado

    state DiaAtual {
        [*] --> Disponivel

        Disponivel --> Disponivel : record_request()\nusage < limit

        Disponivel --> QuotaEsgotada : usage >= limit

        QuotaEsgotada --> QuotaEsgotada : is_available() = false\n(provider pulado no router)

        note right of QuotaEsgotada
            Persiste até
            virar o dia
        end note
    }

    DiaAtual --> ResetandoContadores : nova requisição\ne data mudou

    state ResetandoContadores {
        [*] --> LimpandoUsage
        LimpandoUsage --> GravandoNovaData
        GravandoNovaData --> [*]
    }
```

---

## 10. Diagrama de Estado — Análise de Hardware

```mermaid
stateDiagram-v2
    [*] --> Iniciado : HardwareAnalyzer()

    Iniciado --> AnalisandoRAM : analyze() chamado

    AnalisandoRAM --> AnalisandoRAMPsutil : psutil disponível
    AnalisandoRAM --> AnalisandoRAMFallback : psutil não instalado

    AnalisandoRAMPsutil --> AnalisandoGPU : RAM detectada
    AnalisandoRAMFallback --> AnalisandoGPU : RAM estimada via OS

    state AnalisandoGPU {
        [*] --> TestandoNVIDIA
        TestandoNVIDIA --> GPUNvidia : nvidia-smi OK
        TestandoNVIDIA --> TestandoAMD : nvidia-smi falhou
        TestandoAMD --> GPUAmd : rocm-smi OK
        TestandoAMD --> TestandoApple : rocm-smi falhou
        TestandoApple --> GPUApple : Apple Silicon
        TestandoApple --> SemGPU : sem GPU dedicada
    }

    AnalisandoGPU --> RecomendandoModelos : GPU/RAM detectados

    state RecomendandoModelos {
        [*] --> FiltraCandidatos
        FiltraCandidatos --> OrdenaQualidade
        OrdenaQualidade --> Top5
        note right of FiltraCandidatos
            Se tem GPU: filtra por VRAM
            Se não tem: filtra por RAM - 2GB
        end note
    }

    RecomendandoModelos --> PerfilPronto : profile completo

    PerfilPronto --> VerificandoInstalados : pull_best_model()

    state VerificandoInstalados {
        [*] --> ListaModelsOllama
        ListaModelsOllama --> ModeloEncontrado : modelo recomendado já instalado
        ListaModelsOllama --> BaixandoModelo : modelo não instalado
        BaixandoModelo --> ModeloEncontrado : ollama pull OK
        BaixandoModelo --> ProximoRecomendado : download falhou
        ProximoRecomendado --> ListaModelsOllama : tenta próximo da lista
        ProximoRecomendado --> UsaInstalado : lista esgotada
    }

    VerificandoInstalados --> ModeloSelecionado : melhor modelo disponível

    ModeloSelecionado --> [*] : retorna nome do modelo
```

---

## 11. Diagrama de Atividades — Roteamento Inteligente

```mermaid
flowchart TD
    Start([Início: route request]) --> CheckPreferred{preferred_provider\ndefinido?}

    CheckPreferred -->|Sim| UsePreferred[Usa provider preferido\ncomo 1º da lista]
    CheckPreferred -->|Não| SelectTier[Selecionar Tier]

    UsePreferred --> BuildFallback[Constrói fallback com\nrestantes do tier]
    BuildFallback --> ReturnList

    SelectTier --> CheckMaxCost{max_cost\nexplícito?}
    CheckMaxCost -->|Sim| SetCostTier[cost_tier = max_cost]
    CheckMaxCost -->|Não| DefaultMedium[cost_tier = 'medium']

    SetCostTier --> MapDifficulty
    DefaultMedium --> MapDifficulty

    MapDifficulty[Mapeia difficulty → tier\neasy→free / medium→low\nhard→medium / expert→high]

    MapDifficulty --> MapComplexity[Mapeia complexity → tier\n0–0.25→free / 0.25–0.5→low\n0.5–0.75→medium / 0.75–1.0→high]

    MapComplexity --> CheckPriority{priority?}

    CheckPriority -->|low| ForceLow[Usa o MENOR tier\nentre os 3]
    CheckPriority -->|high| ForceHigh[Usa pelo menos 'medium'\ndo MAIOR dos 3]
    CheckPriority -->|normal| UseMax[Usa o MAIOR tier\nentre os 3]

    ForceLow --> GetOrder
    ForceHigh --> GetOrder
    UseMax --> GetOrder

    GetOrder[Obtém ordem dos providers\npara o tier selecionado]

    GetOrder --> FilterLoop{Para cada provider\nna ordem}

    FilterLoop -->|próximo| CheckAvailable{Provider\nconfigurado?}
    CheckAvailable -->|Não| FilterLoop
    CheckAvailable -->|Sim| CheckQuota{Quota\ndisponível?}
    CheckQuota -->|Não| LogSkip[Log: quota esgotada]
    LogSkip --> FilterLoop
    CheckQuota -->|Sim| AddToList[Adiciona à lista\nde resultado]
    AddToList --> FilterLoop

    FilterLoop -->|fim da lista| CheckEmpty{Lista\nvazia?}
    CheckEmpty -->|Sim| UseAny[Usa qualquer provider\ndisponível como fallback]
    CheckEmpty -->|Não| ReturnList([Retorna lista ordenada])
    UseAny --> ReturnList
```

---

## 12. Diagrama de Implantação

```mermaid
graph LR
    subgraph Client["Cliente / Sistema Consumidor"]
        AgentSystem["Agente de Prompts\n(microserviço externo)"]
    end

    subgraph Server["Servidor de Implantação"]
        subgraph Docker["Container (opcional)"]
            FastAPI["AI Adapter\nFastAPI + Uvicorn\n:8000"]
            DataDir["data/\ndaily_quotas.json\n(quotas diárias)"]
            EnvFile[".env\n(chaves de API)"]
        end

        subgraph Local["Serviços Locais"]
            OllamaService["Ollama Service\nlocalhost:11434"]
            subgraph OllamaModels["Modelos Baixados"]
                LlamaModel["llama3.2:3b"]
                MistralModel["mistral:7b"]
                GemmaModel["gemma2:9b"]
            end
        end
    end

    subgraph Cloud["APIs em Nuvem (externas)"]
        GroqCloud["Groq Cloud\napi.groq.com"]
        GeminiCloud["Google AI\ngenerativelanguage\n.googleapis.com"]
        OpenRouterCloud["OpenRouter\nopenrouter.ai"]
        DeepSeekCloud["DeepSeek\napi.deepseek.com"]
        MistralCloud["Mistral AI\napi.mistral.ai"]
        OpenAICloud["OpenAI\napi.openai.com"]
        AnthropicCloud["Anthropic\napi.anthropic.com"]
    end

    AgentSystem -->|HTTP X-Tenant-ID| FastAPI
    FastAPI --> OllamaService
    OllamaService --> OllamaModels
    FastAPI --> GroqCloud
    FastAPI --> GeminiCloud
    FastAPI --> OpenRouterCloud
    FastAPI --> DeepSeekCloud
    FastAPI --> MistralCloud
    FastAPI --> OpenAICloud
    FastAPI --> AnthropicCloud
    FastAPI --- DataDir
    FastAPI --- EnvFile
```

---

## 13. Providers Disponíveis

### Hierarquia por Custo e Qualidade

```
QUALIDADE / CUSTO
        ▲
        │  ┌────────────────────────────────────────────┐
  alto  │  │  GPT-4o ($2.50/1M)   Claude Sonnet ($3/1M) │
        │  ├────────────────────────────────────────────┤
        │  │  GPT-4o-mini (0.15)  Claude Haiku (0.25)   │
 médio  │  │  Gemini Pro (1.25)   Mistral Medium (2.70)  │
        │  ├────────────────────────────────────────────┤
        │  │  Groq 70B (0.79)     DeepSeek Chat (0.28)  │
  baixo │  │  Gemini Flash (0.075) Mistral Small (0.60) │
        │  ├────────────────────────────────────────────┤
  zero  │  │  Groq 8B (0.08)  OpenRouter Free (grátis)  │
        │  │  Gemini Free (grátis)  Ollama (local)       │
        │  └────────────────────────────────────────────┘
        └─────────────────────────────────────────────────► VELOCIDADE
                                                     lento      rápido
```

### Tabela Completa de Providers

| Provider | Chave Env | Free Tier | Latência | Modelos Destaque |
|----------|-----------|-----------|----------|-----------------|
| **Ollama** | — (local) | Ilimitado (local) | ~500ms | llama3.2, mistral, gemma2 |
| **Groq** | `GROQ_API_KEY` | 14.400 req/dia | ~300ms | llama-3.1-8b-instant, llama-3.3-70b |
| **Gemini** | `GEMINI_API_KEY` | 1.500 req/dia | ~600ms | gemini-1.5-flash, gemini-1.5-pro |
| **OpenRouter** | `OPENROUTER_API_KEY` | ~200 req/dia | ~1.500ms | 8+ modelos `:free` |
| **DeepSeek** | `DEEPSEEK_API_KEY` | $5 crédito inicial | ~1.000ms | deepseek-chat, deepseek-reasoner |
| **Mistral** | `MISTRAL_API_KEY` | Créditos iniciais | ~900ms | mistral-small, codestral |
| **OpenAI** | `OPENAI_API_KEY` | Sem free tier | ~800ms | gpt-4o, gpt-4o-mini |
| **Anthropic** | `ANTHROPIC_API_KEY` | Sem free tier | ~1.200ms | claude-3.5-sonnet, claude-3-haiku |

### Modelos Gratuitos OpenRouter

```
meta-llama/llama-3.2-3b-instruct:free
meta-llama/llama-3.2-1b-instruct:free
google/gemma-2-9b-it:free
mistralai/mistral-7b-instruct:free
microsoft/phi-3-mini-128k-instruct:free
nousresearch/hermes-3-llama-3.1-405b:free
huggingfaceh4/zephyr-7b-beta:free
qwen/qwen-2-7b-instruct:free
```

---

## 14. Lógica de Roteamento por Tier

### Mapeamento Difficulty → Tier

| difficulty | Tier mínimo | Raciocínio |
|-----------|-------------|-----------|
| `easy` | `free` | Tarefas triviais: resumo simples, classificação básica |
| `medium` | `low` | Tarefas comuns: análise, redação, tradução |
| `hard` | `medium` | Raciocínio complexo, código, múltiplos passos |
| `expert` | `high` | Pesquisa avançada, arquitetura de sistemas, CoT profundo |

### Mapeamento Complexity → Tier

| complexity | Tier | Exemplo de tarefa |
|-----------|------|-----------------|
| 0.0 – 0.25 | `free` | "Qual é a capital do Brasil?" |
| 0.25 – 0.50 | `low` | "Resuma este texto de 500 palavras" |
| 0.50 – 0.75 | `medium` | "Explique a diferença entre TCP e UDP com exemplos" |
| 0.75 – 1.00 | `high` | "Projete uma arquitetura de microserviços para..." |

### Ordem de Preferência por Tier

```
TIER FREE:
  1. Ollama (local, zero latência de rede)
  2. OpenRouter :free models
  3. Groq (free tier, muito rápido)
  4. Gemini Flash (free tier)
  5. DeepSeek (fallback muito barato)

TIER LOW:
  1. Groq (rápido, baratíssimo)
  2. Gemini Flash (bom equilíbrio)
  3. DeepSeek Chat (ótima qualidade/preço)
  4. Mistral Small
  5. Ollama (fallback local)
  6. OpenAI GPT-4o-mini

TIER MEDIUM:
  1. DeepSeek (melhor custo-benefício)
  2. Mistral Medium
  3. Groq 70B
  4. Gemini Pro
  5. GPT-4o-mini
  6. Claude Haiku

TIER HIGH:
  1. GPT-4o
  2. Claude 3.5 Sonnet
  3. Gemini Pro
  4. DeepSeek Reasoner (CoT)
  5. Mistral Large
```

### Impacto da Priority

```
priority=low  → força o MENOR tier calculado (economiza custo)
priority=high → garante pelo menos tier MEDIUM (qualidade mínima)
priority=normal → usa o MAIOR tier entre difficulty/complexity/max_cost
```

---

## 15. Gerenciamento de Quotas Diárias

### Estrutura do Arquivo de Estado

```json
{
  "date": "2026-03-12",
  "usage": {
    "groq": 142,
    "gemini": 38,
    "openrouter_free": 12,
    "together_free": 0,
    "cohere": 5,
    "mistral": 0
  }
}
```

### Limites Configurados

| Provider | Limite/dia | Fonte |
|----------|-----------|-------|
| `groq` | 14.400 req | Groq free tier (~10 req/min) |
| `gemini` | 1.500 req | Google AI Studio free |
| `openrouter_free` | 200 req | OpenRouter free models |
| `together_free` | 300 req | Together AI free tier |
| `cohere` | 1.000 req | Cohere trial (~33/dia estimado) |
| `mistral` | 500 req | Estimado para free tier |

### Ciclo de Reset

```
┌──────────────────────────────────────────────────────┐
│  Início do dia (00:00)                               │
│  ┌──────────────┐                                    │
│  │ data != hoje │ → reseta todos os contadores para 0│
│  └──────────────┘   grava nova data                  │
│                                                      │
│  Durante o dia                                       │
│  ┌─────────────────────────────────────────────────┐ │
│  │ record_request("groq") → usage["groq"] += 1     │ │
│  │ is_available("groq"):                           │ │
│  │   if usage < 14.400 → True (router usa)         │ │
│  │   if usage >= 14.400 → False (router pula)      │ │
│  └─────────────────────────────────────────────────┘ │
└──────────────────────────────────────────────────────┘
```

### Tratamento de Erro de Quota pela API

Quando a API retorna erro de quota (ex: 429 da Groq), o código pode chamar:

```python
quota_manager.mark_exhausted("groq")
# → usage["groq"] = limit (14.400)
# → is_available("groq") = False até amanhã
```

---

## 16. Análise de Hardware e Modelos Locais

### Algoritmo de Detecção

```
1. RAM Total
   └── psutil.virtual_memory().total
   └── (fallback) /proc/meminfo | sysctl | wmic

2. CPU
   └── psutil.cpu_count(logical=False)  # cores físicos
   └── psutil.cpu_count(logical=True)   # threads

3. GPU (em ordem de tentativa)
   ├── NVIDIA: nvidia-smi --query-gpu=name,memory.total
   ├── AMD:    rocm-smi --showmeminfo vram
   └── Apple:  system_profiler SPDisplaysDataType
```

### Critério de Recomendação de Modelos

```python
# Se tem GPU → usa VRAM como critério
if gpu_vram_gb > 0:
    compatível = modelo.vram_gb <= gpu_vram_gb

# Se não tem GPU → usa RAM (menos 2GB para o OS)
else:
    compatível = modelo.ram_gb <= (ram_gb - 2.0)
```

### Tabela de Requisitos dos Modelos

| Modelo | RAM mín. | VRAM mín. | Qualidade |
|--------|----------|-----------|-----------|
| llama3.2:1b | 2 GB | 1,5 GB | basic |
| llama3.2:3b | 4 GB | 2,5 GB | low |
| phi3.5 | 4 GB | 2,5 GB | low |
| gemma2:2b | 4 GB | 2,0 GB | low |
| llama3.1:8b | 8 GB | 5,0 GB | medium |
| mistral:7b | 8 GB | 4,5 GB | medium |
| gemma2:9b | 8 GB | 5,5 GB | medium |
| qwen2.5:7b | 8 GB | 5,0 GB | medium |
| llama3.3:70b | 48 GB | 40 GB | excellent |
| qwen2.5:72b | 48 GB | 40 GB | excellent |

### Exemplos de Recomendações por Hardware

| Hardware | Modelo Recomendado |
|----------|-------------------|
| 4 GB RAM, sem GPU | phi3.5 ou gemma2:2b |
| 8 GB RAM, sem GPU | mistral:7b ou llama3.1:8b |
| 16 GB RAM + GTX 1660 (6GB VRAM) | mistral:7b (via GPU) |
| 32 GB RAM + RTX 3090 (24GB VRAM) | gemma2:9b (via GPU) |
| 64 GB RAM + A100 (40GB VRAM) | llama3.3:70b |
| Apple M1 Pro (16 GB unified) | llama3.1:8b (via Metal) |

---

## 17. Providers de Voz — TTS e STT

O AI Adapter v2.1 incorpora suporte completo a **voz** em ambas as direções: síntese (texto → áudio) e transcrição (áudio → texto). Assim como o roteamento de LLMs prioriza custo e qualidade, o `AudioService` aplica uma lógica de **fallback em cascata**: sempre tenta o provider mais econômico primeiro.

### 17.1 Teoria — Text-to-Speech (TTS)

TTS é o processo de converter texto escrito em fala sintetizada. As abordagens evoluíram de:

1. **Concatenação de fonemas** (anos 90): recortes de fala humana ligados — sons robóticos
2. **Síntese paramétrica** (HMM): modelo estatístico do trato vocal — melhor, mas artificial
3. **Neural TTS** (WaveNet, Tacotron, 2016+): redes neurais profundas que aprendem a imitar voz humana com qualidade indistinguível

O sistema usa **4 providers TTS** em ordem de preferência:

| Provider | Tipo | Custo | Qualidade | Idioma |
|----------|------|-------|-----------|--------|
| `pyttsx3` | Local/offline | Grátis | Básica (SAPI5/espeak) | Sistema operacional |
| `edge_tts` | Remoto gratuito | Grátis | Excelente (neural Azure) | 400+ vozes, pt-BR nativo |
| `elevenlabs_tts` | Remoto pago | 10k chars/mês grátis | Ultra-realista | Multilingual v2 |
| `openai_tts` | Remoto pago | $15/1M chars (tts-1) | Muito boa | 6 vozes multilingual |

**Vozes pt-BR disponíveis (Edge TTS):**
- `pt-BR-AntonioNeural` — masculina, geral
- `pt-BR-FranciscaNeural` — feminina, geral *(padrão)*
- `pt-BR-ThalitaNeural` — feminina, conversacional

### 17.2 Teoria — Speech-to-Text (STT)

STT converte áudio de fala em texto. A revolução veio com o modelo **Whisper** da OpenAI (2022), treinado em 680.000 horas de áudio multilíngue. Características do Whisper:

- **Zero-shot multilingual**: funciona em 99+ idiomas sem fine-tuning
- **Robusto a ruído**: treinado com diversas condições acústicas
- **Tamanhos escaláveis**: de `tiny` (39M params, Pi Zero) a `large` (1.5B params, GPU server)

O sistema usa **3 providers STT** em ordem de preferência:

| Provider | Tipo | Custo | Qualidade | Modelo |
|----------|------|-------|-----------|--------|
| `whisper_local` | Local/offline | Grátis | Boa–Excelente | faster-whisper (CTranslate2) |
| `groq_stt` | Remoto gratuito | Grátis (quota diária) | Excelente | whisper-large-v3 |
| `openai_stt` | Remoto pago | $0.006/min | Excelente | whisper-1 |

**faster-whisper** é uma reimplementação do Whisper usando **CTranslate2** que oferece:
- 4× mais rápido que o Whisper original no mesmo hardware
- 2× menos memória RAM via quantização int8
- Ideal para Raspberry Pi 4 com modelo `base` ou `small`

### 17.3 Seleção de Modelo Whisper por Hardware

| Modelo | Params | RAM | Uso recomendado |
|--------|--------|-----|-----------------|
| `tiny` | 39M | ~1 GB | Pi Zero 2W, ambientes extremamente limitados |
| `base` | 74M | ~1,5 GB | Pi 4 com 2 GB RAM *(padrão do sistema)* |
| `small` | 244M | ~2,5 GB | Pi 4 com 4 GB, boa qualidade |
| `medium` | 769M | ~5 GB | Desktop/servidor sem GPU |
| `large-v3` | 1.5B | ~10 GB | GPU ou servidor dedicado — máxima qualidade |

---

## 18. Diagrama de Classes — Voz

```mermaid
classDiagram
    class AudioRequest {
        +audio_data: Optional[bytes]
        +audio_format: str
        +language: Optional[str]
        +text: Optional[str]
        +voice: Optional[str]
        +speed: float
        +audio_format_out: str
        +preferred_provider: Optional[str]
        +is_stt() bool
        +is_tts() bool
    }

    class AudioResponse {
        +provider_name: str
        +cost: float
        +transcription: Optional[str]
        +language_detected: Optional[str]
        +confidence: float
        +segments: Optional[list]
        +audio_data: Optional[bytes]
        +audio_format: str
        +duration_seconds: float
    }

    class AITTSProvider {
        <<interface>>
        +speak(request: AudioRequest) AudioResponse
        +is_available() bool
        +get_name() str
        +list_voices(language: str) list[dict]
    }

    class AISTTProvider {
        <<interface>>
        +transcribe(request: AudioRequest) AudioResponse
        +is_available() bool
        +get_name() str
        +supported_formats() list[str]
    }

    class AudioService {
        -_tts_providers: list[AITTSProvider]
        -_stt_providers: list[AISTTProvider]
        +speak(request: AudioRequest) AudioResponse
        +transcribe(request: AudioRequest) AudioResponse
        +list_tts_voices(language: str) list[dict]
        +status() dict
        -_get_available_tts(preferred) list
        -_get_available_stt(preferred) list
    }

    class Pyttsx3TTSProvider {
        -_engine: pyttsx3.Engine
        -_rate: int
        -_volume: float
        +speak(request) AudioResponse
        +list_voices(language) list[dict]
    }

    class EdgeTTSProvider {
        -_default_voice: str
        -_available: bool
        +speak(request) AudioResponse
        +list_voices_async() list[dict]
        -_synthesize_async(text, voice, rate) bytes
        -_speed_to_rate(speed) str
    }

    class ElevenLabsTTSProvider {
        -_api_key: str
        -_model_id: str
        -_client: ElevenLabs
        +speak(request) AudioResponse
        -_synthesize(text, voice_id) bytes
    }

    class OpenAITTSProvider {
        -_api_key: str
        -_model: str
        -_client: OpenAI
        +speak(request) AudioResponse
    }

    class WhisperLocalProvider {
        -_model_size: str
        -_device: str
        -_model: WhisperModel
        +transcribe(request) AudioResponse
        +model_size: str
        -_try_load()
    }

    class GroqSTTProvider {
        -_api_key: str
        -_model: str
        -_client: Groq
        +transcribe(request) AudioResponse
    }

    class OpenAISTTProvider {
        -_api_key: str
        -_client: OpenAI
        +transcribe(request) AudioResponse
    }

    class MicrophoneCapture {
        -_sample_rate: int
        -_channels: int
        -_backend: str
        +record_fixed(duration) bytes
        +record_until_silence(max_dur, silence_dur) bytes
        +list_devices() list[dict]
        +is_available() bool
        -_rms(samples) float
    }

    AITTSProvider <|.. Pyttsx3TTSProvider
    AITTSProvider <|.. EdgeTTSProvider
    AITTSProvider <|.. ElevenLabsTTSProvider
    AITTSProvider <|.. OpenAITTSProvider

    AISTTProvider <|.. WhisperLocalProvider
    AISTTProvider <|.. GroqSTTProvider
    AISTTProvider <|.. OpenAISTTProvider

    AudioService o-- AITTSProvider : uses
    AudioService o-- AISTTProvider : uses
    AudioService ..> AudioRequest : consumes
    AudioService ..> AudioResponse : produces

    AITTSProvider ..> AudioRequest : consumes
    AITTSProvider ..> AudioResponse : produces
    AISTTProvider ..> AudioRequest : consumes
    AISTTProvider ..> AudioResponse : produces
```

---

## 19. Diagrama de Sequência — Fluxo de Voz

### 19.1 TTS — POST /v1/speak

```mermaid
sequenceDiagram
    actor Client
    participant API as FastAPI /v1/speak
    participant SVC as AudioService
    participant P1 as Pyttsx3TTS
    participant P2 as EdgeTTS
    participant P3 as ElevenLabsTTS

    Client->>API: POST /v1/speak (form: text, voice, speed)
    API->>SVC: speak(AudioRequest)
    SVC->>P1: is_available()?
    P1-->>SVC: true (local disponível)
    SVC->>P1: speak(request)
    alt pyttsx3 OK
        P1-->>SVC: AudioResponse(audio_data=WAV, cost=0.0)
        SVC-->>API: AudioResponse
        API-->>Client: 200 audio/wav (X-Provider: pyttsx3)
    else pyttsx3 falhou
        P1-->>SVC: RuntimeError
        SVC->>P2: is_available()?
        P2-->>SVC: true (edge-tts instalado)
        SVC->>P2: speak(request)
        P2->>P2: asyncio.run(_synthesize_async)
        P2-->>SVC: AudioResponse(audio_data=MP3, cost=0.0)
        SVC-->>API: AudioResponse
        API-->>Client: 200 audio/mpeg (X-Provider: edge_tts)
    else edge_tts também falhou
        SVC->>P3: is_available()? + speak(request)
        P3->>P3: ElevenLabs API call
        P3-->>SVC: AudioResponse(audio_data=MP3, cost=0.000018)
        SVC-->>API: AudioResponse
        API-->>Client: 200 audio/mpeg (X-Provider: elevenlabs_tts)
    end
```

### 19.2 STT — POST /v1/transcribe

```mermaid
sequenceDiagram
    actor Client
    participant API as FastAPI /v1/transcribe
    participant SVC as AudioService
    participant W as WhisperLocal
    participant G as GroqSTT
    participant O as OpenAISTT

    Client->>API: POST /v1/transcribe (file: audio.wav)
    API->>API: await file.read()
    API->>SVC: transcribe(AudioRequest(audio_data, format))
    SVC->>W: is_available()?
    W-->>SVC: true (modelo carregado em memória)
    SVC->>W: transcribe(request)
    W->>W: salva tmpfile → faster_whisper.transcribe()
    W->>W: VAD filter + beam_size=5
    W-->>SVC: AudioResponse(transcription, language_detected, segments)
    SVC-->>API: AudioResponse
    API-->>Client: 200 JSON {transcription, language_detected, segments, cost: 0.0}

    Note over Client,O: Se Whisper local não disponível:
    SVC->>G: is_available()? → speak(request)
    G->>G: groq.audio.transcriptions.create(whisper-large-v3)
    G-->>SVC: AudioResponse(transcription, cost=0.0)
```

### 19.3 STT em Tempo Real — WebSocket /v1/transcribe/stream

```mermaid
sequenceDiagram
    actor Client
    participant WS as WebSocket /v1/transcribe/stream
    participant SVC as AudioService

    Client->>WS: WebSocket connect
    WS-->>Client: 101 Switching Protocols

    loop Envio de chunks
        Client->>WS: bytes (chunk PCM 16kHz)
        WS-->>Client: {"status": "chunk_received", "total_bytes": N}
    end

    Client->>WS: text {"done": true, "language": "pt"}
    WS->>WS: junta chunks → monta WAV
    WS->>SVC: transcribe(AudioRequest)
    SVC-->>WS: AudioResponse
    WS-->>Client: {"transcription": "...", "language_detected": "pt", "final": true}
    WS->>WS: fecha conexão
```

---

## 20. Diagrama de Estado — Seleção de Provider de Voz

```mermaid
stateDiagram-v2
    [*] --> Iniciando: AudioService.speak() / .transcribe()

    Iniciando --> FiltrandoDisponiveis: filtra is_available()

    FiltrandoDisponiveis --> VerificandoPreferido: lista providers disponíveis

    VerificandoPreferido --> TentandoProvider: preferred_provider definido?
    VerificandoPreferido --> TentandoProvider: usa ordem padrão

    state TentandoProvider {
        [*] --> Executando
        Executando --> Sucesso: resposta OK
        Executando --> Falha: exceção capturada

        Falha --> ProximoProvider: ainda há providers
        Falha --> TodosFalharam: lista esgotada
    }

    Sucesso --> [*]: retorna AudioResponse
    TodosFalharam --> [*]: RuntimeError "Todos os providers falharam"

    state "Ordem TTS" as OrdemTTS {
        pyttsx3_local --> edge_tts_gratis
        edge_tts_gratis --> elevenlabs_pago
        elevenlabs_pago --> openai_tts_pago
    }

    state "Ordem STT" as OrdemSTT {
        whisper_local --> groq_whisper_gratis
        groq_whisper_gratis --> openai_whisper_pago
    }
```

---

## 21. Referência da API REST

### Base URL

```
http://localhost:8000
```

### Headers Obrigatórios

```
X-Tenant-ID: <identificador-do-tenant>
Content-Type: application/json
```

---

### `POST /v1/completions`

Submete uma requisição de geração de texto.

**Request Body:**

```json
{
  "prompt": "Explique o que é Clean Architecture",
  "model": null,
  "messages": null,
  "temperature": 0.7,
  "max_tokens": 512,
  "stream": false,
  "tools": null,
  "priority": "normal",
  "difficulty": "medium",
  "complexity": 0.5,
  "max_cost": "low",
  "preferred_provider": null
}
```

| Campo | Tipo | Default | Descrição |
|-------|------|---------|-----------|
| `prompt` | `string` | — | Texto da requisição (obrigatório) |
| `model` | `string\|null` | `null` | Modelo específico (o router decide se null) |
| `messages` | `array\|null` | `null` | Histórico no formato `[{role, content}]` |
| `temperature` | `float` | `0.7` | Aleatoriedade (0.0–2.0) |
| `max_tokens` | `int` | `512` | Limite de tokens na resposta |
| `stream` | `bool` | `false` | Resposta em streaming NDJSON |
| `priority` | `string` | `"normal"` | `low\|normal\|high` |
| `difficulty` | `string` | `"medium"` | `easy\|medium\|hard\|expert` |
| `complexity` | `float` | `0.5` | Complexidade 0.0–1.0 |
| `max_cost` | `string` | `"medium"` | `free\|low\|medium\|high` |
| `preferred_provider` | `string\|null` | `null` | Nome do provider preferido |

**Response (stream=false):**

```json
{
  "output": "Clean Architecture é um padrão proposto por...",
  "tokens_used": 234,
  "provider_name": "groq",
  "cost": 0.0000187,
  "is_streaming_chunk": false,
  "tool_calls": null
}
```

**Response (stream=true):** NDJSON — um objeto por linha:

```
{"output": "Clean", "tokens_used": 0, "provider_name": "groq", "cost": 0.0, "is_streaming_chunk": true}
{"output": " Architecture", "tokens_used": 0, "provider_name": "groq", "cost": 0.0, "is_streaming_chunk": true}
...
```

---

### `GET /v1/models`

Lista todos os modelos disponíveis nos providers configurados.

**Response:**

```json
{
  "models": [
    {
      "id": "llama-3.1-8b-instant",
      "provider": "groq",
      "supports_streaming": true,
      "cost_per_1k_tokens": 0.00008,
      "is_free": false,
      "is_local": false,
      "capabilities": ["text", "function_calling"]
    },
    {
      "id": "meta-llama/llama-3.2-3b-instruct:free",
      "provider": "openrouter",
      "supports_streaming": true,
      "cost_per_1k_tokens": 0.0,
      "is_free": true,
      "is_local": false,
      "capabilities": ["text"]
    },
    {
      "id": "llama3.2:3b",
      "provider": "ollama",
      "supports_streaming": true,
      "cost_per_1k_tokens": 0.0,
      "is_free": true,
      "is_local": true,
      "capabilities": ["text"]
    }
  ],
  "total": 32
}
```

---

### `GET /v1/quotas`

Retorna o status atual das quotas diárias.

**Response:**

```json
{
  "groq": {
    "usage": 142,
    "limit": 14400,
    "remaining": 14258,
    "available": true,
    "reset_at": "amanhã 00:00"
  },
  "gemini": {
    "usage": 38,
    "limit": 1500,
    "remaining": 1462,
    "available": true,
    "reset_at": "amanhã 00:00"
  }
}
```

---

### `GET /v1/hardware`

Retorna informações de hardware detectado e modelos recomendados.

**Response:**

```json
{
  "ram_gb": 16.0,
  "cpu_cores": 8,
  "cpu_threads": 16,
  "gpu": "NVIDIA GeForce RTX 3060",
  "gpu_vram_gb": 12.0,
  "acceleration": "CUDA",
  "recommended_models": [
    "gemma2:9b",
    "llama3.1:8b",
    "mistral:7b",
    "qwen2.5:7b",
    "phi3.5"
  ]
}
```

---

### `GET /health`

Verifica disponibilidade do serviço e de todos os providers.

**Response:**

```json
{
  "status": "ok",
  "providers": {
    "ollama": { "available": true, "models": ["llama3.2:3b", "mistral:7b"] },
    "groq": { "available": true, "models": ["llama-3.1-8b-instant", "llama-3.3-70b"] },
    "gemini": { "available": true, "models": ["gemini-1.5-flash", "gemini-1.5-pro"] }
  },
  "quota_status": { "groq": { "usage": 142, "limit": 14400, "available": true } }
}
```

---

### `GET /v1/tenants/{tenant_id}/stats`

Retorna estatísticas de um tenant específico.

---

### `POST /v1/speak`

Sintetiza voz a partir de texto. Retorna bytes de áudio diretamente.

**Content-Type:** `multipart/form-data`

| Campo | Tipo | Default | Descrição |
|-------|------|---------|-----------|
| `text` | `string` | — | Texto a ser sintetizado (obrigatório) |
| `voice` | `string\|null` | `null` | Nome/ID da voz (ex: `pt-BR-FranciscaNeural`, `nova`) |
| `speed` | `float` | `1.0` | Velocidade 0.25–4.0 |
| `preferred_provider` | `string\|null` | `null` | `pyttsx3`, `edge_tts`, `elevenlabs_tts`, `openai_tts` |

**Response:** `audio/mpeg` ou `audio/wav` (bytes do áudio)

**Headers da resposta:**
```
X-Provider: edge_tts
X-Cost: 0.0
X-Audio-Format: mp3
```

**Exemplo cURL:**
```bash
curl -X POST http://localhost:8000/v1/speak \
  -F "text=Olá! Bem-vindo ao AI Adapter." \
  -F "voice=pt-BR-FranciscaNeural" \
  -F "speed=1.0" \
  --output resposta.mp3
```

---

### `POST /v1/transcribe`

Transcreve um arquivo de áudio para texto.

**Content-Type:** `multipart/form-data`

| Campo | Tipo | Default | Descrição |
|-------|------|---------|-----------|
| `file` | `UploadFile` | — | Arquivo de áudio (wav, mp3, m4a, webm) |
| `language` | `string\|null` | `null` | Código do idioma (`pt`, `en`). `null` = auto-detect |
| `preferred_provider` | `string\|null` | `null` | `whisper_local`, `groq_stt`, `openai_stt` |

**Response:**

```json
{
  "transcription": "Olá, isso é um teste de transcrição.",
  "language_detected": "pt",
  "confidence": 0.98,
  "segments": [
    {"start": 0.0, "end": 2.3, "text": "Olá, isso é um teste"},
    {"start": 2.3, "end": 3.8, "text": "de transcrição."}
  ],
  "provider": "whisper_local",
  "cost": 0.0
}
```

**Exemplo cURL:**
```bash
curl -X POST http://localhost:8000/v1/transcribe \
  -F "file=@minha_voz.wav" \
  -F "language=pt"
```

---

### `GET /v1/voices`

Lista todas as vozes TTS disponíveis.

**Query Params:** `language=pt` (padrão)

**Response:**

```json
{
  "voices": [
    {
      "name": "pt-BR-FranciscaNeural",
      "gender": "female",
      "language": "pt-BR",
      "style": "general",
      "provider": "edge_tts"
    },
    {
      "name": "nova",
      "gender": "female",
      "language": "multilingual",
      "style": "quick",
      "provider": "openai_tts"
    }
  ]
}
```

---

### `GET /v1/audio/status`

Retorna disponibilidade dos providers de voz configurados.

**Response:**

```json
{
  "tts": [
    {"name": "pyttsx3",        "available": true},
    {"name": "edge_tts",       "available": true},
    {"name": "elevenlabs_tts", "available": false},
    {"name": "openai_tts",     "available": true}
  ],
  "stt": [
    {"name": "whisper_local", "available": true},
    {"name": "groq_stt",      "available": true},
    {"name": "openai_stt",    "available": true}
  ]
}
```

---

### `WebSocket /v1/transcribe/stream`

Transcrição em tempo real via WebSocket.

**Protocolo:**

```
→ bytes               : chunk PCM raw (16kHz, mono, int16)
→ {"done": true}      : sinaliza fim do áudio
← {"status": "chunk_received", "total_bytes": N}  : ACK de chunk
← {"transcription": "...", "language_detected": "pt", "final": true}
```

**Exemplo Python:**
```python
import asyncio, websockets, json

async def transcrever(arquivo_wav: bytes):
    uri = "ws://localhost:8000/v1/transcribe/stream"
    async with websockets.connect(uri) as ws:
        # Envia em chunks de 16KB
        for i in range(0, len(arquivo_wav), 16384):
            await ws.send(arquivo_wav[i:i+16384])
            ack = await ws.recv()
            print(json.loads(ack))

        # Sinaliza fim
        await ws.send(json.dumps({"done": True, "language": "pt"}))
        resultado = json.loads(await ws.recv())
        print(resultado["transcription"])
```

---

## 22. Configuração e Instalação

### Pré-requisitos

- Python 3.10+
- (Opcional) Ollama instalado: https://ollama.ai

### Instalação

```bash
# 1. Clone e entre na pasta
cd assistente-inteligente

# 2. Crie ambiente virtual
python -m venv .venv
source .venv/bin/activate     # Linux/macOS
.venv\Scripts\activate         # Windows

# 3. Instale dependências básicas
pip install -e .

# 4. Instale todos os providers
pip install -e ".[all-providers]"

# 5. Configure as variáveis de ambiente
cp .env.example .env
# Edite .env com suas chaves de API

# 6. (Opcional) Inicie o Ollama
ollama serve

# 7. Inicie o servidor
python main.py
# ou para desenvolvimento:
uvicorn aiadapter.api.main:app --reload
```

### Variáveis de Ambiente Completas

```env
# ── LLM Providers ─────────────────────────────────────────────────────────────
OPENAI_API_KEY=sk-...           # openai.com
ANTHROPIC_API_KEY=sk-ant-...    # anthropic.com
GEMINI_API_KEY=AIza...          # aistudio.google.com (free tier disponível)
GROQ_API_KEY=gsk_...            # console.groq.com (free tier 14.400 req/dia)
MISTRAL_API_KEY=...             # console.mistral.ai
DEEPSEEK_API_KEY=...            # platform.deepseek.com ($5 crédito inicial)
OPENROUTER_API_KEY=sk-or-...    # openrouter.ai (free tier disponível)
OLLAMA_BASE_URL=http://localhost:11434  # padrão

# ── Voice TTS ─────────────────────────────────────────────────────────────────
ELEVENLABS_API_KEY=...          # elevenlabs.io (10k chars/mês grátis)
# OpenAI TTS usa OPENAI_API_KEY automaticamente

# ── Voice STT ─────────────────────────────────────────────────────────────────
WHISPER_MODEL_SIZE=base         # tiny | base | small | medium | large-v3
# Groq STT usa GROQ_API_KEY automaticamente

# ── Servidor ──────────────────────────────────────────────────────────────────
HOST=0.0.0.0
PORT=8000
LOG_LEVEL=INFO
OPENROUTER_SITE_URL=http://localhost
OPENROUTER_SITE_NAME=AI Adapter
```

### Configuração Mínima (só free — sem gastar nada)

```env
GROQ_API_KEY=gsk_...          # groq.com - cadastro gratuito (LLM + STT)
GEMINI_API_KEY=AIza...         # aistudio.google.com - cadastro gratuito
OPENROUTER_API_KEY=sk-or-...   # openrouter.ai - cadastro gratuito
```

Instale o Ollama para modelos locais e voz offline:
```bash
# Ollama — LLM local
curl -fsSL https://ollama.ai/install.sh | sh
ollama pull llama3.2:3b

# Dependências de voz local (offline total)
pip install -e ".[voice-local]"     # faster-whisper + pyttsx3

# Dependências de voz remota gratuita
pip install -e ".[voice-remote]"    # edge-tts (gratuito, pt-BR nativo)

# Microfone (captura em tempo real)
pip install -e ".[voice-mic]"       # sounddevice + scipy
```

### Instalação para Raspberry Pi

```bash
# Pi OS 64-bit (bullseye/bookworm)
sudo apt-get update
sudo apt-get install -y python3-pip ffmpeg espeak espeak-ng portaudio19-dev

# Instala o projeto
pip install -e ".[voice-local,voice-mic]"

# Whisper tiny para Pi com 2GB RAM, base para 4GB+
echo "WHISPER_MODEL_SIZE=tiny" >> .env   # Pi 2/3
echo "WHISPER_MODEL_SIZE=base" >> .env   # Pi 4 com 4GB

# Edge TTS (pt-BR gratuito, não precisa de hardware)
pip install edge-tts
```

### Exemplo de Uso (cURL)

```bash
# Tarefa simples — usará free tier automaticamente
curl -X POST http://localhost:8000/v1/completions \
  -H "Content-Type: application/json" \
  -H "X-Tenant-ID: meu-agente" \
  -d '{
    "prompt": "Qual é a capital do Brasil?",
    "difficulty": "easy",
    "complexity": 0.1,
    "max_cost": "free"
  }'

# Tarefa complexa — usará modelo de alta qualidade
curl -X POST http://localhost:8000/v1/completions \
  -H "Content-Type: application/json" \
  -H "X-Tenant-ID: meu-agente" \
  -d '{
    "prompt": "Projete uma arquitetura de event sourcing para um sistema bancário",
    "difficulty": "expert",
    "complexity": 0.95,
    "max_cost": "high",
    "max_tokens": 2048
  }'

# Síntese de voz (TTS)
curl -X POST http://localhost:8000/v1/speak \
  -F "text=Olá! Sou o assistente de IA, como posso ajudar?" \
  -F "voice=pt-BR-FranciscaNeural" \
  --output resposta.mp3

# Transcrição de voz (STT)
curl -X POST http://localhost:8000/v1/transcribe \
  -F "file=@minha_pergunta.wav" \
  -F "language=pt"

# Listar vozes disponíveis
curl http://localhost:8000/v1/voices?language=pt

# Verificar quotas
curl http://localhost:8000/v1/quotas

# Verificar hardware e modelos recomendados
curl http://localhost:8000/v1/hardware
```

---

## 23. Estrutura de Arquivos

```
assistente-inteligente/
│
├── main.py                          # Entry point: carrega .env e inicia uvicorn
├── pyproject.toml                   # Dependências e configurações do projeto
├── .env.example                     # Template de variáveis de ambiente
├── .gitignore
├── README.md
│
├── data/                            # Dados persistidos em runtime
│   └── daily_quotas.json            # Estado das quotas diárias (auto-gerado)
│
└── aiadapter/                       # Pacote principal
    │
    ├── config/
    │   └── settings.py              # Carrega variáveis de ambiente → Settings
    │
    ├── core/                        # ← NÚCLEO (sem dependências externas)
    │   ├── entities/
    │   │   ├── airequest.py         # Entidade: intenção de uso da IA (LLM)
    │   │   ├── airesponse.py        # Entidade: resposta padronizada (LLM)
    │   │   ├── aiprovidermedata.py  # Entidade: metadados de um provider
    │   │   ├── audiorequest.py      # Entidade: requisição TTS/STT ← NOVO
    │   │   └── audioresponse.py     # Entidade: resposta TTS/STT   ← NOVO
    │   ├── enums/
    │   │   └── aicapability.py      # Enum: capacidades (TEXT, VISION, etc.)
    │   └── interfaces/
    │       ├── provider.py          # Contrato: AIProvider (ABC)
    │       ├── router.py            # Contrato: AIRouter (ABC)
    │       ├── policy.py            # Contrato: AIPolicy (ABC)
    │       ├── cache.py             # Contrato: AICache (ABC)
    │       ├── rate_limiter.py      # Contrato: AIRateLimiter (ABC)
    │       ├── observability.py     # Contrato: AIObservability (ABC)
    │       ├── tool.py              # Contrato: AITool (ABC)
    │       ├── tts_provider.py      # Contrato: AITTSProvider (ABC) ← NOVO
    │       └── stt_provider.py      # Contrato: AISTTProvider (ABC) ← NOVO
    │
    ├── infrastructure/              # ← INFRAESTRUTURA (SDKs externos aqui)
    │   ├── providers/
    │   │   ├── openai/
    │   │   │   └── openai_provider.py
    │   │   ├── anthropic/
    │   │   │   └── calude_provider.py
    │   │   ├── google/
    │   │   │   └── gemini_provider.py
    │   │   ├── groq/
    │   │   │   └── groq_provider.py
    │   │   ├── mistral/
    │   │   │   └── mistral_provider.py
    │   │   ├── deepseek/
    │   │   │   └── deepseek_provider.py
    │   │   ├── openrouter/
    │   │   │   └── openrouter_provider.py
    │   │   ├── local/
    │   │   │   └── ollama_provider.py
    │   │   ├── tts/                         # ← NOVO
    │   │   │   ├── pyttsx3_provider.py      # 100% offline (SAPI5/espeak/nsss)
    │   │   │   ├── edge_tts_provider.py     # Microsoft Edge TTS gratuito
    │   │   │   ├── elevenlabs_provider.py   # Ultra-realista (10k chars/mês free)
    │   │   │   └── openai_tts_provider.py   # OpenAI TTS ($15/1M chars)
    │   │   └── stt/                         # ← NOVO
    │   │       ├── whisper_local_provider.py  # faster-whisper offline
    │   │       ├── groq_stt_provider.py       # whisper-large-v3 gratuito
    │   │       └── openai_stt_provider.py     # whisper-1 ($0.006/min)
    │   ├── routing/
    │   │   └── cost_router.py       # Seleção inteligente por tier
    │   ├── governance/
    │   │   ├── cost_router.py       # Re-export (compatibilidade)
    │   │   ├── simple_policy.py     # Validação de requisições
    │   │   ├── simple_cache.py      # Cache em memória
    │   │   ├── simple_rate_limiter.py # Rate limiting por minuto
    │   │   ├── logger_observability.py # Logging estruturado
    │   │   └── daily_quota_manager.py  # Quotas diárias com reset automático
    │   └── system/
    │       ├── hardware_analyzer.py    # Detecção de hardware (RAM/GPU)
    │       └── microphone_capture.py   # Captura de microfone com VAD ← NOVO
    │
    ├── application/
    │   ├── ai_service.py            # Orquestrador LLM (pipeline completo)
    │   └── audio_service.py         # Orquestrador TTS/STT com fallback ← NOVO
    │
    ├── api/
    │   └── main.py                  # FastAPI: todas as rotas + voice endpoints
    │
    ├── agents/
    │   ├── base_agent.py            # Agente base com histórico de conversação
    │   ├── simple_agent.py          # Implementação simples
    │   └── agent_manager.py         # Gerenciador de múltiplos agentes
    │
    └── factory/
        ├── abstract_factory.py      # Interface de fábrica de providers
        └── factory_provider.py      # Fábrica concreta
```

---

### Testes

```
tests/
├── conftest.py                   # Fixtures compartilhadas
├── unit/
│   ├── test_entities.py          # AIRequest, AIResponse, AIProviderMetadata
│   ├── test_policy.py            # SimplePolicy — validação de campos
│   ├── test_cache.py             # SimpleCache — hit/miss/isolation
│   ├── test_rate_limiter.py      # SimpleRateLimiter — sliding window
│   ├── test_quota_manager.py     # DailyQuotaManager — reset, persistência
│   ├── test_cost_router.py       # CostRouter — tier selection, fallback
│   ├── test_ai_service.py        # AIService — pipeline completo
│   ├── test_hardware_analyzer.py # HardwareAnalyzer — mock subprocess
│   ├── test_observability.py     # LoggerObservability — caplog
│   ├── test_audio_entities.py    # AudioRequest, AudioResponse ← NOVO
│   ├── test_audio_service.py     # AudioService — TTS/STT fallback ← NOVO
│   ├── test_tts_providers.py     # pyttsx3, edge-tts, openai-tts  ← NOVO
│   └── test_stt_providers.py     # whisper-local, groq-stt, openai-stt ← NOVO
└── integration/
    └── test_ollama_integration.py  # Requer Ollama rodando (@pytest.mark.integration)
```

---

*Documentação gerada para o AI Adapter v2.1.0*
*Arquitetura: Clean Architecture + Strategy + Chain of Responsibility + Proxy + DI + Template Method*
*Voz: TTS (pyttsx3 / Edge TTS / ElevenLabs / OpenAI) + STT (faster-whisper / Groq / OpenAI)*
