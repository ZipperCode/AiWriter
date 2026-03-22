"""End-to-end pipeline integration tests."""

import pytest
from uuid import uuid4
from unittest.mock import AsyncMock

from app.orchestration.pipeline import PipelineDAG, PipelineEdge, PipelineNode
from app.orchestration.executor import PipelineExecutor
from app.orchestration.human_loop import HumanLoopPoint
from app.schemas.agent import AgentContext, AgentResult


class MockAgent:
    """Configurable mock agent."""

    def __init__(self, name: str, output: dict | None = None, fail: bool = False):
        self.name = name
        self._output = output or {"result": f"{name}-output"}
        self._fail = fail
        self.executed = False

    async def execute(self, context: AgentContext) -> AgentResult:
        self.executed = True
        if self._fail:
            return AgentResult(agent_name=self.name, success=False, error="mock failure")
        return AgentResult(agent_name=self.name, success=True, data=self._output)


def _build_full_pipeline():
    """Build a simplified version of the writing pipeline DAG."""
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
    return dag


@pytest.mark.asyncio
async def test_e2e_pipeline_full_success():
    """Full pipeline should execute all agents in order."""
    dag = _build_full_pipeline()
    agents = {
        "radar": MockAgent("radar"),
        "architect": MockAgent("architect"),
        "context": MockAgent("context"),
        "writer": MockAgent("writer"),
        "settler": MockAgent("settler"),
        "auditor": MockAgent("auditor", output={"audit_passed": True, "score": 0.9}),
    }
    checkpoints = []

    def on_checkpoint(data):
        checkpoints.append(dict(data))

    executor = PipelineExecutor(dag, agents, on_checkpoint=on_checkpoint)
    ctx = AgentContext(project_id=str(uuid4()), chapter_id=str(uuid4()))
    results = await executor.run(ctx)

    assert len(results) == 6
    assert all(r.success for r in results)
    assert len(checkpoints) == 6
    for agent_name in ["radar", "architect", "context", "writer", "settler", "auditor"]:
        assert agents[agent_name].executed


@pytest.mark.asyncio
async def test_e2e_pipeline_failure_mid_run():
    """Pipeline should stop at failure and save checkpoint."""
    dag = _build_full_pipeline()
    agents = {
        "radar": MockAgent("radar"),
        "architect": MockAgent("architect"),
        "context": MockAgent("context", fail=True),
        "writer": MockAgent("writer"),
        "settler": MockAgent("settler"),
        "auditor": MockAgent("auditor"),
    }
    checkpoints = []

    def on_checkpoint(data):
        checkpoints.append(dict(data))

    executor = PipelineExecutor(dag, agents, on_checkpoint=on_checkpoint)
    results = await executor.run(AgentContext(project_id=str(uuid4())))

    assert not all(r.success for r in results)
    assert agents["writer"].executed is False
    # Checkpoint should contain completed nodes
    assert "radar" in checkpoints[-1]
    assert "architect" in checkpoints[-1]


@pytest.mark.asyncio
async def test_e2e_pipeline_resume_after_failure():
    """Pipeline should resume from checkpoint, skipping completed nodes."""
    dag = _build_full_pipeline()

    # First run: context fails
    agents_run1 = {
        "radar": MockAgent("radar"),
        "architect": MockAgent("architect"),
        "context": MockAgent("context", fail=True),
        "writer": MockAgent("writer"),
        "settler": MockAgent("settler"),
        "auditor": MockAgent("auditor"),
    }
    checkpoints = []

    def on_checkpoint(data):
        checkpoints.clear()
        checkpoints.append(dict(data))

    executor1 = PipelineExecutor(dag, agents_run1, on_checkpoint=on_checkpoint)
    await executor1.run(AgentContext(project_id=str(uuid4())))

    # Extract checkpoint (only successful nodes)
    checkpoint = {}
    for name, result in checkpoints[-1].items():
        if result.success:
            checkpoint[name] = result

    # Second run: resume with fixed context agent
    agents_run2 = {
        "radar": MockAgent("radar"),
        "architect": MockAgent("architect"),
        "context": MockAgent("context"),  # Fixed
        "writer": MockAgent("writer"),
        "settler": MockAgent("settler"),
        "auditor": MockAgent("auditor"),
    }
    executor2 = PipelineExecutor(dag, agents_run2, checkpoint=checkpoint)
    results = await executor2.run(AgentContext(project_id=str(uuid4())))

    # radar and architect should NOT be re-executed
    assert agents_run2["radar"].executed is False
    assert agents_run2["architect"].executed is False
    # context, writer, settler, auditor should be executed
    assert agents_run2["context"].executed is True
    assert agents_run2["writer"].executed is True


@pytest.mark.asyncio
async def test_e2e_pipeline_with_checkpoint_callback():
    """Checkpoint callback should receive accumulated node results."""
    dag = PipelineDAG()
    dag.add_node(PipelineNode(name="a", agent_name="a"))
    dag.add_node(PipelineNode(name="b", agent_name="b"))
    dag.add_edge(PipelineEdge(from_node="a", to_node="b"))

    agents = {"a": MockAgent("a"), "b": MockAgent("b")}
    all_checkpoints = []

    def on_checkpoint(data):
        all_checkpoints.append(dict(data))

    executor = PipelineExecutor(dag, agents, on_checkpoint=on_checkpoint)
    await executor.run(AgentContext(project_id=str(uuid4())))

    # First checkpoint: only "a"
    assert "a" in all_checkpoints[0]
    assert "b" not in all_checkpoints[0]
    # Second checkpoint: "a" and "b"
    assert "a" in all_checkpoints[1]
    assert "b" in all_checkpoints[1]
