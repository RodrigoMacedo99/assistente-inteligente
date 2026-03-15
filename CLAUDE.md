# 🧠 Assistente Inteligente — AI Adapter Multi-Provider

## 🎯 Objetivo

Construir um **AI Adapter multi-provider com Clean Architecture**, capaz de:

- Integrar múltiplos provedores (OpenAI, Anthropic, etc.)
- Permitir roteamento inteligente entre modelos com fallback automático
- Aplicar políticas de governança e rate limiting
- Manter observabilidade e cache de respostas
- Ser extensível para novos modelos e capacidades, incluindo streaming e tool calling
- Servir como base para um assistente tipo “Jarvis” e uma API REST multi-tenant

## 🏗 Arquitetura do Sistema

Estrutura baseada em **Clean Architecture**:

```
aiadapter/
│
├── core/                → Domínio (regras e contratos)
├── infrastructure/      → Implementações concretas
├── application/         → Orquestração
├── config/              → Configuração
├── api/                 → API REST com FastAPI
├── agents/              → Sistema de Agentes
```

### Princípios aplicados

- Clean Architecture
- Dependency Inversion
- Baixo acoplamento
- Alta coesão
- Separação clara de responsabilidades

## 🧩 Componentes Principais

### 1️⃣ Core (Domínio)

Define contratos e entidades principais:

- `AIProvider` (interface)
- `AIRequest`
- `AIResponse`
- `AIProviderMetadata`
- `AICapability`
- `AIRouter`
- `AIPolicy`
- `AIObservability`
- `AIRateLimiter`
- `AICache`
- `AITool`

⚠️ O core não depende de SDK externo.

### 2️⃣ Infrastructure

Implementações concretas:

- `OpenAIProvider`
- `AnthropicProvider`
- `CostRouter` (com fallback)
- `SimplePolicy`
- `LoggerObservability`
- `SimpleRateLimiter`
- `SimpleCache`

Aqui vivem:

- SDKs externos
- Clients autenticados
- Lógica técnica de roteamento

### 3️⃣ Application

Camada de orquestração com `AIService`.

Fluxo:

```
Request
↓
Policy check
↓
Rate Limiting check
↓
Cache check
↓
Router decide provider(s)
↓
Provider executa (com fallback e streaming)
↓
Tool Calling (se aplicável)
↓
Observability registra
↓
Cache response
↓
Response

```

Essa camada não conhece detalhes de SDK.

### 4️⃣ Configuração

`Settings` carrega variáveis de ambiente:

- `OPENAI_API_KEY`
- `ANTHROPIC_API_KEY`

Responsável por isolar configuração do domínio.

### 5️⃣ API REST (FastAPI)

- Endpoint `/v1/completions` para interagir com o AI Adapter, suportando streaming e tool calling.
- Suporte multi-tenant via `X-Tenant-ID` header.
- Endpoints para `health check` e `list models`.

### 6️⃣ Sistema de Agentes

- `BaseAgent`: Classe abstrata para agentes de IA com histórico de conversação.
- `SimpleAgent`: Implementação básica de um agente.
- `AgentManager`: Gerenciador para múltiplos agentes.

## 🔁 Fluxo Completo do Sistema

```
.env
↓
Settings
↓
Clients (OpenAI / Anthropic)
↓
Providers
↓
Router
↓
Policy
↓
Rate Limiter
↓
Cache
↓
AIService
↓
API REST (FastAPI)
↓
Agentes (opcional)
↓
Resposta final

```

## 🚀 O Que Esse Projeto Representa

Não é apenas um script.

É:

- Um SDK de abstração de IA
- Um motor multi-provider com fallback
- Base para assistente inteligente com streaming e tool calling
- Plataforma extensível
- Gateway de IA corporativo com multi-tenancy e API REST
- Sistema de agentes modular

Pode evoluir para:

- Microserviço
- Biblioteca pública
- SaaS
- Plataforma de agentes avançados
- API Gateway de IA

## 🏆 Pontos Fortes

✔ Separação clara de responsabilidades  
✔ Injeção de dependência adequada  
✔ Providers desacoplados  
✔ Fácil adicionar novos modelos  
✔ Roteamento inteligente com fallback  
✔ Governança centralizada com políticas e rate limiting  
✔ Arquitetura testável  
✔ Suporte a streaming de tokens  
✔ Suporte a tool calling  
✔ API REST com FastAPI  
✔ Suporte multi-tenant  
✔ Sistema de agentes modular

## 📈 Próximos Passos Naturais (Já Implementados)

1. Fallback automático entre providers  
2. Rate limiting inteligente  
3. Cache de respostas  
4. Streaming de tokens  
5. Tool calling estruturado  
6. Multi-tenant (suporte a múltiplas chaves)  
7. API REST (ex: FastAPI)  
8. Sistema de agentes  

## 🧠 Em Uma Frase

Um **AI Gateway com arquitetura limpa e extensível**, pronto para escalar além de um simples uso de SDK, com suporte a streaming, tool calling, multi-tenancy e um sistema de agentes modular.
