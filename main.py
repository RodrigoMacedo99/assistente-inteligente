"""
Ponto de entrada do AI Adapter.

Inicia o servidor FastAPI com uvicorn.
Para desenvolvimento use: uvicorn aiadapter.api.main:app --reload
Para produção use: python main.py
"""
import os
from dotenv import load_dotenv

# Carrega .env antes de qualquer import de settings
load_dotenv()

from aiadapter.api.main import app  # noqa: E402 - importado após load_dotenv
from aiadapter.config.settings import load_settings

if __name__ == "__main__":
    import uvicorn
    settings = load_settings()
    uvicorn.run(
        "aiadapter.api.main:app",
        host=settings.host,
        port=settings.port,
        log_level=settings.log_level.lower(),
        reload=False,
    )
