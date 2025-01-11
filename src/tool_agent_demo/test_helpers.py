from typing import Union
from tool_agent_demo.agent import Agent
from tool_agent_demo.result import Result


class TestAgent(Agent):
    @Agent.tool
    def success_tool(self) -> str:
        return "success"

    @Agent.tool
    def error_tool(self) -> str:
        raise ValueError("test error")

    @Agent.tool
    def concat_tool(self, a: str, b: str) -> str:
        return f"{a}-{b}"

    @Agent.workflow
    def example_workflow(self) -> str:
        return "workflow"

    def normal_function(self, text: Union[str, Result]) -> str:
        if isinstance(text, Result):
            text = text.value
        return f"normal-{text}"

    @Agent.workflow
    def tool_only_workflow(self) -> str:
        """Workflow that only uses tool functions."""
        a = self.success_tool()
        b = self.concat_tool(a, "test")
        c = self.success_tool() | self.success_tool()
        return self.concat_tool(b, c.unwrap()[0])

    @Agent.workflow
    def mixed_workflow(self) -> str:
        """Workflow that uses both tool and non-tool functions."""
        a = self.success_tool()
        b = self.concat_tool(a, "test")
        # Add a non-tool function call
        b = self.normal_function(b)
        c = self.success_tool() | self.success_tool()
        return self.concat_tool(b, c.unwrap()[0])
