"""Tests for pipeline checkpoint and resume functionality."""
from unittest.mock import AsyncMock
from uuid import uuid4

from app.orchestration.executor import PipelineExecutor
from app.orchestration.pipeline import PipelineDAG, PipelineEdge, PipelineNode
from app.schemas.agent import AgentContext, AgentResult


def _make_simple_dag():
    dag = PipelineDAG()
    dag.add_node(PipelineNode(name="a", agent_name="agent_a"))
    dag.add_node(PipelineNode(name="b", agent_name="agent_b"))
    dag.add_node(PipelineNode(name="c", agent_name="agent_c"))
    dag.add_edge(PipelineEdge(from_node="a", to_node="b"))
    dag.add_edge(PipelineEdge(from_node="b", to_node="c"))
    return dag


def _make_success_result(name: str, data: dict = None):
    return AgentResult(
        agent_name=name, success=True, data=data or {"status": "ok"}, duration_ms=10
    )


def _make_agent_registry(results: dict[str, AgentResult]):
    registry = {}
    for agent_name, result in results.items():
        agent = AsyncMock()
        agent.execute = AsyncMock(return_value=result)
        registry[agent_name] = agent
    return registry


async def test_executor_saves_checkpoint():
    """Test that executor calls on_checkpoint callback after each successful node."""
    dag = _make_simple_dag()
    agents = _make_agent_registry(
        {
            "agent_a": _make_success_result("a", {"output": "from_a"}),
            "agent_b": _make_success_result("b", {"output": "from_b"}),
            "agent_c": _make_success_result("c", {"output": "from_c"}),
        }
    )

    checkpoints = []

    def on_checkpoint(checkpoint_data):
        checkpoints.append(dict(checkpoint_data))

    executor = PipelineExecutor(dag, agents, on_checkpoint=on_checkpoint)
    results = await executor.run(AgentContext(project_id=uuid4()))

    assert len(results) == 3
    assert all(r.success for r in results)

    # Should have 3 checkpoints (after a, b, c)
    assert len(checkpoints) == 3

    # First checkpoint: only node a completed
    assert "a" in checkpoints[0]
    assert checkpoints[0]["a"].success is True
    assert checkpoints[0]["a"].data == {"output": "from_a"}
    assert "b" not in checkpoints[0]
    assert "c" not in checkpoints[0]

    # Second checkpoint: nodes a and b completed
    assert "a" in checkpoints[1]
    assert "b" in checkpoints[1]
    assert checkpoints[1]["b"].success is True
    assert checkpoints[1]["b"].data == {"output": "from_b"}
    assert "c" not in checkpoints[1]

    # Third checkpoint: all nodes completed
    assert "a" in checkpoints[2]
    assert "b" in checkpoints[2]
    assert "c" in checkpoints[2]
    assert checkpoints[2]["c"].success is True
    assert checkpoints[2]["c"].data == {"output": "from_c"}


async def test_executor_resume_from_checkpoint():
    """Test that executor skips nodes in checkpoint and restores results."""
    dag = _make_simple_dag()

    # Create a checkpoint with nodes a and b already completed
    checkpoint = {
        "a": _make_success_result("a", {"output": "from_a"}),
        "b": _make_success_result("b", {"output": "from_b"}),
    }

    call_count = {"agent_a": 0, "agent_b": 0, "agent_c": 0}

    def make_tracking_agent(name):
        async def execute(ctx):
            call_count[name] += 1
            if name == "agent_a":
                return _make_success_result("a", {"output": "from_a"})
            elif name == "agent_b":
                return _make_success_result("b", {"output": "from_b"})
            else:
                return _make_success_result("c", {"output": "from_c"})

        agent = AsyncMock()
        agent.execute = execute
        return agent

    agents = {
        "agent_a": make_tracking_agent("agent_a"),
        "agent_b": make_tracking_agent("agent_b"),
        "agent_c": make_tracking_agent("agent_c"),
    }

    executor = PipelineExecutor(dag, agents, checkpoint=checkpoint)
    results = await executor.run(AgentContext(project_id=uuid4()))

    assert len(results) == 3
    assert all(r.success for r in results)

    # Verify agents a and b were NOT executed (skipped from checkpoint)
    assert call_count["agent_a"] == 0
    assert call_count["agent_b"] == 0
    # Only agent c should be executed
    assert call_count["agent_c"] == 1

    # Verify node_results contains all nodes (from checkpoint + fresh execution)
    assert "a" in executor.node_results
    assert "b" in executor.node_results
    assert "c" in executor.node_results
    assert executor.node_results["a"].data == {"output": "from_a"}
    assert executor.node_results["b"].data == {"output": "from_b"}
    assert executor.node_results["c"].data == {"output": "from_c"}


async def test_executor_checkpoint_on_failure():
    """Test that checkpoint saves completed nodes even when pipeline fails."""
    dag = _make_simple_dag()
    agents = _make_agent_registry(
        {
            "agent_a": _make_success_result("a", {"output": "from_a"}),
            "agent_b": AgentResult(
                agent_name="b", success=False, error="LLM failed", duration_ms=10
            ),
            "agent_c": _make_success_result("c", {"output": "from_c"}),
        }
    )

    checkpoints = []

    def on_checkpoint(checkpoint_data):
        checkpoints.append(dict(checkpoint_data))

    executor = PipelineExecutor(dag, agents, on_checkpoint=on_checkpoint)
    results = await executor.run(AgentContext(project_id=uuid4()))

    assert len(results) == 2
    assert results[0].success is True
    assert results[1].success is False

    # Should have 2 checkpoints: after successful node a, then after failed node b
    assert len(checkpoints) == 2

    # First checkpoint: only node a
    assert "a" in checkpoints[0]
    assert checkpoints[0]["a"].success is True
    assert "b" not in checkpoints[0]

    # Second checkpoint: nodes a and b (even though b failed)
    assert "a" in checkpoints[1]
    assert "b" in checkpoints[1]
    assert checkpoints[1]["b"].success is False
    assert checkpoints[1]["b"].error == "LLM failed"


async def test_executor_backward_compatible():
    """Test that PipelineExecutor(dag, agents) still works without checkpoint params."""
    dag = _make_simple_dag()
    agents = _make_agent_registry(
        {
            "agent_a": _make_success_result("a"),
            "agent_b": _make_success_result("b"),
            "agent_c": _make_success_result("c"),
        }
    )

    # Create executor WITHOUT checkpoint parameters (backward compatibility)
    executor = PipelineExecutor(dag, agents)
    results = await executor.run(AgentContext(project_id=uuid4()))

    assert len(results) == 3
    assert all(r.success for r in results)


async def test_executor_resume_partial_then_fail():
    """Test resuming from checkpoint but failing on a later node."""
    dag = _make_simple_dag()

    # Create a checkpoint with node a already completed
    checkpoint = {
        "a": _make_success_result("a", {"output": "from_a"}),
    }

    call_count = {"agent_b": 0, "agent_c": 0}

    def make_tracking_agent(name):
        async def execute(ctx):
            call_count[name] += 1
            if name == "agent_b":
                return AgentResult(
                    agent_name="b",
                    success=False,
                    error="B failed",
                    duration_ms=10,
                )
            else:
                return _make_success_result("c", {"output": "from_c"})

        agent = AsyncMock()
        agent.execute = execute
        return agent

    agents = {
        "agent_a": _make_agent_registry({"agent_a": _make_success_result("a")})["agent_a"],
        "agent_b": make_tracking_agent("agent_b"),
        "agent_c": make_tracking_agent("agent_c"),
    }

    checkpoints = []

    def on_checkpoint(checkpoint_data):
        checkpoints.append(dict(checkpoint_data))

    executor = PipelineExecutor(dag, agents, checkpoint=checkpoint, on_checkpoint=on_checkpoint)
    results = await executor.run(AgentContext(project_id=uuid4()))

    # Results: a (from checkpoint, success), b (executed and failed), c (not executed)
    assert len(results) == 2
    assert results[0].success is True
    assert results[0].agent_name == "a"
    assert results[1].success is False
    assert results[1].agent_name == "b"

    # Checkpoint called once after b fails
    assert len(checkpoints) == 1
    assert "a" in checkpoints[0]
    assert "b" in checkpoints[0]
    assert checkpoints[0]["b"].success is False
