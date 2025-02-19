import pytest
import asyncio
from pathlib import Path
import sys
import json
import os
from unittest.mock import MagicMock, patch

from fastapi import HTTPException
from tool_agent_demo.api.executor import AsyncExecutor
from tool_agent_demo.core.result import Result, Ok, Err

# Set Jupyter platform dirs
os.environ["JUPYTER_PLATFORM_DIRS"] = "1"

# Test fixtures and helpers


def create_test_agent():
    """Create a test agent instance with tools and workflows"""
    class _TestAgent:
        def __init__(self):
            self._tools = {
                "test_tool": self.test_tool,
                "error_tool": self.error_tool
            }
            self._workflows = {
                "test_workflow": self.test_workflow,
                "error_workflow": self.error_workflow
            }

        def test_tool(self, arg1: str) -> Result[str]:
            return Ok(f"Tool result: {arg1}")

        def error_tool(self) -> Result[str]:
            return Err("Tool error")

        def test_workflow(self, arg1: str):
            yield f"Step 1: {arg1}"
            yield Ok(f"Workflow result: {arg1}")

        def error_workflow(self):
            yield "Step 1"
            yield Err("Workflow error")

    return _TestAgent()


@pytest.fixture
def executor():
    # Use current Python executable for testing
    executor = AsyncExecutor("env", str(Path(sys.executable).parent.parent))
    yield executor
    # Cleanup
    if executor.km:
        executor.km.shutdown_kernel(now=True)


@pytest.mark.asyncio
async def test_kernel_initialization(executor):
    """Test kernel initialization"""
    await executor._init_kernel()
    assert executor.initialized
    assert executor.km is not None
    assert executor.kc is not None


@pytest.mark.asyncio
async def test_kernel_cleanup(executor):
    """Test kernel cleanup"""
    await executor._init_kernel()
    assert executor.initialized

    await executor._cleanup()
    assert not executor.initialized
    assert executor.km is None
    assert executor.kc is None


@pytest.mark.asyncio
async def test_execute_tool_success(executor, tmp_path):
    """Test successful tool execution"""
    # Create test module file
    module_path = tmp_path / "test_module.py"
    with open(module_path, "w") as f:
        f.write("""
from tool_agent_demo.core.result import Result, Ok, Err

class TestAgent:
    def __init__(self):
        self._tools = {"test": self.test_tool}

    def test_tool(self, msg: str) -> Result[str]:
        return Ok(f"Success: {msg}")
""")

    result = await executor.execute(
        str(module_path.with_suffix("")),
        "TestAgent",
        "tools",
        "test",
        ["Hello"],
        {}
    )

    assert result == {"result": "Success: Hello"}


@pytest.mark.asyncio
async def test_execute_tool_error(executor, tmp_path):
    """Test tool execution with error"""
    # Create test module file
    module_path = tmp_path / "test_module.py"
    with open(module_path, "w") as f:
        f.write("""
from tool_agent_demo.core.result import Result, Ok, Err

class TestAgent:
    def __init__(self):
        self._tools = {"test": self.test_tool}

    def test_tool(self) -> Result[str]:
        return Err("Test error")
""")

    result = await executor.execute(
        str(module_path.with_suffix("")),
        "TestAgent",
        "tools",
        "test",
        [],
        {}
    )

    assert result == {"error": "Test error"}


@pytest.mark.asyncio
async def test_execute_workflow_success(executor, tmp_path):
    """Test successful workflow execution"""
    # Create test module file
    module_path = tmp_path / "test_module.py"
    with open(module_path, "w") as f:
        f.write("""
from tool_agent_demo.core.result import Result, Ok, Err

class TestAgent:
    def __init__(self):
        self._workflows = {"test": self.test_workflow}

    def test_workflow(self, msg: str):
        yield f"Step: {msg}"
        yield Ok(f"Success: {msg}")
""")

    result = await executor.execute(
        str(module_path.with_suffix("")),
        "TestAgent",
        "workflows",
        "test",
        ["Hello"],
        {}
    )

    assert result == {"result": "Success: Hello"}


@pytest.mark.asyncio
async def test_execute_workflow_error(executor, tmp_path):
    """Test workflow execution with error"""
    # Create test module file
    module_path = tmp_path / "test_module.py"
    with open(module_path, "w") as f:
        f.write("""
from tool_agent_demo.core.result import Result, Ok, Err

class TestAgent:
    def __init__(self):
        self._workflows = {"test": self.test_workflow}

    def test_workflow(self):
        yield "Step 1"
        yield Err("Test error")
""")

    result = await executor.execute(
        str(module_path.with_suffix("")),
        "TestAgent",
        "workflows",
        "test",
        [],
        {}
    )

    assert result == {"error": "Test error"}


@pytest.mark.asyncio
async def test_invalid_executor_type():
    """Test invalid executor type"""
    executor = AsyncExecutor("invalid", "/path")
    with pytest.raises(HTTPException) as exc_info:
        await executor.execute("module", "Agent", "tools", "test", [], {})
    assert "Unsupported executor type" in str(exc_info.value)


@pytest.mark.asyncio
async def test_kernel_initialization_failure():
    """Test kernel initialization failure"""
    executor = AsyncExecutor("env", "/invalid/path")
    with pytest.raises(HTTPException) as exc_info:
        await executor._init_kernel()
    assert "Python interpreter not found" in str(exc_info.value)


@pytest.mark.asyncio
async def test_workflow_step_by_step(executor, tmp_path):
    """Test step by step workflow execution"""
    # Create test module file
    module_path = tmp_path / "test_module.py"
    with open(module_path, "w") as f:
        f.write("""
from tool_agent_demo.core.result import Result, Ok, Err

class TestAgent:
    def __init__(self):
        self._workflows = {"test": self.test_workflow}

    def test_workflow(self, msg: str):
        yield f"Step 1: {msg}"
        yield f"Step 2: {msg}"
        yield Ok(f"Success: {msg}")
""")

    # First step
    result = await executor.execute(
        str(module_path.with_suffix("")),
        "TestAgent",
        "workflows",
        "test",
        ["Hello"],
        {},
        step_by_step=True
    )
    assert "Step 1: Hello" == result["result"]
    assert "kernel_id" in result
    kernel_id = result["kernel_id"]

    # Second step
    result = await executor.execute(
        str(module_path.with_suffix("")),
        "TestAgent",
        "workflows",
        "test",
        ["Hello"],
        {},
        step_by_step=True,
        kernel_id=kernel_id
    )
    assert "Step 2: Hello" == result["result"]
    assert result["kernel_id"] == kernel_id

    # Final step
    result = await executor.execute(
        str(module_path.with_suffix("")),
        "TestAgent",
        "workflows",
        "test",
        ["Hello"],
        {},
        step_by_step=True,
        kernel_id=kernel_id
    )
    assert "Success: Hello" == result["result"]
    assert result["kernel_id"] is None

    # Verify kernel was cleaned up
    assert kernel_id not in executor.active_kernels


@pytest.mark.asyncio
async def test_workflow_invalid_kernel_id(executor, tmp_path):
    """Test workflow execution with invalid kernel ID"""
    # Create test module file
    module_path = tmp_path / "test_module.py"
    with open(module_path, "w") as f:
        f.write("""
from tool_agent_demo.core.result import Result, Ok, Err

class TestAgent:
    def __init__(self):
        self._workflows = {"test": self.test_workflow}

    def test_workflow(self, msg: str):
        yield f"Step: {msg}"
        yield Ok(f"Success: {msg}")
""")

    with pytest.raises(HTTPException) as exc_info:
        await executor.execute(
            str(module_path.with_suffix("")),
            "TestAgent",
            "workflows",
            "test",
            ["Hello"],
            {},
            step_by_step=True,
            kernel_id="k99xyz"  # Non-existent kernel ID
        )
    assert "Kernel k99xyz not found" in str(exc_info.value)


@pytest.mark.asyncio
async def test_workflow_parameter_mismatch(executor, tmp_path):
    """Test workflow execution with mismatched parameters"""
    # Create test module file
    module_path = tmp_path / "test_module.py"
    with open(module_path, "w") as f:
        f.write("""
from tool_agent_demo.core.result import Result, Ok, Err

class TestAgent:
    def __init__(self):
        self._workflows = {"test": self.test_workflow}

    def test_workflow(self, msg: str):
        yield f"Step: {msg}"
        yield Ok(f"Success: {msg}")
""")

    # Start workflow
    result = await executor.execute(
        str(module_path.with_suffix("")),
        "TestAgent",
        "workflows",
        "test",
        ["Hello"],
        {},
        step_by_step=True
    )
    kernel_id = result["kernel_id"]

    # Try to continue with different parameters
    with pytest.raises(HTTPException) as exc_info:
        await executor.execute(
            str(module_path.with_suffix("")),
            "TestAgent",
            "workflows",
            "test",
            ["Different"],  # Different argument
            {},
            step_by_step=True,
            kernel_id=kernel_id
        )
    assert "Kernel parameters do not match" in str(exc_info.value)
