import pytest
from tool_agent_demo import Agent, DeserializationError
from tool_agent_demo.serializers.workflow_serializer import Node, Edge, Port, WorkflowGraph, WorkflowSerializer


@pytest.mark.no_collect
class TestAgent(Agent):  # This is a helper class, not a test class
    @Agent.tool
    def tool1(self, input1: str) -> str:
        return f"processed_{input1}"

    @Agent.tool
    def tool2(self, input1: str, input2: str) -> str:
        return f"combined_{input1}_{input2}"

    @Agent.workflow
    def test_workflow(self):
        result1 = self.tool1("data1")
        result2 = self.tool1("data2")
        final = self.tool2(result1, result2)
        return final


def test_workflow_serialization():
    agent = TestAgent()

    # Get workflow graph
    graph = agent.get_workflow_graph("test_workflow")
    assert graph is not None

    # Verify nodes
    assert len(graph.nodes) == 3  # 3 function calls

    # Find nodes by type
    tool1_nodes = [n for n in graph.nodes if n.type == "tool1"]
    tool2_nodes = [n for n in graph.nodes if n.type == "tool2"]
    assert len(tool1_nodes) == 2  # Two tool1 calls
    assert len(tool2_nodes) == 1  # One tool2 call

    # Verify first tool1 node
    node1 = tool1_nodes[0]
    assert len(node1.inputs) == 1  # One input
    assert len(node1.outputs) == 1  # One output
    assert node1.outputs[0].name == "result1"

    # Verify second tool1 node
    node2 = tool1_nodes[1]
    assert len(node2.inputs) == 1
    assert len(node2.outputs) == 1
    assert node2.outputs[0].name == "result2"

    # Verify tool2 node
    node3 = tool2_nodes[0]
    assert len(node3.inputs) == 2  # Two inputs
    assert len(node3.outputs) == 1  # One output
    assert node3.outputs[0].name == "final"

    # Verify edges
    assert len(graph.edges) == 2  # result1->tool2, result2->tool2

    # Verify edge connections
    edge_targets = {e.target.split(":")[0] for e in graph.edges}
    tool2_id = tool2_nodes[0].id
    assert tool2_id in edge_targets  # Both edges should connect to tool2


def test_workflow_deserialization():
    agent = TestAgent()

    # Create a simple workflow graph
    nodes = [
        Node(
            id="node_0",
            type="tool1",
            inputs=[Port(id="node_0:input:0",
                         name='"test_input"', type="str")],
            outputs=[Port(id="node_0:output:0", name="result1", type="str")],
            position={"x": 100, "y": 100}
        ),
        Node(
            id="node_1",
            type="tool2",
            inputs=[
                Port(id="node_1:input:0", name="result1", type="str"),
                Port(id="node_1:input:1", name='"test_input2"', type="str")
            ],
            outputs=[Port(id="node_1:output:0", name="final", type="str")],
            position={"x": 300, "y": 100}
        )
    ]
    edges = [
        Edge(
            id="edge_0",
            source="node_0:output:0",
            target="node_1:input:0"
        )
    ]
    graph = WorkflowGraph(nodes=nodes, edges=edges)

    # Update workflow
    agent.update_workflow_from_graph("test_workflow", graph)

    # Verify the workflow was updated
    new_graph = agent.get_workflow_graph("test_workflow")
    assert new_graph is not None

    # Verify the structure matches
    assert len(new_graph.nodes) == 2
    assert len(new_graph.edges) == 1

    # Execute workflow to verify it works
    workflow = agent._workflows["test_workflow"]
    results = list(workflow())
    assert len(results) == 2  # Two tool calls
    assert results[-1].unwrap().startswith("combined_processed_")


def test_workflow_with_unknown_tool():
    agent = TestAgent()

    # Create a workflow graph with unknown tool
    nodes = [
        Node(
            id="node_0",
            type="unknown_tool",  # 不存在的工具
            inputs=[Port(id="node_0:input:0",
                         name='"test_input"', type="str")],
            outputs=[Port(id="node_0:output:0", name="result1", type="str")],
            position={"x": 100, "y": 100}
        )
    ]
    edges = []
    graph = WorkflowGraph(nodes=nodes, edges=edges)

    # Verify that update fails with DeserializationError
    with pytest.raises(DeserializationError, match="The following tools are not available: unknown_tool"):
        agent.update_workflow_from_graph("test_workflow", graph)


def test_workflow_not_found():
    agent = TestAgent()
    with pytest.raises(ValueError, match="Workflow nonexistent not found"):
        agent.update_workflow_from_graph(
            "nonexistent", WorkflowGraph(nodes=[], edges=[]))


def test_get_nonexistent_workflow():
    agent = TestAgent()
    assert agent.get_workflow_graph("nonexistent") is None


def test_workflow_json_serialization():
    # Create a test workflow graph
    nodes = [
        Node(
            id="node_0",
            type="tool1",
            inputs=[Port(id="node_0:input:0",
                         name='"test_input"', type="str")],
            outputs=[Port(id="node_0:output:0", name="result1", type="str")],
            position={"x": 100, "y": 100}
        )
    ]
    edges = []
    original_graph = WorkflowGraph(nodes=nodes, edges=edges)

    # Convert to JSON
    json_str = WorkflowSerializer.to_json(original_graph)
    assert isinstance(json_str, str)
    assert "node_0" in json_str
    assert "tool1" in json_str

    # Convert back from JSON
    restored_graph = WorkflowSerializer.from_json(json_str)
    assert isinstance(restored_graph, WorkflowGraph)

    # Verify structure is preserved
    assert len(restored_graph.nodes) == len(original_graph.nodes)
    assert len(restored_graph.edges) == len(original_graph.edges)

    # Verify node details
    original_node = original_graph.nodes[0]
    restored_node = restored_graph.nodes[0]
    assert restored_node.id == original_node.id
    assert restored_node.type == original_node.type
    assert len(restored_node.inputs) == len(original_node.inputs)
    assert len(restored_node.outputs) == len(original_node.outputs)
    assert restored_node.position == original_node.position


def test_workflow_json_invalid():
    # Test with invalid JSON
    with pytest.raises(ValueError):
        WorkflowSerializer.from_json("invalid json")

    # Test with valid JSON but wrong structure
    with pytest.raises(ValueError):
        WorkflowSerializer.from_json('{"invalid": "structure"}')
