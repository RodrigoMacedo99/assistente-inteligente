"""
Ponto de entrada do AI Adapter.

Inicia o servidor FastAPI com uvicorn.
Para desenvolvimento use: uvicorn aiadapter.api.main:app --reload
Para produção use: python main.py
"""

from dotenv import load_dotenv

# Carrega .env antes de qualquer import de settings
load_dotenv()

from aiadapter.config.settings import load_settings  # noqa: E402

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
