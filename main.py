from dotenv import load_dotenv
from openai import OpenAI
from anthropic import Anthropic

from aiadapter.config.settings import load_settings
from aiadapter.infrastructure.providers.openai.openai_provider import OpenAIProvider
from aiadapter.infrastructure.providers.anthropic.antropic_provider import AnthropicProvider
from aiadapter.infrastructure.routing.cost_router import CostRouter
from aiadapter.infrastructure.governance.simple_policy import SimplePolicy
from aiadapter.infrastructure.governance.logger_observability import LoggerObservability
from aiadapter.application.ai_service import AIService


# 🔹 1. Carrega ambiente
load_dotenv()

# 🔹 2. Carrega settings
settings = load_settings()

# 🔹 3. Cria clients
openai_client = OpenAI(api_key=settings.openai_api_key)
#anthropic_client = Anthropic(api_key=settings.anthropic_api_key)

# 🔹 4. Injeta clients nos providers
openai_provider = OpenAIProvider(client=openai_client)
#anthropic_provider = AnthropicProvider(client=anthropic_client)

providers = {
    "openai": openai_provider,
    #"anthropic": anthropic_provider
}

# 🔹 5. Router
router = CostRouter(providers)

# 🔹 6. Policy
policy = SimplePolicy()

# 🔹 7. Observability
observability = LoggerObservability()

# 🔹 8. Service
ai_service = AIService(
    router=router,
    policy=policy,
    observability=observability
)
