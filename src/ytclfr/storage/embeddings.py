import logging
import time

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

                # Clamp or pad vectors to settings.embedding_dim
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


def generate_embeddings_batch(texts: list[str], settings: Settings) -> list[list[float] | None]:
    return [generate_embedding(text, settings) for text in texts]
