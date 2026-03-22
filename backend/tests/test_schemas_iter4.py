import pytest
from uuid import uuid4
from app.schemas.search import SearchRequest, SearchResultResponse, SearchResponse
from app.schemas.memory import MemoryCreate, MemoryResponse


def test_search_request_defaults():
    req = SearchRequest(query="test query", project_id=uuid4())
    assert req.top_m == 5
    assert req.pov_entity_id is None


def test_search_request_with_pov():
    pid = uuid4()
    eid = uuid4()
    req = SearchRequest(query="test", project_id=pid, pov_entity_id=eid, top_m=10)
    assert req.pov_entity_id == eid
    assert req.top_m == 10


def test_search_result_response():
    r = SearchResultResponse(
        source="entity", source_id=uuid4(), content="test", score=0.9, metadata={},
    )
    assert r.source == "entity"
    assert r.score == 0.9


def test_search_response():
    r = SearchResponse(results=[], total=0)
    assert r.total == 0


def test_memory_create():
    m = MemoryCreate(summary="Test memory")
    assert m.summary == "Test memory"


def test_memory_response():
    m = MemoryResponse(
        id=uuid4(), chapter_id=uuid4(), summary="Test",
        has_embedding=True, created_at="2026-01-01T00:00:00",
    )
    assert m.has_embedding is True
