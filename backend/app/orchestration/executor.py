"""Pipeline executor: runs agents through DAG with conditions and loops."""

from __future__ import annotations

from typing import Any, Callable, Protocol

from app.orchestration.pipeline import PipelineDAG
from app.schemas.agent import AgentContext, AgentResult


class AgentProtocol(Protocol):
    async def execute(self, context: AgentContext) -> AgentResult: ...


class PipelineExecutor:
    def __init__(
        self,
        dag: PipelineDAG,
        agents: dict[str, AgentProtocol],
        on_checkpoint: Callable[[dict[str, AgentResult]], None] | None = None,
        checkpoint: dict[str, AgentResult] | None = None,
    ):
        self.dag = dag
        self.agents = agents
        self.node_results: dict[str, AgentResult] = {}
        self._loop_counts: dict[str, int] = {}
        self.on_checkpoint = on_checkpoint
        self._checkpoint_data: dict[str, AgentResult] = {}

        # Restore from checkpoint if provided
        if checkpoint:
            self.node_results = dict(checkpoint)
            self._checkpoint_data = dict(checkpoint)

    async def run(self, context: AgentContext) -> list[AgentResult]:
        results: list[AgentResult] = []
        start_nodes = [
            name
            for name in self.dag.nodes
            if not self.dag.get_predecessors(name, include_loop_back=False)
        ]
        queue = list(start_nodes)
        visited: set[str] = set()

        while queue:
            node_name = queue.pop(0)

            # Skip nodes that are already in checkpoint (but only on first visit)
            if node_name in self._checkpoint_data and node_name not in visited:
                # Restore result from checkpoint and add to results
                result = self._checkpoint_data[node_name]
                results.append(result)
                visited.add(node_name)

                # If this node failed, stop execution
                if not result.success:
                    break

                # Continue to next nodes even if restored from checkpoint
                next_nodes = self.dag.get_next_nodes(node_name, result.data)
                queue.extend(next_nodes)
                continue

            if node_name in visited:
                node = self.dag.nodes[node_name]
                loop_count = self._loop_counts.get(node_name, 0)
                if loop_count >= node.max_loops:
                    continue
            else:
                visited.add(node_name)

            self._loop_counts[node_name] = self._loop_counts.get(node_name, 0) + 1
            node = self.dag.nodes[node_name]
            agent = self.agents.get(node.agent_name)
            if agent is None:
                result = AgentResult(
                    agent_name=node_name,
                    success=False,
                    error=f"Agent '{node.agent_name}' not found",
                )
                results.append(result)
                self.node_results[node_name] = result
                self._checkpoint_data[node_name] = result
                if self.on_checkpoint:
                    self.on_checkpoint(dict(self._checkpoint_data))
                break

            ctx = self._build_context(context, node_name)
            result = await agent.execute(ctx)
            results.append(result)
            self.node_results[node_name] = result
            self._checkpoint_data[node_name] = result

            # Save checkpoint after each node (success or failure)
            if self.on_checkpoint:
                self.on_checkpoint(dict(self._checkpoint_data))

            if not result.success:
                break

            next_nodes = self.dag.get_next_nodes(node_name, result.data)
            queue.extend(next_nodes)

        return results

    def _build_context(
        self, base_context: AgentContext, node_name: str
    ) -> AgentContext:
        pipeline_data = dict(base_context.pipeline_data)
        for prev_name, prev_result in self.node_results.items():
            if prev_result.success:
                pipeline_data[prev_name] = prev_result.data
        return AgentContext(
            project_id=base_context.project_id,
            chapter_id=base_context.chapter_id,
            volume_id=base_context.volume_id,
            pipeline_data=pipeline_data,
            params=self.dag.nodes[node_name].params,
        )
