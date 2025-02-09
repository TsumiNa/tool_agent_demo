"""
Test suite for the Agent class, focusing on tools, workflows, and Result handling.

This module contains tests for:
1. Tool and workflow collection during agent initialization
2. Workflow transformation and yield behavior
3. Tool execution (success and error cases)
4. Result combination using the | operator
5. Result handling when used as tool arguments
"""

from tool_agent_demo import Result
from tool_agent_demo.tests.test_helpers import TestAgent


def test_method_collection():
    """
    Test that decorated methods are properly collected during agent initialization.

    Verifies:
    - Tools are collected in _tools dictionary
    - Workflows are collected in _workflows dictionary
    - Collected methods are callable
    """
    agent = TestAgent()

    # Test tool collection
    assert "success_tool" in agent._tools
    assert "error_tool" in agent._tools
    assert callable(agent._tools["success_tool"])
    assert callable(agent._tools["error_tool"])

    # Test workflow collection
    assert "example_workflow" in agent._workflows
    assert callable(agent._workflows["example_workflow"])
    assert agent.example_workflow() == "workflow"


def test_tool_only_workflow():
    """
    Test workflow transformation with only tool function calls.

    Verifies:
    - Each tool call is yielded
    - Results are yielded in correct order
    - Result values are correct
    - Combined tool calls are handled properly
    """
    agent = TestAgent()
    workflow = agent.tool_only_workflow()
    steps = list(workflow)

    # Should yield after each tool call
    # 1. success_tool
    # 2. concat_tool(success_tool result, "test")
    # 3. success_tool | success_tool
    # 4. concat_tool(previous result, combined result)
    assert len(steps) == 4

    # First yield: success_tool result
    assert isinstance(steps[0], Result)
    assert steps[0].value == "success"

    # Second yield: concat_tool result
    assert isinstance(steps[1], Result)
    assert steps[1].value == "success-test"

    # Third yield: combined success_tool results
    assert isinstance(steps[2], Result)
    assert steps[2].unwrap() == ("success", "success")

    # Fourth yield: final concat_tool result
    assert isinstance(steps[3], Result)
    assert steps[3].value == "success-test-success"


def test_mixed_workflow():
    """
    Test workflow transformation with both tool and non-tool function calls.

    Verifies:
    - Only tool calls are yielded
    - Non-tool calls are executed without yielding
    - Results are yielded in correct order
    - Result values include non-tool function modifications
    """
    agent = TestAgent()
    workflow = agent.mixed_workflow()
    steps = list(workflow)

    # Should yield after each tool call (not after normal_function)
    # 1. success_tool
    # 2. concat_tool(success_tool result, "test")
    # 3. success_tool | success_tool
    # 4. concat_tool(previous result, combined result)
    assert len(steps) == 4

    # First yield: success_tool result
    assert isinstance(steps[0], Result)
    assert steps[0].value == "success"

    # Second yield: concat_tool result
    assert isinstance(steps[1], Result)
    assert steps[1].value == "success-test"

    # Third yield: combined success_tool results (after normal_function)
    assert isinstance(steps[2], Result)
    assert steps[2].unwrap() == ("success", "success")

    # Fourth yield: final concat_tool result (includes normal_function modification)
    assert isinstance(steps[3], Result)
    assert steps[3].value == "normal-success-test-success"


def test_tool_execution():
    """
    Test tool execution in both success and error scenarios.

    Verifies:
    - Successful tool calls return ok Result
    - Error tool calls return err Result
    - Result status checks work correctly
    - Error information is preserved
    """
    agent = TestAgent()

    # Test successful execution
    success_result = agent.success_tool()
    assert isinstance(success_result, Result)
    assert success_result.is_ok()
    assert not success_result.is_err()
    assert success_result.value == "success"
    assert success_result.unwrap() == "success"

    # Test error execution
    error_result = agent.error_tool()
    assert isinstance(error_result, Result)
    assert error_result.is_err()
    assert not error_result.is_ok()
    assert isinstance(error_result.error, ValueError)
    assert str(error_result.error) == "test error"


def test_result_combination():
    """
    Test Result combination using the | operator.

    Verifies:
    - Combining successful results
    - Combining success with error
    - Combining multiple errors
    - Error collection in combined results
    """
    agent = TestAgent()

    # Test combining two successful results
    combined_success = agent.success_tool() | (agent.success_tool())
    assert combined_success.is_ok()
    assert combined_success.unwrap() == ("success", "success")

    # Test combining success with error
    combined_error = agent.success_tool() | (agent.error_tool())
    assert combined_error.is_err()
    assert len(combined_error.combined_errors) == 1  # type: ignore
    assert isinstance(
        combined_error.combined_errors[0], ValueError)  # type: ignore

    # Test combining multiple errors
    combined_errors = agent.error_tool() | (agent.error_tool())
    assert combined_errors.is_err()
    assert len(combined_errors.combined_errors) == 2  # type: ignore
    assert all(isinstance(e, ValueError)
               for e in combined_errors.combined_errors)  # type: ignore


def test_result_as_argument():
    """
    Test using Result objects as arguments to tool calls.

    Verifies:
    - Passing error Result propagates the error
    - Passing success Result unwraps the value
    - Mixing Result and normal arguments works
    """
    agent = TestAgent()
    success_input = agent.success_tool()
    error_input = agent.error_tool()

    # Test passing error Result
    result_with_error_input = agent.concat_tool(error_input, "test")
    assert result_with_error_input.is_err()
    assert isinstance(result_with_error_input.error, ValueError)

    # Test passing success Result
    result_with_success_input = agent.concat_tool(success_input, "test")
    assert result_with_success_input.is_ok()
    assert result_with_success_input.value == "success-test"

    # Test mixing Result and normal input
    mixed_result = agent.concat_tool("test", success_input)
    assert mixed_result.is_ok()
    assert mixed_result.value == "test-success"


def test_to_json():
    """
    Test the to_json method for serializing Agent's tools and workflows.

    Verifies:
    - JSON string output format
    - File saving functionality
    - Tools information (description, parameters)
    - Workflows information (source code, graph)
    """
    import json
    import tempfile
    import os

    agent = TestAgent()

    # Test direct JSON string output
    json_str = agent.to_json()
    data = json.loads(json_str)

    # Verify tools information
    assert "tools" in data
    assert "success_tool" in data["tools"]
    assert "error_tool" in data["tools"]
    assert "concat_tool" in data["tools"]

    # Verify tool details
    concat_tool = data["tools"]["concat_tool"]
    assert "description" in concat_tool
    assert "parameters" in concat_tool
    assert "a" in concat_tool["parameters"]
    assert "b" in concat_tool["parameters"]
    assert concat_tool["parameters"]["a"] == "str"
    assert concat_tool["parameters"]["b"] == "str"

    # Verify workflows information
    assert "workflows" in data
    assert "tool_only_workflow" in data["workflows"]
    assert "mixed_workflow" in data["workflows"]

    # Verify workflow details
    tool_only_workflow = data["workflows"]["tool_only_workflow"]
    assert "source" in tool_only_workflow
    assert "graph" in tool_only_workflow
    assert "nodes" in tool_only_workflow["graph"]
    assert "edges" in tool_only_workflow["graph"]

    # Test file saving functionality
    with tempfile.NamedTemporaryFile(delete=False, suffix='.json') as tmp:
        # Save to temporary file
        agent.to_json(file_path=tmp.name)

        # Read and verify file content
        with open(tmp.name) as f:
            file_data = json.load(f)
            assert file_data == data

        # Clean up
        os.unlink(tmp.name)
