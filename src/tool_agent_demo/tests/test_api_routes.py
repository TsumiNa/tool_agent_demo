import pytest
from fastapi.testclient import TestClient
from pathlib import Path
import sys
import os

from tool_agent_demo.api.routes import app
from tool_agent_demo.api.executor import executors, AsyncExecutor
from tool_agent_demo.core.db import list_executors, get_executor

# Set Jupyter platform dirs
os.environ["JUPYTER_PLATFORM_DIRS"] = "1"

# Test client
client = TestClient(app)

# Mock executor for testing


class MockExecutor:
    def __init__(self, id="test-agent"):
        self.id = id
        self.executor_type = "env"
        self.executor_path = str(Path(sys.executable).parent.parent)
        self.entrypoint_path = "test_module"
        self.variable_name = "TestAgent"
        self.agent_info = {
            "tools": [{"name": "test_tool"}],
            "workflows": [{"name": "test_workflow"}]
        }


@pytest.fixture
def mock_executor(monkeypatch):
    """Setup mock executor"""
    executor = MockExecutor()

    def mock_get_executor(id):
        return executor if id == "test-agent" else None

    def mock_list_executors():
        return [executor]

    monkeypatch.setattr(
        "tool_agent_demo.api.routes.get_executor", mock_get_executor)
    monkeypatch.setattr(
        "tool_agent_demo.api.routes.list_executors", mock_list_executors)

    return executor


@pytest.fixture
def setup_test_files(tmp_path):
    """Create test module file"""
    module_path = tmp_path / "test_module.py"
    with open(module_path, "w") as f:
        f.write("""
from tool_agent_demo.core.result import Result, Ok, Err

class TestAgent:
    def __init__(self):
        self._tools = {"test_tool": self.test_tool}
        self._workflows = {"test_workflow": self.test_workflow}
        
    def test_tool(self, msg: str) -> Result[str]:
        return Ok(f"Success: {msg}")
        
    def test_workflow(self, msg: str):
        yield f"Step 1: {msg}"
        yield f"Step 2: {msg}"
        yield Ok(f"Success: {msg}")
""")
    return str(module_path.with_suffix(""))


@pytest.mark.asyncio
async def test_list_agents(mock_executor):
    """Test GET /agents endpoint"""
    response = client.get("/agents")
    assert response.status_code == 200
    agents = response.json()
    assert len(agents) == 1
    assert agents[0]["id"] == "test-agent"


@pytest.mark.asyncio
async def test_workflow_execution(mock_executor, setup_test_files, monkeypatch):
    """Test workflow execution with kernel"""
    # Setup AsyncExecutor with test files
    executor = AsyncExecutor("env", str(Path(sys.executable).parent.parent))

    async def mock_execute(*args, **kwargs):
        if "kernel_id" not in kwargs or not kwargs["kernel_id"]:
            # Store kernel info when starting workflow
            executor.active_kernels["test-kernel"] = (
                setup_test_files,
                "TestAgent",
                "test_workflow",
                ["Hello"],
                {}
            )
            return {"result": "Step 1: Hello", "kernel_id": "test-kernel"}
        elif kwargs["kernel_id"] == "test-kernel":
            # Clean up kernel info when workflow completes
            del executor.active_kernels["test-kernel"]
            return {"result": "Success: Hello", "kernel_id": None}
        return {"error": "Invalid kernel"}

    executor.execute = mock_execute
    executors["test-agent"] = executor

    # Start workflow
    response = client.post(
        "/agents/test-agent/workflows/test_workflow",
        json={"args": ["Hello"], "kwargs": {}}
    )
    assert response.status_code == 200
    result = response.json()
    assert result["result"] == "Step 1: Hello"
    assert result["kernel_id"] == "test-kernel"

    # Continue execution
    response = client.post(f"/agents/kernel/test-kernel/next")
    assert response.status_code == 200
    result = response.json()
    assert result["result"] == "Success: Hello"
    assert result["kernel_id"] is None


@pytest.mark.asyncio
async def test_workflow_cancel(mock_executor, setup_test_files, monkeypatch):
    """Test workflow cancellation"""
    # Setup AsyncExecutor with test files
    executor = AsyncExecutor("env", str(Path(sys.executable).parent.parent))
    executor.active_kernels["test-kernel"] = (
        "test_module", "TestAgent", "test_workflow", ["Hello"], {}
    )
    executors["test-agent"] = executor

    # Cancel workflow
    response = client.post(f"/agents/kernel/test-kernel/cancel")
    assert response.status_code == 200
    result = response.json()
    assert "cancelled successfully" in result["message"]
    assert "test-kernel" not in executor.active_kernels


@pytest.mark.asyncio
async def test_invalid_kernel_operations():
    """Test operations with invalid kernel ID"""
    # Test next with invalid kernel
    response = client.post("/agents/kernel/invalid-kernel/next")
    assert response.status_code == 404
    assert "not found" in response.json()["detail"]

    # Test cancel with invalid kernel
    response = client.post("/agents/kernel/invalid-kernel/cancel")
    assert response.status_code == 404
    assert "not found" in response.json()["detail"]
