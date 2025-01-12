from typing import List

from fastapi import FastAPI
from pydantic import BaseModel

from tool_agent_demo.db import list_executors, init_db

# Initialize database
init_db()


class AgentInfo(BaseModel):
    id: str
    executor_type: str
    executor_path: str
    entrypoint_path: str
    variable_name: str
    agent_info: dict


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
