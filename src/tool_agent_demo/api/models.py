from typing import List, Dict, Any
from pydantic import BaseModel


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
