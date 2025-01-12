from typing import List, Dict, Any

from fastapi import FastAPI, HTTPException

from tool_agent_demo.core.db import list_executors, get_executor
from tool_agent_demo.api.models import AgentInfo, ToolRequest, WorkflowRequest
from tool_agent_demo.api.executor import get_executor_wrapper, executors


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
        request.kwargs,
        step_by_step=True
    )


@app.post("/agents/kernel/{kernel_id}/next")
async def continue_execution(kernel_id: str):
    """Continue execution for a given kernel"""
    # Find the executor that owns this kernel
    owner_executor = None
    for executor in executors.values():
        if kernel_id in executor.active_kernels:
            owner_executor = executor
            break

    if not owner_executor:
        raise HTTPException(
            status_code=404,
            detail=f"Kernel {kernel_id} not found"
        )

    # Get stored kernel info
    stored_info = owner_executor.active_kernels[kernel_id]
    module_path, var_name, method_name, args, kwargs = stored_info

    # Continue execution
    return await owner_executor.execute(
        module_path,
        var_name,
        "workflows",  # Only workflows use kernels
        method_name,
        args,
        kwargs,
        kernel_id=kernel_id
    )


@app.post("/agents/kernel/{kernel_id}/cancel")
async def cancel_execution(kernel_id: str):
    """Cancel execution for a given kernel"""
    # Find the executor that owns this kernel
    for executor in executors.values():
        if await executor.cancel_kernel(kernel_id):
            return {"message": f"Kernel {kernel_id} cancelled successfully"}

    raise HTTPException(
        status_code=404,
        detail=f"Kernel {kernel_id} not found"
    )
