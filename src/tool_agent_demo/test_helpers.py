from tool_agent_demo.agent import Agent


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

    @Agent.workflow
    def test_workflow(self) -> str:
        a = self.success_tool()
        b = self.concat_tool(a, "test")
        c = self.success_tool() | self.success_tool()
        return self.concat_tool(b, c.unwrap()[0])
