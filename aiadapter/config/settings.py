import os
from dataclasses import dataclass


@dataclass
class Settings:
    openai_api_key: str
    anthropic_api_key: str


def load_settings() -> Settings:
    return Settings(
        openai_api_key=os.getenv("OPENAI_API_KEY"),
        anthropic_api_key=os.getenv("ANTHROPIC_API_KEY"),
    )
