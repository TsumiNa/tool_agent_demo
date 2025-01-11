import unittest
from tool_agent_demo.agent import Agent
from tool_agent_demo.result import Result


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


class TestAgentPrint(unittest.TestCase):
    def test_agent_print(self):
        agent = TestAgent()
        print("\nAgent string representation:")
        print(agent)

        # Basic assertions to ensure the output contains key elements
        output = str(agent)

        # Check tools section
        self.assertIn("Tools:", output)
        self.assertIn("  - add: Add two numbers together.", output)
        self.assertIn("  - multiply: Multiply two numbers.", output)

        # Check workflows section
        self.assertIn("Workflows:", output)
        self.assertIn("  calculate:", output)
        self.assertIn("    Nodes:", output)
        self.assertIn("    Edges:", output)

        # Check workflow graph structure
        self.assertIn("      - add (inputs: 1 2 outputs: sum_result)", output)
        self.assertIn(
            "      - multiply (inputs: sum_result 3 outputs: [return])", output)
        self.assertIn("      - add -> multiply", output)


if __name__ == '__main__':
    unittest.main()
