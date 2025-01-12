from typing import List, Dict, Any, Optional
import importlib.util
import sys
import json
import asyncio
from pathlib import Path

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel

from tool_agent_demo.db import list_executors, init_db, get_executor
from tool_agent_demo.result import Result

# Initialize database
init_db()


class AgentInfo(BaseModel):
    id: str
    executor_type: str
    executor_path: str
    entrypoint_path: str
    variable_name: str
    agent_info: dict


class ToolRequest(BaseModel):
    args: List[Any] = []
    kwargs: Dict[str, Any] = {}


class WorkflowRequest(BaseModel):
    args: List[Any] = []
    kwargs: Dict[str, Any] = {}


class AsyncExecutor:
    """Async wrapper for executing agent methods"""

    def __init__(self, executor_type: str, executor_path: str):
        self.executor_type = executor_type
        self.executor_path = executor_path

    async def execute(self, module_path: str, var_name: str, method_type: str,
                      method_name: str, args: List[Any], kwargs: Dict[str, Any]) -> Any:
        """Execute a method asynchronously using the registered executor"""
        if self.executor_type == "env":
            python_path = str(Path(self.executor_path) / "bin" / "python")

            # Create execution script
            script = f"""
import json
import sys
import importlib.util
from pathlib import Path

# Import module
module_path = Path('{module_path}.py')
spec = importlib.util.spec_from_file_location(
    module_path.stem, str(module_path))
if not spec or not spec.loader:
    sys.exit(1)

module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)

# Get agent class and create instance
agent_class = getattr(module, '{var_name}')
agent = agent_class()

# Get method
method = getattr(agent, '_{method_type}')['{method_name}']

# Execute
try:
    # Import Result type
    from tool_agent_demo.result import Result

    # Parse arguments
    args = json.loads('''{json.dumps(args)}''')
    kwargs = json.loads('''{json.dumps(kwargs)}''')

    if '{method_type}' == 'workflows':
        # For workflows, collect all results
        results = []
        final_result = None
        for result in method(*args, **kwargs):
            if isinstance(result, Result):
                if result.is_err():
                    print(json.dumps({{'error': str(result.unwrap_err())}}))
                    sys.exit(1)
                final_result = result
            else:
                results.append(result)

        # Use final result if available
        if final_result is not None:
            print(json.dumps({{'result': final_result.unwrap()}}))
        else:
            print(json.dumps({{'results': results}}))
    else:
        # For tools, get single result
        result = method(*args, **kwargs)
        if isinstance(result, Result):
            if result.is_err():
                print(json.dumps({{'error': str(result.unwrap_err())}}))
                sys.exit(1)
            print(json.dumps({{'result': result.unwrap()}}))
        else:
            print(json.dumps({{'result': result}}))
except Exception as e:
    print(json.dumps({{'error': str(e)}}))
    sys.exit(1)
"""
            # Create process
            process = await asyncio.create_subprocess_exec(
                python_path,
                "-c",
                script,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE
            )

            # Wait for result
            stdout, stderr = await process.communicate()

            if process.returncode != 0:
                raise HTTPException(
                    status_code=500,
                    detail=f"Execution failed: {stderr.decode()}"
                )

            try:
                return json.loads(stdout.decode())
            except json.JSONDecodeError:
                raise HTTPException(
                    status_code=500,
                    detail=f"Failed to parse result: {stdout.decode()}"
                )

        else:
            raise HTTPException(
                status_code=400,
                detail=f"Unsupported executor type: {self.executor_type}"
            )


# Store loaded executors
executors: Dict[str, AsyncExecutor] = {}


def get_executor_wrapper(executor_id: str) -> AsyncExecutor:
    """Get or create executor wrapper"""
    if executor_id in executors:
        return executors[executor_id]

    executor = get_executor(executor_id)
    if not executor:
        raise HTTPException(
            status_code=404,
            detail=f"Agent {executor_id} not found"
        )

    wrapper = AsyncExecutor(executor.executor_type, executor.executor_path)
    executors[executor_id] = wrapper
    return wrapper


# Create FastAPI app
app = FastAPI(title="Tool Agent Demo API")


@app.get("/")
async def root():
    return {"message": "Welcome to Tool Agent Demo API"}


@app.get("/agents", response_model=List[AgentInfo])
async def get_agents():
    """List all registered agents"""
    executors = list_executors()
    return [
        {
            "id": executor.id,
            "executor_type": executor.executor_type,
            "executor_path": executor.executor_path,
            "entrypoint_path": executor.entrypoint_path,
            "variable_name": executor.variable_name,
            "agent_info": executor.agent_info
        }
        for executor in executors
    ]


@app.post("/agents/{agent_id}/tools/{tool_name}")
async def call_tool(agent_id: str, tool_name: str, request: ToolRequest):
    """Call an agent's tool"""
    executor = get_executor(agent_id)
    if not executor:
        raise HTTPException(
            status_code=404,
            detail=f"Agent {agent_id} not found"
        )

    # Check if tool exists
    tools = executor.agent_info.get("tools", [])
    if not any(t["name"] == tool_name for t in tools):
        raise HTTPException(
            status_code=404,
            detail=f"Tool {tool_name} not found for agent {agent_id}"
        )

    # Execute tool
    wrapper = get_executor_wrapper(agent_id)
    return await wrapper.execute(
        executor.entrypoint_path,
        executor.variable_name,
        "tools",
        tool_name,
        request.args,
        request.kwargs
    )


@app.post("/agents/{agent_id}/workflows/{workflow_name}")
async def call_workflow(agent_id: str, workflow_name: str, request: WorkflowRequest):
    """Call an agent's workflow"""
    executor = get_executor(agent_id)
    if not executor:
        raise HTTPException(
            status_code=404,
            detail=f"Agent {agent_id} not found"
        )

    # Check if workflow exists
    workflows = executor.agent_info.get("workflows", [])
    if not any(w["name"] == workflow_name for w in workflows):
        raise HTTPException(
            status_code=404,
            detail=f"Workflow {workflow_name} not found for agent {agent_id}"
        )

    # Execute workflow
    wrapper = get_executor_wrapper(agent_id)
    return await wrapper.execute(
        executor.entrypoint_path,
        executor.variable_name,
        "workflows",
        workflow_name,
        request.args,
        request.kwargs
    )
