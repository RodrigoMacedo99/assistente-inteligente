import os
from dataclasses import dataclass
from typing import Optional


@dataclass
class Settings:
    # APIs pagas (com free tier)
    openai_api_key: Optional[str] = None
    anthropic_api_key: Optional[str] = None
    gemini_api_key: Optional[str] = None
    groq_api_key: Optional[str] = None
    mistral_api_key: Optional[str] = None
    deepseek_api_key: Optional[str] = None
    openrouter_api_key: Optional[str] = None

    # Ollama local
    ollama_base_url: str = "http://localhost:11434"

    # Configurações do servidor
    host: str = "0.0.0.0"
    port: int = 8000
    log_level: str = "INFO"

    # OpenRouter site info (aparece nas estatísticas)
    openrouter_site_url: str = "http://localhost"
    openrouter_site_name: str = "AI Adapter"

    # Voice — TTS
    elevenlabs_api_key: Optional[str] = None

    # Voice — STT (Whisper local)
    whisper_model_size: str = "base"  # tiny | base | small | medium | large-v3


def load_settings() -> Settings:
    return Settings(
        openai_api_key=os.getenv("OPENAI_API_KEY"),
        anthropic_api_key=os.getenv("ANTHROPIC_API_KEY"),
        gemini_api_key=os.getenv("GEMINI_API_KEY"),
        groq_api_key=os.getenv("GROQ_API_KEY"),
        mistral_api_key=os.getenv("MISTRAL_API_KEY"),
        deepseek_api_key=os.getenv("DEEPSEEK_API_KEY"),
        openrouter_api_key=os.getenv("OPENROUTER_API_KEY"),
        ollama_base_url=os.getenv("OLLAMA_BASE_URL", "http://localhost:11434"),
        host=os.getenv("HOST", "0.0.0.0"),
        port=int(os.getenv("PORT", "8000")),
        log_level=os.getenv("LOG_LEVEL", "INFO"),
        openrouter_site_url=os.getenv("OPENROUTER_SITE_URL", "http://localhost"),
        openrouter_site_name=os.getenv("OPENROUTER_SITE_NAME", "AI Adapter"),
        elevenlabs_api_key=os.getenv("ELEVENLABS_API_KEY"),
        whisper_model_size=os.getenv("WHISPER_MODEL_SIZE", "base"),
    )
