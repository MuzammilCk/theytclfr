import logging
import time
import asyncio

import httpx

from ytclfr.core.config import Settings

logger = logging.getLogger(__name__)

EMBEDDING_RETRY_ATTEMPTS: int = 3
EMBEDDING_RETRY_DELAY_SECONDS: float = 2.0


def generate_embedding(text: str, settings: Settings) -> list[float] | None:
    if not text.strip():
        return None

    endpoint = f"{settings.ollama_base_url.rstrip('/')}/api/embeddings"
    payload = {
        "model": settings.ollama_embedding_model,
        "prompt": text,
    }

    for attempt in range(EMBEDDING_RETRY_ATTEMPTS):
        try:
            with httpx.Client(timeout=settings.llm_request_timeout_seconds) as client:
                response = client.post(endpoint, json=payload)
                if response.status_code != 200:
                    logger.warning("Ollama API Error %s: %s", response.status_code, response.text)
                response.raise_for_status()
                data = response.json()
                embedding = data.get("embedding")

                if not embedding or not isinstance(embedding, list):
                    logger.warning(f"Invalid embedding format returned from Ollama: {type(embedding)}")
                    return None

                if len(embedding) > settings.embedding_dim:
                    embedding = embedding[:settings.embedding_dim]
                elif len(embedding) < settings.embedding_dim:
                    embedding = embedding + [0.0] * (settings.embedding_dim - len(embedding))

                return embedding

        except Exception as e:
            logger.warning(
                f"Embedding generation attempt {attempt + 1}/{EMBEDDING_RETRY_ATTEMPTS} failed: {e}"
            )
            if attempt < EMBEDDING_RETRY_ATTEMPTS - 1:
                time.sleep(EMBEDDING_RETRY_DELAY_SECONDS)

    logger.warning("Total failure in generating embedding.")
    return None

async def _generate_embedding_async(client: httpx.AsyncClient, text: str, settings: Settings, semaphore: asyncio.Semaphore) -> list[float] | None:
    if not text.strip():
        return None

    endpoint = f"{settings.ollama_base_url.rstrip('/')}/api/embeddings"
    payload = {
        "model": settings.ollama_embedding_model,
        "prompt": text,
    }

    async with semaphore:
        for attempt in range(EMBEDDING_RETRY_ATTEMPTS):
            try:
                response = await client.post(endpoint, json=payload)
                if response.status_code != 200:
                    logger.warning("Ollama API Error %s: %s", response.status_code, response.text)
                response.raise_for_status()
                data = response.json()
                embedding = data.get("embedding")

                if not embedding or not isinstance(embedding, list):
                    logger.warning(f"Invalid embedding format returned from Ollama: {type(embedding)}")
                    return None

                if len(embedding) > settings.embedding_dim:
                    embedding = embedding[:settings.embedding_dim]
                elif len(embedding) < settings.embedding_dim:
                    embedding = embedding + [0.0] * (settings.embedding_dim - len(embedding))

                return embedding

            except Exception as e:
                logger.warning(
                    f"Async embedding generation attempt {attempt + 1}/{EMBEDDING_RETRY_ATTEMPTS} failed: {e}"
                )
                if attempt < EMBEDDING_RETRY_ATTEMPTS - 1:
                    await asyncio.sleep(EMBEDDING_RETRY_DELAY_SECONDS)

        logger.warning("Total failure in async generating embedding.")
        return None

async def _generate_embeddings_batch_async(texts: list[str], settings: Settings, max_concurrent: int = 20) -> list[list[float] | None]:
    semaphore = asyncio.Semaphore(max_concurrent)
    async with httpx.AsyncClient(timeout=settings.llm_request_timeout_seconds) as client:
        tasks = [_generate_embedding_async(client, t, settings, semaphore) for t in texts]
        return await asyncio.gather(*tasks)

def generate_embeddings_batch(texts: list[str], settings: Settings) -> list[list[float] | None]:
    return asyncio.run(_generate_embeddings_batch_async(texts, settings))
