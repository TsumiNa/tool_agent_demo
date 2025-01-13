from tool_agent_demo import Agent
from tool_agent_demo import Result


class CalculatorAgent(Agent):
    @Agent.tool
    def add(self, a: float, b: float) -> float:
        """Add two numbers together"""
        return a + b

    @Agent.tool
    def multiply(self, a: float, b: float) -> float:
        """Multiply two numbers"""
        return a * b

    @Agent.tool
    def divide(self, a: float, b: float) -> float:
        """Divide first number by second number"""
        if b == 0:
            raise ValueError("Cannot divide by zero")
        return a / b

    @Agent.workflow
    def calculate_average(self, numbers: list[float]) -> Result:
        """Calculate the average of a list of numbers"""
        # Add all numbers using reduce
        total = 0
        for num in numbers:
            total = self.add(total, num)
        # Divide by count to get average
        return self.divide(total, len(numbers))

    @Agent.workflow
    def calculate_compound(self, a: float, b: float) -> Result:
        """Demonstrate chaining operations using the | operator"""
        # First multiply a and b, then add 10 to the result
        mult_result = self.multiply(a, b)
        # if mult_result.is_err():
        #     return mult_result
        final_result = self.add(mult_result.unwrap(), 10)
        return final_result


def main():
    # Create calculator agent
    calc = CalculatorAgent()

    # Use individual tools
    print("\n=== Basic Tool Usage ===")
    result1 = calc.add(5, 3)
    print(f"5 + 3 = {result1.unwrap()}")

    result2 = calc.multiply(4, 6)
    print(f"4 * 6 = {result2.unwrap()}")

    # Demonstrate error handling
    print("\n=== Error Handling ===")
    result3 = calc.divide(10, 0)
    if result3.is_err():
        print(f"Error caught: {result3.error}")

    # Use workflows
    print("\n=== Workflow Usage ===")
    numbers = [1, 2, 3, 4, 5]
    for result in calc.calculate_average(numbers):
        if result.is_err():
            print(f"Error in workflow: {result.error}")
            break
        avg_result = result

    if 'avg_result' in locals() and avg_result.is_ok():
        print(f"Average of {numbers} = {avg_result.unwrap()}")

    # Demonstrate compound operations
    print("\n=== Compound Operations ===")
    for result in calc.calculate_compound(5, 3):
        if result.is_err():
            print(f"Error in workflow: {result.error}")
            break
        compound_result = result

    if 'compound_result' in locals() and compound_result.is_ok():
        print(f"(5 * 3) + 10 = {compound_result.unwrap()}")

    # Print agent information
    print("\n=== Agent Information ===")
    print(calc)


if __name__ == "__main__":
    main()
