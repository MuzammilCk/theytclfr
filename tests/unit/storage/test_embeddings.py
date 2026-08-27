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
    mock_post.return_value.status_code = 200
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
    # generate_embeddings_batch runs on the async path internally
    # (_generate_embeddings_batch_async uses httpx.AsyncClient), so the
    # mock target must be AsyncClient.post, not Client.post — otherwise
    # this silently falls through to a real network call.
    #
    # unittest.mock propagates AsyncMock to every auto-created descendant
    # of an AsyncMock (including .return_value.json), so response.json()
    # would return an un-awaited coroutine instead of a dict. Assigning an
    # explicit plain MagicMock as return_value keeps .json() synchronous,
    # matching the real httpx.Response API.
    fake_response = mocker.MagicMock()
    fake_response.status_code = 200
    fake_response.json.return_value = {"embedding": [0.1] * 768}
    mock_post = mocker.patch("httpx.AsyncClient.post")
    mock_post.return_value = fake_response
    
    embs = generate_embeddings_batch(["hello", "world"], settings)
    assert len(embs) == 2
    assert len(embs[0]) == 768
