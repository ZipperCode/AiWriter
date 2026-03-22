import pytest

from app.orchestration.pipeline import PipelineDAG, PipelineEdge, PipelineNode


def test_create_pipeline():
    dag = PipelineDAG()
    dag.add_node(PipelineNode(name="radar", agent_name="radar"))
    dag.add_node(PipelineNode(name="architect", agent_name="architect"))
    dag.add_edge(PipelineEdge(from_node="radar", to_node="architect"))
    assert len(dag.nodes) == 2
    assert len(dag.edges) == 1


def test_topological_sort():
    dag = PipelineDAG()
    dag.add_node(PipelineNode(name="a", agent_name="radar"))
    dag.add_node(PipelineNode(name="b", agent_name="architect"))
    dag.add_node(PipelineNode(name="c", agent_name="writer"))
    dag.add_edge(PipelineEdge(from_node="a", to_node="b"))
    dag.add_edge(PipelineEdge(from_node="b", to_node="c"))
    order = dag.topological_sort()
    assert order == ["a", "b", "c"]


def test_topological_sort_parallel():
    dag = PipelineDAG()
    dag.add_node(PipelineNode(name="start", agent_name="radar"))
    dag.add_node(PipelineNode(name="branch_a", agent_name="context"))
    dag.add_node(PipelineNode(name="branch_b", agent_name="context"))
    dag.add_node(PipelineNode(name="end", agent_name="writer"))
    dag.add_edge(PipelineEdge(from_node="start", to_node="branch_a"))
    dag.add_edge(PipelineEdge(from_node="start", to_node="branch_b"))
    dag.add_edge(PipelineEdge(from_node="branch_a", to_node="end"))
    dag.add_edge(PipelineEdge(from_node="branch_b", to_node="end"))
    order = dag.topological_sort()
    assert order[0] == "start"
    assert order[-1] == "end"
    assert set(order[1:3]) == {"branch_a", "branch_b"}


def test_topological_sort_cycle_detection():
    dag = PipelineDAG()
    dag.add_node(PipelineNode(name="a", agent_name="radar"))
    dag.add_node(PipelineNode(name="b", agent_name="architect"))
    dag.add_edge(PipelineEdge(from_node="a", to_node="b"))
    dag.add_edge(PipelineEdge(from_node="b", to_node="a"))
    with pytest.raises(ValueError, match="cycle"):
        dag.topological_sort()


def test_loop_back_edge_excluded_from_topo_sort():
    dag = PipelineDAG()
    dag.add_node(PipelineNode(name="auditor", agent_name="auditor"))
    dag.add_node(PipelineNode(name="reviser", agent_name="reviser"))
    dag.add_edge(PipelineEdge(from_node="auditor", to_node="reviser"))
    dag.add_edge(
        PipelineEdge(from_node="reviser", to_node="auditor", is_loop_back=True)
    )
    order = dag.topological_sort()
    assert "auditor" in order
    assert "reviser" in order


def test_conditional_edge():
    edge = PipelineEdge(
        from_node="auditor",
        to_node="reviser",
        condition=lambda result: result.get("recommendation") == "revise",
    )
    assert edge.condition({"recommendation": "revise"}) is True
    assert edge.condition({"recommendation": "pass"}) is False


def test_get_next_nodes():
    dag = PipelineDAG()
    dag.add_node(PipelineNode(name="auditor", agent_name="auditor"))
    dag.add_node(PipelineNode(name="reviser", agent_name="reviser"))
    dag.add_node(PipelineNode(name="done", agent_name="radar"))
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
    assert dag.get_next_nodes("auditor", {"recommendation": "revise"}) == ["reviser"]
    assert dag.get_next_nodes("auditor", {"recommendation": "pass"}) == ["done"]


def test_build_chapter_dag():
    dag = PipelineDAG.build_chapter_dag()
    order = dag.topological_sort()
    assert order[0] == "radar"
    assert "writer" in order
    assert "settler" in order
    assert "auditor" in order
    assert "finalize" in order
