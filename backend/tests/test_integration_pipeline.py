"""Integration test: full chapter pipeline with mocked LLM."""
import json
from unittest.mock import AsyncMock
from uuid import uuid4
from app.agents import AGENT_CLASSES
from app.orchestration.executor import PipelineExecutor
from app.orchestration.pipeline import PipelineDAG, PipelineEdge, PipelineNode
from app.schemas.agent import AgentContext, AgentResult


def _make_finalize_agent():
    agent = AsyncMock()
    agent.execute = AsyncMock(return_value=AgentResult(agent_name="finalize", success=True, data={"status": "finalized"}))
    return agent


def _make_mock_context_agent():
    agent = AsyncMock()
    agent.execute = AsyncMock(return_value=AgentResult(agent_name="context", success=True, data={"system_prompt": "You are a writer.", "user_prompt": "Write.", "context_tokens": 50, "sections": {}}))
    return agent


def _make_mock_provider():
    from app.providers.base import ChatResponse
    provider = AsyncMock()
    responses = [
        json.dumps({"next_action": "write_chapter", "reasoning": "Chapter planned"}),
        json.dumps({"stage": "scene_cards", "content": {"scenes": []}}),
        "叶辰站在青云宗大门前。",
        json.dumps({"new_entities": [], "state_changes": {}, "summary": "叶辰到达"}),
        json.dumps({"extracted_entities": [], "truth_file_updates": {}}),
        json.dumps({"scores": {"consistency": 8}, "pass_rate": 1.0, "has_blocking": False, "issues": [], "recommendation": "pass"}),
    ]
    call_idx = {"n": 0}
    async def mock_chat(**kwargs):
        idx = call_idx["n"]
        call_idx["n"] += 1
        content = responses[idx] if idx < len(responses) else "{}"
        return ChatResponse(content=content, model="mock", usage={})
    provider.chat = mock_chat
    return provider


async def test_full_pipeline_pass():
    provider = _make_mock_provider()
    dag = PipelineDAG()
    dag.add_node(PipelineNode(name="radar", agent_name="radar"))
    dag.add_node(PipelineNode(name="architect", agent_name="architect"))
    dag.add_node(PipelineNode(name="context", agent_name="context"))
    dag.add_node(PipelineNode(name="writer", agent_name="writer"))
    dag.add_node(PipelineNode(name="settler", agent_name="settler"))
    dag.add_node(PipelineNode(name="auditor", agent_name="auditor"))
    dag.add_edge(PipelineEdge(from_node="radar", to_node="architect"))
    dag.add_edge(PipelineEdge(from_node="architect", to_node="context"))
    dag.add_edge(PipelineEdge(from_node="context", to_node="writer"))
    dag.add_edge(PipelineEdge(from_node="writer", to_node="settler"))
    dag.add_edge(PipelineEdge(from_node="settler", to_node="auditor"))
    agents = {}
    for name, cls in AGENT_CLASSES.items():
        if name == "context":
            agents[name] = _make_mock_context_agent()
        else:
            agents[name] = cls(provider=provider)
    executor = PipelineExecutor(dag, agents)
    results = await executor.run(AgentContext(project_id=uuid4(), chapter_id=uuid4()))
    assert len(results) == 6
    assert all(r.success for r in results), [f"{r.agent_name}: {r.error}" for r in results if not r.success]
    assert [r.agent_name for r in results] == ["radar", "architect", "context", "writer", "settler", "auditor"]


async def test_pipeline_agent_failure_stops():
    provider = AsyncMock()
    provider.chat = AsyncMock(side_effect=Exception("API error"))
    dag = PipelineDAG()
    dag.add_node(PipelineNode(name="radar", agent_name="radar"))
    dag.add_node(PipelineNode(name="writer", agent_name="writer"))
    dag.add_edge(PipelineEdge(from_node="radar", to_node="writer"))
    agents = {"radar": AGENT_CLASSES["radar"](provider=provider), "writer": AGENT_CLASSES["writer"](provider=provider)}
    for a in agents.values():
        a.max_retries = 1
    executor = PipelineExecutor(dag, agents)
    results = await executor.run(AgentContext(project_id=uuid4()))
    assert len(results) == 1
    assert results[0].success is False


async def test_pipeline_audit_revise_loop():
    from app.providers.base import ChatResponse
    call_count = {"n": 0}
    async def mock_chat(**kwargs):
        call_count["n"] += 1
        n = call_count["n"]
        if n <= 2:
            return ChatResponse(content=json.dumps({"next_action": "write", "stage": "test", "content": {}}), model="mock", usage={})
        if n == 3:
            return ChatResponse(content="Story text.", model="mock", usage={})
        if n == 4:
            return ChatResponse(content=json.dumps({"summary": "test"}), model="mock", usage={})
        if n == 5:
            return ChatResponse(content=json.dumps({"extracted_entities": [], "truth_file_updates": {}}), model="mock", usage={})
        if n == 6:
            return ChatResponse(content=json.dumps({"scores": {"quality": 4}, "pass_rate": 0.3, "has_blocking": False, "issues": [{"dimension": "quality", "message": "needs work", "severity": "error"}], "recommendation": "revise"}), model="mock", usage={})
        if n == 7:
            return ChatResponse(content="Revised text.", model="mock", usage={})
        return ChatResponse(content=json.dumps({"scores": {"quality": 8}, "pass_rate": 1.0, "has_blocking": False, "issues": [], "recommendation": "pass"}), model="mock", usage={})
    provider = AsyncMock()
    provider.chat = mock_chat
    dag = PipelineDAG.build_chapter_dag()
    agents = {}
    for name, cls in AGENT_CLASSES.items():
        if name == "context":
            agents[name] = _make_mock_context_agent()
        else:
            agent = cls(provider=provider)
            agent.max_retries = 1
            agents[name] = agent
    agents["finalize"] = _make_finalize_agent()
    executor = PipelineExecutor(dag, agents)
    results = await executor.run(AgentContext(project_id=uuid4(), chapter_id=uuid4()))
    names = [r.agent_name for r in results]
    assert "reviser" in names
    assert names.count("auditor") == 2
    assert names[-1] == "finalize"
