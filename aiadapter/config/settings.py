import os
from dataclasses import dataclass


@dataclass
class Settings:
    openai_api_key: str
    anthropic_api_key: str
    gemini_api_key: str
    ollama_base_url: str


def load_settings() -> Settings:
    return Settings(
        openai_api_key=os.getenv("OPENAI_API_KEY"),
        anthropic_api_key=os.getenv("ANTHROPIC_API_KEY"),
        gemini_api_key=os.getenv("GEMINI_API_KEY"),
        ollama_base_url=os.getenv("OLLAMA_BASE_URL", "http://localhost:11434"),
    )