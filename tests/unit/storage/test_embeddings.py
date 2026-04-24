from ytclfr.storage.embeddings import generate_embedding, generate_embeddings_batch
from ytclfr.core.config import Settings

def test_generate_embedding_mock(mocker):
    settings = Settings(
        database_url="sqlite:///:memory:",
        redis_url="redis://localhost:6379/0",
        groq_api_key="test",
        jwt_secret_key="test"
    )
    mock_post = mocker.patch("httpx.Client.post")
    mock_post.return_value.json.return_value = {"embedding": [0.1] * 768}
    
    emb = generate_embedding("hello", settings)
    assert len(emb) == 768

def test_generate_embeddings_batch_mock(mocker):
    settings = Settings(
        database_url="sqlite:///:memory:",
        redis_url="redis://localhost:6379/0",
        groq_api_key="test",
        jwt_secret_key="test"
    )
    mock_post = mocker.patch("httpx.Client.post")
    mock_post.return_value.json.return_value = {"embedding": [0.1] * 768}
    
    embs = generate_embeddings_batch(["hello", "world"], settings)
    assert len(embs) == 2
    assert len(embs[0]) == 768
