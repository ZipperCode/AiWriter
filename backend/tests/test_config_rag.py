from app.config import Settings


def test_rag_config_defaults():
    s = Settings(
        database_url="postgresql+asyncpg://x:x@localhost/x",
        auth_token="test",
    )
    assert s.embedding_dim == 1536
    assert s.rag_top_k == 20
    assert s.rag_top_m == 5
    assert s.rag_rrf_k == 60
    assert s.jina_api_key == ""
    assert s.jina_rerank_model == "jina-reranker-v2-base-multilingual"


def test_rag_config_custom():
    s = Settings(
        database_url="postgresql+asyncpg://x:x@localhost/x",
        auth_token="test",
        rag_top_k=30,
        rag_top_m=10,
        jina_api_key="test-key",
    )
    assert s.rag_top_k == 30
    assert s.rag_top_m == 10
    assert s.jina_api_key == "test-key"
