"""Pipeline DAG: topological sort, conditional branching, loop-back edges."""

from __future__ import annotations

from collections import defaultdict, deque
from dataclasses import dataclass, field
from typing import Any, Callable


@dataclass
class PipelineNode:
    name: str
    agent_name: str
    params: dict[str, Any] = field(default_factory=dict)
    max_loops: int = 1


@dataclass
class PipelineEdge:
    from_node: str
    to_node: str
    condition: Callable[[dict], bool] | None = None
    is_loop_back: bool = False


class PipelineDAG:
    def __init__(self):
        self.nodes: dict[str, PipelineNode] = {}
        self.edges: list[PipelineEdge] = []
        self._adjacency: dict[str, list[PipelineEdge]] = defaultdict(list)

    def add_node(self, node: PipelineNode) -> None:
        self.nodes[node.name] = node

    def add_edge(self, edge: PipelineEdge) -> None:
        self.edges.append(edge)
        self._adjacency[edge.from_node].append(edge)

    def topological_sort(self) -> list[str]:
        forward_edges = [e for e in self.edges if not e.is_loop_back]
        in_degree: dict[str, int] = {name: 0 for name in self.nodes}
        adj: dict[str, list[str]] = defaultdict(list)
        for edge in forward_edges:
            if edge.to_node in in_degree:
                in_degree[edge.to_node] += 1
                adj[edge.from_node].append(edge.to_node)
        queue = deque(name for name, deg in in_degree.items() if deg == 0)
        result: list[str] = []
        while queue:
            node = queue.popleft()
            result.append(node)
            for next_node in adj.get(node, []):
                in_degree[next_node] -= 1
                if in_degree[next_node] == 0:
                    queue.append(next_node)
        if len(result) != len(self.nodes):
            raise ValueError("Pipeline DAG contains a cycle (excluding loop-back edges)")
        return result

    def get_next_nodes(self, current_node: str, result_data: dict[str, Any]) -> list[str]:
        next_nodes = []
        for edge in self._adjacency.get(current_node, []):
            if edge.condition is None or edge.condition(result_data):
                next_nodes.append(edge.to_node)
        return next_nodes

    def get_predecessors(
        self, node_name: str, include_loop_back: bool = True
    ) -> list[str]:
        return [
            edge.from_node
            for edge in self.edges
            if edge.to_node == node_name
            and (include_loop_back or not edge.is_loop_back)
        ]

    @classmethod
    def build_chapter_dag(cls) -> PipelineDAG:
        dag = cls()
        dag.add_node(PipelineNode(name="radar", agent_name="radar"))
        dag.add_node(PipelineNode(name="architect", agent_name="architect"))
        dag.add_node(PipelineNode(name="context", agent_name="context"))
        dag.add_node(PipelineNode(name="writer", agent_name="writer"))
        dag.add_node(PipelineNode(name="settler", agent_name="settler"))
        dag.add_node(PipelineNode(name="auditor", agent_name="auditor", max_loops=3))
        dag.add_node(PipelineNode(name="reviser", agent_name="reviser"))
        dag.add_node(
            PipelineNode(name="finalize", agent_name="finalize", params={"action": "finalize"})
        )
        dag.add_edge(PipelineEdge(from_node="radar", to_node="architect"))
        dag.add_edge(PipelineEdge(from_node="architect", to_node="context"))
        dag.add_edge(PipelineEdge(from_node="context", to_node="writer"))
        dag.add_edge(PipelineEdge(from_node="writer", to_node="settler"))
        dag.add_edge(PipelineEdge(from_node="settler", to_node="auditor"))
        dag.add_edge(
            PipelineEdge(
                from_node="auditor",
                to_node="finalize",
                condition=lambda r: r.get("recommendation") == "pass",
            )
        )
        dag.add_edge(
            PipelineEdge(
                from_node="auditor",
                to_node="reviser",
                condition=lambda r: r.get("recommendation") in ("revise", "rework"),
            )
        )
        dag.add_edge(
            PipelineEdge(from_node="reviser", to_node="auditor", is_loop_back=True)
        )
        return dag
