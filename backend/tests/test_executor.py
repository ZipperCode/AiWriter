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


async def test_executor_linear_pipeline():
    dag = _make_simple_dag()
    agents = _make_agent_registry(
        {
            "agent_a": _make_success_result("a"),
            "agent_b": _make_success_result("b"),
            "agent_c": _make_success_result("c"),
        }
    )
    executor = PipelineExecutor(dag, agents)
    results = await executor.run(AgentContext(project_id=uuid4()))
    assert len(results) == 3
    assert all(r.success for r in results)
    assert [r.agent_name for r in results] == ["a", "b", "c"]


async def test_executor_stops_on_failure():
    dag = _make_simple_dag()
    agents = _make_agent_registry(
        {
            "agent_a": _make_success_result("a"),
            "agent_b": AgentResult(
                agent_name="b", success=False, error="LLM failed"
            ),
            "agent_c": _make_success_result("c"),
        }
    )
    executor = PipelineExecutor(dag, agents)
    results = await executor.run(AgentContext(project_id=uuid4()))
    assert len(results) == 2
    assert results[1].success is False


async def test_executor_conditional_branch():
    dag = PipelineDAG()
    dag.add_node(PipelineNode(name="auditor", agent_name="auditor"))
    dag.add_node(PipelineNode(name="reviser", agent_name="reviser"))
    dag.add_node(PipelineNode(name="done", agent_name="done"))
    dag.add_edge(
        PipelineEdge(
            from_node="auditor",
            to_node="done",
            condition=lambda r: r.get("recommendation") == "pass",
        )
    )
    dag.add_edge(
        PipelineEdge(
            from_node="auditor",
            to_node="reviser",
            condition=lambda r: r.get("recommendation") == "revise",
        )
    )
    agents = _make_agent_registry(
        {
            "auditor": _make_success_result("auditor", {"recommendation": "pass"}),
            "reviser": _make_success_result("reviser"),
            "done": _make_success_result("done"),
        }
    )
    executor = PipelineExecutor(dag, agents)
    results = await executor.run(AgentContext(project_id=uuid4()))
    names = [r.agent_name for r in results]
    assert "auditor" in names
    assert "done" in names
    assert "reviser" not in names


async def test_executor_loop():
    dag = PipelineDAG()
    dag.add_node(PipelineNode(name="auditor", agent_name="auditor", max_loops=3))
    dag.add_node(PipelineNode(name="reviser", agent_name="reviser"))
    dag.add_node(PipelineNode(name="done", agent_name="done"))
    dag.add_edge(
        PipelineEdge(
            from_node="auditor",
            to_node="reviser",
            condition=lambda r: r.get("recommendation") == "revise",
        )
    )
    dag.add_edge(
        PipelineEdge(
            from_node="auditor",
            to_node="done",
            condition=lambda r: r.get("recommendation") == "pass",
        )
    )
    dag.add_edge(
        PipelineEdge(from_node="reviser", to_node="auditor", is_loop_back=True)
    )
    call_count = {"auditor": 0}

    async def auditor_execute(ctx):
        call_count["auditor"] += 1
        if call_count["auditor"] == 1:
            return _make_success_result("auditor", {"recommendation": "revise"})
        return _make_success_result("auditor", {"recommendation": "pass"})

    auditor_mock = AsyncMock()
    auditor_mock.execute = auditor_execute
    agents = {
        "auditor": auditor_mock,
        "reviser": _make_agent_registry(
            {"reviser": _make_success_result("reviser")}
        )["reviser"],
        "done": _make_agent_registry({"done": _make_success_result("done")})["done"],
    }
    executor = PipelineExecutor(dag, agents)
    results = await executor.run(AgentContext(project_id=uuid4()))
    names = [r.agent_name for r in results]
    assert names == ["auditor", "reviser", "auditor", "done"]


async def test_executor_node_results_stored():
    dag = _make_simple_dag()
    agents = _make_agent_registry(
        {
            "agent_a": _make_success_result("a", {"key": "value"}),
            "agent_b": _make_success_result("b"),
            "agent_c": _make_success_result("c"),
        }
    )
    executor = PipelineExecutor(dag, agents)
    await executor.run(AgentContext(project_id=uuid4()))
    assert "a" in executor.node_results
    assert executor.node_results["a"].data["key"] == "value"
