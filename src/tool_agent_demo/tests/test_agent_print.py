from tool_agent_demo.agent import Agent


class TestAgent(Agent):
    @Agent.tool
    def add(self, a: int, b: int) -> int:
        """Add two numbers together."""
        return a + b

    @Agent.tool
    def multiply(self, a: int, b: int) -> int:
        """Multiply two numbers."""
        return a * b

    @Agent.workflow
    def calculate(self):
        """Perform a calculation workflow."""
        sum_result = self.add(1, 2)
        return self.multiply(sum_result, 3)


def test_agent_print():
    agent = TestAgent()
    print("\nAgent string representation:")
    print(agent)

    # Basic assertions to ensure the output contains key elements
    output = str(agent)

    # Check tools section
    assert "Tools:" in output
    assert "  - add: Add two numbers together." in output
    assert "  - multiply: Multiply two numbers." in output

    # Check workflows section
    assert "Workflows:" in output
    assert "  calculate:" in output
    assert "    Nodes:" in output
    assert "    Edges:" in output

    # Check workflow graph structure
    assert "      - add (inputs: 1 2 outputs: sum_result)" in output
    assert "      - multiply (inputs: sum_result 3 outputs: [return])" in output
    assert "      - add -> multiply" in output
